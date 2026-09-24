"""Controlled Phase-2 historical lesson/content backfill.

The source database is read through one checked descriptor, deserialized into
an in-memory/query-only SQLite connection and never opened for writes.  Apply
requires a separately named, repository-head, owner-only disposable copy plus
the hash of the exact aggregate preview.  The authoritative ``db/vmsh.db`` is
never an apply target.

The tool intentionally does not guess historical publication/cutoff times.
Unknown values stay ``null`` in immutable revision provenance; publication or
window rows are omitted until an explicit mapping supplies the timestamp.

Authoritative requirements:
``vmshpwa/dev/development-plan/06-phase-2-content.md`` and
``vmshpwa/docs/data-model-and-migrations.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db_methods.pwa.migrations import require_current_schema
from helpers.pwa.content import ContentCompileError, ContentRole, compile_latex
from helpers.pwa.content.compiler import COMPILER_VERSION
from helpers.pwa.content.model import (
    CompileResult,
    DiagnosticSeverity,
    SourceEncoding,
    SubpartNode,
    canonical_json,
)
from vmshpwa.scripts.report_io import AtomicReportWriteError, atomic_write_text
from vmshpwa.scripts.safe_source import (
    SafeSourceError,
    SourceFingerprint,
    fingerprint,
    read_and_fingerprint,
    secure_open,
    verify_path_matches,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITATIVE_DATABASE = REPOSITORY_ROOT / "db" / "vmsh.db"
APPLY_DATABASE_ROOT = REPOSITORY_ROOT / ".runtime" / "content-history-backfill"

MAPPING_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
BACKFILL_IMPLEMENTATION_VERSION = "phase2-content-history-backfill/1"
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MATERIAL_KINDS = ("condition", "hint", "solution")
_REQUIRED_LEGACY_TABLES = {"groups", "lessons", "problems"}
_REQUIRED_TARGET_TABLES = {
    "courses",
    "course_lessons",
    "group_lessons",
    "content_sources",
    "content_revisions",
    "content_derivatives",
    "content_problem_matches",
    "problem_revisions",
    "lesson_windows",
    "lesson_publications",
}


class ContentHistoryBackfillError(RuntimeError):
    """Raised when preview/apply cannot prove a safe deterministic result."""


@dataclass(frozen=True, slots=True)
class MaterialMapping:
    kind: Literal["condition", "hint", "solution"]
    source_path: str | None
    published_at: str | None


@dataclass(frozen=True, slots=True)
class LessonTimestamps:
    opens_at: str | None
    submission_closes_at: str | None
    hint_scheduled_at: str | None
    solution_scheduled_at: str | None


@dataclass(frozen=True, slots=True)
class GroupLessonMapping:
    legacy_group_id: str
    legacy_lesson_number: int
    course_lesson_number: int
    cycle_anchor_date: str
    business_timezone: str
    timestamps: LessonTimestamps
    materials: tuple[MaterialMapping, ...]


@dataclass(frozen=True, slots=True)
class GroupMapping:
    legacy_group_id: str
    target_group_public_id: str


@dataclass(frozen=True, slots=True)
class BackfillMapping:
    backfill_id: str
    recorded_at: str
    season_public_id: str
    course_public_id: str
    first_legacy_lesson: int
    last_legacy_lesson: int
    groups: tuple[GroupMapping, ...]
    lessons: tuple[GroupLessonMapping, ...]
    mapping_directory: Path


@dataclass(frozen=True, slots=True)
class LegacyProblem:
    problem_id: int
    group_id: str
    lesson: int
    problem_number: int
    item: str
    title: str
    problem_type: int
    answer_type: int | None
    answer_validation: str | None
    validation_error: str | None
    correct_answer: str | None
    correct_answer_checker: str | None
    wrong_answer: str | None
    congratulation: str | None


@dataclass(frozen=True, slots=True)
class BackfillDiagnostic:
    code: str
    severity: Literal["error", "warning"]
    legacy_lesson_number: int | None = None
    expected_count: int | None = None
    observed_count: int | None = None


@dataclass(frozen=True, slots=True)
class MaterialPlan:
    mapping: MaterialMapping
    logical_filename: str
    compile_result: CompileResult
    provenance_json: str


@dataclass(frozen=True, slots=True)
class GroupLessonPlan:
    mapping: GroupLessonMapping
    target_group_public_id: str
    legacy_problems: tuple[LegacyProblem, ...]
    materials: tuple[MaterialPlan, ...]


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    mapping: BackfillMapping
    group_lessons: tuple[GroupLessonPlan, ...]
    diagnostics: tuple[BackfillDiagnostic, ...]
    legacy_fingerprint: str
    source_fingerprint: SourceFingerprint
    discovered_group_lessons: int
    discovered_legacy_problems: int
    duplicate_title_candidate_groups: int
    input_binding_sha256: str

    @property
    def is_ready(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContentHistoryBackfillError(
                "Mapping JSON contains a duplicate object key"
            )
        result[key] = value
    return result


def _exact_object(value: object, keys: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ContentHistoryBackfillError(
            f"{label} must contain exactly the documented keys"
        )
    return value


def _nonempty_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ContentHistoryBackfillError(
            f"{label} must be a non-empty string without edge whitespace"
        )
    if unicodedata.normalize("NFKC", value) != value:
        raise ContentHistoryBackfillError(f"{label} must already be Unicode NFKC")
    return value


def _public_id(value: object, *, label: str) -> str:
    result = _nonempty_string(value, label=label)
    if _PUBLIC_ID.fullmatch(result) is None:
        raise ContentHistoryBackfillError(f"{label} is not a canonical public ID")
    return result


def _positive_integer(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContentHistoryBackfillError(f"{label} must be a positive integer")
    return value


def _iso_date(value: object, *, label: str) -> str:
    result = _nonempty_string(value, label=label)
    try:
        parsed = date.fromisoformat(result)
    except ValueError as error:
        raise ContentHistoryBackfillError(f"{label} must be an ISO date") from error
    if parsed.isoformat() != result:
        raise ContentHistoryBackfillError(f"{label} must be a canonical ISO date")
    return result


def _rfc3339(value: object, *, label: str, nullable: bool = True) -> str | None:
    if value is None and nullable:
        return None
    result = _nonempty_string(value, label=label)
    try:
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContentHistoryBackfillError(
            f"{label} must be an RFC 3339 timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContentHistoryBackfillError(f"{label} must include a UTC offset")
    return result


def _relative_source_path(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    result = _nonempty_string(value, label=label)
    path = PurePosixPath(result)
    if (
        len(result) > 500
        or path.is_absolute()
        or not path.name
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in result
        or any(ord(character) < 32 or ord(character) == 127 for character in result)
    ):
        raise ContentHistoryBackfillError(
            f"{label} must be a bounded relative POSIX path"
        )
    return result


def load_mapping(path: Path) -> BackfillMapping:
    """Read one strict mapping file without following aliases."""

    mapping_path = Path(path)
    try:
        with secure_open(mapping_path) as descriptor:
            before, content = read_and_fingerprint(descriptor)
            verify_path_matches(mapping_path, before)
            if len(content) > 4 * 1024 * 1024:
                raise ContentHistoryBackfillError("Mapping file is unexpectedly large")
            try:
                payload = json.loads(
                    content.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ContentHistoryBackfillError(
                    "Mapping file is not valid UTF-8 JSON"
                ) from error
            after = fingerprint(descriptor)
            verify_path_matches(mapping_path, after)
            if before != after:
                raise ContentHistoryBackfillError(
                    "Mapping file changed while it was being read"
                )
    except SafeSourceError as error:
        raise ContentHistoryBackfillError(str(error)) from error

    root = _exact_object(
        payload,
        {
            "schemaVersion",
            "purpose",
            "backfillId",
            "recordedAt",
            "seasonPublicId",
            "coursePublicId",
            "legacyLessonRange",
            "groupMappings",
            "lessonMappings",
        },
        label="Mapping document",
    )
    if root["schemaVersion"] != MAPPING_SCHEMA_VERSION:
        raise ContentHistoryBackfillError("Unsupported mapping schema version")
    if root["purpose"] != "phase2-content-history-backfill":
        raise ContentHistoryBackfillError("Mapping document has the wrong purpose")
    backfill_id = _public_id(root["backfillId"], label="backfillId")
    recorded_at = _rfc3339(root["recordedAt"], label="recordedAt", nullable=False)
    assert recorded_at is not None
    season_public_id = _public_id(root["seasonPublicId"], label="seasonPublicId")
    course_public_id = _public_id(root["coursePublicId"], label="coursePublicId")

    raw_range = _exact_object(
        root["legacyLessonRange"], {"first", "last"}, label="legacyLessonRange"
    )
    first = _positive_integer(raw_range["first"], label="legacyLessonRange.first")
    last = _positive_integer(raw_range["last"], label="legacyLessonRange.last")
    if first > last or last - first > 10_000:
        raise ContentHistoryBackfillError("legacyLessonRange is invalid or too large")

    raw_groups = root["groupMappings"]
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ContentHistoryBackfillError("groupMappings must be a non-empty array")
    groups: list[GroupMapping] = []
    for index, raw_group in enumerate(raw_groups):
        group = _exact_object(
            raw_group,
            {"legacyGroupId", "targetGroupPublicId"},
            label=f"groupMappings[{index}]",
        )
        groups.append(
            GroupMapping(
                legacy_group_id=_nonempty_string(
                    group["legacyGroupId"],
                    label=f"groupMappings[{index}].legacyGroupId",
                ),
                target_group_public_id=_public_id(
                    group["targetGroupPublicId"],
                    label=f"groupMappings[{index}].targetGroupPublicId",
                ),
            )
        )
    if len({item.legacy_group_id for item in groups}) != len(groups):
        raise ContentHistoryBackfillError("groupMappings repeats a legacy group")
    if len({item.target_group_public_id for item in groups}) != len(groups):
        raise ContentHistoryBackfillError("groupMappings repeats a target group")
    known_groups = {item.legacy_group_id for item in groups}

    raw_lessons = root["lessonMappings"]
    if not isinstance(raw_lessons, list):
        raise ContentHistoryBackfillError("lessonMappings must be an array")
    lessons: list[GroupLessonMapping] = []
    for index, raw_lesson in enumerate(raw_lessons):
        lesson = _exact_object(
            raw_lesson,
            {
                "legacyGroupId",
                "legacyLessonNumber",
                "courseLessonNumber",
                "cycleAnchorDate",
                "businessTimezone",
                "timestamps",
                "materials",
            },
            label=f"lessonMappings[{index}]",
        )
        legacy_group_id = _nonempty_string(
            lesson["legacyGroupId"],
            label=f"lessonMappings[{index}].legacyGroupId",
        )
        if legacy_group_id not in known_groups:
            raise ContentHistoryBackfillError(
                "lessonMappings references a group absent from groupMappings"
            )
        legacy_lesson = _positive_integer(
            lesson["legacyLessonNumber"],
            label=f"lessonMappings[{index}].legacyLessonNumber",
        )
        if not first <= legacy_lesson <= last:
            raise ContentHistoryBackfillError(
                "lessonMappings contains a lesson outside legacyLessonRange"
            )
        timezone_name = _nonempty_string(
            lesson["businessTimezone"],
            label=f"lessonMappings[{index}].businessTimezone",
        )
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ContentHistoryBackfillError(
                "lessonMappings contains an unknown business timezone"
            ) from error
        timestamps = _exact_object(
            lesson["timestamps"],
            {
                "opensAt",
                "submissionClosesAt",
                "hintScheduledAt",
                "solutionScheduledAt",
            },
            label=f"lessonMappings[{index}].timestamps",
        )
        lesson_timestamps = LessonTimestamps(
            opens_at=_rfc3339(timestamps["opensAt"], label="timestamps.opensAt"),
            submission_closes_at=_rfc3339(
                timestamps["submissionClosesAt"],
                label="timestamps.submissionClosesAt",
            ),
            hint_scheduled_at=_rfc3339(
                timestamps["hintScheduledAt"], label="timestamps.hintScheduledAt"
            ),
            solution_scheduled_at=_rfc3339(
                timestamps["solutionScheduledAt"],
                label="timestamps.solutionScheduledAt",
            ),
        )
        if (
            lesson_timestamps.opens_at is not None
            and lesson_timestamps.submission_closes_at is not None
            and datetime.fromisoformat(
                lesson_timestamps.opens_at.replace("Z", "+00:00")
            )
            >= datetime.fromisoformat(
                lesson_timestamps.submission_closes_at.replace("Z", "+00:00")
            )
        ):
            raise ContentHistoryBackfillError("opensAt must precede submissionClosesAt")

        raw_materials = lesson["materials"]
        if not isinstance(raw_materials, list):
            raise ContentHistoryBackfillError("materials must be an array")
        materials: list[MaterialMapping] = []
        for material_index, raw_material in enumerate(raw_materials):
            material = _exact_object(
                raw_material,
                {"kind", "sourcePath", "publishedAt"},
                label=f"lessonMappings[{index}].materials[{material_index}]",
            )
            kind = material["kind"]
            if kind not in _MATERIAL_KINDS:
                raise ContentHistoryBackfillError(
                    "Unsupported historical material kind"
                )
            materials.append(
                MaterialMapping(
                    kind=kind,
                    source_path=_relative_source_path(
                        material["sourcePath"], label="material.sourcePath"
                    ),
                    published_at=_rfc3339(
                        material["publishedAt"], label="material.publishedAt"
                    ),
                )
            )
        if len({item.kind for item in materials}) != len(materials):
            raise ContentHistoryBackfillError(
                "A lesson mapping repeats a material kind"
            )
        if "condition" not in {item.kind for item in materials}:
            raise ContentHistoryBackfillError(
                "Each historical group lesson needs an explicit condition material"
            )
        lessons.append(
            GroupLessonMapping(
                legacy_group_id=legacy_group_id,
                legacy_lesson_number=legacy_lesson,
                course_lesson_number=_positive_integer(
                    lesson["courseLessonNumber"],
                    label=f"lessonMappings[{index}].courseLessonNumber",
                ),
                cycle_anchor_date=_iso_date(
                    lesson["cycleAnchorDate"],
                    label=f"lessonMappings[{index}].cycleAnchorDate",
                ),
                business_timezone=timezone_name,
                timestamps=lesson_timestamps,
                materials=tuple(sorted(materials, key=lambda item: item.kind)),
            )
        )
    lesson_keys = [
        (item.legacy_group_id, item.legacy_lesson_number) for item in lessons
    ]
    if len(set(lesson_keys)) != len(lesson_keys):
        raise ContentHistoryBackfillError(
            "lessonMappings repeats a legacy group lesson"
        )

    return BackfillMapping(
        backfill_id=backfill_id,
        recorded_at=recorded_at,
        season_public_id=season_public_id,
        course_public_id=course_public_id,
        first_legacy_lesson=first,
        last_legacy_lesson=last,
        groups=tuple(sorted(groups, key=lambda item: item.legacy_group_id)),
        lessons=tuple(
            sorted(
                lessons,
                key=lambda item: (
                    item.legacy_lesson_number,
                    item.legacy_group_id,
                ),
            )
        ),
        mapping_directory=mapping_path.resolve().parent,
    )


def _require_quiescent_source(path: Path) -> None:
    if any(
        path.with_name(path.name + suffix).exists()
        for suffix in ("-wal", "-shm", "-journal")
    ):
        raise ContentHistoryBackfillError(
            "Source database must be quiescent without WAL/journal sidecars"
        )


def _deserialize_snapshot(content: bytes) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", autocommit=True)
    try:
        deserialize = getattr(connection, "deserialize", None)
        if not callable(deserialize):
            raise ContentHistoryBackfillError(
                "SQLite deserialize support is required for read-only preview"
            )
        deserialize(content)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise ContentHistoryBackfillError("SQLite refused query_only mode")
        connection.execute("BEGIN")
        return connection
    except Exception:
        connection.close()
        raise


@contextmanager
def _source_snapshot(
    path: Path,
) -> Iterator[tuple[sqlite3.Connection, SourceFingerprint]]:
    source_path = Path(path)
    try:
        _require_quiescent_source(source_path)
        with secure_open(source_path) as descriptor:
            before, content = read_and_fingerprint(descriptor)
            verify_path_matches(source_path, before)
            connection = _deserialize_snapshot(content)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_schema WHERE type = 'table'"
                    )
                }
                if not _REQUIRED_LEGACY_TABLES <= tables:
                    raise ContentHistoryBackfillError(
                        "Source database lacks legacy lessons/problems/groups"
                    )
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ContentHistoryBackfillError(
                        "Source SQLite integrity_check failed"
                    )
                yield connection, before
            finally:
                connection.close()
            after = fingerprint(descriptor)
            verify_path_matches(source_path, after)
            if before != after:
                raise ContentHistoryBackfillError(
                    "Source database changed while it was inspected"
                )
            _require_quiescent_source(source_path)
    except SafeSourceError as error:
        raise ContentHistoryBackfillError(str(error)) from error


def _normalize_title(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _load_legacy(
    connection: sqlite3.Connection,
    mapping: BackfillMapping,
) -> tuple[
    dict[tuple[str, int], int],
    dict[tuple[str, int], tuple[LegacyProblem, ...]],
    str,
]:
    group_ids = [item.legacy_group_id for item in mapping.groups]
    placeholders = ",".join("?" for _ in group_ids)
    lesson_rows = connection.execute(
        "SELECT id, group_id, lesson FROM lessons "
        f"WHERE group_id IN ({placeholders}) AND lesson BETWEEN ? AND ? "
        "ORDER BY lesson, group_id, id",
        (*group_ids, mapping.first_legacy_lesson, mapping.last_legacy_lesson),
    ).fetchall()
    lessons: dict[tuple[str, int], int] = {}
    for row in lesson_rows:
        key = (str(row["group_id"]), int(row["lesson"]))
        if key in lessons:
            raise ContentHistoryBackfillError(
                "Legacy source contains duplicate group lesson rows"
            )
        lessons[key] = int(row["id"])

    problem_rows = connection.execute(
        "SELECT id, group_id, lesson, prob, item, title, prob_type, ans_type, "
        "ans_validation, validation_error, cor_ans, cor_ans_checker, wrong_ans, "
        "congrat FROM problems "
        f"WHERE group_id IN ({placeholders}) AND lesson BETWEEN ? AND ? "
        "ORDER BY lesson, group_id, prob, item, id",
        (*group_ids, mapping.first_legacy_lesson, mapping.last_legacy_lesson),
    ).fetchall()
    problems: dict[tuple[str, int], list[LegacyProblem]] = {key: [] for key in lessons}
    fingerprint_rows: list[dict[str, object]] = [
        {"type": "lesson", "id": row_id, "group": key[0], "lesson": key[1]}
        for key, row_id in sorted(
            lessons.items(), key=lambda item: (item[0][1], item[0][0])
        )
    ]
    for row in problem_rows:
        key = (str(row["group_id"]), int(row["lesson"]))
        problem = LegacyProblem(
            problem_id=int(row["id"]),
            group_id=key[0],
            lesson=key[1],
            problem_number=int(row["prob"]),
            item=str(row["item"]),
            title=str(row["title"]),
            problem_type=int(row["prob_type"]),
            answer_type=None if row["ans_type"] is None else int(row["ans_type"]),
            answer_validation=row["ans_validation"],
            validation_error=row["validation_error"],
            correct_answer=row["cor_ans"],
            correct_answer_checker=row["cor_ans_checker"],
            wrong_answer=row["wrong_ans"],
            congratulation=row["congrat"],
        )
        problems.setdefault(key, []).append(problem)
        # This digest protects target/source equality without exposing answer or
        # checker material in the aggregate report.
        fingerprint_rows.append(
            {
                "type": "problem",
                "id": problem.problem_id,
                "group": problem.group_id,
                "lesson": problem.lesson,
                "prob": problem.problem_number,
                "item": problem.item,
                "payloadHash": hashlib.sha256(
                    canonical_json(
                        {
                            "title": problem.title,
                            "problemType": problem.problem_type,
                            "answerType": problem.answer_type,
                            "answerValidation": problem.answer_validation,
                            "validationError": problem.validation_error,
                            "correctAnswer": problem.correct_answer,
                            "correctAnswerChecker": problem.correct_answer_checker,
                            "wrongAnswer": problem.wrong_answer,
                            "congratulation": problem.congratulation,
                        }
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )
    immutable_problems = {key: tuple(value) for key, value in sorted(problems.items())}
    legacy_fingerprint = hashlib.sha256(
        canonical_json(fingerprint_rows).encode("utf-8")
    ).hexdigest()
    return lessons, immutable_problems, legacy_fingerprint


def _flat_task_count(result: CompileResult) -> int:
    count = 0

    def subpart_count(blocks: Iterable[object]) -> int:
        total = 0
        for block in blocks:
            if isinstance(block, SubpartNode):
                total += 1
        return total

    for problem in result.ast.problems:
        parts = subpart_count(problem.statement)
        count += parts if parts else 1
    return count


def _diagnostics_json(result: CompileResult) -> str:
    return canonical_json(result.diagnostics)


def _timestamp_provenance(value: str | None) -> dict[str, object]:
    return {
        "value": value,
        "source": "explicit_mapping" if value is not None else "manual_backfill",
        "precision": "exact" if value is not None else "unknown",
    }


def _material_provenance(
    mapping: BackfillMapping,
    lesson: GroupLessonMapping,
    material: MaterialMapping,
) -> str:
    return canonical_json(
        {
            "schemaVersion": 1,
            "operation": "historical-content-backfill",
            "implementationVersion": BACKFILL_IMPLEMENTATION_VERSION,
            "backfillId": mapping.backfill_id,
            "legacyScope": {
                "seasonPublicId": mapping.season_public_id,
                "coursePublicId": mapping.course_public_id,
                "groupId": lesson.legacy_group_id,
                "lessonNumber": lesson.legacy_lesson_number,
                "materialKind": material.kind,
            },
            "historicalTimestamps": {
                "opensAt": _timestamp_provenance(lesson.timestamps.opens_at),
                "submissionClosesAt": _timestamp_provenance(
                    lesson.timestamps.submission_closes_at
                ),
                "hintScheduledAt": _timestamp_provenance(
                    lesson.timestamps.hint_scheduled_at
                ),
                "solutionScheduledAt": _timestamp_provenance(
                    lesson.timestamps.solution_scheduled_at
                ),
                "publicationAt": _timestamp_provenance(material.published_at),
            },
        }
    )


def _input_binding_sha256(
    mapping: BackfillMapping,
    group_lessons: Sequence[GroupLessonPlan],
    *,
    legacy_fingerprint: str,
) -> str:
    """Bind owner review to the exact private mapping and compiler inputs.

    Only the resulting digest enters the report. Paths, LaTeX, task metadata
    and answer/checker material stay private, while any change to schedule,
    target scope, source bytes or compiler outputs invalidates the preview.
    """

    mapping_document = {
        "schemaVersion": MAPPING_SCHEMA_VERSION,
        "backfillId": mapping.backfill_id,
        "recordedAt": mapping.recorded_at,
        "seasonPublicId": mapping.season_public_id,
        "coursePublicId": mapping.course_public_id,
        "legacyLessonRange": {
            "first": mapping.first_legacy_lesson,
            "last": mapping.last_legacy_lesson,
        },
        "groups": [
            {
                "legacyGroupId": item.legacy_group_id,
                "targetGroupPublicId": item.target_group_public_id,
            }
            for item in mapping.groups
        ],
        "lessons": [
            {
                "legacyGroupId": lesson.legacy_group_id,
                "legacyLessonNumber": lesson.legacy_lesson_number,
                "courseLessonNumber": lesson.course_lesson_number,
                "cycleAnchorDate": lesson.cycle_anchor_date,
                "businessTimezone": lesson.business_timezone,
                "timestamps": {
                    "opensAt": lesson.timestamps.opens_at,
                    "submissionClosesAt": lesson.timestamps.submission_closes_at,
                    "hintScheduledAt": lesson.timestamps.hint_scheduled_at,
                    "solutionScheduledAt": lesson.timestamps.solution_scheduled_at,
                },
                "materials": [
                    {
                        "kind": material.kind,
                        "sourcePath": material.source_path,
                        "publishedAt": material.published_at,
                    }
                    for material in lesson.materials
                ],
            }
            for lesson in mapping.lessons
        ],
    }
    compiled_materials: list[dict[str, object]] = []
    for lesson in group_lessons:
        for material in lesson.materials:
            result = material.compile_result
            compiled_materials.append(
                {
                    "legacyGroupId": lesson.mapping.legacy_group_id,
                    "legacyLessonNumber": lesson.mapping.legacy_lesson_number,
                    "kind": material.mapping.kind,
                    "compilerVersion": COMPILER_VERSION,
                    "sourceSha256": result.source.raw_sha256,
                    "astSha256": result.ast_sha256,
                    "diagnosticsSha256": hashlib.sha256(
                        canonical_json(result.diagnostics).encode("utf-8")
                    ).hexdigest(),
                    "derivatives": [
                        None
                        if derivative is None
                        else {
                            "kind": derivative.kind,
                            "rendererVersion": derivative.renderer_version,
                            "sha256": derivative.sha256,
                        }
                        for derivative in (
                            result.web_document,
                            result.web,
                            result.telegram,
                        )
                    ],
                }
            )
    binding = {
        "implementationVersion": BACKFILL_IMPLEMENTATION_VERSION,
        "legacyFingerprint": legacy_fingerprint,
        "mapping": mapping_document,
        "compiledMaterials": compiled_materials,
    }
    return hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()


def _read_material(
    mapping: BackfillMapping,
    lesson: GroupLessonMapping,
    material: MaterialMapping,
) -> tuple[bytes, str]:
    if material.source_path is None:
        raise FileNotFoundError("No historical source was mapped")
    source_path = mapping.mapping_directory / Path(material.source_path)
    try:
        with secure_open(source_path) as descriptor:
            before, content = read_and_fingerprint(descriptor)
            verify_path_matches(source_path, before)
            after = fingerprint(descriptor)
            verify_path_matches(source_path, after)
            if before != after:
                raise ContentHistoryBackfillError(
                    "Historical source changed while it was being read"
                )
    except SafeSourceError as error:
        if not source_path.exists():
            raise FileNotFoundError(
                "Mapped historical source does not exist"
            ) from error
        raise ContentHistoryBackfillError(str(error)) from error
    logical_filename = PurePosixPath(material.source_path).name
    return content, logical_filename


def build_plan(
    connection: sqlite3.Connection,
    source_fingerprint: SourceFingerprint,
    mapping: BackfillMapping,
) -> BackfillPlan:
    """Build a secret-free report plan plus in-memory source/legacy payloads."""

    legacy_lessons, legacy_problems, legacy_fingerprint = _load_legacy(
        connection, mapping
    )
    mapped_keys = {
        (item.legacy_group_id, item.legacy_lesson_number) for item in mapping.lessons
    }
    discovered_keys = set(legacy_lessons)
    diagnostics: list[BackfillDiagnostic] = []
    for _key in sorted(discovered_keys - mapped_keys, key=lambda key: (key[1], key[0])):
        diagnostics.append(
            BackfillDiagnostic("missingGroupLessonMapping", "error", _key[1])
        )
    for _key in sorted(mapped_keys - discovered_keys, key=lambda key: (key[1], key[0])):
        diagnostics.append(BackfillDiagnostic("missingGroupLesson", "error", _key[1]))

    target_group_by_legacy = {
        item.legacy_group_id: item.target_group_public_id for item in mapping.groups
    }
    group_plans: list[GroupLessonPlan] = []
    for lesson in mapping.lessons:
        key = (lesson.legacy_group_id, lesson.legacy_lesson_number)
        problems = legacy_problems.get(key, ())
        if key not in discovered_keys:
            continue
        if not problems:
            diagnostics.append(
                BackfillDiagnostic("missingLegacyProblems", "error", key[1])
            )
            continue
        if lesson.timestamps.submission_closes_at is None:
            diagnostics.append(
                BackfillDiagnostic("unknownSubmissionTimestamp", "warning", key[1])
            )
        materials: list[MaterialPlan] = []
        for material in lesson.materials:
            if material.published_at is None:
                diagnostics.append(
                    BackfillDiagnostic("unknownPublicationTimestamp", "warning", key[1])
                )
            try:
                content, logical_filename = _read_material(mapping, lesson, material)
            except FileNotFoundError:
                diagnostics.append(BackfillDiagnostic("missingSource", "error", key[1]))
                continue
            role = ContentRole(material.kind)
            try:
                compiled = compile_latex(
                    content,
                    source_name=logical_filename,
                    role=role,
                    revision_id=(
                        f"backfill:{mapping.backfill_id}:{lesson.legacy_group_id}:"
                        f"{lesson.legacy_lesson_number}:{material.kind}"
                    ),
                )
            except ContentCompileError as error:
                code = (
                    "unsupportedEncoding"
                    if "decode" in str(error).casefold()
                    or "codec" in str(error).casefold()
                    else "sourceCompileEnvelopeError"
                )
                diagnostics.append(BackfillDiagnostic(code, "error", key[1]))
                continue
            compiler_errors = sum(
                item.severity is DiagnosticSeverity.ERROR
                for item in compiled.diagnostics
            )
            if compiler_errors:
                diagnostics.append(
                    BackfillDiagnostic(
                        "sourceCompilerErrors",
                        "error",
                        key[1],
                        expected_count=0,
                        observed_count=compiler_errors,
                    )
                )
                continue
            observed_count = _flat_task_count(compiled)
            expected_count = len(problems)
            if observed_count != expected_count:
                diagnostics.append(
                    BackfillDiagnostic(
                        "taskCountMismatch",
                        "error",
                        key[1],
                        expected_count=expected_count,
                        observed_count=observed_count,
                    )
                )
                continue
            materials.append(
                MaterialPlan(
                    mapping=material,
                    logical_filename=logical_filename,
                    compile_result=compiled,
                    provenance_json=_material_provenance(mapping, lesson, material),
                )
            )
        group_plans.append(
            GroupLessonPlan(
                mapping=lesson,
                target_group_public_id=target_group_by_legacy[lesson.legacy_group_id],
                legacy_problems=problems,
                materials=tuple(materials),
            )
        )

    title_counts: Counter[tuple[int, str]] = Counter()
    title_groups: dict[tuple[int, str], set[str]] = {}
    course_number_by_legacy = {
        (item.legacy_group_id, item.legacy_lesson_number): item.course_lesson_number
        for item in mapping.lessons
    }
    for key, problems in legacy_problems.items():
        course_number = course_number_by_legacy.get(key)
        if course_number is None:
            continue
        for problem in problems:
            normalized = _normalize_title(problem.title)
            candidate_key = (course_number, normalized)
            title_counts[candidate_key] += 1
            title_groups.setdefault(candidate_key, set()).add(problem.group_id)
    duplicate_candidates = sum(
        count > 1 and len(title_groups[key]) > 1 for key, count in title_counts.items()
    )
    if duplicate_candidates:
        diagnostics.append(
            BackfillDiagnostic(
                "duplicateTitleCandidate",
                "warning",
                expected_count=duplicate_candidates,
                observed_count=duplicate_candidates,
            )
        )

    immutable_group_plans = tuple(group_plans)
    return BackfillPlan(
        mapping=mapping,
        group_lessons=immutable_group_plans,
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.severity,
                    item.code,
                    item.legacy_lesson_number or 0,
                ),
            )
        ),
        legacy_fingerprint=legacy_fingerprint,
        source_fingerprint=source_fingerprint,
        discovered_group_lessons=len(discovered_keys),
        discovered_legacy_problems=sum(
            len(value) for value in legacy_problems.values()
        ),
        duplicate_title_candidate_groups=duplicate_candidates,
        input_binding_sha256=_input_binding_sha256(
            mapping,
            immutable_group_plans,
            legacy_fingerprint=legacy_fingerprint,
        ),
    )


def _predicted_changes(plan: BackfillPlan) -> dict[str, int]:
    materials = [
        material for lesson in plan.group_lessons for material in lesson.materials
    ]
    condition_problem_count = sum(
        len(lesson.legacy_problems)
        for lesson in plan.group_lessons
        if any(material.mapping.kind == "condition" for material in lesson.materials)
    )
    return {
        "courseLessons": len(
            {item.mapping.course_lesson_number for item in plan.group_lessons}
        ),
        "groupLessons": len(plan.group_lessons),
        "lessonWindows": sum(
            item.mapping.timestamps.submission_closes_at is not None
            for item in plan.group_lessons
        ),
        "contentSources": len(materials),
        "contentRevisions": len(materials),
        "contentDerivatives": len(materials) * 3,
        "problemMatches": condition_problem_count,
        "problemRevisions": condition_problem_count,
        "publications": sum(
            material.mapping.published_at is not None for material in materials
        ),
        "legacyRowsUpdated": 0,
    }


def _preview_payload(plan: BackfillPlan) -> dict[str, Any]:
    counts = Counter(item.code for item in plan.diagnostics)
    errors = sum(item.severity == "error" for item in plan.diagnostics)
    warnings = sum(item.severity == "warning" for item in plan.diagnostics)
    report: dict[str, Any] = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "operation": "preview",
        "status": "ready" if plan.is_ready else "blocked",
        "scope": {
            "legacyLessonRange": {
                "first": plan.mapping.first_legacy_lesson,
                "last": plan.mapping.last_legacy_lesson,
            },
            "mappedGroups": len(plan.mapping.groups),
            "discoveredGroupLessons": plan.discovered_group_lessons,
            "mappedGroupLessons": len(plan.mapping.lessons),
            "legacyProblems": plan.discovered_legacy_problems,
        },
        "diagnostics": {
            "errors": errors,
            "warnings": warnings,
            "byCode": {key: counts[key] for key in sorted(counts)},
            "duplicateTitleCandidateGroups": plan.duplicate_title_candidate_groups,
        },
        "predictedChanges": _predicted_changes(plan),
        "safety": {
            "sourceDatabaseMode": "descriptor-snapshot-query-only",
            "applyTarget": "explicit-disposable-migrated-copy-only",
            "historicalTimestampInferenceCount": 0,
            "legacyRowsRewritten": 0,
            "synonymGroupsAutomaticallyMerged": 0,
            "containsUserNamesTokensOrMessages": False,
        },
        "sourceLegacyFingerprint": plan.legacy_fingerprint,
        "inputBindingSha256": plan.input_binding_sha256,
    }
    report_hash = hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()
    report["previewSha256"] = report_hash
    return report


def preview_backfill(
    source_database: Path, mapping_path: Path
) -> tuple[BackfillPlan, dict[str, Any]]:
    """Build a deterministic dry-run report without writing either database."""

    mapping = load_mapping(mapping_path)
    with _source_snapshot(Path(source_database)) as (connection, source_fingerprint):
        plan = build_plan(connection, source_fingerprint, mapping)
    return plan, _preview_payload(plan)


def _reject_symlink_components(path: Path, *, label: str) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        except OSError as error:
            raise ContentHistoryBackfillError(f"Could not inspect {label}") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise ContentHistoryBackfillError(f"{label} must not contain symlinks")


def _reject_apply_target(path: Path, source_database: Path) -> Path:
    target = Path(os.path.abspath(path))
    source = Path(os.path.abspath(source_database))
    authoritative = Path(os.path.abspath(AUTHORITATIVE_DATABASE))
    _reject_symlink_components(target, label="Apply database path")
    if target == authoritative:
        raise ContentHistoryBackfillError(
            "The authoritative db/vmsh.db is never a backfill apply target"
        )
    if target == source:
        raise ContentHistoryBackfillError(
            "The read-only source and writable apply target must be different files"
        )
    try:
        if (
            target.exists()
            and authoritative.exists()
            and target.samefile(authoritative)
        ):
            raise ContentHistoryBackfillError(
                "An alias of db/vmsh.db is never a backfill apply target"
            )
        if target.exists() and source.exists() and target.samefile(source):
            raise ContentHistoryBackfillError(
                "The source and target must not be filesystem aliases"
            )
    except OSError as error:
        raise ContentHistoryBackfillError(
            "Could not establish apply database identity"
        ) from error
    allowed_root = Path(os.path.abspath(APPLY_DATABASE_ROOT))
    if not target.is_relative_to(allowed_root):
        raise ContentHistoryBackfillError(
            "Apply database must be below .runtime/content-history-backfill"
        )
    try:
        with secure_open(target) as descriptor:
            mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
            if mode & 0o077:
                raise ContentHistoryBackfillError(
                    "Apply database must be owner-only (mode 0600)"
                )
    except SafeSourceError as error:
        raise ContentHistoryBackfillError(str(error)) from error
    return target


def _require_target_schema(path: Path) -> None:
    try:
        require_current_schema(path)
    except Exception as error:
        raise ContentHistoryBackfillError(
            "Apply target must be an explicitly migrated disposable copy"
        ) from error
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
        if not _REQUIRED_TARGET_TABLES <= tables:
            raise ContentHistoryBackfillError("Apply target lacks Phase-2 tables")


def _insert_or_verify(
    connection: sqlite3.Connection,
    *,
    table: str,
    insert_columns: Sequence[str],
    values: Sequence[object],
    verify_columns: Sequence[str],
    expected: Sequence[object],
) -> tuple[int, bool]:
    placeholders = ", ".join("?" for _ in insert_columns)
    columns = ", ".join(insert_columns)
    before = connection.total_changes
    connection.execute(
        f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})", values
    )
    inserted = connection.total_changes > before
    identity = " AND ".join(f"{column} IS ?" for column in verify_columns)
    row = connection.execute(
        f"SELECT id FROM {table} WHERE {identity}", expected
    ).fetchone()
    if row is None:
        raise ContentHistoryBackfillError(
            f"Existing {table} row conflicts with the backfill data"
        )
    return int(row["id"]), inserted


def _resolve_target_scope(
    connection: sqlite3.Connection, mapping: BackfillMapping
) -> tuple[int, dict[str, tuple[str, int]]]:
    course = connection.execute(
        "SELECT course.id FROM courses AS course "
        "JOIN seasons AS season ON season.id = course.season_id "
        "WHERE course.public_id = ? AND season.public_id = ?",
        (mapping.course_public_id, mapping.season_public_id),
    ).fetchone()
    if course is None:
        raise ContentHistoryBackfillError(
            "Target course/season does not match the explicit mapping"
        )
    course_id = int(course["id"])
    groups: dict[str, tuple[str, int]] = {}
    for group_mapping in mapping.groups:
        row = connection.execute(
            "SELECT group_id, course_id FROM groups WHERE public_id = ?",
            (group_mapping.target_group_public_id,),
        ).fetchone()
        if (
            row is None
            or str(row["group_id"]) != group_mapping.legacy_group_id
            or int(row["course_id"]) != course_id
        ):
            raise ContentHistoryBackfillError(
                "Target group does not match its explicit legacy/course mapping"
            )
        groups[group_mapping.legacy_group_id] = (
            group_mapping.target_group_public_id,
            course_id,
        )
    return course_id, groups


def _source_encoding(result: CompileResult) -> str:
    return (
        "cp1251" if result.source.encoding is SourceEncoding.WINDOWS_1251 else "utf-8"
    )


def _answer_config(problem: LegacyProblem) -> str:
    return canonical_json(
        {
            "schemaVersion": 1,
            "source": "legacy-manual-backfill",
            "answerType": problem.answer_type,
            "answerValidation": problem.answer_validation,
            "validationError": problem.validation_error,
            "correctAnswer": problem.correct_answer,
            "correctAnswerChecker": problem.correct_answer_checker,
            "wrongAnswer": problem.wrong_answer,
            "congratulation": problem.congratulation,
        }
    )


def _apply_plan(connection: sqlite3.Connection, plan: BackfillPlan) -> Counter[str]:
    mapping = plan.mapping
    course_id, _groups = _resolve_target_scope(connection, mapping)
    changes: Counter[str] = Counter()
    course_lesson_ids: dict[int, int] = {}
    for lesson_number in sorted(
        {item.mapping.course_lesson_number for item in plan.group_lessons}
    ):
        course_lesson_id, inserted = _insert_or_verify(
            connection,
            table="course_lessons",
            insert_columns=(
                "course_id",
                "lesson_number",
                "created_at",
                "updated_at",
            ),
            values=(
                course_id,
                lesson_number,
                mapping.recorded_at,
                mapping.recorded_at,
            ),
            verify_columns=("course_id", "lesson_number"),
            expected=(course_id, lesson_number),
        )
        course_lesson_ids[lesson_number] = course_lesson_id
        changes["courseLessons"] += inserted

    for lesson_plan in plan.group_lessons:
        lesson = lesson_plan.mapping
        course_lesson_id = course_lesson_ids[lesson.course_lesson_number]
        group_lesson_id, inserted = _insert_or_verify(
            connection,
            table="group_lessons",
            insert_columns=(
                "course_lesson_id",
                "course_id",
                "group_id",
                "cycle_anchor_date",
                "business_timezone",
                "status",
                "created_at",
                "updated_at",
            ),
            values=(
                course_lesson_id,
                course_id,
                lesson.legacy_group_id,
                lesson.cycle_anchor_date,
                lesson.business_timezone,
                "active",
                mapping.recorded_at,
                mapping.recorded_at,
            ),
            verify_columns=(
                "course_lesson_id",
                "course_id",
                "group_id",
                "cycle_anchor_date",
                "business_timezone",
                "status",
            ),
            expected=(
                course_lesson_id,
                course_id,
                lesson.legacy_group_id,
                lesson.cycle_anchor_date,
                lesson.business_timezone,
                "active",
            ),
        )
        changes["groupLessons"] += inserted

        if lesson.timestamps.submission_closes_at is not None:
            _window_id, inserted = _insert_or_verify(
                connection,
                table="lesson_windows",
                insert_columns=(
                    "group_lesson_id",
                    "opens_at",
                    "submission_closes_at",
                    "hint_scheduled_at",
                    "solution_scheduled_at",
                    "timezone",
                    "source",
                    "created_at",
                    "updated_at",
                ),
                values=(
                    group_lesson_id,
                    lesson.timestamps.opens_at,
                    lesson.timestamps.submission_closes_at,
                    lesson.timestamps.hint_scheduled_at,
                    lesson.timestamps.solution_scheduled_at,
                    lesson.business_timezone,
                    "manual_backfill",
                    mapping.recorded_at,
                    mapping.recorded_at,
                ),
                verify_columns=(
                    "group_lesson_id",
                    "opens_at",
                    "submission_closes_at",
                    "hint_scheduled_at",
                    "solution_scheduled_at",
                    "timezone",
                    "source",
                ),
                expected=(
                    group_lesson_id,
                    lesson.timestamps.opens_at,
                    lesson.timestamps.submission_closes_at,
                    lesson.timestamps.hint_scheduled_at,
                    lesson.timestamps.solution_scheduled_at,
                    lesson.business_timezone,
                    "manual_backfill",
                ),
            )
            changes["lessonWindows"] += inserted

        for material_plan in lesson_plan.materials:
            material = material_plan.mapping
            result = material_plan.compile_result
            source_id, inserted = _insert_or_verify(
                connection,
                table="content_sources",
                insert_columns=(
                    "group_lesson_id",
                    "kind",
                    "logical_filename",
                    "source_encoding",
                    "created_at",
                ),
                values=(
                    group_lesson_id,
                    material.kind,
                    material_plan.logical_filename,
                    _source_encoding(result),
                    mapping.recorded_at,
                ),
                verify_columns=(
                    "group_lesson_id",
                    "kind",
                    "logical_filename",
                    "source_encoding",
                ),
                expected=(
                    group_lesson_id,
                    material.kind,
                    material_plan.logical_filename,
                    _source_encoding(result),
                ),
            )
            changes["contentSources"] += inserted
            revision_id, inserted = _insert_or_verify(
                connection,
                table="content_revisions",
                insert_columns=(
                    "source_id",
                    "revision_number",
                    "source_sha256",
                    "latex_text",
                    "parser_version",
                    "status",
                    "canonical_json",
                    "diagnostics_json",
                    "provenance_json",
                    "created_at",
                ),
                values=(
                    source_id,
                    1,
                    result.source.raw_sha256,
                    result.source.text,
                    BACKFILL_IMPLEMENTATION_VERSION,
                    "ready",
                    canonical_json(result.ast),
                    _diagnostics_json(result),
                    material_plan.provenance_json,
                    mapping.recorded_at,
                ),
                verify_columns=(
                    "source_id",
                    "revision_number",
                    "source_sha256",
                    "latex_text",
                    "parser_version",
                    "status",
                    "canonical_json",
                    "diagnostics_json",
                    "provenance_json",
                ),
                expected=(
                    source_id,
                    1,
                    result.source.raw_sha256,
                    result.source.text,
                    BACKFILL_IMPLEMENTATION_VERSION,
                    "ready",
                    canonical_json(result.ast),
                    _diagnostics_json(result),
                    material_plan.provenance_json,
                ),
            )
            changes["contentRevisions"] += inserted

            derivatives = (
                ("web_ast", result.web_document),
                ("web_html", result.web),
                ("telegram_html", result.telegram),
            )
            for derivative_kind, derivative in derivatives:
                if derivative is None:
                    raise ContentHistoryBackfillError(
                        "Compiler omitted a required persisted derivative"
                    )
                existing = connection.execute(
                    "SELECT content_text, sha256, provenance_json FROM content_derivatives "
                    "WHERE revision_id = ? AND kind = ? AND renderer_version = ?",
                    (revision_id, derivative_kind, derivative.renderer_version),
                ).fetchone()
                derivative_provenance = canonical_json(
                    {
                        "source": "manual_backfill",
                        "backfillId": mapping.backfill_id,
                        "sourceSha256": result.source.raw_sha256,
                    }
                )
                if existing is None:
                    connection.execute(
                        "INSERT INTO content_derivatives "
                        "(revision_id, kind, renderer_version, content_text, sha256, "
                        "diagnostics_json, provenance_json, created_at) "
                        "VALUES (?, ?, ?, ?, ?, '[]', ?, ?)",
                        (
                            revision_id,
                            derivative_kind,
                            derivative.renderer_version,
                            derivative.content,
                            derivative.sha256,
                            derivative_provenance,
                            mapping.recorded_at,
                        ),
                    )
                    changes["contentDerivatives"] += 1
                elif tuple(existing) != (
                    derivative.content,
                    derivative.sha256,
                    derivative_provenance,
                ):
                    raise ContentHistoryBackfillError(
                        "Existing content derivative conflicts with backfill"
                    )

            if material.kind == "condition":
                for problem in lesson_plan.legacy_problems:
                    source_item = problem.item or "main"
                    existing_match = connection.execute(
                        "SELECT problem_id, decision, resolved_at, diagnostics_json "
                        "FROM content_problem_matches WHERE content_revision_id = ? "
                        "AND source_ordinal = ? AND source_item = ?",
                        (revision_id, problem.problem_number, source_item),
                    ).fetchone()
                    expected_match = (
                        problem.problem_id,
                        "auto_position",
                        mapping.recorded_at,
                        "[]",
                    )
                    if existing_match is None:
                        connection.execute(
                            "INSERT INTO content_problem_matches "
                            "(content_revision_id, source_ordinal, source_item, "
                            "problem_id, decision, resolved_at, diagnostics_json, created_at) "
                            "VALUES (?, ?, ?, ?, 'auto_position', ?, '[]', ?)",
                            (
                                revision_id,
                                problem.problem_number,
                                source_item,
                                problem.problem_id,
                                mapping.recorded_at,
                                mapping.recorded_at,
                            ),
                        )
                        changes["problemMatches"] += 1
                    elif tuple(existing_match) != expected_match:
                        raise ContentHistoryBackfillError(
                            "Existing problem match conflicts with backfill"
                        )

                    answer_config = _answer_config(problem)
                    attempt_policy = canonical_json(
                        {"schemaVersion": 1, "source": "legacy-manual-backfill"}
                    )
                    existing_revision = connection.execute(
                        "SELECT source_ordinal, source_item, display_number, title, "
                        "normalized_title, problem_type, answer_type, answer_config_json, "
                        "attempt_policy_json, config_version FROM problem_revisions "
                        "WHERE problem_id = ? AND content_revision_id = ?",
                        (problem.problem_id, revision_id),
                    ).fetchone()
                    expected_revision = (
                        problem.problem_number,
                        source_item,
                        f"{problem.problem_number}{problem.item}",
                        problem.title,
                        _normalize_title(problem.title),
                        problem.problem_type,
                        problem.answer_type,
                        answer_config,
                        attempt_policy,
                        1,
                    )
                    if existing_revision is None:
                        connection.execute(
                            "INSERT INTO problem_revisions "
                            "(problem_id, content_revision_id, source_ordinal, source_item, "
                            "display_number, title, normalized_title, problem_type, "
                            "answer_type, answer_config_json, attempt_policy_json, "
                            "config_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                            (
                                problem.problem_id,
                                revision_id,
                                *expected_revision[:-1],
                                mapping.recorded_at,
                            ),
                        )
                        changes["problemRevisions"] += 1
                    elif tuple(existing_revision) != expected_revision:
                        raise ContentHistoryBackfillError(
                            "Existing problem revision conflicts with backfill"
                        )

            if material.published_at is not None:
                _publication_id, inserted = _insert_or_verify(
                    connection,
                    table="lesson_publications",
                    insert_columns=(
                        "group_lesson_id",
                        "kind",
                        "revision_id",
                        "state",
                        "published_at",
                        "provenance_kind",
                        "created_at",
                        "updated_at",
                    ),
                    values=(
                        group_lesson_id,
                        material.kind,
                        revision_id,
                        "published",
                        material.published_at,
                        "legacy_backfill",
                        mapping.recorded_at,
                        mapping.recorded_at,
                    ),
                    verify_columns=(
                        "group_lesson_id",
                        "kind",
                        "revision_id",
                        "state",
                        "published_at",
                        "provenance_kind",
                    ),
                    expected=(
                        group_lesson_id,
                        material.kind,
                        revision_id,
                        "published",
                        material.published_at,
                        "legacy_backfill",
                    ),
                )
                changes["publications"] += inserted
    return changes


def apply_backfill(
    source_database: Path,
    target_database: Path,
    mapping_path: Path,
    *,
    expected_preview_sha256: str,
) -> tuple[BackfillPlan, dict[str, Any]]:
    """Apply a reviewed plan transactionally to a separate migrated DB copy."""

    if _SHA256.fullmatch(expected_preview_sha256) is None:
        raise ContentHistoryBackfillError("Expected preview SHA-256 is invalid")
    target = _reject_apply_target(target_database, source_database)
    _require_target_schema(target)
    plan, preview = preview_backfill(source_database, mapping_path)
    if preview["previewSha256"] != expected_preview_sha256:
        raise ContentHistoryBackfillError(
            "Current deterministic preview does not match the reviewed hash"
        )
    if not plan.is_ready:
        raise ContentHistoryBackfillError("Blocked preview cannot be applied")

    source_path = Path(source_database)
    try:
        _require_quiescent_source(source_path)
        with secure_open(source_path) as source_descriptor:
            source_before = fingerprint(source_descriptor)
            verify_path_matches(source_path, source_before)
            if source_before != plan.source_fingerprint:
                raise ContentHistoryBackfillError(
                    "Read-only source changed after the reviewed preview"
                )
            connection = sqlite3.connect(target, autocommit=True)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("PRAGMA busy_timeout = 5000")
                connection.execute("BEGIN IMMEDIATE")
                try:
                    # Historical migrations contain credential-shaped
                    # ``kv_logins`` rows without matching synthetic users.
                    # Prove this content-only increment adds no FK defect.
                    foreign_keys_before = tuple(
                        tuple(row)
                        for row in connection.execute("PRAGMA foreign_key_check")
                    )
                    _target_lessons, _target_problems, target_fingerprint = (
                        _load_legacy(connection, plan.mapping)
                    )
                    if target_fingerprint != plan.legacy_fingerprint:
                        raise ContentHistoryBackfillError(
                            "Target legacy lesson/problem rows differ from reviewed source"
                        )
                    changes = _apply_plan(connection, plan)
                    _after_lessons, _after_problems, after_fingerprint = _load_legacy(
                        connection, plan.mapping
                    )
                    if after_fingerprint != target_fingerprint:
                        raise ContentHistoryBackfillError(
                            "Backfill attempted to rewrite legacy lesson/problem rows"
                        )
                    foreign_keys_after = tuple(
                        tuple(row)
                        for row in connection.execute("PRAGMA foreign_key_check")
                    )
                    if foreign_keys_after != foreign_keys_before:
                        raise ContentHistoryBackfillError(
                            "Backfill changed the target foreign_key_check baseline"
                        )
                    if (
                        connection.execute("PRAGMA integrity_check").fetchone()[0]
                        != "ok"
                    ):
                        raise ContentHistoryBackfillError(
                            "Target integrity_check failed"
                        )
                    source_after = fingerprint(source_descriptor)
                    verify_path_matches(source_path, source_after)
                    _require_quiescent_source(source_path)
                    if source_after != source_before:
                        raise ContentHistoryBackfillError(
                            "Read-only source changed during the apply operation"
                        )
                    connection.execute("COMMIT")
                except Exception:
                    connection.execute("ROLLBACK")
                    raise
            finally:
                connection.close()
    except SafeSourceError as error:
        raise ContentHistoryBackfillError(str(error)) from error

    inserted_total = sum(changes.values())
    report = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "operation": "apply",
        "status": "applied" if inserted_total else "already-applied",
        "reviewedPreviewSha256": expected_preview_sha256,
        "insertedRows": {key: changes[key] for key in sorted(_predicted_changes(plan))},
        "legacyRowsUpdated": 0,
        "historicalTimestampInferenceCount": 0,
        "sourceLegacyFingerprint": plan.legacy_fingerprint,
    }
    return plan, report


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        atomic_write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            mode=0o644,
        )
    except AtomicReportWriteError as error:
        raise ContentHistoryBackfillError("Could not write backfill report") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preview = subparsers.add_parser("preview")
    preview.add_argument("--source-db", type=Path, required=True)
    preview.add_argument("--mapping", type=Path, required=True)
    preview.add_argument("--report", type=Path)
    apply = subparsers.add_parser("apply")
    apply.add_argument("--source-db", type=Path, required=True)
    apply.add_argument("--target-db", type=Path, required=True)
    apply.add_argument("--mapping", type=Path, required=True)
    apply.add_argument("--expected-preview-sha256", required=True)
    apply.add_argument("--report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preview":
            _plan, report = preview_backfill(args.source_db, args.mapping)
        else:
            _plan, report = apply_backfill(
                args.source_db,
                args.target_db,
                args.mapping,
                expected_preview_sha256=args.expected_preview_sha256,
            )
        if args.report is not None:
            _write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["status"] != "blocked" else 2
    except ContentHistoryBackfillError as error:
        print(f"content history backfill refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
