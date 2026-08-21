"""Connection-per-operation repository for Phase-2 lesson/content storage.

This is the persistence half of the first Phase-2 increment.  It deliberately
contains no aiohttp or compiler behavior. It updates the legacy ``problems``
projection only when an administrator atomically confirms a metadata grid; it
never rewrites legacy ``lessons`` or historical result rows. See
``vmshpwa/dev/development-plan/06-phase-2-content.md`` and tests in
``pwa_tests/{domain,integration}/test_content*.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from models.pwa.content import (
    ContentInvariantError,
    ContentKind,
    LessonWindowDraft,
    ProblemMatchDraft,
    ProblemMatchDecision,
    ProblemMetadataDraft,
    ProblemRevisionDraft,
    ProblemSynonymCandidate,
    ProblemTitleCandidateInput,
    PROBLEM_TYPE_VALUES,
    PublicationState,
    RevisionStatus,
    ScheduleField,
    ScheduleOverrideMode,
    ScheduleRuleValue,
    SourceRevisionPayload,
    WindowSource,
    find_problem_synonym_candidates,
    format_utc_timestamp,
    materialize_lesson_window,
    parse_utc_timestamp,
    require_publication_transition,
    require_revision_transition,
    resolve_student_lesson_phase,
)
from models.pwa.content_asset_names import (
    figure_lookup_names,
    normalize_content_asset_name,
)

from .connection import PwaConnectionFactory


_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMPILE_LEASE_DURATION = timedelta(minutes=2)
CONTENT_HISTORY_ITEMS_PER_KIND_LIMIT = 250


class ContentRepositoryError(RuntimeError):
    """Base class for expected Phase-2 persistence failures."""


class ContentNotFound(ContentRepositoryError):
    """A requested content object does not exist."""


class ContentConflict(ContentRepositoryError):
    """A unique or immutable content identity conflicts with stored state."""


class ContentVersionConflict(ContentConflict):
    """A mutable record changed after the caller read its version."""


@dataclass(frozen=True, slots=True)
class CourseLessonRecord:
    id: int
    public_id: str
    course_id: int
    lesson_number: int
    title: str | None
    version: int


@dataclass(frozen=True, slots=True)
class GroupLessonRecord:
    id: int
    public_id: str
    course_lesson_id: int
    course_id: int
    group_id: str
    cycle_anchor_date: date
    business_timezone: str
    status: str
    version: int


@dataclass(frozen=True, slots=True)
class ContentUploadTargetRecord:
    """One concrete group lesson available in a course-lesson bulk upload."""

    course_lesson_public_id: str
    lesson_number: int
    course_public_id: str
    course_name: str
    group_lesson_public_id: str
    group_public_id: str
    group_name: str
    group_short_code: str
    group_color_key: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ContentSourceRecord:
    id: int
    public_id: str
    group_lesson_id: int
    kind: ContentKind
    logical_filename: str
    source_encoding: str


@dataclass(frozen=True, slots=True)
class ContentRevisionRecord:
    id: int
    public_id: str
    source_id: int
    revision_number: int
    source_sha256: str
    latex_text: str
    parser_version: str
    status: RevisionStatus
    canonical_document: object | None
    diagnostics: tuple[object, ...]
    provenance: Mapping[str, object]
    version: int
    supersedes_revision_id: int | None
    compile_claim_token: str | None
    compile_claimed_at: datetime | None
    compile_lease_expires_at: datetime | None
    compile_attempt_count: int
    compile_completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LessonWindowRecord:
    id: int
    public_id: str
    group_lesson_id: int
    opens_at: datetime | None
    submission_closes_at: datetime
    hint_scheduled_at: datetime | None
    solution_scheduled_at: datetime | None
    timezone: str
    source: str
    version: int


@dataclass(frozen=True, slots=True)
class LessonWindowScheduleSourceRecord:
    lesson_window_id: int
    schedule_field: ScheduleField
    course_schedule_rule_id: int
    course_rule_version: int
    group_schedule_override_id: int | None
    group_override_version: int | None
    resolution_mode: ScheduleOverrideMode
    resolved_value: ScheduleRuleValue | None


@dataclass(frozen=True, slots=True)
class CourseScheduleRuleRecord:
    id: int
    public_id: str
    course_id: int
    schedule_field: ScheduleField
    rule_version: int
    value: ScheduleRuleValue
    state: str
    version: int


@dataclass(frozen=True, slots=True)
class GroupScheduleOverrideRecord:
    id: int
    public_id: str
    course_id: int
    group_id: str
    schedule_field: ScheduleField
    override_version: int
    mode: ScheduleOverrideMode
    value: ScheduleRuleValue | None
    based_on_schedule_rule_id: int | None
    state: str
    version: int


@dataclass(frozen=True, slots=True)
class ScheduleImpactPreview:
    draft_rule_id: int
    active_rule_id: int | None
    group_lesson_count: int
    materialized_window_count: int


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    id: int
    public_id: str
    group_lesson_id: int
    kind: ContentKind
    revision_id: int
    state: PublicationState
    scheduled_at: datetime | None
    published_at: datetime | None
    hidden_at: datetime | None
    supersedes_publication_id: int | None
    activated_from_schedule_id: int | None
    version: int
    terminal_by_user_id: int | None
    terminal_at: datetime | None


@dataclass(frozen=True, slots=True)
class MediaAssetRecord:
    id: int
    public_id: str
    sha256: str
    storage_namespace: str
    object_key: str
    media_type: str
    byte_size: int
    conversion_version: str
    public_url: str | None = None
    width: int | None = None
    height: int | None = None
    source_filename: str | None = None


@dataclass(frozen=True, slots=True)
class ContentRevisionAssetRecord:
    """One immutable media attachment on an exact source revision."""

    revision_id: int
    logical_name: str
    role: str
    ordinal: int
    alt_text: str | None
    asset: MediaAssetRecord


@dataclass(frozen=True, slots=True)
class ContentDerivativeRecord:
    id: int
    revision_id: int
    kind: str
    renderer_version: str
    sha256: str
    content_text: str | None
    asset_id: int | None


@dataclass(frozen=True, slots=True)
class TextDerivativeDraft:
    """One text derivative persisted with a successful compiler transition."""

    kind: str
    renderer_version: str
    content_text: str
    provenance: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class GroupLessonContentScope:
    """Public authorization scope for one concrete group lesson."""

    group_lesson_id: int
    group_lesson_public_id: str
    course_id: int
    course_public_id: str
    group_id: str
    group_public_id: str
    status: str
    business_timezone: str


@dataclass(frozen=True, slots=True)
class ContentRevisionContext:
    """Revision plus its immutable source and course/group scope."""

    revision: ContentRevisionRecord
    source: ContentSourceRecord
    scope: GroupLessonContentScope


@dataclass(frozen=True, slots=True)
class PublicationContext:
    """Publication plus the exact revision and authorization scope it uses."""

    publication: PublicationRecord
    revision_public_id: str
    scope: GroupLessonContentScope


@dataclass(frozen=True, slots=True)
class PublishedContentRecord:
    """The only Student/Family-readable Phase-2 content projection."""

    publication: PublicationRecord
    revision_public_id: str
    scope: GroupLessonContentScope
    document: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StudentProblemRevealRecord:
    """One idempotent, audited Student reveal of a published task material."""

    problem_public_id: str
    source_ordinal: int
    kind: ContentKind
    revealed_at: datetime
    first_reveal: bool
    content: PublishedContentRecord


@dataclass(frozen=True, slots=True)
class StudentLessonMaterialRecord:
    """One currently published, browser-readable Student material."""

    revision_public_id: str
    published_at: datetime
    publication_version: int


@dataclass(frozen=True, slots=True)
class StudentLessonSummaryRecord:
    """Bounded course/group lesson projection for Student navigation.

    ``group_lesson_public_id`` is deliberately the routable lesson identity:
    schedule and content belong to a concrete group lesson even when several
    groups share one course lesson number. See Phase 3 in
    ``vmshpwa/dev/development-plan/07-phase-3-student-reading.md``.
    """

    group_lesson_public_id: str
    course_lesson_public_id: str
    course_public_id: str
    group_public_id: str
    lesson_number: int
    title: str | None
    cycle_anchor_date: date
    business_timezone: str
    version: int
    window: LessonWindowRecord | None
    condition: StudentLessonMaterialRecord
    hint: StudentLessonMaterialRecord | None
    solution: StudentLessonMaterialRecord | None
    problem_count: int


@dataclass(frozen=True, slots=True)
class StudentHomeLessonRecord:
    lesson: StudentLessonSummaryRecord
    phase: str


@dataclass(frozen=True, slots=True)
class StudentHomeSnapshot:
    generated_at: datetime
    lessons: tuple[StudentHomeLessonRecord, ...]


@dataclass(frozen=True, slots=True)
class StudentProblemVerdictRecord:
    """Best persisted verdict across the problem's current synonym projection."""

    verdict_id: int
    symbol: str
    weight: float


@dataclass(frozen=True, slots=True)
class StudentProblemSummaryRecord:
    """One exact problem revision with Student-owned work state."""

    problem_public_id: str
    config_version: int
    source_ordinal: int
    display_number: str
    title: str
    problem_type: int
    answer_type: int | None
    hint_state: str
    solution_state: str
    status: str
    verdict: StudentProblemVerdictRecord | None


@dataclass(frozen=True, slots=True)
class StudentProblemListRecord:
    """Canonical task list of the condition revision currently published."""

    group_lesson_public_id: str
    course_public_id: str
    group_public_id: str
    condition_revision_public_id: str
    problems: tuple[StudentProblemSummaryRecord, ...]


@dataclass(frozen=True, slots=True)
class GroupLessonContentHistory:
    """Staff read model needed to resume publication work after a reload."""

    scope: GroupLessonContentScope
    revisions: tuple[ContentRevisionContext, ...]
    publications: tuple[PublicationContext, ...]


@dataclass(frozen=True, slots=True)
class RevisionPublicationReadiness:
    """Minimal explicit gate between compiler output and student publication."""

    expected_problem_count: int
    resolved_match_count: int
    reviewed_problem_count: int
    omitted_problem_count: int
    structure_matches: bool

    @property
    def is_structurally_ready(self) -> bool:
        return (
            self.resolved_match_count == self.expected_problem_count
            and self.structure_matches
        )

    @property
    def is_ready(self) -> bool:
        return (
            self.is_structurally_ready
            and self.reviewed_problem_count + self.omitted_problem_count
            == self.expected_problem_count
        )


@dataclass(frozen=True, slots=True)
class CanonicalProblemRecord:
    source_ordinal: int
    source_item: str
    source_title: str | None
    display_number: str
    problem_type: int


@dataclass(frozen=True, slots=True)
class LegacyProblemRecord:
    problem_id: int
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
class ProblemMatchRecord:
    source_ordinal: int
    source_item: str
    problem_id: int | None
    decision: ProblemMatchDecision


@dataclass(frozen=True, slots=True)
class ProblemMatchReviewItem:
    source: CanonicalProblemRecord
    match: ProblemMatchRecord | None
    suggested_problem_id: int | None


@dataclass(frozen=True, slots=True)
class ProblemMatchReview:
    revision_id: int
    revision_public_id: str
    group_lesson_public_id: str
    review_version: int
    items: tuple[ProblemMatchReviewItem, ...]
    candidates: tuple[LegacyProblemRecord, ...]


@dataclass(frozen=True, slots=True)
class ProblemMetadataRecord:
    source: CanonicalProblemRecord
    problem: LegacyProblemRecord
    reviewed: bool


@dataclass(frozen=True, slots=True)
class ProblemMetadataGrid:
    revision_id: int
    revision_public_id: str
    group_lesson_public_id: str
    review_version: int
    rows: tuple[ProblemMetadataRecord, ...]


@dataclass(frozen=True, slots=True)
class ProblemRevisionRecord:
    id: int
    problem_id: int
    content_revision_id: int
    normalized_title: str


@dataclass(frozen=True, slots=True)
class SynonymGroupRecord:
    id: int
    public_id: str
    course_lesson_id: int
    group_key: str
    display_title: str
    status: str
    version: int


@dataclass(frozen=True, slots=True)
class SynonymMemberRecord:
    id: int
    synonym_group_id: int
    group_lesson_id: int
    problem_id: int
    membership_version: int
    removed_at: datetime | None


def _require_public_id(value: str) -> str:
    if _PUBLIC_ID.fullmatch(value) is None:
        raise ContentInvariantError("public ID is not canonical")
    return value


def _require_sha256(value: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise ContentInvariantError("SHA-256 must be lowercase hexadecimal")
    return value


def _required_text(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ContentInvariantError(f"{label} must not be empty")
    return normalized


def _optional_text(value: str | None, *, label: str) -> str | None:
    return None if value is None else _required_text(value, label=label)


def _require_timezone(value: str, *, label: str) -> str:
    timezone = _required_text(value, label=label)
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ContentInvariantError(f"{label} is unknown") from error
    return timezone


def _require_object_key(value: str) -> str:
    object_key = _required_text(value, label="object key")
    if (
        len(object_key) > 1024
        or object_key.startswith("/")
        or object_key.endswith("/")
        or "\\" in object_key
        or any(part in {"", ".", ".."} for part in object_key.split("/"))
        or any(ord(character) < 32 or ord(character) == 127 for character in object_key)
    ):
        raise ContentInvariantError("object key is not canonical")
    return object_key


def _optional_public_url(value: str | None) -> str | None:
    if value is None:
        return None
    public_url = _required_text(value, label="public URL")
    parsed = urlsplit(public_url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ContentInvariantError("public URL must be HTTP(S) without credentials")
    return public_url


def _optional_timestamp(value: object) -> datetime | None:
    return None if value is None else parse_utc_timestamp(str(value))


def _canonical_json_object(value: Mapping[str, object], *, label: str) -> str:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ContentInvariantError(f"{label} must be JSON-serializable") from error
    if not isinstance(json.loads(serialized), dict):
        raise ContentInvariantError(f"{label} must be an object")
    return serialized


def _canonical_json_document(value: object, *, label: str) -> str:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ContentInvariantError(f"{label} must be JSON-serializable") from error
    if not isinstance(json.loads(serialized), (dict, list)):
        raise ContentInvariantError(f"{label} must be an object or array")
    return serialized


def _canonical_diagnostics(value: Sequence[object]) -> str:
    try:
        serialized = json.dumps(
            list(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ContentInvariantError("diagnostics must be JSON-serializable") from error
    if not isinstance(json.loads(serialized), list):
        raise ContentInvariantError("diagnostics must be an array")
    return serialized


def _translate_integrity(
    error: sqlite3.IntegrityError, *, action: str
) -> ContentConflict:
    return ContentConflict(f"{action} conflicts with stored content state")


def _require_expected_slot(
    public_id: str | None, version: int | None, *, label: str
) -> None:
    if public_id is None and version is None:
        return
    if public_id is None or version is None or version < 1:
        raise ContentInvariantError(f"{label} expected identity/version is invalid")
    _require_public_id(public_id)


def _course_lesson(row: Mapping[str, object]) -> CourseLessonRecord:
    return CourseLessonRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        course_id=int(row["course_id"]),
        lesson_number=int(row["lesson_number"]),
        title=None if row["title"] is None else str(row["title"]),
        version=int(row["version"]),
    )


def _group_lesson(row: Mapping[str, object]) -> GroupLessonRecord:
    return GroupLessonRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        course_lesson_id=int(row["course_lesson_id"]),
        course_id=int(row["course_id"]),
        group_id=str(row["group_id"]),
        cycle_anchor_date=date.fromisoformat(str(row["cycle_anchor_date"])),
        business_timezone=str(row["business_timezone"]),
        status=str(row["status"]),
        version=int(row["version"]),
    )


def _content_upload_target(row: Mapping[str, object]) -> ContentUploadTargetRecord:
    return ContentUploadTargetRecord(
        course_lesson_public_id=str(row["course_lesson_public_id"]),
        lesson_number=int(row["lesson_number"]),
        course_public_id=str(row["course_public_id"]),
        course_name=str(row["course_name"]),
        group_lesson_public_id=str(row["group_lesson_public_id"]),
        group_public_id=str(row["group_public_id"]),
        group_name=str(row["group_name"]),
        group_short_code=str(row["group_short_code"]),
        group_color_key=(
            None if row["group_color_key"] is None else str(row["group_color_key"])
        ),
        status=str(row["group_lesson_status"]),
    )


def _content_source(row: Mapping[str, object]) -> ContentSourceRecord:
    return ContentSourceRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        group_lesson_id=int(row["group_lesson_id"]),
        kind=ContentKind(str(row["kind"])),
        logical_filename=str(row["logical_filename"]),
        source_encoding=str(row["source_encoding"]),
    )


def _content_revision(row: Mapping[str, object]) -> ContentRevisionRecord:
    provenance = json.loads(str(row["provenance_json"]))
    if not isinstance(provenance, dict):
        raise ContentRepositoryError("stored revision provenance is not an object")
    diagnostics = json.loads(str(row["diagnostics_json"]))
    if not isinstance(diagnostics, list):
        raise ContentRepositoryError("stored revision diagnostics are not an array")
    canonical_document = (
        None
        if row["canonical_json"] is None
        else json.loads(str(row["canonical_json"]))
    )
    return ContentRevisionRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        source_id=int(row["source_id"]),
        revision_number=int(row["revision_number"]),
        source_sha256=str(row["source_sha256"]),
        latex_text=str(row["latex_text"]),
        parser_version=str(row["parser_version"]),
        status=RevisionStatus(str(row["status"])),
        canonical_document=canonical_document,
        diagnostics=tuple(diagnostics),
        provenance=provenance,
        version=int(row["version"]),
        supersedes_revision_id=(
            None
            if row["supersedes_revision_id"] is None
            else int(row["supersedes_revision_id"])
        ),
        compile_claim_token=(
            None
            if row["compile_claim_token"] is None
            else str(row["compile_claim_token"])
        ),
        compile_claimed_at=_optional_timestamp(row["compile_claimed_at"]),
        compile_lease_expires_at=_optional_timestamp(row["compile_lease_expires_at"]),
        compile_attempt_count=int(row["compile_attempt_count"]),
        compile_completed_at=_optional_timestamp(row["compile_completed_at"]),
        created_at=parse_utc_timestamp(str(row["created_at"])),
    )


def _canonical_problem_records(value: object) -> tuple[CanonicalProblemRecord, ...]:
    """Decode the exact compiler identities used by immutable review rows."""

    if not isinstance(value, dict) or not isinstance(value.get("problems"), list):
        raise ContentRepositoryError(
            "content revision canonical AST has no problem list"
        )
    records: list[CanonicalProblemRecord] = []
    identities: set[tuple[int, str]] = set()
    for raw in value["problems"]:
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("ordinal"), int)
            or isinstance(raw.get("ordinal"), bool)
        ):
            raise ContentRepositoryError(
                "content revision canonical problem is invalid"
            )
        ordinal = int(raw["ordinal"])
        source_item_value = raw.get("source_item")
        if source_item_value is not None and not isinstance(source_item_value, str):
            raise ContentRepositoryError(
                "content revision canonical problem identity is invalid"
            )
        source_item = (
            str(ordinal)
            if source_item_value is None or source_item_value == ""
            else str(source_item_value).strip()
        )
        if ordinal < 0 or not source_item:
            raise ContentRepositoryError(
                "content revision canonical problem identity is invalid"
            )
        source_title_value = raw.get("source_title")
        if source_title_value is None or source_title_value == "":
            source_title = None
        elif isinstance(source_title_value, str):
            source_title = source_title_value.strip() or None
        else:
            raise ContentRepositoryError("content revision canonical title is invalid")
        raw_problem_type = raw.get("problem_type", 2)
        problem_type = (
            raw_problem_type
            if isinstance(raw_problem_type, int)
            and not isinstance(raw_problem_type, bool)
            and raw_problem_type in {1, 2, 3}
            else 2
        )

        subpart_labels: list[str] = []

        def collect_subparts(blocks: object) -> None:
            if not isinstance(blocks, list):
                return
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                label = block.get("label")
                children = block.get("children")
                if isinstance(label, str) and isinstance(children, list):
                    normalized = label.strip()
                    if normalized:
                        subpart_labels.append(normalized)
                    continue
                for nested in block.values():
                    if isinstance(nested, list):
                        collect_subparts(nested)

        collect_subparts(raw.get("statement"))
        canonical_items = subpart_labels or [source_item]
        for canonical_item in canonical_items:
            identity = (ordinal, canonical_item)
            if identity in identities:
                raise ContentRepositoryError(
                    "content revision canonical problem identities are duplicated"
                )
            identities.add(identity)
            records.append(
                CanonicalProblemRecord(
                    source_ordinal=ordinal,
                    source_item=canonical_item,
                    source_title=source_title,
                    display_number=(
                        str(ordinal)
                        if canonical_item == str(ordinal)
                        else f"{ordinal}{canonical_item}"
                    ),
                    problem_type=problem_type,
                )
            )
    return tuple(records)


def _legacy_problem(row: Mapping[str, object]) -> LegacyProblemRecord:
    return LegacyProblemRecord(
        problem_id=int(row["id"]),
        problem_number=int(row["prob"]),
        item=str(row["item"]),
        title=str(row["title"]),
        problem_type=int(row["prob_type"]),
        answer_type=None if row["ans_type"] is None else int(row["ans_type"]),
        answer_validation=(
            None if row["ans_validation"] is None else str(row["ans_validation"])
        ),
        validation_error=(
            None if row["validation_error"] is None else str(row["validation_error"])
        ),
        correct_answer=None if row["cor_ans"] is None else str(row["cor_ans"]),
        correct_answer_checker=(
            None if row["cor_ans_checker"] is None else str(row["cor_ans_checker"])
        ),
        wrong_answer=None if row["wrong_ans"] is None else str(row["wrong_ans"]),
        congratulation=None if row["congrat"] is None else str(row["congrat"]),
    )


def _review_version(connection: sqlite3.Connection, revision_id: int) -> int:
    """Return the optimistic-concurrency version of current task review."""

    state = connection.execute(
        "SELECT version FROM content_review_states WHERE content_revision_id = ?",
        (revision_id,),
    ).fetchone()
    if state is not None:
        return int(state["version"])

    row = connection.execute(
        "SELECT "
        "(SELECT count(*) FROM content_problem_matches "
        " WHERE content_revision_id = ?) + "
        "(SELECT count(*) FROM problem_revisions "
        " WHERE content_revision_id = ?) AS review_rows",
        (revision_id, revision_id),
    ).fetchone()
    return 1 + int(row["review_rows"])


def _advance_review_version(
    connection: sqlite3.Connection,
    *,
    revision_id: int,
    expected_version: int,
    timestamp: str,
    actor_user_id: int | None,
) -> None:
    """Advance review state once a current structure/configuration changes."""

    state = connection.execute(
        "SELECT 1 FROM content_review_states WHERE content_revision_id = ?",
        (revision_id,),
    ).fetchone()
    if state is None:
        connection.execute(
            "INSERT INTO content_review_states "
            "(content_revision_id, version, updated_at, updated_by_user_id) "
            "VALUES (?, ?, ?, ?)",
            (revision_id, expected_version + 1, timestamp, actor_user_id),
        )
        return
    cursor = connection.execute(
        "UPDATE content_review_states SET version = version + 1, updated_at = ?, "
        "updated_by_user_id = ? WHERE content_revision_id = ? AND version = ?",
        (timestamp, actor_user_id, revision_id, expected_version),
    )
    if cursor.rowcount != 1:
        raise ContentVersionConflict("problem review version changed")


def _review_scope_row(
    connection: sqlite3.Connection, revision_public_id: str
) -> Mapping[str, object]:
    row = connection.execute(
        "SELECT revision.id AS revision_id, revision.public_id AS revision_public_id, "
        "revision.status AS revision_status, revision.canonical_json, "
        "source.group_lesson_id, group_lesson.public_id AS group_lesson_public_id, "
        "group_lesson.group_id, course_lesson.lesson_number "
        "FROM content_revisions AS revision "
        "JOIN content_sources AS source ON source.id = revision.source_id "
        "JOIN group_lessons AS group_lesson "
        "  ON group_lesson.id = source.group_lesson_id "
        "JOIN course_lessons AS course_lesson "
        "  ON course_lesson.id = group_lesson.course_lesson_id "
        "WHERE revision.public_id = ?",
        (revision_public_id,),
    ).fetchone()
    if row is None:
        raise ContentNotFound("content revision does not exist")
    if row["revision_status"] != RevisionStatus.READY.value:
        raise ContentConflict("problem review requires a ready revision")
    if not isinstance(row["canonical_json"], str):
        raise ContentRepositoryError("content revision has no canonical AST")
    return row


def _problem_match_review_from_connection(
    connection: sqlite3.Connection, revision_public_id: str
) -> ProblemMatchReview:
    scope = _review_scope_row(connection, revision_public_id)
    try:
        document = json.loads(str(scope["canonical_json"]))
    except (json.JSONDecodeError, RecursionError) as error:
        raise ContentRepositoryError(
            "content revision canonical AST is invalid"
        ) from error
    sources = _canonical_problem_records(document)
    revision_id = int(scope["revision_id"])
    matches = {
        (int(row["source_ordinal"]), str(row["source_item"])): ProblemMatchRecord(
            source_ordinal=int(row["source_ordinal"]),
            source_item=str(row["source_item"]),
            problem_id=None if row["problem_id"] is None else int(row["problem_id"]),
            decision=ProblemMatchDecision(str(row["decision"])),
        )
        for row in connection.execute(
            "SELECT source_ordinal, source_item, problem_id, decision "
            "FROM content_problem_matches WHERE content_revision_id = ? "
            "ORDER BY source_ordinal, source_item",
            (revision_id,),
        ).fetchall()
    }
    candidate_rows = connection.execute(
        "SELECT * FROM problems WHERE group_id = ? AND lesson = ? "
        "ORDER BY prob, item COLLATE NOCASE, id LIMIT 5001",
        (scope["group_id"], scope["lesson_number"]),
    ).fetchall()
    if len(candidate_rows) > 5_000:
        raise ContentRepositoryError("legacy problem candidate list exceeds limit")
    candidates = tuple(_legacy_problem(row) for row in candidate_rows)
    by_position: dict[int, list[LegacyProblemRecord]] = {}
    for candidate in candidates:
        by_position.setdefault(candidate.problem_number, []).append(candidate)

    items: list[ProblemMatchReviewItem] = []
    for source in sources:
        exact = by_position.get(source.source_ordinal, [])
        suggested: int | None = None
        if len(exact) == 1:
            suggested = exact[0].problem_id
        elif exact:
            by_item = [
                candidate
                for candidate in exact
                if candidate.item.strip() == source.source_item
            ]
            if len(by_item) == 1:
                suggested = by_item[0].problem_id
        match = matches.get((source.source_ordinal, source.source_item))
        if match is not None:
            suggested = match.problem_id
        items.append(
            ProblemMatchReviewItem(
                source=source,
                match=match,
                suggested_problem_id=suggested,
            )
        )
    return ProblemMatchReview(
        revision_id=revision_id,
        revision_public_id=str(scope["revision_public_id"]),
        group_lesson_public_id=str(scope["group_lesson_public_id"]),
        review_version=_review_version(connection, revision_id),
        items=tuple(items),
        candidates=candidates,
    )


def _reviewed_problem(
    legacy: LegacyProblemRecord, row: Mapping[str, object]
) -> LegacyProblemRecord:
    try:
        answer_config = json.loads(str(row["answer_config_json"]))
    except (json.JSONDecodeError, RecursionError) as error:
        raise ContentRepositoryError("stored answer config is invalid") from error
    if not isinstance(answer_config, dict):
        raise ContentRepositoryError("stored answer config is not an object")

    def optional_config(name: str) -> str | None:
        value = answer_config.get(name)
        return None if value is None else str(value)

    return LegacyProblemRecord(
        problem_id=legacy.problem_id,
        problem_number=legacy.problem_number,
        item=legacy.item,
        title=str(row["title"]),
        problem_type=int(row["problem_type"]),
        answer_type=None if row["answer_type"] is None else int(row["answer_type"]),
        answer_validation=optional_config("answerValidation"),
        validation_error=optional_config("validationError"),
        correct_answer=optional_config("correctAnswer"),
        correct_answer_checker=optional_config("correctAnswerChecker"),
        wrong_answer=optional_config("wrongAnswer"),
        congratulation=optional_config("congratulation"),
    )


def _metadata_matches_draft(
    problem: LegacyProblemRecord, draft: ProblemMetadataDraft
) -> bool:
    return (
        problem.problem_id == draft.problem_id
        and problem.title == draft.title
        and problem.problem_type == draft.problem_type
        and problem.answer_type == draft.answer_type
        and problem.answer_validation == draft.answer_validation
        and problem.validation_error == draft.validation_error
        and problem.correct_answer == draft.correct_answer
        and problem.correct_answer_checker == draft.correct_answer_checker
        and problem.wrong_answer == draft.wrong_answer
        and problem.congratulation == draft.congratulation
    )


def _problem_metadata_grid_from_connection(
    connection: sqlite3.Connection, revision_public_id: str
) -> ProblemMetadataGrid:
    review = _problem_match_review_from_connection(connection, revision_public_id)
    source_by_identity = {
        (item.source.source_ordinal, item.source.source_item): item.source
        for item in review.items
    }
    match_rows = connection.execute(
        "SELECT source_ordinal, source_item, problem_id, decision "
        "FROM content_problem_matches WHERE content_revision_id = ? "
        "ORDER BY source_ordinal, source_item",
        (review.revision_id,),
    ).fetchall()
    if len(match_rows) != len(review.items):
        raise ContentConflict("problem matches are incomplete")
    candidates = {candidate.problem_id: candidate for candidate in review.candidates}
    revision_rows = {
        (
            int(row["source_ordinal"]),
            str(row["source_item"]),
            int(row["problem_id"]),
        ): row
        for row in connection.execute(
            "SELECT * FROM problem_revisions WHERE content_revision_id = ?",
            (review.revision_id,),
        ).fetchall()
    }
    rows: list[ProblemMetadataRecord] = []
    seen: set[tuple[int, str]] = set()
    for match in match_rows:
        identity = (int(match["source_ordinal"]), str(match["source_item"]))
        source = source_by_identity.get(identity)
        if source is None or identity in seen:
            raise ContentRepositoryError("stored problem match structure is invalid")
        seen.add(identity)
        if match["decision"] == ProblemMatchDecision.OMIT.value:
            continue
        problem_id = int(match["problem_id"])
        legacy = candidates.get(problem_id)
        if legacy is None:
            raise ContentRepositoryError(
                "matched legacy problem is outside lesson scope"
            )
        revision_row = revision_rows.get((*identity, problem_id))
        rows.append(
            ProblemMetadataRecord(
                source=source,
                problem=(
                    legacy
                    if revision_row is None
                    else _reviewed_problem(legacy, revision_row)
                ),
                reviewed=revision_row is not None,
            )
        )
    if seen != set(source_by_identity):
        raise ContentConflict("problem matches are incomplete")
    return ProblemMetadataGrid(
        revision_id=review.revision_id,
        revision_public_id=review.revision_public_id,
        group_lesson_public_id=review.group_lesson_public_id,
        review_version=review.review_version,
        rows=tuple(rows),
    )


def _window(row: Mapping[str, object]) -> LessonWindowRecord:
    return LessonWindowRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        group_lesson_id=int(row["group_lesson_id"]),
        opens_at=_optional_timestamp(row["opens_at"]),
        submission_closes_at=parse_utc_timestamp(str(row["submission_closes_at"])),
        hint_scheduled_at=_optional_timestamp(row["hint_scheduled_at"]),
        solution_scheduled_at=_optional_timestamp(row["solution_scheduled_at"]),
        timezone=str(row["timezone"]),
        source=str(row["source"]),
        version=int(row["version"]),
    )


def _window_audit_json(row: Mapping[str, object]) -> str:
    """Canonical current projection stored in the append-only audit journal."""

    return json.dumps(
        {
            "hintScheduledAt": row["hint_scheduled_at"],
            "opensAt": row["opens_at"],
            "solutionScheduledAt": row["solution_scheduled_at"],
            "submissionClosesAt": row["submission_closes_at"],
            "timezone": row["timezone"],
            "version": int(row["version"]),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _window_schedule_source(
    row: Mapping[str, object],
) -> LessonWindowScheduleSourceRecord:
    mode = ScheduleOverrideMode(str(row["resolution_mode"]))
    value = (
        None
        if mode is ScheduleOverrideMode.DISABLED
        else ScheduleRuleValue(
            day_offset=int(row["resolved_day_offset"]),
            local_time=time.fromisoformat(str(row["resolved_local_time"])),
            timezone=str(row["resolved_timezone"]),
        )
    )
    return LessonWindowScheduleSourceRecord(
        lesson_window_id=int(row["lesson_window_id"]),
        schedule_field=ScheduleField(str(row["schedule_field"])),
        course_schedule_rule_id=int(row["course_schedule_rule_id"]),
        course_rule_version=int(row["course_rule_version"]),
        group_schedule_override_id=(
            None
            if row["group_schedule_override_id"] is None
            else int(row["group_schedule_override_id"])
        ),
        group_override_version=(
            None
            if row["group_override_version"] is None
            else int(row["group_override_version"])
        ),
        resolution_mode=mode,
        resolved_value=value,
    )


def _course_schedule_rule(row: Mapping[str, object]) -> CourseScheduleRuleRecord:
    return CourseScheduleRuleRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        course_id=int(row["course_id"]),
        schedule_field=ScheduleField(str(row["schedule_field"])),
        rule_version=int(row["rule_version"]),
        value=ScheduleRuleValue(
            day_offset=int(row["day_offset"]),
            local_time=time.fromisoformat(str(row["local_time"])),
            timezone=str(row["timezone"]),
        ),
        state=str(row["state"]),
        version=int(row["version"]),
    )


def _group_schedule_override(
    row: Mapping[str, object],
) -> GroupScheduleOverrideRecord:
    mode = ScheduleOverrideMode(str(row["mode"]))
    override = (
        None
        if mode is not ScheduleOverrideMode.OVERRIDE
        else ScheduleRuleValue(
            day_offset=int(row["day_offset"]),
            local_time=time.fromisoformat(str(row["local_time"])),
            timezone=str(row["timezone"]),
        )
    )
    return GroupScheduleOverrideRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        course_id=int(row["course_id"]),
        group_id=str(row["group_id"]),
        schedule_field=ScheduleField(str(row["schedule_field"])),
        override_version=int(row["override_version"]),
        mode=mode,
        value=override,
        based_on_schedule_rule_id=(
            None
            if row["based_on_schedule_rule_id"] is None
            else int(row["based_on_schedule_rule_id"])
        ),
        state=str(row["state"]),
        version=int(row["version"]),
    )


def _group_lesson_content_scope(row: Mapping[str, object]) -> GroupLessonContentScope:
    group_public_id = row["group_public_id"]
    if group_public_id is None:
        raise ContentRepositoryError("group lesson has no public group identity")
    return GroupLessonContentScope(
        group_lesson_id=int(row["group_lesson_id"]),
        group_lesson_public_id=str(row["group_lesson_public_id"]),
        course_id=int(row["course_id"]),
        course_public_id=str(row["course_public_id"]),
        group_id=str(row["group_id"]),
        group_public_id=str(group_public_id),
        status=str(row["group_lesson_status"]),
        business_timezone=str(row["business_timezone"]),
    )


def _publication(row: Mapping[str, object]) -> PublicationRecord:
    return PublicationRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        group_lesson_id=int(row["group_lesson_id"]),
        kind=ContentKind(str(row["kind"])),
        revision_id=int(row["revision_id"]),
        state=PublicationState(str(row["state"])),
        scheduled_at=_optional_timestamp(row["scheduled_at"]),
        published_at=_optional_timestamp(row["published_at"]),
        hidden_at=_optional_timestamp(row["hidden_at"]),
        supersedes_publication_id=(
            None
            if row["supersedes_publication_id"] is None
            else int(row["supersedes_publication_id"])
        ),
        activated_from_schedule_id=(
            None
            if row["activated_from_schedule_id"] is None
            else int(row["activated_from_schedule_id"])
        ),
        version=int(row["version"]),
        terminal_by_user_id=(
            None
            if row["terminal_by_user_id"] is None
            else int(row["terminal_by_user_id"])
        ),
        terminal_at=_optional_timestamp(row["terminal_at"]),
    )


def _student_lesson_material(
    row: Mapping[str, object], prefix: str
) -> StudentLessonMaterialRecord | None:
    revision_public_id = row[f"{prefix}_revision_public_id"]
    if revision_public_id is None:
        return None
    published_at = _optional_timestamp(row[f"{prefix}_published_at"])
    publication_version = row[f"{prefix}_publication_version"]
    if published_at is None or publication_version is None:
        raise ContentRepositoryError("published lesson material is incomplete")
    return StudentLessonMaterialRecord(
        revision_public_id=str(revision_public_id),
        published_at=published_at,
        publication_version=int(publication_version),
    )


def _student_lesson_summary(
    row: Mapping[str, object],
) -> StudentLessonSummaryRecord:
    condition = _student_lesson_material(row, "condition")
    if condition is None:  # pragma: no cover - inner-join invariant
        raise ContentRepositoryError("student lesson has no published condition")
    window = None
    if row["window_public_id"] is not None:
        window = LessonWindowRecord(
            id=int(row["window_id"]),
            public_id=str(row["window_public_id"]),
            group_lesson_id=int(row["group_lesson_id"]),
            opens_at=_optional_timestamp(row["window_opens_at"]),
            submission_closes_at=parse_utc_timestamp(
                str(row["window_submission_closes_at"])
            ),
            hint_scheduled_at=_optional_timestamp(row["window_hint_scheduled_at"]),
            solution_scheduled_at=_optional_timestamp(
                row["window_solution_scheduled_at"]
            ),
            timezone=str(row["window_timezone"]),
            source=str(row["window_source"]),
            version=int(row["window_version"]),
        )
    return StudentLessonSummaryRecord(
        group_lesson_public_id=str(row["group_lesson_public_id"]),
        course_lesson_public_id=str(row["course_lesson_public_id"]),
        course_public_id=str(row["course_public_id"]),
        group_public_id=str(row["group_public_id"]),
        lesson_number=int(row["lesson_number"]),
        title=None if row["lesson_title"] is None else str(row["lesson_title"]),
        cycle_anchor_date=date.fromisoformat(str(row["cycle_anchor_date"])),
        business_timezone=str(row["business_timezone"]),
        version=int(row["group_lesson_version"]),
        window=window,
        condition=condition,
        hint=_student_lesson_material(row, "hint"),
        solution=_student_lesson_material(row, "solution"),
        problem_count=int(row["problem_count"]),
    )


def _student_problem_summary(
    row: Mapping[str, object],
) -> StudentProblemSummaryRecord:
    public_id = row["problem_public_id"]
    if public_id is None:
        raise ContentRepositoryError("published problem has no public identity")
    problem_type = int(row["problem_type"])
    if problem_type not in PROBLEM_TYPE_VALUES:
        raise ContentRepositoryError("published problem type is invalid")

    verdict = None
    queue_checking = row["queue_checking"]
    verdict_id = row["verdict_id"]
    queue_is_newer = queue_checking is not None and (
        verdict_id is None
        or parse_utc_timestamp(str(row["latest_queue_at"]))
        > parse_utc_timestamp(str(row["verdict_at"]))
    )
    if queue_is_newer:
        status = "checking" if int(queue_checking) == 1 else "sent"
    elif verdict_id is not None:
        weight = float(row["verdict_weight"])
        if not 0 <= weight <= 1:
            raise ContentRepositoryError("published problem verdict weight is invalid")
        verdict = StudentProblemVerdictRecord(
            verdict_id=int(verdict_id),
            symbol=str(row["verdict_symbol"]),
            weight=weight,
        )
        if weight >= 0.8:
            status = "accepted"
        elif problem_type == 1:
            status = "rejected"
        else:
            status = "needs-work"
    elif row["has_discussion"] is not None:
        status = "sent"
    else:
        status = "not-started"

    return StudentProblemSummaryRecord(
        problem_public_id=str(public_id),
        config_version=int(row["config_version"]),
        source_ordinal=int(row["source_ordinal"]),
        display_number=str(row["display_number"]),
        title=str(row["title"]),
        problem_type=problem_type,
        answer_type=(None if row["answer_type"] is None else int(row["answer_type"])),
        hint_state=(
            "unavailable" if row["hint_available"] is None else str(row["hint_state"])
        ),
        solution_state=(
            "unavailable"
            if row["solution_available"] is None
            else str(row["solution_state"])
        ),
        status=status,
        verdict=verdict,
    )


def _media_asset(row: Mapping[str, object]) -> MediaAssetRecord:
    return MediaAssetRecord(
        id=int(row["id"]),
        public_id=str(row["public_id"]),
        sha256=str(row["sha256"]),
        storage_namespace=str(row["storage_namespace"]),
        object_key=str(row["object_key"]),
        media_type=str(row["media_type"]),
        byte_size=int(row["byte_size"]),
        conversion_version=str(row["conversion_version"]),
        public_url=(None if row["public_url"] is None else str(row["public_url"])),
        width=None if row["width"] is None else int(row["width"]),
        height=None if row["height"] is None else int(row["height"]),
        source_filename=(
            None if row["source_filename"] is None else str(row["source_filename"])
        ),
    )


_GROUP_LESSON_SCOPE_SELECT = (
    "SELECT group_lesson.id AS group_lesson_id, "
    "group_lesson.public_id AS group_lesson_public_id, "
    "group_lesson.course_id AS course_id, course.public_id AS course_public_id, "
    "group_lesson.group_id AS group_id, group_record.public_id AS group_public_id, "
    "group_lesson.status AS group_lesson_status, "
    "group_lesson.business_timezone AS business_timezone "
    "FROM group_lessons AS group_lesson "
    "JOIN courses AS course ON course.id = group_lesson.course_id "
    "JOIN groups AS group_record "
    "  ON group_record.course_id = group_lesson.course_id "
    " AND group_record.group_id = group_lesson.group_id "
)


_STUDENT_LESSON_SELECT = (
    "SELECT row_number() OVER ("
    "  PARTITION BY course.public_id, group_record.public_id "
    "  ORDER BY course_lesson.lesson_number DESC, group_lesson.id DESC"
    ") AS scope_rank, group_lesson.id AS group_lesson_id, "
    "group_lesson.public_id AS group_lesson_public_id, "
    "course_lesson.public_id AS course_lesson_public_id, "
    "course.public_id AS course_public_id, "
    "group_record.public_id AS group_public_id, "
    "course_lesson.lesson_number, course_lesson.title AS lesson_title, "
    "group_lesson.cycle_anchor_date, group_lesson.business_timezone, "
    "group_lesson.version AS group_lesson_version, "
    "lesson_window.id AS window_id, lesson_window.public_id AS window_public_id, "
    "lesson_window.opens_at AS window_opens_at, "
    "lesson_window.submission_closes_at AS window_submission_closes_at, "
    "lesson_window.hint_scheduled_at AS window_hint_scheduled_at, "
    "lesson_window.solution_scheduled_at AS window_solution_scheduled_at, "
    "lesson_window.timezone AS window_timezone, "
    "lesson_window.source AS window_source, "
    "lesson_window.version AS window_version, "
    "condition_revision.public_id AS condition_revision_public_id, "
    "condition_publication.published_at AS condition_published_at, "
    "condition_publication.version AS condition_publication_version, "
    "hint_revision.public_id AS hint_revision_public_id, "
    "hint_publication.published_at AS hint_published_at, "
    "hint_publication.version AS hint_publication_version, "
    "solution_revision.public_id AS solution_revision_public_id, "
    "solution_publication.published_at AS solution_published_at, "
    "solution_publication.version AS solution_publication_version, "
    "(SELECT count(*) FROM problem_revisions AS problem_revision "
    " WHERE problem_revision.content_revision_id = condition_publication.revision_id) "
    "AS problem_count "
    "FROM group_lessons AS group_lesson "
    "JOIN course_lessons AS course_lesson "
    "  ON course_lesson.id = group_lesson.course_lesson_id "
    "JOIN courses AS course ON course.id = group_lesson.course_id "
    "JOIN groups AS group_record "
    "  ON group_record.course_id = group_lesson.course_id "
    " AND group_record.group_id = group_lesson.group_id "
    "JOIN lesson_publications AS condition_publication "
    "  ON condition_publication.group_lesson_id = group_lesson.id "
    " AND condition_publication.kind = 'condition' "
    " AND condition_publication.state = 'published' "
    " AND EXISTS (SELECT 1 FROM content_derivatives AS condition_derivative "
    "             WHERE condition_derivative.revision_id = condition_publication.revision_id "
    "               AND condition_derivative.kind = 'web_ast' "
    "               AND condition_derivative.invalidated_at IS NULL) "
    "JOIN content_revisions AS condition_revision "
    "  ON condition_revision.id = condition_publication.revision_id "
    " AND condition_revision.status = 'ready' "
    "LEFT JOIN lesson_windows AS lesson_window "
    "  ON lesson_window.group_lesson_id = group_lesson.id "
    "LEFT JOIN lesson_publications AS hint_publication "
    "  ON hint_publication.group_lesson_id = group_lesson.id "
    " AND hint_publication.kind = 'hint' AND hint_publication.state = 'published' "
    " AND EXISTS (SELECT 1 FROM content_derivatives AS hint_derivative "
    "             WHERE hint_derivative.revision_id = hint_publication.revision_id "
    "               AND hint_derivative.kind = 'web_ast' "
    "               AND hint_derivative.invalidated_at IS NULL) "
    "LEFT JOIN content_revisions AS hint_revision "
    "  ON hint_revision.id = hint_publication.revision_id "
    " AND hint_revision.status = 'ready' "
    "LEFT JOIN lesson_publications AS solution_publication "
    "  ON solution_publication.group_lesson_id = group_lesson.id "
    " AND solution_publication.kind = 'solution' "
    " AND solution_publication.state = 'published' "
    " AND EXISTS (SELECT 1 FROM content_derivatives AS solution_derivative "
    "             WHERE solution_derivative.revision_id = solution_publication.revision_id "
    "               AND solution_derivative.kind = 'web_ast' "
    "               AND solution_derivative.invalidated_at IS NULL) "
    "LEFT JOIN content_revisions AS solution_revision "
    "  ON solution_revision.id = solution_publication.revision_id "
    " AND solution_revision.status = 'ready' "
)


_STUDENT_PROBLEM_LIST_SELECT = """
WITH published_scope AS (
    SELECT group_lesson.course_lesson_id,
           group_lesson.course_id,
           group_lesson.id AS group_lesson_id,
           course_lesson.lesson_number,
           group_lesson.public_id AS group_lesson_public_id,
           course.public_id AS course_public_id,
           group_record.public_id AS group_public_id,
           condition_revision.id AS condition_revision_id,
           condition_revision.public_id AS condition_revision_public_id
    FROM group_lessons AS group_lesson
    JOIN course_lessons AS course_lesson
      ON course_lesson.id = group_lesson.course_lesson_id
    JOIN courses AS course ON course.id = group_lesson.course_id
    JOIN groups AS group_record
      ON group_record.course_id = group_lesson.course_id
     AND group_record.group_id = group_lesson.group_id
    JOIN lesson_publications AS condition_publication
      ON condition_publication.group_lesson_id = group_lesson.id
     AND condition_publication.kind = 'condition'
     AND condition_publication.state = 'published'
    JOIN content_revisions AS condition_revision
      ON condition_revision.id = condition_publication.revision_id
     AND condition_revision.status = 'ready'
    WHERE course.public_id = :course_public_id
      AND group_record.public_id = :group_public_id
      AND group_lesson.public_id = :group_lesson_public_id
      AND group_lesson.status = 'active'
      AND EXISTS (
          SELECT 1
          FROM content_derivatives AS derivative
          WHERE derivative.revision_id = condition_revision.id
            AND derivative.kind = 'web_ast'
            AND derivative.invalidated_at IS NULL
      )
),
visible_problem AS (
    SELECT problem_revision.problem_id,
           problem_revision.config_version,
           problem.public_id AS problem_public_id,
           problem.synonyms AS legacy_synonyms,
           problem_revision.display_number,
           problem_revision.title,
           problem_revision.problem_type,
           problem_revision.answer_type,
           problem_revision.source_ordinal,
           problem_revision.source_item,
           published_scope.course_lesson_id,
           published_scope.course_id,
           published_scope.group_lesson_id,
           published_scope.lesson_number
    FROM published_scope
    JOIN problem_revisions AS problem_revision
      ON problem_revision.content_revision_id = published_scope.condition_revision_id
    JOIN content_problem_matches AS problem_match
      ON problem_match.content_revision_id = problem_revision.content_revision_id
     AND problem_match.source_ordinal = problem_revision.source_ordinal
     AND problem_match.source_item = problem_revision.source_item
     AND problem_match.problem_id = problem_revision.problem_id
     AND problem_match.resolved_at IS NOT NULL
     AND problem_match.decision <> 'omit'
    JOIN problems AS problem ON problem.id = problem_revision.problem_id
),
hint_state AS (
    SELECT visible.problem_id,
           1 AS hint_available,
           CASE WHEN reveal.id IS NULL THEN 'available' ELSE 'revealed' END AS hint_state
    FROM visible_problem AS visible
    JOIN lesson_publications AS publication
      ON publication.group_lesson_id = visible.group_lesson_id
     AND publication.kind = 'hint'
     AND publication.state = 'published'
    JOIN content_revisions AS revision
      ON revision.id = publication.revision_id
     AND revision.status = 'ready'
    JOIN content_problem_matches AS problem_match
      ON problem_match.content_revision_id = revision.id
     AND problem_match.problem_id = visible.problem_id
     AND problem_match.resolved_at IS NOT NULL
     AND problem_match.decision <> 'omit'
    JOIN content_derivatives AS derivative
      ON derivative.revision_id = revision.id
     AND derivative.kind = 'web_ast'
     AND derivative.invalidated_at IS NULL
    LEFT JOIN hint_reveals AS reveal
      ON reveal.student_user_id = :student_user_id
     AND reveal.problem_id = visible.problem_id
     AND reveal.publication_id = publication.id
    GROUP BY visible.problem_id, publication.id, reveal.id
),
solution_state AS (
    SELECT visible.problem_id,
           1 AS solution_available,
           CASE WHEN reveal.id IS NULL THEN 'available' ELSE 'revealed' END AS solution_state
    FROM visible_problem AS visible
    JOIN lesson_publications AS publication
      ON publication.group_lesson_id = visible.group_lesson_id
     AND publication.kind = 'solution'
     AND publication.state = 'published'
    JOIN content_revisions AS revision
      ON revision.id = publication.revision_id
     AND revision.status = 'ready'
    JOIN content_problem_matches AS problem_match
      ON problem_match.content_revision_id = revision.id
     AND problem_match.problem_id = visible.problem_id
     AND problem_match.resolved_at IS NOT NULL
     AND problem_match.decision <> 'omit'
    JOIN content_derivatives AS derivative
      ON derivative.revision_id = revision.id
     AND derivative.kind = 'web_ast'
     AND derivative.invalidated_at IS NULL
    LEFT JOIN solution_reveals AS reveal
      ON reveal.student_user_id = :student_user_id
     AND reveal.problem_id = visible.problem_id
     AND reveal.publication_id = publication.id
    GROUP BY visible.problem_id, publication.id, reveal.id
),
logical_member AS (
    SELECT problem_id AS visible_problem_id,
           problem_id AS member_problem_id
    FROM visible_problem
    UNION
    SELECT visible.problem_id,
           peer.problem_id
    FROM visible_problem AS visible
    JOIN problem_synonym_members AS own
      ON own.problem_id = visible.problem_id
     AND own.removed_at IS NULL
    JOIN problem_synonym_groups AS synonym_group
      ON synonym_group.id = own.synonym_group_id
     AND synonym_group.course_lesson_id = visible.course_lesson_id
     AND synonym_group.status = 'active'
    JOIN problem_synonym_members AS peer
      ON peer.synonym_group_id = synonym_group.id
     AND peer.removed_at IS NULL
    UNION
    SELECT visible.problem_id,
           legacy_peer.id
    FROM visible_problem AS visible
    JOIN problems AS legacy_peer
      ON legacy_peer.lesson = visible.lesson_number
     AND instr(
         ';' || visible.legacy_synonyms || ';',
         ';' || cast(legacy_peer.id AS text) || ';'
     ) > 0
    JOIN groups AS legacy_group
      ON legacy_group.group_id = legacy_peer.group_id
     AND legacy_group.course_id = visible.course_id
    WHERE trim(visible.legacy_synonyms) <> ''
      AND NOT EXISTS (
          SELECT 1
          FROM problem_synonym_members AS current_member
          JOIN problem_synonym_groups AS current_group
            ON current_group.id = current_member.synonym_group_id
           AND current_group.status = 'active'
          WHERE current_member.problem_id = visible.problem_id
            AND current_member.removed_at IS NULL
      )
),
queue_state AS (
    SELECT logical_member.visible_problem_id,
           max(CASE WHEN queue.cur_status > 0 THEN 1 ELSE 0 END) AS checking,
           max(queue.ts) AS latest_queue_at
    FROM logical_member
    JOIN written_tasks_queue AS queue
      ON queue.problem_id = logical_member.member_problem_id
     AND queue.student_id = :student_user_id
    GROUP BY logical_member.visible_problem_id
),
ranked_result AS (
    SELECT logical_member.visible_problem_id,
           result.verdict AS verdict_id,
           result.ts AS verdict_at,
           verdict.tick AS verdict_symbol,
           verdict.val AS verdict_weight,
           row_number() OVER (
               PARTITION BY logical_member.visible_problem_id
               ORDER BY result.ts DESC, result.id DESC
           ) AS result_rank
    FROM logical_member
    JOIN results AS result
      ON result.problem_id = logical_member.member_problem_id
     AND result.student_id = :student_user_id
    JOIN verdicts AS verdict ON verdict.id = result.verdict
),
discussion_state AS (
    SELECT logical_member.visible_problem_id,
           1 AS has_discussion
    FROM logical_member
    JOIN written_tasks_discussions AS discussion
      ON discussion.problem_id = logical_member.member_problem_id
     AND discussion.student_id = :student_user_id
    GROUP BY logical_member.visible_problem_id
)
SELECT published_scope.group_lesson_public_id,
       published_scope.course_public_id,
       published_scope.group_public_id,
       published_scope.condition_revision_public_id,
       visible_problem.*,
       queue_state.checking AS queue_checking,
       queue_state.latest_queue_at,
       ranked_result.verdict_id,
       ranked_result.verdict_at,
       ranked_result.verdict_symbol,
       ranked_result.verdict_weight,
       discussion_state.has_discussion,
       hint_state.hint_available,
       hint_state.hint_state,
       solution_state.solution_available,
       solution_state.solution_state
FROM published_scope
LEFT JOIN visible_problem ON true
LEFT JOIN hint_state ON hint_state.problem_id = visible_problem.problem_id
LEFT JOIN solution_state ON solution_state.problem_id = visible_problem.problem_id
LEFT JOIN queue_state
  ON queue_state.visible_problem_id = visible_problem.problem_id
LEFT JOIN ranked_result
  ON ranked_result.visible_problem_id = visible_problem.problem_id
 AND ranked_result.result_rank = 1
LEFT JOIN discussion_state
  ON discussion_state.visible_problem_id = visible_problem.problem_id
ORDER BY visible_problem.source_ordinal,
         visible_problem.source_item,
         visible_problem.problem_id
"""


def _scope_by_group_lesson_id(
    connection: sqlite3.Connection, group_lesson_id: int
) -> GroupLessonContentScope:
    row = connection.execute(
        _GROUP_LESSON_SCOPE_SELECT + "WHERE group_lesson.id = ?",
        (group_lesson_id,),
    ).fetchone()
    if row is None:
        raise ContentNotFound("group lesson does not exist")
    return _group_lesson_content_scope(row)


class PwaContentRepository:
    """Async-facing repository; each operation owns one SQLite connection."""

    def __init__(
        self,
        factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _timestamp(self) -> str:
        return format_utc_timestamp(self._clock())

    async def create_course_lesson(
        self,
        *,
        public_id: str,
        course_id: int,
        lesson_number: int,
        title: str | None,
        actor_user_id: int | None,
    ) -> CourseLessonRecord:
        _require_public_id(public_id)
        if lesson_number < 1:
            raise ContentInvariantError("lesson number must be positive")
        title = _optional_text(title, label="course lesson title")
        timestamp = self._timestamp()

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO course_lessons "
                    "(public_id, course_id, lesson_number, title, "
                    "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        course_id,
                        lesson_number,
                        title,
                        actor_user_id,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="course lesson") from error
            return _course_lesson(row)

        return await self._factory.run_write_async(write)

    async def create_group_lesson(
        self,
        *,
        public_id: str,
        course_lesson_id: int,
        course_id: int,
        group_id: str,
        cycle_anchor_date: date,
        business_timezone: str,
        actor_user_id: int | None,
        status: str = "draft",
    ) -> GroupLessonRecord:
        _require_public_id(public_id)
        group_id = _required_text(group_id, label="group ID")
        if type(cycle_anchor_date) is not date:
            raise ContentInvariantError("cycle anchor date must be a date")
        business_timezone = _require_timezone(
            business_timezone, label="business timezone"
        )
        if status not in {"draft", "active", "archived"}:
            raise ContentInvariantError("group lesson status is invalid")
        timestamp = self._timestamp()

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO group_lessons "
                    "(public_id, course_lesson_id, course_id, group_id, "
                    "cycle_anchor_date, business_timezone, status, "
                    "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        course_lesson_id,
                        course_id,
                        group_id,
                        cycle_anchor_date.isoformat(),
                        business_timezone,
                        status,
                        actor_user_id,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="group lesson") from error
            return _group_lesson(row)

        return await self._factory.run_write_async(write)

    async def get_group_lesson_scope(self, public_id: str) -> GroupLessonContentScope:
        """Resolve attacker-supplied public identity to authoritative scope."""

        _require_public_id(public_id)

        def read(connection):
            row = connection.execute(
                _GROUP_LESSON_SCOPE_SELECT + "WHERE group_lesson.public_id = ?",
                (public_id,),
            ).fetchone()
            if row is None:
                raise ContentNotFound("group lesson does not exist")
            return _group_lesson_content_scope(row)

        return await self._factory.run_read_async(read)

    async def list_student_lessons(
        self,
        *,
        course_public_id: str,
        group_public_id: str,
        before_lesson_number: int | None = None,
        limit: int = 50,
    ) -> tuple[StudentLessonSummaryRecord, ...]:
        """Return one bounded, query-complete Student lesson page.

        The condition publication is an inner join, so drafts, scheduled-only
        conditions, hidden conditions and broken browser derivatives never
        reveal a lesson. All optional material/window state is projected by the
        same SQL statement; callers do not need per-lesson reads.
        """

        _require_public_id(course_public_id)
        _require_public_id(group_public_id)
        if before_lesson_number is not None and before_lesson_number < 1:
            raise ContentInvariantError("lesson cursor must be positive")
        if limit < 1 or limit > 100:
            raise ContentInvariantError("lesson page limit must be between 1 and 100")

        def read(connection):
            where = (
                "WHERE course.public_id = ? AND group_record.public_id = ? "
                "AND group_lesson.status = 'active' "
            )
            parameters: list[object] = [course_public_id, group_public_id]
            if before_lesson_number is not None:
                where += "AND course_lesson.lesson_number < ? "
                parameters.append(before_lesson_number)
            parameters.append(limit)
            rows = connection.execute(
                _STUDENT_LESSON_SELECT
                + where
                + "ORDER BY course_lesson.lesson_number DESC, group_lesson.id DESC "
                + "LIMIT ?",
                parameters,
            ).fetchall()
            return tuple(_student_lesson_summary(row) for row in rows)

        return await self._factory.run_read_async(read)

    async def get_student_home_snapshot(
        self,
        *,
        scopes: Sequence[tuple[str, str]],
    ) -> StudentHomeSnapshot:
        """Return the latest visible lesson for every course enrollment.

        The dynamic scope predicate is built only from placeholders and the
        window rank is applied inside the same SQLite statement. Thus a home
        with several courses remains one bounded repository read instead of an
        application-level query loop.
        """

        if len(scopes) > 100:
            raise ContentInvariantError("student home scope count exceeds limit")
        prepared: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for course_public_id, group_public_id in scopes:
            _require_public_id(course_public_id)
            _require_public_id(group_public_id)
            scope = (course_public_id, group_public_id)
            if scope in seen:
                raise ContentInvariantError("student home scopes are duplicated")
            seen.add(scope)
            prepared.append(scope)
        generated_at = self._clock()
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ContentInvariantError("student home clock must be timezone-aware")
        generated_at = generated_at.astimezone(UTC)
        if not prepared:
            return StudentHomeSnapshot(generated_at=generated_at, lessons=())

        def read(connection):
            predicates = " OR ".join(
                "(course.public_id = ? AND group_record.public_id = ?)"
                for _scope in prepared
            )
            parameters = [value for scope in prepared for value in scope]
            rows = connection.execute(
                "SELECT * FROM ("
                + _STUDENT_LESSON_SELECT
                + "WHERE group_lesson.status = 'active' AND ("
                + predicates
                + ")) AS visible_lessons WHERE scope_rank = 1 "
                + "ORDER BY course_public_id, group_public_id",
                parameters,
            ).fetchall()
            records: list[StudentHomeLessonRecord] = []
            for row in rows:
                lesson = _student_lesson_summary(row)
                window = lesson.window
                phase = resolve_student_lesson_phase(
                    now=generated_at,
                    opens_at=None if window is None else window.opens_at,
                    submission_closes_at=(
                        None if window is None else window.submission_closes_at
                    ),
                    hint_published=lesson.hint is not None,
                    solution_published=lesson.solution is not None,
                )
                records.append(
                    StudentHomeLessonRecord(lesson=lesson, phase=phase.value)
                )
            return tuple(records)

        lessons = await self._factory.run_read_async(read)
        return StudentHomeSnapshot(generated_at=generated_at, lessons=lessons)

    async def get_student_lesson(
        self,
        *,
        course_public_id: str,
        group_public_id: str,
        group_lesson_public_id: str,
    ) -> StudentLessonSummaryRecord:
        """Read one published group lesson inside an explicit allowed scope."""

        _require_public_id(course_public_id)
        _require_public_id(group_public_id)
        _require_public_id(group_lesson_public_id)

        def read(connection):
            row = connection.execute(
                _STUDENT_LESSON_SELECT
                + "WHERE course.public_id = ? AND group_record.public_id = ? "
                + "AND group_lesson.public_id = ? "
                + "AND group_lesson.status = 'active' LIMIT 1",
                (course_public_id, group_public_id, group_lesson_public_id),
            ).fetchone()
            if row is None:
                raise ContentNotFound("published student lesson does not exist")
            return _student_lesson_summary(row)

        return await self._factory.run_read_async(read)

    async def list_student_problems(
        self,
        *,
        student_user_id: int,
        course_public_id: str,
        group_public_id: str,
        group_lesson_public_id: str,
    ) -> StudentProblemListRecord:
        """Read the exact published problem list and one logical work status each.

        Source rows remain tied to their concrete ``problem_id``. Status reads
        may span an explicitly active synonym group; the old semicolon
        projection is a compatibility fallback only until the Phase-11
        synonym rehearsal has materialized current memberships.
        """

        if student_user_id < 1:
            raise ContentInvariantError("student user ID must be positive")
        _require_public_id(course_public_id)
        _require_public_id(group_public_id)
        _require_public_id(group_lesson_public_id)

        def read(connection):
            rows = connection.execute(
                _STUDENT_PROBLEM_LIST_SELECT,
                {
                    "student_user_id": student_user_id,
                    "course_public_id": course_public_id,
                    "group_public_id": group_public_id,
                    "group_lesson_public_id": group_lesson_public_id,
                },
            ).fetchall()
            if not rows:
                raise ContentNotFound("published student problem list does not exist")
            first = rows[0]
            problems = tuple(
                _student_problem_summary(row)
                for row in rows
                if row["problem_id"] is not None
            )
            if len(problems) > 2_000:  # compiler/WebContentDocument invariant
                raise ContentRepositoryError("published problem list exceeds limit")
            return StudentProblemListRecord(
                group_lesson_public_id=str(first["group_lesson_public_id"]),
                course_public_id=str(first["course_public_id"]),
                group_public_id=str(first["group_public_id"]),
                condition_revision_public_id=str(first["condition_revision_public_id"]),
                problems=problems,
            )

        return await self._factory.run_read_async(read)

    async def list_content_upload_targets(
        self, anchor_group_lesson_public_id: str
    ) -> tuple[ContentUploadTargetRecord, ...]:
        """List sibling group lessons without guessing targets from filenames.

        Phase 2 bulk upload spans the explicit group lessons of one
        ``course_lesson``.  It never infers another course, lesson number or
        publication target from a LaTeX filename; see
        ``vmshpwa/dev/development-plan/06-phase-2-content.md``.
        """

        _require_public_id(anchor_group_lesson_public_id)

        def read(connection):
            rows = connection.execute(
                "SELECT course_lesson.public_id AS course_lesson_public_id, "
                "course_lesson.lesson_number AS lesson_number, "
                "course.public_id AS course_public_id, "
                "course.name AS course_name, "
                "group_lesson.public_id AS group_lesson_public_id, "
                "group_record.public_id AS group_public_id, "
                "group_record.public_name AS group_name, "
                "group_record.short_code AS group_short_code, "
                "group_record.color_key AS group_color_key, "
                "group_lesson.status AS group_lesson_status "
                "FROM group_lessons AS anchor "
                "JOIN group_lessons AS group_lesson "
                "  ON group_lesson.course_lesson_id = anchor.course_lesson_id "
                "JOIN course_lessons AS course_lesson "
                "  ON course_lesson.id = group_lesson.course_lesson_id "
                "JOIN courses AS course ON course.id = group_lesson.course_id "
                "JOIN groups AS group_record "
                "  ON group_record.course_id = group_lesson.course_id "
                " AND group_record.group_id = group_lesson.group_id "
                "WHERE anchor.public_id = ? "
                "ORDER BY coalesce(group_record.sort_order, 2147483647), "
                "group_record.public_name COLLATE NOCASE, group_lesson.id",
                (anchor_group_lesson_public_id,),
            ).fetchall()
            if not rows:
                raise ContentNotFound("group lesson does not exist")
            targets = tuple(map(_content_upload_target, rows))
            if any(
                not target.group_public_id
                or not target.group_lesson_public_id
                or not target.course_lesson_public_id
                for target in targets
            ):
                raise ContentRepositoryError(
                    "content upload target identity is invalid"
                )
            return targets

        return await self._factory.run_read_async(read)

    async def create_course_schedule_rule_draft(
        self,
        *,
        public_id: str,
        course_id: int,
        schedule_field: ScheduleField,
        value: ScheduleRuleValue,
        actor_user_id: int | None,
    ) -> CourseScheduleRuleRecord:
        _require_public_id(public_id)
        timestamp = self._timestamp()

        def write(connection):
            latest = connection.execute(
                "SELECT max(rule_version) AS version FROM course_schedule_rules "
                "WHERE course_id = ? AND schedule_field = ?",
                (course_id, schedule_field.value),
            ).fetchone()["version"]
            rule_version = 1 if latest is None else int(latest) + 1
            try:
                row = connection.execute(
                    "INSERT INTO course_schedule_rules "
                    "(public_id, course_id, schedule_field, rule_version, day_offset, "
                    "local_time, timezone, state, created_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        course_id,
                        schedule_field.value,
                        rule_version,
                        value.day_offset,
                        value.local_time_text,
                        value.timezone,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="course schedule draft"
                ) from error
            return _course_schedule_rule(row)

        return await self._factory.run_write_async(write)

    async def preview_course_schedule_rule_change(
        self, *, draft_public_id: str
    ) -> ScheduleImpactPreview:
        _require_public_id(draft_public_id)

        def read(connection):
            draft = connection.execute(
                "SELECT * FROM course_schedule_rules WHERE public_id = ? AND state = 'draft'",
                (draft_public_id,),
            ).fetchone()
            if draft is None:
                raise ContentNotFound("course schedule draft does not exist")
            active = connection.execute(
                "SELECT id FROM course_schedule_rules WHERE course_id = ? "
                "AND schedule_field = ? AND state = 'active'",
                (draft["course_id"], draft["schedule_field"]),
            ).fetchone()
            group_lesson_count = connection.execute(
                "SELECT count(*) AS count FROM group_lessons WHERE course_id = ?",
                (draft["course_id"],),
            ).fetchone()["count"]
            materialized_count = connection.execute(
                "SELECT count(*) AS count FROM lesson_window_schedule_sources AS source "
                "JOIN lesson_windows AS window ON window.id = source.lesson_window_id "
                "JOIN group_lessons AS group_lesson "
                "  ON group_lesson.id = window.group_lesson_id "
                "WHERE group_lesson.course_id = ? AND source.schedule_field = ?",
                (draft["course_id"], draft["schedule_field"]),
            ).fetchone()["count"]
            return ScheduleImpactPreview(
                draft_rule_id=int(draft["id"]),
                active_rule_id=None if active is None else int(active["id"]),
                group_lesson_count=int(group_lesson_count),
                materialized_window_count=int(materialized_count),
            )

        return await self._factory.run_read_async(read)

    async def confirm_course_schedule_rule(
        self,
        *,
        draft_public_id: str,
        expected_version: int,
        actor_user_id: int,
    ) -> CourseScheduleRuleRecord:
        _require_public_id(draft_public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        timestamp = self._timestamp()

        def write(connection):
            draft = connection.execute(
                "SELECT * FROM course_schedule_rules WHERE public_id = ?",
                (draft_public_id,),
            ).fetchone()
            if draft is None:
                raise ContentNotFound("course schedule draft does not exist")
            if draft["state"] != "draft" or int(draft["version"]) != expected_version:
                raise ContentVersionConflict("course schedule draft version changed")
            connection.execute(
                "UPDATE course_schedule_rules SET state = 'superseded', "
                "superseded_at = ?, updated_at = ?, version = version + 1 "
                "WHERE course_id = ? AND schedule_field = ? AND state = 'active'",
                (
                    timestamp,
                    timestamp,
                    draft["course_id"],
                    draft["schedule_field"],
                ),
            )
            row = connection.execute(
                "UPDATE course_schedule_rules SET state = 'active', confirmed_by_user_id = ?, "
                "confirmed_at = ?, updated_at = ?, version = version + 1 "
                "WHERE id = ? AND state = 'draft' AND version = ? RETURNING *",
                (
                    actor_user_id,
                    timestamp,
                    timestamp,
                    draft["id"],
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("course schedule draft version changed")
            return _course_schedule_rule(row)

        return await self._factory.run_write_async(write)

    async def create_group_schedule_override_draft(
        self,
        *,
        public_id: str,
        course_id: int,
        group_id: str,
        schedule_field: ScheduleField,
        mode: ScheduleOverrideMode,
        value: ScheduleRuleValue | None,
        based_on_schedule_rule_id: int,
        actor_user_id: int | None,
    ) -> GroupScheduleOverrideRecord:
        _require_public_id(public_id)
        group_id = _required_text(group_id, label="group ID")
        if (mode is ScheduleOverrideMode.OVERRIDE) != (value is not None):
            raise ContentInvariantError(
                "override mode requires a value; inherit/disabled forbid one"
            )
        if (
            schedule_field is ScheduleField.SUBMISSION_CLOSES_AT
            and mode is ScheduleOverrideMode.DISABLED
        ):
            raise ContentInvariantError("submission close schedule cannot be disabled")
        if based_on_schedule_rule_id < 1:
            raise ContentInvariantError("base schedule rule ID must be positive")
        timestamp = self._timestamp()

        def write(connection):
            latest = connection.execute(
                "SELECT max(override_version) AS version "
                "FROM group_schedule_overrides WHERE course_id = ? AND group_id = ? "
                "AND schedule_field = ?",
                (course_id, group_id, schedule_field.value),
            ).fetchone()["version"]
            override_version = 1 if latest is None else int(latest) + 1
            try:
                row = connection.execute(
                    "INSERT INTO group_schedule_overrides "
                    "(public_id, course_id, group_id, schedule_field, override_version, "
                    "mode, day_offset, local_time, timezone, based_on_schedule_rule_id, "
                    "state, created_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        course_id,
                        group_id,
                        schedule_field.value,
                        override_version,
                        mode.value,
                        None if value is None else value.day_offset,
                        None if value is None else value.local_time_text,
                        None if value is None else value.timezone,
                        based_on_schedule_rule_id,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="group schedule draft"
                ) from error
            return _group_schedule_override(row)

        return await self._factory.run_write_async(write)

    async def confirm_group_schedule_override(
        self,
        *,
        draft_public_id: str,
        expected_version: int,
        actor_user_id: int,
    ) -> GroupScheduleOverrideRecord:
        _require_public_id(draft_public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        timestamp = self._timestamp()

        def write(connection):
            draft = connection.execute(
                "SELECT * FROM group_schedule_overrides WHERE public_id = ?",
                (draft_public_id,),
            ).fetchone()
            if draft is None:
                raise ContentNotFound("group schedule draft does not exist")
            if draft["state"] != "draft" or int(draft["version"]) != expected_version:
                raise ContentVersionConflict("group schedule draft version changed")
            base_rule = connection.execute(
                "SELECT 1 FROM course_schedule_rules WHERE id = ? AND course_id = ? "
                "AND schedule_field = ? AND state = 'active'",
                (
                    draft["based_on_schedule_rule_id"],
                    draft["course_id"],
                    draft["schedule_field"],
                ),
            ).fetchone()
            if base_rule is None:
                raise ContentVersionConflict(
                    "group schedule base rule changed; refresh impact preview"
                )
            connection.execute(
                "UPDATE group_schedule_overrides SET state = 'superseded', "
                "superseded_at = ?, updated_at = ?, version = version + 1 "
                "WHERE course_id = ? AND group_id = ? AND schedule_field = ? "
                "AND state = 'active'",
                (
                    timestamp,
                    timestamp,
                    draft["course_id"],
                    draft["group_id"],
                    draft["schedule_field"],
                ),
            )
            row = connection.execute(
                "UPDATE group_schedule_overrides SET state = 'active', "
                "confirmed_by_user_id = ?, confirmed_at = ?, updated_at = ?, "
                "version = version + 1 WHERE id = ? AND state = 'draft' "
                "AND version = ? RETURNING *",
                (
                    actor_user_id,
                    timestamp,
                    timestamp,
                    draft["id"],
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("group schedule draft version changed")
            return _group_schedule_override(row)

        return await self._factory.run_write_async(write)

    async def create_content_source(
        self,
        *,
        public_id: str,
        group_lesson_id: int,
        kind: ContentKind,
        logical_filename: str,
        source_encoding: str,
        actor_user_id: int | None,
    ) -> ContentSourceRecord:
        _require_public_id(public_id)
        logical_filename = _required_text(logical_filename, label="logical filename")
        source_encoding = _required_text(source_encoding, label="source encoding")
        if source_encoding not in {"utf-8", "cp1251"}:
            raise ContentInvariantError(
                "source encoding must be canonical UTF-8 or CP1251"
            )
        timestamp = self._timestamp()

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO content_sources "
                    "(public_id, group_lesson_id, kind, logical_filename, "
                    "source_encoding, created_by_user_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        group_lesson_id,
                        kind.value,
                        logical_filename,
                        source_encoding,
                        actor_user_id,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="content source") from error
            return _content_source(row)

        return await self._factory.run_write_async(write)

    async def resolve_source_and_append_revision(
        self,
        *,
        source_public_id: str,
        revision_public_id: str,
        group_lesson_id: int,
        kind: ContentKind,
        logical_filename: str,
        payload: SourceRevisionPayload,
        actor_user_id: int | None,
        parser_version: str = "pending-v1",
    ) -> ContentRevisionContext:
        """Atomically resolve/create one material source and append its revision.

        ``BEGIN IMMEDIATE`` serializes first-upload races.  Together with
        ``content_sources_one_active_material_uq`` this guarantees that two
        concurrent filenames cannot create parallel active histories.
        """

        _require_public_id(source_public_id)
        _require_public_id(revision_public_id)
        logical_filename = _required_text(logical_filename, label="logical filename")
        parser_version = _required_text(parser_version, label="parser version")
        if payload.source_encoding not in {"utf-8", "cp1251"}:
            raise ContentInvariantError(
                "source encoding must be canonical UTF-8 or CP1251"
            )
        timestamp = self._timestamp()

        def write(connection):
            # Resolve inside the write transaction: a preceding concurrent
            # creator has committed before our BEGIN IMMEDIATE can succeed.
            source_rows = connection.execute(
                "SELECT * FROM content_sources WHERE group_lesson_id = ? "
                "AND kind = ? AND archived_at IS NULL ORDER BY id",
                (group_lesson_id, kind.value),
            ).fetchall()
            if len(source_rows) > 1:  # pragma: no cover - 0042 invariant
                raise ContentConflict(
                    "material slot has more than one active source lineage"
                )
            try:
                if source_rows:
                    source = _content_source(source_rows[0])
                    # The lesson/material slot is the lineage boundary. The
                    # concrete filename and encoding of this upload remain in
                    # revision provenance, so a corrected local filename must
                    # not fork or rename the stored source identity.
                else:
                    source_row = connection.execute(
                        "INSERT INTO content_sources "
                        "(public_id, group_lesson_id, kind, logical_filename, "
                        "source_encoding, created_by_user_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *",
                        (
                            source_public_id,
                            group_lesson_id,
                            kind.value,
                            logical_filename,
                            payload.source_encoding,
                            actor_user_id,
                            timestamp,
                        ),
                    ).fetchone()
                    source = _content_source(source_row)

                latest = connection.execute(
                    "SELECT id, revision_number FROM content_revisions "
                    "WHERE source_id = ? ORDER BY revision_number DESC LIMIT 1",
                    (source.id,),
                ).fetchone()
                existing_revision = connection.execute(
                    "SELECT * FROM content_revisions "
                    "WHERE source_id = ? AND source_sha256 = ?",
                    (source.id, payload.source_sha256),
                ).fetchone()
                if existing_revision is not None:
                    if str(existing_revision["parser_version"]) != parser_version:
                        existing_revision = connection.execute(
                            "UPDATE content_revisions SET status = 'uploaded', "
                            "parser_version = ?, diagnostics_json = '[]', canonical_json = NULL, "
                            "compile_claim_token = NULL, compile_claimed_at = NULL, "
                            "compile_lease_expires_at = NULL, compile_completed_at = NULL, "
                            "version = version + 1 WHERE id = ? RETURNING *",
                            (parser_version, existing_revision["id"]),
                        ).fetchone()
                    return ContentRevisionContext(
                        revision=_content_revision(existing_revision),
                        source=source,
                        scope=_scope_by_group_lesson_id(connection, group_lesson_id),
                    )
                current_number = 0 if latest is None else int(latest["revision_number"])
                revision_row = connection.execute(
                    "INSERT INTO content_revisions "
                    "(public_id, source_id, revision_number, source_sha256, "
                    "latex_text, parser_version, status, diagnostics_json, "
                    "provenance_json, created_by_user_id, created_at, "
                    "supersedes_revision_id) VALUES "
                    "(?, ?, ?, ?, ?, ?, 'uploaded', '[]', ?, ?, ?, ?) RETURNING *",
                    (
                        revision_public_id,
                        source.id,
                        current_number + 1,
                        payload.source_sha256,
                        payload.latex_text,
                        parser_version,
                        payload.provenance_json(),
                        actor_user_id,
                        timestamp,
                        None if latest is None else int(latest["id"]),
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="content source revision append"
                ) from error
            return ContentRevisionContext(
                revision=_content_revision(revision_row),
                source=source,
                scope=_scope_by_group_lesson_id(connection, group_lesson_id),
            )

        return await self._factory.run_write_async(write)

    async def append_revision(
        self,
        *,
        public_id: str,
        source_id: int,
        payload: SourceRevisionPayload,
        actor_user_id: int | None,
        parser_version: str = "pending-v1",
        expected_previous_revision_number: int | None = None,
    ) -> ContentRevisionRecord:
        _require_public_id(public_id)
        parser_version = _required_text(parser_version, label="parser version")
        timestamp = self._timestamp()

        def write(connection):
            source = connection.execute(
                "SELECT source_encoding FROM content_sources WHERE id = ? ",
                (source_id,),
            ).fetchone()
            if source is None:
                raise ContentNotFound("content source does not exist")
            if str(source["source_encoding"]).casefold() != payload.source_encoding:
                raise ContentConflict("revision encoding does not match content source")
            latest = connection.execute(
                "SELECT id, revision_number FROM content_revisions "
                "WHERE source_id = ? ORDER BY revision_number DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            current_number = 0 if latest is None else int(latest["revision_number"])
            if (
                expected_previous_revision_number is not None
                and expected_previous_revision_number != current_number
            ):
                raise ContentVersionConflict("content source revision changed")
            try:
                row = connection.execute(
                    "INSERT INTO content_revisions "
                    "(public_id, source_id, revision_number, source_sha256, "
                    "latex_text, parser_version, status, diagnostics_json, "
                    "provenance_json, created_by_user_id, created_at, "
                    "supersedes_revision_id) VALUES "
                    "(?, ?, ?, ?, ?, ?, 'uploaded', '[]', ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        source_id,
                        current_number + 1,
                        payload.source_sha256,
                        payload.latex_text,
                        parser_version,
                        payload.provenance_json(),
                        actor_user_id,
                        timestamp,
                        None if latest is None else int(latest["id"]),
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="content revision") from error
            return _content_revision(row)

        return await self._factory.run_write_async(write)

    async def get_revision(self, public_id: str) -> ContentRevisionRecord:
        _require_public_id(public_id)

        def read(connection):
            row = connection.execute(
                "SELECT * FROM content_revisions WHERE public_id = ?", (public_id,)
            ).fetchone()
            if row is None:
                raise ContentNotFound("content revision does not exist")
            return _content_revision(row)

        return await self._factory.run_read_async(read)

    async def get_revision_context(self, public_id: str) -> ContentRevisionContext:
        """Load a revision and derive its course/group scope from SQLite."""

        _require_public_id(public_id)

        def read(connection):
            revision_row = connection.execute(
                "SELECT * FROM content_revisions WHERE public_id = ?", (public_id,)
            ).fetchone()
            if revision_row is None:
                raise ContentNotFound("content revision does not exist")
            source_row = connection.execute(
                "SELECT * FROM content_sources WHERE id = ?",
                (revision_row["source_id"],),
            ).fetchone()
            if source_row is None:  # pragma: no cover - foreign-key invariant
                raise ContentRepositoryError("content revision source is missing")
            return ContentRevisionContext(
                revision=_content_revision(revision_row),
                source=_content_source(source_row),
                scope=_scope_by_group_lesson_id(
                    connection, int(source_row["group_lesson_id"])
                ),
            )

        return await self._factory.run_read_async(read)

    async def claim_revision_compilation(
        self,
        *,
        public_id: str,
        expected_version: int,
        claim_token: str,
        parser_version: str,
    ) -> ContentRevisionRecord:
        """Claim an upload, or reclaim it only after the fixed lease expires."""

        _require_public_id(public_id)
        claim_token = _required_text(claim_token, label="compile claim token")
        if not 16 <= len(claim_token) <= 128:
            raise ContentInvariantError("compile claim token length is invalid")
        parser_version = _required_text(parser_version, label="parser version")
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        now = self._clock()
        claimed_at = format_utc_timestamp(now)
        lease_expires_at = format_utc_timestamp(now + COMPILE_LEASE_DURATION)

        def write(connection):
            current = connection.execute(
                "SELECT * FROM content_revisions WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("content revision does not exist")
            if int(current["version"]) != expected_version:
                raise ContentVersionConflict("content revision version changed")
            status = RevisionStatus(str(current["status"]))
            if status is RevisionStatus.COMPILING:
                stored_expiry = _optional_timestamp(current["compile_lease_expires_at"])
                if stored_expiry is not None and stored_expiry > now:
                    raise ContentConflict("content compilation lease is still active")
            elif status is not RevisionStatus.UPLOADED:
                raise ContentConflict("content revision is terminal")
            row = connection.execute(
                "UPDATE content_revisions SET status = 'compiling', "
                "parser_version = ?, compile_claim_token = ?, "
                "compile_claimed_at = ?, compile_lease_expires_at = ?, "
                "compile_attempt_count = compile_attempt_count + 1, "
                "compile_completed_at = NULL, version = version + 1 "
                "WHERE id = ? AND version = ? RETURNING *",
                (
                    parser_version,
                    claim_token,
                    claimed_at,
                    lease_expires_at,
                    current["id"],
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("content revision version changed")
            return _content_revision(row)

        return await self._factory.run_write_async(write)

    async def abandon_revision_compilation(
        self,
        *,
        public_id: str,
        expected_version: int,
        claim_token: str,
    ) -> ContentRevisionRecord:
        """Expire one owned claim after cooperative request cancellation."""

        _require_public_id(public_id)
        timestamp = self._timestamp()

        def write(connection):
            row = connection.execute(
                "UPDATE content_revisions SET compile_lease_expires_at = ?, "
                "version = version + 1 WHERE public_id = ? AND version = ? "
                "AND status = 'compiling' AND compile_claim_token = ? RETURNING *",
                (timestamp, public_id, expected_version, claim_token),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("compile claim changed")
            return _content_revision(row)

        return await self._factory.run_write_async(write)

    async def fail_revision_compilation(
        self,
        *,
        public_id: str,
        expected_version: int,
        claim_token: str,
        parser_version: str,
        canonical_document: object | None,
        diagnostics: Sequence[object],
    ) -> ContentRevisionRecord:
        """Atomically finish the owned compile claim as terminal invalid."""

        _require_public_id(public_id)
        parser_version = _required_text(parser_version, label="parser version")
        diagnostics_json = _canonical_diagnostics(diagnostics)
        canonical_json = (
            None
            if canonical_document is None
            else _canonical_json_document(
                canonical_document, label="canonical document"
            )
        )
        completed_at = self._timestamp()

        def write(connection):
            current = connection.execute(
                "SELECT * FROM content_revisions WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("content revision does not exist")
            if (
                int(current["version"]) != expected_version
                or current["status"] != RevisionStatus.COMPILING.value
                or current["compile_claim_token"] != claim_token
            ):
                raise ContentVersionConflict("compile claim changed")
            row = connection.execute(
                "UPDATE content_revisions SET status = 'invalid', "
                "parser_version = ?, canonical_json = ?, diagnostics_json = ?, "
                "compile_claim_token = NULL, compile_lease_expires_at = NULL, "
                "compile_completed_at = ?, "
                "version = version + 1 WHERE id = ? AND version = ? RETURNING *",
                (
                    parser_version,
                    canonical_json,
                    diagnostics_json,
                    completed_at,
                    current["id"],
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("compile claim changed")
            return _content_revision(row)

        return await self._factory.run_write_async(write)

    async def transition_revision(
        self,
        *,
        public_id: str,
        expected_version: int,
        target: RevisionStatus,
        parser_version: str,
        canonical_document: object | None = None,
        diagnostics: Sequence[object] = (),
    ) -> ContentRevisionRecord:
        """Persist one optimistic compiler lifecycle transition.

        Appending a newer source revision does not silently supersede an older
        ready revision: that explicit transition is reserved for publication
        or retention workflows so rollback remains possible.
        """

        _require_public_id(public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        parser_version = _required_text(parser_version, label="parser version")
        diagnostics_json = _canonical_diagnostics(diagnostics)
        canonical_json = (
            None
            if canonical_document is None
            else _canonical_json_document(
                canonical_document, label="canonical document"
            )
        )
        if target is RevisionStatus.READY and canonical_json is None:
            raise ContentInvariantError("ready revision requires a canonical document")

        def write(connection):
            current = connection.execute(
                "SELECT * FROM content_revisions WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("content revision does not exist")
            if int(current["version"]) != expected_version:
                raise ContentVersionConflict("content revision version changed")
            current_status = RevisionStatus(str(current["status"]))
            require_revision_transition(current_status, target)
            if target is RevisionStatus.SUPERSEDED:
                parser = str(current["parser_version"])
                canonical = current["canonical_json"]
                stored_diagnostics = str(current["diagnostics_json"])
            else:
                parser = parser_version
                canonical = canonical_json
                stored_diagnostics = diagnostics_json
            try:
                row = connection.execute(
                    "UPDATE content_revisions SET status = ?, parser_version = ?, "
                    "canonical_json = ?, diagnostics_json = ?, version = version + 1 "
                    "WHERE id = ? AND version = ? RETURNING *",
                    (
                        target.value,
                        parser,
                        canonical,
                        stored_diagnostics,
                        current["id"],
                        expected_version,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="content revision transition"
                ) from error
            if row is None:
                raise ContentVersionConflict("content revision version changed")
            return _content_revision(row)

        return await self._factory.run_write_async(write)

    async def create_lesson_window(
        self,
        *,
        public_id: str,
        group_lesson_id: int,
        draft: LessonWindowDraft,
        actor_user_id: int | None,
    ) -> LessonWindowRecord:
        _require_public_id(public_id)
        timestamp = self._timestamp()
        values = self._window_values(draft)

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO lesson_windows "
                    "(public_id, group_lesson_id, opens_at, submission_closes_at, "
                    "hint_scheduled_at, solution_scheduled_at, timezone, source, "
                    "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING *",
                    (
                        public_id,
                        group_lesson_id,
                        *values,
                        actor_user_id,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="lesson window") from error
            return _window(row)

        return await self._factory.run_write_async(write)

    async def create_materialized_lesson_window(
        self,
        *,
        public_id: str,
        group_lesson_id: int,
        actor_user_id: int | None,
    ) -> LessonWindowRecord:
        """Resolve active field rules once and retain immutable provenance.

        Confirming a later course rule or group override never rewrites an
        existing window.  Staff must preview and explicitly materialize a new
        group lesson/window instead.
        """

        _require_public_id(public_id)
        timestamp = self._timestamp()

        def write(connection):
            group_lesson = connection.execute(
                "SELECT * FROM group_lessons WHERE id = ?", (group_lesson_id,)
            ).fetchone()
            if group_lesson is None:
                raise ContentNotFound("group lesson does not exist")

            rule_rows = connection.execute(
                "SELECT * FROM course_schedule_rules WHERE course_id = ? "
                "AND state = 'active'",
                (group_lesson["course_id"],),
            ).fetchall()
            course_rules = {
                record.schedule_field: record
                for record in map(_course_schedule_rule, rule_rows)
            }
            missing = set(ScheduleField) - course_rules.keys()
            if missing:
                labels = ", ".join(sorted(field.value for field in missing))
                raise ContentConflict(f"active course schedule is incomplete: {labels}")

            override_rows = connection.execute(
                "SELECT * FROM group_schedule_overrides WHERE course_id = ? "
                "AND group_id = ? AND state = 'active'",
                (group_lesson["course_id"], group_lesson["group_id"]),
            ).fetchall()
            overrides = {
                record.schedule_field: record
                for record in map(_group_schedule_override, override_rows)
            }
            resolved_rules: dict[ScheduleField, ScheduleRuleValue | None] = {}
            resolutions: dict[
                ScheduleField,
                tuple[
                    CourseScheduleRuleRecord,
                    GroupScheduleOverrideRecord | None,
                    ScheduleOverrideMode,
                    ScheduleRuleValue | None,
                ],
            ] = {}
            for field in ScheduleField:
                course_rule = course_rules[field]
                override = overrides.get(field)
                mode = (
                    ScheduleOverrideMode.INHERIT if override is None else override.mode
                )
                if mode is ScheduleOverrideMode.INHERIT:
                    value = course_rule.value
                elif mode is ScheduleOverrideMode.OVERRIDE:
                    if override is None or override.value is None:
                        raise ContentRepositoryError(
                            "stored schedule override has no explicit value"
                        )
                    value = override.value
                else:
                    value = None
                if field is ScheduleField.SUBMISSION_CLOSES_AT and value is None:
                    raise ContentConflict(
                        "submission close schedule cannot be disabled"
                    )
                resolved_rules[field] = value
                resolutions[field] = (course_rule, override, mode, value)

            draft = materialize_lesson_window(
                cycle_anchor_date=date.fromisoformat(
                    str(group_lesson["cycle_anchor_date"])
                ),
                business_timezone=str(group_lesson["business_timezone"]),
                rules=resolved_rules,
            )
            values = self._window_values(draft)
            try:
                row = connection.execute(
                    "INSERT INTO lesson_windows "
                    "(public_id, group_lesson_id, opens_at, submission_closes_at, "
                    "hint_scheduled_at, solution_scheduled_at, timezone, source, "
                    "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        group_lesson_id,
                        *values,
                        actor_user_id,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
                for field in ScheduleField:
                    course_rule, override, mode, value = resolutions[field]
                    connection.execute(
                        "INSERT INTO lesson_window_schedule_sources "
                        "(lesson_window_id, schedule_field, course_schedule_rule_id, "
                        "course_rule_version, group_schedule_override_id, "
                        "group_override_version, resolution_mode, resolved_day_offset, "
                        "resolved_local_time, resolved_timezone, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            row["id"],
                            field.value,
                            course_rule.id,
                            course_rule.rule_version,
                            None if override is None else override.id,
                            None if override is None else override.override_version,
                            mode.value,
                            None if value is None else value.day_offset,
                            None if value is None else value.local_time_text,
                            None if value is None else value.timezone,
                            timestamp,
                        ),
                    )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="materialized lesson window"
                ) from error
            return _window(row)

        return await self._factory.run_write_async(write)

    async def get_lesson_window_schedule_sources(
        self, *, lesson_window_id: int
    ) -> tuple[LessonWindowScheduleSourceRecord, ...]:
        def read(connection):
            rows = connection.execute(
                "SELECT * FROM lesson_window_schedule_sources "
                "WHERE lesson_window_id = ? ORDER BY schedule_field",
                (lesson_window_id,),
            ).fetchall()
            return tuple(_window_schedule_source(row) for row in rows)

        return await self._factory.run_read_async(read)

    async def update_lesson_window(
        self,
        *,
        public_id: str,
        expected_version: int,
        draft: LessonWindowDraft,
        actor_user_id: int | None,
    ) -> LessonWindowRecord:
        _require_public_id(public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        timestamp = self._timestamp()
        values = self._window_values(draft)

        def write(connection):
            row = connection.execute(
                "UPDATE lesson_windows SET opens_at = ?, submission_closes_at = ?, "
                "hint_scheduled_at = ?, solution_scheduled_at = ?, timezone = ?, "
                "source = ?, updated_by_user_id = ?, "
                "updated_at = ?, version = version + 1 "
                "WHERE public_id = ? AND version = ? RETURNING *",
                (*values, actor_user_id, timestamp, public_id, expected_version),
            ).fetchone()
            if row is not None:
                return _window(row)
            exists = connection.execute(
                "SELECT 1 FROM lesson_windows WHERE public_id = ?", (public_id,)
            ).fetchone()
            if exists is None:
                raise ContentNotFound("lesson window does not exist")
            raise ContentVersionConflict("lesson window version changed")

        return await self._factory.run_write_async(write)

    async def get_lesson_window(
        self, *, group_lesson_id: int
    ) -> LessonWindowRecord | None:
        """Return the authoritative current window for one concrete lesson."""

        def read(connection):
            row = connection.execute(
                "SELECT * FROM lesson_windows WHERE group_lesson_id = ?",
                (group_lesson_id,),
            ).fetchone()
            return None if row is None else _window(row)

        return await self._factory.run_read_async(read)

    async def create_lesson_window_with_audit(
        self,
        *,
        public_id: str,
        audit_public_id: str,
        group_lesson_id: int,
        draft: LessonWindowDraft,
        actor_user_id: int,
        request_id: str,
    ) -> LessonWindowRecord:
        """Create a manually confirmed window and its first audit record."""

        _require_public_id(public_id)
        _require_public_id(audit_public_id)
        request_id = _required_text(request_id, label="request ID")
        timestamp = self._timestamp()
        values = self._window_values(draft)

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO lesson_windows "
                    "(public_id, group_lesson_id, opens_at, submission_closes_at, "
                    "hint_scheduled_at, solution_scheduled_at, timezone, source, "
                    "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        group_lesson_id,
                        *values,
                        actor_user_id,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
                connection.execute(
                    "INSERT INTO lesson_window_changes "
                    "(public_id, lesson_window_id, change_kind, before_json, "
                    "after_json, actor_user_id, request_id, created_at) "
                    "VALUES (?, ?, 'created', NULL, ?, ?, ?, ?)",
                    (
                        audit_public_id,
                        row["id"],
                        _window_audit_json(row),
                        actor_user_id,
                        request_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="lesson window") from error
            return _window(row)

        return await self._factory.run_write_async(write)

    async def update_lesson_window_schedule_with_audit(
        self,
        *,
        public_id: str,
        expected_version: int,
        audit_public_id: str,
        opens_at: datetime | None,
        hint_scheduled_at: datetime | None,
        solution_scheduled_at: datetime | None,
        actor_user_id: int,
        request_id: str,
    ) -> LessonWindowRecord:
        """Edit non-cutoff fields without coupling them to deadline approval."""

        _require_public_id(public_id)
        _require_public_id(audit_public_id)
        request_id = _required_text(request_id, label="request ID")
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        timestamp = self._timestamp()

        def write(connection):
            current = connection.execute(
                "SELECT * FROM lesson_windows WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("lesson window does not exist")
            if int(current["version"]) != expected_version:
                raise ContentVersionConflict("lesson window version changed")
            draft = LessonWindowDraft(
                opens_at=opens_at,
                submission_closes_at=parse_utc_timestamp(
                    str(current["submission_closes_at"])
                ),
                hint_scheduled_at=hint_scheduled_at,
                solution_scheduled_at=solution_scheduled_at,
                timezone=str(current["timezone"]),
                source=WindowSource(str(current["source"])),
            )
            values = self._window_values(draft)
            if (
                values[0] == current["opens_at"]
                and values[2] == current["hint_scheduled_at"]
                and values[3] == current["solution_scheduled_at"]
            ):
                return _window(current)
            row = connection.execute(
                "UPDATE lesson_windows SET opens_at = ?, hint_scheduled_at = ?, "
                "solution_scheduled_at = ?, updated_by_user_id = ?, updated_at = ?, "
                "version = version + 1 WHERE id = ? AND version = ? RETURNING *",
                (
                    values[0],
                    values[2],
                    values[3],
                    actor_user_id,
                    timestamp,
                    current["id"],
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("lesson window version changed")
            try:
                connection.execute(
                    "INSERT INTO lesson_window_changes "
                    "(public_id, lesson_window_id, change_kind, before_json, "
                    "after_json, actor_user_id, request_id, created_at) "
                    "VALUES (?, ?, 'schedule_changed', ?, ?, ?, ?, ?)",
                    (
                        audit_public_id,
                        current["id"],
                        _window_audit_json(current),
                        _window_audit_json(row),
                        actor_user_id,
                        request_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="lesson window schedule audit"
                ) from error
            return _window(row)

        return await self._factory.run_write_async(write)

    async def update_submission_cutoff_with_audit(
        self,
        *,
        public_id: str,
        expected_version: int,
        audit_public_id: str,
        submission_closes_at: datetime,
        actor_user_id: int,
        request_id: str,
    ) -> LessonWindowRecord:
        """Apply the separately confirmed SCHEDULE-01 cutoff mutation."""

        _require_public_id(public_id)
        _require_public_id(audit_public_id)
        request_id = _required_text(request_id, label="request ID")
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        timestamp = self._timestamp()

        def write(connection):
            current = connection.execute(
                "SELECT * FROM lesson_windows WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("lesson window does not exist")
            if int(current["version"]) != expected_version:
                raise ContentVersionConflict("lesson window version changed")
            draft = LessonWindowDraft(
                opens_at=_optional_timestamp(current["opens_at"]),
                submission_closes_at=submission_closes_at,
                hint_scheduled_at=_optional_timestamp(current["hint_scheduled_at"]),
                solution_scheduled_at=_optional_timestamp(
                    current["solution_scheduled_at"]
                ),
                timezone=str(current["timezone"]),
                source=WindowSource(str(current["source"])),
            )
            cutoff = self._window_values(draft)[1]
            if cutoff == current["submission_closes_at"]:
                return _window(current)
            row = connection.execute(
                "UPDATE lesson_windows SET submission_closes_at = ?, "
                "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
                "WHERE id = ? AND version = ? RETURNING *",
                (
                    cutoff,
                    actor_user_id,
                    timestamp,
                    current["id"],
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ContentVersionConflict("lesson window version changed")
            try:
                connection.execute(
                    "INSERT INTO lesson_window_changes "
                    "(public_id, lesson_window_id, change_kind, before_json, "
                    "after_json, actor_user_id, request_id, created_at) "
                    "VALUES (?, ?, 'submission_cutoff_changed', ?, ?, ?, ?, ?)",
                    (
                        audit_public_id,
                        current["id"],
                        _window_audit_json(current),
                        _window_audit_json(row),
                        actor_user_id,
                        request_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="submission cutoff audit"
                ) from error
            return _window(row)

        return await self._factory.run_write_async(write)

    async def get_revision_publication_readiness(
        self, *, revision_id: int
    ) -> RevisionPublicationReadiness:
        """Count resolved structural matches and explicit metadata reviews.

        A successful compiler transition only proves that the LaTeX is
        renderable.  ``content_problem_matches`` and ``problem_revisions`` are
        the separate human-review records mandated by Phase 2; publication is
        fail-closed until their counts cover the canonical problem list.
        """

        def read(connection):
            revision_row = connection.execute(
                "SELECT canonical_json FROM content_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
            if revision_row is None:
                raise ContentNotFound("content revision does not exist")
            raw_document = revision_row["canonical_json"]
            if not isinstance(raw_document, str):
                raise ContentRepositoryError("content revision has no canonical AST")
            try:
                document = json.loads(raw_document)
            except (json.JSONDecodeError, RecursionError) as error:
                raise ContentRepositoryError(
                    "content revision canonical AST is invalid"
                ) from error
            problems = _canonical_problem_records(document)
            match_rows = connection.execute(
                "SELECT source_ordinal, source_item, decision, resolved_at "
                "FROM content_problem_matches WHERE content_revision_id = ?",
                (revision_id,),
            ).fetchall()
            expected_keys = {
                (problem.source_ordinal, problem.source_item) for problem in problems
            }
            resolved_keys = {
                (int(row["source_ordinal"]), str(row["source_item"]))
                for row in match_rows
                if row["resolved_at"] is not None
            }
            counts = connection.execute(
                "SELECT "
                "count(*) FILTER (WHERE match.resolved_at IS NOT NULL) "
                "  AS resolved_match_count, "
                "count(*) FILTER (WHERE match.decision = 'omit' "
                "  AND match.resolved_at IS NOT NULL) AS omitted_problem_count, "
                "count(problem_revision.id) FILTER (WHERE match.decision <> 'omit') "
                "AS reviewed_problem_count "
                "FROM content_problem_matches AS match "
                "LEFT JOIN problem_revisions AS problem_revision "
                "  ON problem_revision.content_revision_id = match.content_revision_id "
                " AND problem_revision.problem_id = match.problem_id "
                " AND problem_revision.source_ordinal = match.source_ordinal "
                " AND problem_revision.source_item = match.source_item "
                "WHERE match.content_revision_id = ?",
                (revision_id,),
            ).fetchone()
            return RevisionPublicationReadiness(
                expected_problem_count=len(problems),
                resolved_match_count=int(counts["resolved_match_count"]),
                reviewed_problem_count=int(counts["reviewed_problem_count"]),
                omitted_problem_count=int(counts["omitted_problem_count"]),
                structure_matches=resolved_keys == expected_keys,
            )

        return await self._factory.run_read_async(read)

    @staticmethod
    def _window_values(draft: LessonWindowDraft) -> tuple[object, ...]:
        return (
            None if draft.opens_at is None else format_utc_timestamp(draft.opens_at),
            format_utc_timestamp(draft.submission_closes_at),
            (
                None
                if draft.hint_scheduled_at is None
                else format_utc_timestamp(draft.hint_scheduled_at)
            ),
            (
                None
                if draft.solution_scheduled_at is None
                else format_utc_timestamp(draft.solution_scheduled_at)
            ),
            draft.timezone,
            draft.source.value,
        )

    async def create_publication(
        self,
        *,
        public_id: str,
        group_lesson_id: int,
        kind: ContentKind,
        revision_id: int,
        state: PublicationState,
        actor_user_id: int | None,
        scheduled_at: datetime | None = None,
        supersedes_publication_id: int | None = None,
    ) -> PublicationRecord:
        _require_public_id(public_id)
        if kind is ContentKind.TEACHER_NOTE:
            raise ContentInvariantError("teacher notes cannot be published to students")
        if state not in {PublicationState.SCHEDULED, PublicationState.PUBLISHED}:
            raise ContentInvariantError(
                "a publication must be created as scheduled or published"
            )
        if actor_user_id is None:
            raise ContentInvariantError("publication actor is required")
        now = self._timestamp()
        scheduled = None if scheduled_at is None else format_utc_timestamp(scheduled_at)
        if state is PublicationState.SCHEDULED and scheduled is None:
            raise ContentInvariantError("scheduled publication requires a timestamp")
        published = now if state is PublicationState.PUBLISHED else None
        hidden = now if state is PublicationState.HIDDEN else None

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO lesson_publications "
                    "(public_id, group_lesson_id, kind, revision_id, state, "
                    "scheduled_at, published_at, hidden_at, created_by_user_id, "
                    "published_by_user_id, supersedes_publication_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        group_lesson_id,
                        kind.value,
                        revision_id,
                        state.value,
                        scheduled,
                        published,
                        hidden,
                        actor_user_id,
                        actor_user_id if published is not None else None,
                        supersedes_publication_id,
                        now,
                        now,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="publication") from error
            return _publication(row)

        return await self._factory.run_write_async(write)

    async def replace_publication(
        self,
        *,
        public_id: str,
        group_lesson_id: int,
        kind: ContentKind,
        revision_id: int,
        state: PublicationState,
        expected_current_public_id: str | None,
        expected_current_version: int | None,
        actor_user_id: int | None,
        scheduled_at: datetime | None = None,
        cancel_scheduled: bool = False,
        expected_scheduled_public_id: str | None = None,
        expected_scheduled_version: int | None = None,
    ) -> PublicationRecord:
        """Atomically supersede the current slot and append its replacement.

        The same operation is used for an explicit rollback: point the new
        publication at an older ready revision while retaining both publication
        rows and their lineage.  An explicit immediate publication may also
        supersede the pending scheduled slot in this same transaction, so an
        older schedule cannot later reactivate unexpectedly.
        """

        _require_public_id(public_id)
        _require_expected_slot(
            expected_current_public_id,
            expected_current_version,
            label="current publication",
        )
        _require_expected_slot(
            expected_scheduled_public_id,
            expected_scheduled_version,
            label="scheduled publication",
        )
        if kind is ContentKind.TEACHER_NOTE:
            raise ContentInvariantError("teacher notes cannot be published to students")
        if actor_user_id is None:
            raise ContentInvariantError("publication actor is required")
        if state not in {PublicationState.SCHEDULED, PublicationState.PUBLISHED}:
            raise ContentInvariantError(
                "publication replacement must be scheduled or published"
            )
        if cancel_scheduled and state is not PublicationState.PUBLISHED:
            raise ContentInvariantError(
                "only an immediate publication can cancel a scheduled slot"
            )
        if state is PublicationState.PUBLISHED and not cancel_scheduled:
            raise ContentInvariantError(
                "an immediate publication must bind and cancel the scheduled slot"
            )
        if not cancel_scheduled and (
            expected_scheduled_public_id is not None
            or expected_scheduled_version is not None
        ):
            # A schedule replacement's primary current slot already is the
            # scheduled slot; require the two wire pairs to agree exactly.
            if (
                state is not PublicationState.SCHEDULED
                or expected_scheduled_public_id != expected_current_public_id
                or expected_scheduled_version != expected_current_version
            ):
                raise ContentInvariantError(
                    "scheduled expectation does not match the affected slot"
                )
        timestamp = self._timestamp()
        scheduled = None if scheduled_at is None else format_utc_timestamp(scheduled_at)
        if state is PublicationState.SCHEDULED and scheduled is None:
            raise ContentInvariantError("scheduled publication requires a timestamp")

        def write(connection):
            current = connection.execute(
                "SELECT * FROM lesson_publications WHERE group_lesson_id = ? "
                "AND kind = ? AND state = ?",
                (group_lesson_id, kind.value, state.value),
            ).fetchone()
            actual_current = (
                (None, None)
                if current is None
                else (str(current["public_id"]), int(current["version"]))
            )
            if actual_current != (
                expected_current_public_id,
                expected_current_version,
            ):
                raise ContentVersionConflict("current publication slot changed")
            scheduled_current = (
                connection.execute(
                    "SELECT * FROM lesson_publications WHERE group_lesson_id = ? "
                    "AND kind = ? AND state = 'scheduled'",
                    (group_lesson_id, kind.value),
                ).fetchone()
                if cancel_scheduled
                else None
            )
            actual_scheduled = (
                (None, None)
                if scheduled_current is None
                else (
                    str(scheduled_current["public_id"]),
                    int(scheduled_current["version"]),
                )
            )
            if cancel_scheduled and actual_scheduled != (
                expected_scheduled_public_id,
                expected_scheduled_version,
            ):
                raise ContentVersionConflict("scheduled publication slot changed")
            try:
                if current is not None:
                    connection.execute(
                        "UPDATE lesson_publications SET state = 'superseded', "
                        "terminal_by_user_id = ?, terminal_at = ?, "
                        "updated_at = ?, version = version + 1 WHERE id = ?",
                        (actor_user_id, timestamp, timestamp, current["id"]),
                    )
                if scheduled_current is not None:
                    connection.execute(
                        "UPDATE lesson_publications SET state = 'superseded', "
                        "terminal_by_user_id = ?, terminal_at = ?, "
                        "updated_at = ?, version = version + 1 WHERE id = ?",
                        (
                            actor_user_id,
                            timestamp,
                            timestamp,
                            scheduled_current["id"],
                        ),
                    )
                row = connection.execute(
                    "INSERT INTO lesson_publications "
                    "(public_id, group_lesson_id, kind, revision_id, state, "
                    "scheduled_at, published_at, created_by_user_id, "
                    "published_by_user_id, supersedes_publication_id, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING *",
                    (
                        public_id,
                        group_lesson_id,
                        kind.value,
                        revision_id,
                        state.value,
                        scheduled,
                        timestamp if state is PublicationState.PUBLISHED else None,
                        actor_user_id,
                        actor_user_id if state is PublicationState.PUBLISHED else None,
                        None if current is None else int(current["id"]),
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="publication replacement"
                ) from error
            return _publication(row)

        return await self._factory.run_write_async(write)

    async def transition_publication(
        self,
        *,
        public_id: str,
        expected_version: int,
        target: PublicationState,
        actor_user_id: int | None,
    ) -> PublicationRecord:
        _require_public_id(public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        if actor_user_id is None:
            raise ContentInvariantError("publication terminal actor is required")
        now = self._timestamp()

        def write(connection):
            current = connection.execute(
                "SELECT * FROM lesson_publications WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("publication does not exist")
            if int(current["version"]) != expected_version:
                raise ContentVersionConflict("publication version changed")
            current_state = PublicationState(str(current["state"]))
            require_publication_transition(current_state, target)
            if (
                current_state is PublicationState.SCHEDULED
                and target is PublicationState.PUBLISHED
            ):
                raise ContentInvariantError(
                    "scheduled publication must use atomic activation"
                )
            try:
                row = connection.execute(
                    "UPDATE lesson_publications SET state = ?, "
                    "hidden_at = CASE WHEN ? = 'hidden' THEN ? ELSE hidden_at END, "
                    "terminal_by_user_id = ?, terminal_at = ?, "
                    "updated_at = ?, version = version + 1 "
                    "WHERE public_id = ? AND version = ? RETURNING *",
                    (
                        target.value,
                        target.value,
                        now,
                        actor_user_id,
                        now,
                        now,
                        public_id,
                        expected_version,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="publication transition"
                ) from error
            if row is None:
                raise ContentVersionConflict("publication version changed")
            return _publication(row)

        return await self._factory.run_write_async(write)

    async def activate_scheduled_publication(
        self,
        *,
        scheduled_public_id: str,
        expected_version: int,
        published_public_id: str,
        actor_user_id: int | None,
    ) -> PublicationRecord:
        """Atomically activate a schedule and preserve published lineage."""

        _require_public_id(scheduled_public_id)
        _require_public_id(published_public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        if actor_user_id is None:
            raise ContentInvariantError("publication activation actor is required")
        timestamp = self._timestamp()

        def write(connection):
            scheduled = connection.execute(
                "SELECT * FROM lesson_publications WHERE public_id = ?",
                (scheduled_public_id,),
            ).fetchone()
            if scheduled is None:
                raise ContentNotFound("scheduled publication does not exist")
            if (
                scheduled["state"] != "scheduled"
                or int(scheduled["version"]) != expected_version
            ):
                raise ContentVersionConflict("scheduled publication version changed")
            scheduled_at = parse_utc_timestamp(str(scheduled["scheduled_at"]))
            if scheduled_at > parse_utc_timestamp(timestamp):
                raise ContentConflict("scheduled publication is not due")
            previous = connection.execute(
                "SELECT * FROM lesson_publications WHERE group_lesson_id = ? "
                "AND kind = ? AND state = 'published'",
                (scheduled["group_lesson_id"], scheduled["kind"]),
            ).fetchone()
            try:
                if previous is not None:
                    connection.execute(
                        "UPDATE lesson_publications SET state = 'superseded', "
                        "terminal_by_user_id = ?, terminal_at = ?, "
                        "updated_at = ?, version = version + 1 WHERE id = ?",
                        (actor_user_id, timestamp, timestamp, previous["id"]),
                    )
                connection.execute(
                    "UPDATE lesson_publications SET state = 'superseded', "
                    "terminal_by_user_id = ?, terminal_at = ?, "
                    "updated_at = ?, version = version + 1 WHERE id = ?",
                    (actor_user_id, timestamp, timestamp, scheduled["id"]),
                )
                row = connection.execute(
                    "INSERT INTO lesson_publications "
                    "(public_id, group_lesson_id, kind, revision_id, state, "
                    "scheduled_at, published_at, created_by_user_id, "
                    "published_by_user_id, supersedes_publication_id, "
                    "activated_from_schedule_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING *",
                    (
                        published_public_id,
                        scheduled["group_lesson_id"],
                        scheduled["kind"],
                        scheduled["revision_id"],
                        scheduled["scheduled_at"],
                        timestamp,
                        actor_user_id,
                        actor_user_id,
                        None if previous is None else int(previous["id"]),
                        int(scheduled["id"]),
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="scheduled publication activation"
                ) from error
            return _publication(row)

        return await self._factory.run_write_async(write)

    async def activate_next_due_publication(
        self,
        *,
        published_public_id: str,
    ) -> PublicationContext | None:
        """Atomically claim and activate the oldest due scheduled publication.

        SQLite's ``BEGIN IMMEDIATE`` write boundary makes the due-row selection,
        both terminal transitions and the new published row one indivisible
        operation.  A second worker therefore observes either the next due row
        or no work; it can never activate the same schedule twice.
        """

        _require_public_id(published_public_id)
        now = self._clock()
        timestamp = format_utc_timestamp(now)

        def write(connection):
            scheduled = connection.execute(
                "SELECT * FROM lesson_publications "
                "WHERE state = 'scheduled' AND scheduled_at <= ? "
                "ORDER BY scheduled_at, id LIMIT 1",
                (timestamp,),
            ).fetchone()
            if scheduled is None:
                return None
            actor_user_id = scheduled["created_by_user_id"]
            if actor_user_id is None:
                raise ContentRepositoryError(
                    "scheduled publication has no activation actor"
                )
            previous = connection.execute(
                "SELECT * FROM lesson_publications WHERE group_lesson_id = ? "
                "AND kind = ? AND state = 'published'",
                (scheduled["group_lesson_id"], scheduled["kind"]),
            ).fetchone()
            try:
                if previous is not None:
                    connection.execute(
                        "UPDATE lesson_publications SET state = 'superseded', "
                        "terminal_by_user_id = ?, terminal_at = ?, "
                        "updated_at = ?, version = version + 1 WHERE id = ?",
                        (actor_user_id, timestamp, timestamp, previous["id"]),
                    )
                connection.execute(
                    "UPDATE lesson_publications SET state = 'superseded', "
                    "terminal_by_user_id = ?, terminal_at = ?, "
                    "updated_at = ?, version = version + 1 WHERE id = ?",
                    (actor_user_id, timestamp, timestamp, scheduled["id"]),
                )
                row = connection.execute(
                    "INSERT INTO lesson_publications "
                    "(public_id, group_lesson_id, kind, revision_id, state, "
                    "scheduled_at, published_at, created_by_user_id, "
                    "published_by_user_id, supersedes_publication_id, "
                    "activated_from_schedule_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING *",
                    (
                        published_public_id,
                        scheduled["group_lesson_id"],
                        scheduled["kind"],
                        scheduled["revision_id"],
                        scheduled["scheduled_at"],
                        timestamp,
                        actor_user_id,
                        actor_user_id,
                        None if previous is None else int(previous["id"]),
                        int(scheduled["id"]),
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="due publication activation"
                ) from error
            publication = _publication(row)
            revision_row = connection.execute(
                "SELECT public_id FROM content_revisions WHERE id = ?",
                (publication.revision_id,),
            ).fetchone()
            if revision_row is None:  # pragma: no cover - foreign-key invariant
                raise ContentRepositoryError("publication revision is missing")
            return PublicationContext(
                publication=publication,
                revision_public_id=str(revision_row["public_id"]),
                scope=_scope_by_group_lesson_id(
                    connection, publication.group_lesson_id
                ),
            )

        return await self._factory.run_write_async(write)

    async def get_publication_context(self, public_id: str) -> PublicationContext:
        """Load one publication with its immutable revision and object scope."""

        _require_public_id(public_id)

        def read(connection):
            publication_row = connection.execute(
                "SELECT * FROM lesson_publications WHERE public_id = ?", (public_id,)
            ).fetchone()
            if publication_row is None:
                raise ContentNotFound("publication does not exist")
            revision_row = connection.execute(
                "SELECT public_id FROM content_revisions WHERE id = ?",
                (publication_row["revision_id"],),
            ).fetchone()
            if revision_row is None:  # pragma: no cover - foreign-key invariant
                raise ContentRepositoryError("publication revision is missing")
            return PublicationContext(
                publication=_publication(publication_row),
                revision_public_id=str(revision_row["public_id"]),
                scope=_scope_by_group_lesson_id(
                    connection, int(publication_row["group_lesson_id"])
                ),
            )

        return await self._factory.run_read_async(read)

    async def get_current_publication(
        self,
        *,
        group_lesson_id: int,
        kind: ContentKind,
        state: PublicationState,
    ) -> PublicationRecord | None:
        """Return the unique current scheduled/published slot, if present."""

        if state not in {PublicationState.SCHEDULED, PublicationState.PUBLISHED}:
            raise ContentInvariantError(
                "current publication state must be scheduled or published"
            )

        def read(connection):
            row = connection.execute(
                "SELECT * FROM lesson_publications WHERE group_lesson_id = ? "
                "AND kind = ? AND state = ?",
                (group_lesson_id, kind.value, state.value),
            ).fetchone()
            return None if row is None else _publication(row)

        return await self._factory.run_read_async(read)

    async def get_published_content(
        self,
        *,
        group_lesson_public_id: str,
        kind: ContentKind,
    ) -> PublishedContentRecord:
        """Read the current typed browser derivative for Student/Family.

        The query deliberately cannot return scheduled/hidden content,
        compiler AST, compatibility HTML or another material kind. See Phase 2
        in ``vmshpwa/dev/development-plan/06-phase-2-content.md``.
        """

        _require_public_id(group_lesson_public_id)
        if kind is ContentKind.TEACHER_NOTE:
            raise ContentInvariantError("teacher notes are not student content")

        def read(connection):
            row = connection.execute(
                "SELECT publication.*, revision.public_id AS revision_public_id, "
                "derivative.content_text AS web_document "
                "FROM group_lessons AS group_lesson "
                "JOIN lesson_publications AS publication "
                "  ON publication.group_lesson_id = group_lesson.id "
                " AND publication.kind = ? AND publication.state = 'published' "
                "JOIN content_revisions AS revision "
                "  ON revision.id = publication.revision_id "
                " AND revision.status = 'ready' "
                "JOIN content_derivatives AS derivative "
                "  ON derivative.revision_id = revision.id "
                " AND derivative.kind = 'web_ast' "
                " AND derivative.invalidated_at IS NULL "
                "WHERE group_lesson.public_id = ? "
                "ORDER BY derivative.created_at DESC, derivative.id DESC LIMIT 1",
                (kind.value, group_lesson_public_id),
            ).fetchone()
            if row is None:
                raise ContentNotFound("published content does not exist")
            raw_document = row["web_document"]
            if not isinstance(raw_document, str) or len(raw_document) > 8_000_000:
                raise ContentRepositoryError("stored web document is invalid")
            try:
                document = json.loads(raw_document)
            except (json.JSONDecodeError, RecursionError) as error:
                raise ContentRepositoryError(
                    "stored web document is invalid"
                ) from error
            revision_public_id = str(row["revision_public_id"])
            if (
                not isinstance(document, dict)
                or document.get("contractVersion") != 1
                or document.get("revisionId") != revision_public_id
                or document.get("materialKind") != kind.value
            ):
                raise ContentRepositoryError("stored web document is invalid")
            return PublishedContentRecord(
                publication=_publication(row),
                revision_public_id=revision_public_id,
                scope=_scope_by_group_lesson_id(
                    connection, int(row["group_lesson_id"])
                ),
                document=document,
            )

        return await self._factory.run_read_async(read)

    async def reveal_student_problem_material(
        self,
        *,
        student_user_id: int,
        group_lesson_public_id: str,
        problem_public_id: str,
        kind: ContentKind,
        request_id: str,
    ) -> StudentProblemRevealRecord:
        """Atomically audit and return one problem's current hint/solution.

        Both the problem and material must belong to the exact currently
        published revisions of one group lesson. The unique reveal row makes a
        retry idempotent; a replaced publication intentionally creates a new
        reveal boundary. See Phase 3 in
        ``vmshpwa/dev/development-plan/07-phase-3-student-reading.md``.
        """

        if student_user_id < 1:
            raise ContentInvariantError("student user ID must be positive")
        _require_public_id(group_lesson_public_id)
        _require_public_id(problem_public_id)
        if kind not in {ContentKind.HINT, ContentKind.SOLUTION}:
            raise ContentInvariantError("only hint or solution can be revealed")
        request_id = _required_text(request_id, label="reveal request ID")
        timestamp = self._timestamp()
        reveal_table = (
            "hint_reveals" if kind is ContentKind.HINT else "solution_reveals"
        )

        def write(connection):
            row = connection.execute(
                "SELECT publication.*, "
                "material_revision.public_id AS revision_public_id, "
                "derivative.content_text AS web_document, "
                "material_problem.source_ordinal AS material_source_ordinal, "
                "problem.id AS selected_problem_id "
                "FROM group_lessons AS group_lesson "
                "JOIN lesson_publications AS condition_publication "
                "  ON condition_publication.group_lesson_id = group_lesson.id "
                " AND condition_publication.kind = 'condition' "
                " AND condition_publication.state = 'published' "
                "JOIN problem_revisions AS condition_problem "
                "  ON condition_problem.content_revision_id = condition_publication.revision_id "
                "JOIN content_problem_matches AS condition_match "
                "  ON condition_match.content_revision_id = condition_problem.content_revision_id "
                " AND condition_match.source_ordinal = condition_problem.source_ordinal "
                " AND condition_match.source_item = condition_problem.source_item "
                " AND condition_match.problem_id = condition_problem.problem_id "
                " AND condition_match.resolved_at IS NOT NULL "
                " AND condition_match.decision <> 'omit' "
                "JOIN problems AS problem ON problem.id = condition_problem.problem_id "
                "JOIN lesson_publications AS publication "
                "  ON publication.group_lesson_id = group_lesson.id "
                " AND publication.kind = ? AND publication.state = 'published' "
                "JOIN content_revisions AS material_revision "
                "  ON material_revision.id = publication.revision_id "
                " AND material_revision.status = 'ready' "
                "JOIN content_problem_matches AS material_problem "
                "  ON material_problem.content_revision_id = material_revision.id "
                " AND material_problem.problem_id = problem.id "
                " AND material_problem.resolved_at IS NOT NULL "
                " AND material_problem.decision <> 'omit' "
                "JOIN content_derivatives AS derivative "
                "  ON derivative.revision_id = material_revision.id "
                " AND derivative.kind = 'web_ast' "
                " AND derivative.invalidated_at IS NULL "
                "WHERE group_lesson.public_id = ? AND problem.public_id = ? "
                "ORDER BY derivative.created_at DESC, derivative.id DESC LIMIT 1",
                (kind.value, group_lesson_public_id, problem_public_id),
            ).fetchone()
            if row is None:
                raise ContentNotFound("published problem material does not exist")

            raw_document = row["web_document"]
            if not isinstance(raw_document, str) or len(raw_document) > 8_000_000:
                raise ContentRepositoryError("stored web document is invalid")
            try:
                document = json.loads(raw_document)
            except (json.JSONDecodeError, RecursionError) as error:
                raise ContentRepositoryError(
                    "stored web document is invalid"
                ) from error
            revision_public_id = str(row["revision_public_id"])
            if (
                not isinstance(document, dict)
                or document.get("contractVersion") != 1
                or document.get("revisionId") != revision_public_id
                or document.get("materialKind") != kind.value
                or not isinstance(document.get("problems"), list)
            ):
                raise ContentRepositoryError("stored web document is invalid")
            source_ordinal = int(row["material_source_ordinal"])
            selected = [
                problem
                for problem in document["problems"]
                if isinstance(problem, dict)
                and problem.get("ordinal") == source_ordinal
            ]
            if len(selected) != 1:
                raise ContentRepositoryError("published problem material is ambiguous")
            selected_document = dict(document)
            selected_document["introduction"] = []
            selected_document["problems"] = selected

            publication = _publication(row)
            cursor = connection.execute(
                f"INSERT INTO {reveal_table} "
                "(student_user_id, problem_id, publication_id, revealed_at, request_id) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(student_user_id, problem_id, publication_id) DO NOTHING",
                (
                    student_user_id,
                    int(row["selected_problem_id"]),
                    publication.id,
                    timestamp,
                    request_id,
                ),
            )
            reveal = connection.execute(
                f"SELECT revealed_at FROM {reveal_table} "
                "WHERE student_user_id = ? AND problem_id = ? AND publication_id = ?",
                (
                    student_user_id,
                    int(row["selected_problem_id"]),
                    publication.id,
                ),
            ).fetchone()
            if reveal is None:  # pragma: no cover - transaction invariant
                raise ContentRepositoryError("problem reveal was not persisted")
            return StudentProblemRevealRecord(
                problem_public_id=problem_public_id,
                source_ordinal=source_ordinal,
                kind=kind,
                revealed_at=parse_utc_timestamp(str(reveal["revealed_at"])),
                first_reveal=cursor.rowcount == 1,
                content=PublishedContentRecord(
                    publication=publication,
                    revision_public_id=revision_public_id,
                    scope=_scope_by_group_lesson_id(
                        connection, int(row["group_lesson_id"])
                    ),
                    document=selected_document,
                ),
            )

        return await self._factory.run_write_async(write)

    async def get_group_lesson_content_history(
        self, *, group_lesson_public_id: str
    ) -> GroupLessonContentHistory:
        """Load revision/publication history for one authorized Staff screen."""

        _require_public_id(group_lesson_public_id)

        def read(connection):
            scope_row = connection.execute(
                _GROUP_LESSON_SCOPE_SELECT + "WHERE group_lesson.public_id = ?",
                (group_lesson_public_id,),
            ).fetchone()
            if scope_row is None:
                raise ContentNotFound("group lesson does not exist")
            scope = _group_lesson_content_scope(scope_row)
            # Active slots must survive the bounded history even when an old
            # revision remains published across many later drafts/schedules.
            # Rank them first for inclusion, then restore chronological order
            # in the outer query. Phase 2 history wire contract.
            revision_rows = connection.execute(
                "SELECT * FROM (SELECT revision.*, source.id AS joined_source_id, "
                "source.public_id AS joined_source_public_id, "
                "source.group_lesson_id AS joined_group_lesson_id, "
                "source.kind AS joined_kind, "
                "source.logical_filename AS joined_logical_filename, "
                "source.source_encoding AS joined_source_encoding, "
                "row_number() OVER (PARTITION BY source.kind ORDER BY "
                "CASE WHEN EXISTS (SELECT 1 FROM lesson_publications AS active "
                "WHERE active.revision_id = revision.id "
                "AND active.state IN ('published', 'scheduled')) THEN 0 ELSE 1 END, "
                "revision.revision_number DESC, revision.id DESC) "
                "AS history_rank "
                "FROM content_sources AS source "
                "JOIN content_revisions AS revision ON revision.source_id = source.id "
                "WHERE source.group_lesson_id = ? "
                "AND source.kind IN ('condition', 'hint', 'solution')) "
                "WHERE history_rank <= ? "
                "ORDER BY joined_kind, revision_number DESC, id DESC",
                (scope.group_lesson_id, CONTENT_HISTORY_ITEMS_PER_KIND_LIMIT),
            ).fetchall()
            revisions = tuple(
                ContentRevisionContext(
                    revision=_content_revision(row),
                    source=ContentSourceRecord(
                        id=int(row["joined_source_id"]),
                        public_id=str(row["joined_source_public_id"]),
                        group_lesson_id=int(row["joined_group_lesson_id"]),
                        kind=ContentKind(str(row["joined_kind"])),
                        logical_filename=str(row["joined_logical_filename"]),
                        source_encoding=str(row["joined_source_encoding"]),
                    ),
                    scope=scope,
                )
                for row in revision_rows
            )
            publication_rows = connection.execute(
                "SELECT * FROM (SELECT publication.*, "
                "revision.public_id AS revision_public_id, "
                "row_number() OVER (PARTITION BY publication.kind ORDER BY "
                "CASE WHEN publication.state IN ('published', 'scheduled') "
                "THEN 0 ELSE 1 END, publication.created_at DESC, publication.id DESC) "
                "AS history_rank "
                "FROM lesson_publications AS publication "
                "JOIN content_revisions AS revision "
                "ON revision.id = publication.revision_id "
                "WHERE publication.group_lesson_id = ? "
                ") WHERE history_rank <= ? "
                "ORDER BY kind, created_at DESC, id DESC",
                (scope.group_lesson_id, CONTENT_HISTORY_ITEMS_PER_KIND_LIMIT),
            ).fetchall()
            publications = tuple(
                PublicationContext(
                    publication=_publication(row),
                    revision_public_id=str(row["revision_public_id"]),
                    scope=scope,
                )
                for row in publication_rows
            )
            return GroupLessonContentHistory(
                scope=scope,
                revisions=revisions,
                publications=publications,
            )

        return await self._factory.run_read_async(read)

    async def register_media_asset(
        self,
        *,
        public_id: str,
        sha256: str,
        storage_namespace: str,
        object_key: str,
        media_type: str,
        byte_size: int,
        actor_user_id: int | None,
        conversion_version: str = "original",
        public_url: str | None = None,
        source_filename: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> MediaAssetRecord:
        _require_public_id(public_id)
        _require_sha256(sha256)
        if storage_namespace not in {
            "content",
            "submission",
            "news",
            "annotation",
            "generated",
        }:
            raise ContentInvariantError("storage namespace is invalid")
        object_key = _require_object_key(object_key)
        public_url = _optional_public_url(public_url)
        media_type = _required_text(media_type, label="media type")
        conversion_version = _required_text(
            conversion_version, label="conversion version"
        )
        if (
            byte_size < 1
            or (width is not None and not 1 <= width <= 20_000)
            or (height is not None and not 1 <= height <= 20_000)
        ):
            raise ContentInvariantError(
                "asset size must be positive and dimensions valid"
            )
        timestamp = self._timestamp()

        def write(connection):
            if storage_namespace in {"content", "generated"}:
                existing = connection.execute(
                    "SELECT * FROM media_assets WHERE storage_namespace = ? "
                    "AND sha256 = ? AND conversion_version = ? AND deleted_at IS NULL",
                    (storage_namespace, sha256, conversion_version),
                ).fetchone()
                if existing is not None:
                    if (
                        int(existing["byte_size"]) != byte_size
                        or str(existing["media_type"]) != media_type
                        or (
                            None
                            if existing["width"] is None
                            else int(existing["width"])
                        )
                        != width
                        or (
                            None
                            if existing["height"] is None
                            else int(existing["height"])
                        )
                        != height
                    ):
                        raise ContentConflict(
                            "deduplicated asset metadata contradicts stored bytes"
                        )
                    return _media_asset(existing)
            try:
                row = connection.execute(
                    "INSERT INTO media_assets "
                    "(public_id, sha256, storage_namespace, object_key, public_url, "
                    "media_type, byte_size, width, height, source_filename, "
                    "conversion_version, created_by_user_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        sha256,
                        storage_namespace,
                        object_key,
                        public_url,
                        media_type,
                        byte_size,
                        width,
                        height,
                        source_filename,
                        conversion_version,
                        actor_user_id,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="media asset") from error
            return _media_asset(row)

        return await self._factory.run_write_async(write)

    async def get_media_asset(self, public_id: str) -> MediaAssetRecord:
        """Resolve one live media row without exposing its internal ID."""

        _require_public_id(public_id)

        def read(connection):
            row = connection.execute(
                "SELECT * FROM media_assets WHERE public_id = ? AND deleted_at IS NULL",
                (public_id,),
            ).fetchone()
            if row is None:
                raise ContentNotFound("media asset does not exist")
            return _media_asset(row)

        return await self._factory.run_read_async(read)

    async def get_media_asset_by_id(self, asset_id: int) -> MediaAssetRecord:
        """Resolve an internal derivative attachment without exposing its ID."""

        if asset_id < 1:
            raise ContentInvariantError("media asset ID must be positive")

        def read(connection):
            row = connection.execute(
                "SELECT * FROM media_assets WHERE id = ? AND deleted_at IS NULL",
                (asset_id,),
            ).fetchone()
            if row is None:
                raise ContentNotFound("media asset does not exist")
            return _media_asset(row)

        return await self._factory.run_read_async(read)

    async def resolve_content_asset_name(
        self, logical_name: str
    ) -> MediaAssetRecord | None:
        """Resolve an immutable global figure alias, including extensionless refs."""

        candidates = figure_lookup_names(logical_name)

        def read(connection):
            for _display_name, normalized_name in candidates:
                row = connection.execute(
                    "SELECT asset.* FROM content_asset_names AS asset_name "
                    "JOIN media_assets AS asset ON asset.id = asset_name.asset_id "
                    "WHERE asset_name.normalized_name = ? "
                    "AND asset.deleted_at IS NULL",
                    (normalized_name,),
                ).fetchone()
                if row is not None:
                    return _media_asset(row)
            return None

        return await self._factory.run_read_async(read)

    async def get_content_asset_name_exact(
        self, logical_name: str
    ) -> MediaAssetRecord | None:
        """Resolve only the named alias, without extensionless fallback."""

        _display_name, normalized_name = normalize_content_asset_name(logical_name)

        def read(connection):
            row = connection.execute(
                "SELECT asset.* FROM content_asset_names AS asset_name "
                "JOIN media_assets AS asset ON asset.id = asset_name.asset_id "
                "WHERE asset_name.normalized_name = ? AND asset.deleted_at IS NULL",
                (normalized_name,),
            ).fetchone()
            return None if row is None else _media_asset(row)

        return await self._factory.run_read_async(read)

    async def bind_content_asset_name(
        self,
        *,
        logical_name: str,
        asset_id: int,
        origin: str,
        actor_user_id: int | None,
    ) -> bool:
        """Bind one global name once; a different asset can never replace it."""

        display_name, normalized_name = normalize_content_asset_name(logical_name)
        if origin not in {"upload", "archive_import", "backfill"}:
            raise ContentInvariantError("content asset name origin is invalid")
        timestamp = self._timestamp()

        def write(connection):
            asset = connection.execute(
                "SELECT storage_namespace FROM media_assets "
                "WHERE id = ? AND deleted_at IS NULL",
                (asset_id,),
            ).fetchone()
            if asset is None:
                raise ContentNotFound("named media asset does not exist")
            if str(asset["storage_namespace"]) != "content":
                raise ContentConflict("named media asset is outside content storage")
            existing = connection.execute(
                "SELECT asset_id FROM content_asset_names WHERE normalized_name = ?",
                (normalized_name,),
            ).fetchone()
            if existing is not None:
                if int(existing["asset_id"]) == asset_id:
                    return False
                raise ContentConflict("content asset name is already bound")
            try:
                connection.execute(
                    "INSERT INTO content_asset_names "
                    "(normalized_name, display_name, asset_id, origin, "
                    "created_by_user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        normalized_name,
                        display_name,
                        asset_id,
                        origin,
                        actor_user_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="content asset name"
                ) from error
            return True

        return await self._factory.run_write_async(write)

    async def get_cached_tikz_asset(
        self,
        *,
        normalized_sha256: str,
        normalization_version: str,
        conversion_version: str,
    ) -> MediaAssetRecord | None:
        _require_sha256(normalized_sha256)
        normalization_version = _required_text(
            normalization_version, label="TikZ normalization version"
        )
        conversion_version = _required_text(
            conversion_version, label="conversion version"
        )

        def read(connection):
            row = connection.execute(
                "SELECT asset.* FROM content_tikz_cache AS cache "
                "JOIN media_assets AS asset ON asset.id = cache.asset_id "
                "WHERE cache.normalized_sha256 = ? "
                "AND cache.normalization_version = ? "
                "AND cache.conversion_version = ? AND asset.deleted_at IS NULL",
                (normalized_sha256, normalization_version, conversion_version),
            ).fetchone()
            return None if row is None else _media_asset(row)

        return await self._factory.run_read_async(read)

    async def cache_tikz_asset(
        self,
        *,
        normalized_sha256: str,
        normalization_version: str,
        conversion_version: str,
        source_sha256: str,
        asset_id: int,
        actor_user_id: int | None,
    ) -> MediaAssetRecord:
        """Publish a TikZ cache entry and return the race-winning asset."""

        _require_sha256(normalized_sha256)
        _require_sha256(source_sha256)
        normalization_version = _required_text(
            normalization_version, label="TikZ normalization version"
        )
        conversion_version = _required_text(
            conversion_version, label="conversion version"
        )
        timestamp = self._timestamp()

        def write(connection):
            asset = connection.execute(
                "SELECT * FROM media_assets WHERE id = ? AND deleted_at IS NULL",
                (asset_id,),
            ).fetchone()
            if asset is None:
                raise ContentNotFound("TikZ media asset does not exist")
            if (
                str(asset["storage_namespace"]) != "content"
                or str(asset["media_type"]) != "image/svg+xml"
            ):
                raise ContentConflict("TikZ cache requires a content SVG")
            try:
                connection.execute(
                    "INSERT INTO content_tikz_cache "
                    "(normalized_sha256, normalization_version, conversion_version, "
                    "asset_id, source_sha256, created_by_user_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                    (
                        normalized_sha256,
                        normalization_version,
                        conversion_version,
                        asset_id,
                        source_sha256,
                        actor_user_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="TikZ cache") from error
            winner = connection.execute(
                "SELECT asset.* FROM content_tikz_cache AS cache "
                "JOIN media_assets AS asset ON asset.id = cache.asset_id "
                "WHERE cache.normalized_sha256 = ? "
                "AND cache.normalization_version = ? "
                "AND cache.conversion_version = ? AND asset.deleted_at IS NULL",
                (normalized_sha256, normalization_version, conversion_version),
            ).fetchone()
            if winner is None:  # pragma: no cover - same transaction invariant
                raise ContentRepositoryError("TikZ cache insert did not converge")
            return _media_asset(winner)

        return await self._factory.run_write_async(write)

    async def list_revision_assets(
        self, *, revision_id: int
    ) -> tuple[ContentRevisionAssetRecord, ...]:
        """Return immutable live attachments in deterministic source order."""

        def read(connection):
            revision = connection.execute(
                "SELECT 1 FROM content_revisions WHERE id = ?", (revision_id,)
            ).fetchone()
            if revision is None:
                raise ContentNotFound("content revision does not exist")
            rows = connection.execute(
                "SELECT asset_link.revision_id, asset_link.logical_name, "
                "asset_link.role, asset_link.ordinal, asset_link.alt_text, asset.* "
                "FROM content_revision_assets AS asset_link "
                "JOIN media_assets AS asset ON asset.id = asset_link.asset_id "
                "WHERE asset_link.revision_id = ? AND asset.deleted_at IS NULL "
                "ORDER BY asset_link.ordinal, asset_link.logical_name, asset_link.role",
                (revision_id,),
            ).fetchall()
            return tuple(
                ContentRevisionAssetRecord(
                    revision_id=int(row["revision_id"]),
                    logical_name=str(row["logical_name"]),
                    role=str(row["role"]),
                    ordinal=int(row["ordinal"]),
                    alt_text=(
                        None if row["alt_text"] is None else str(row["alt_text"])
                    ),
                    asset=_media_asset(row),
                )
                for row in rows
            )

        return await self._factory.run_read_async(read)

    async def attach_asset_to_uploaded_revision(
        self,
        *,
        revision_id: int,
        expected_revision_version: int,
        asset_id: int,
        logical_name: str,
        role: str,
        ordinal: int = 0,
        alt_text: str | None = None,
    ) -> tuple[int, bool]:
        """Attach once under an optimistic revision version.

        The exact same attachment is an idempotent no-op even when a client
        retries with the pre-insert ETag after losing the first HTTP response.
        A different asset under the same logical revision key cannot replace
        immutable provenance; staff uploads a new source revision instead.
        """

        logical_name = _required_text(logical_name, label="asset logical name")
        if role not in {"figure", "tikz"}:
            raise ContentInvariantError("upload attachment role is invalid")
        if ordinal < 0:
            raise ContentInvariantError("asset ordinal must be non-negative")
        if expected_revision_version < 1:
            raise ContentInvariantError("expected revision version must be positive")
        timestamp = self._timestamp()

        def write(connection):
            revision = connection.execute(
                "SELECT status, version FROM content_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
            if revision is None:
                raise ContentNotFound("content revision does not exist")
            existing = connection.execute(
                "SELECT asset_id, ordinal, alt_text FROM content_revision_assets "
                "WHERE revision_id = ? AND logical_name = ? AND role = ?",
                (revision_id, logical_name, role),
            ).fetchone()
            if existing is not None:
                if (
                    int(existing["asset_id"]) == asset_id
                    and int(existing["ordinal"]) == ordinal
                    and existing["alt_text"] == alt_text
                ):
                    return int(revision["version"]), False
                raise ContentConflict("revision logical asset is immutable")
            if int(revision["version"]) != expected_revision_version:
                raise ContentVersionConflict("content revision version changed")
            if RevisionStatus(str(revision["status"])) is not RevisionStatus.UPLOADED:
                raise ContentConflict("assets attach only to uploaded revisions")
            asset = connection.execute(
                "SELECT 1 FROM media_assets WHERE id = ? AND deleted_at IS NULL",
                (asset_id,),
            ).fetchone()
            if asset is None:
                raise ContentNotFound("revision media asset does not exist")
            try:
                connection.execute(
                    "INSERT INTO content_revision_assets "
                    "(revision_id, asset_id, logical_name, role, ordinal, alt_text, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        revision_id,
                        asset_id,
                        logical_name,
                        role,
                        ordinal,
                        alt_text,
                        timestamp,
                    ),
                )
                updated = connection.execute(
                    "UPDATE content_revisions SET version = version + 1 "
                    "WHERE id = ? AND version = ? AND status = 'uploaded' "
                    "RETURNING version",
                    (revision_id, expected_revision_version),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="revision asset") from error
            if updated is None:  # pragma: no cover - same write transaction
                raise ContentVersionConflict("content revision version changed")
            return int(updated["version"]), True

        return await self._factory.run_write_async(write)

    async def attach_asset(
        self,
        *,
        revision_id: int,
        asset_id: int,
        logical_name: str,
        role: str,
        ordinal: int = 0,
        alt_text: str | None = None,
    ) -> None:
        logical_name = _required_text(logical_name, label="asset logical name")
        if role not in {"source", "figure", "tikz", "pdf", "preview"}:
            raise ContentInvariantError("content asset role is invalid")
        if ordinal < 0:
            raise ContentInvariantError("asset ordinal must be non-negative")
        timestamp = self._timestamp()

        def write(connection):
            asset = connection.execute(
                "SELECT 1 FROM media_assets WHERE id = ? AND deleted_at IS NULL",
                (asset_id,),
            ).fetchone()
            if asset is None:
                raise ContentNotFound("revision media asset does not exist")
            try:
                connection.execute(
                    "INSERT INTO content_revision_assets "
                    "(revision_id, asset_id, logical_name, role, ordinal, alt_text, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        revision_id,
                        asset_id,
                        logical_name,
                        role,
                        ordinal,
                        alt_text,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="revision asset") from error

        await self._factory.run_write_async(write)

    async def add_derivative(
        self,
        *,
        revision_id: int,
        kind: str,
        renderer_version: str,
        provenance: Mapping[str, object],
        content_text: str | None = None,
        asset_id: int | None = None,
        sha256: str | None = None,
    ) -> ContentDerivativeRecord:
        if kind not in {"web_ast", "web_html", "telegram_html", "pdf", "thumbnail"}:
            raise ContentInvariantError("derivative kind is invalid")
        renderer_version = _required_text(renderer_version, label="renderer version")
        if (content_text is None) == (asset_id is None):
            raise ContentInvariantError(
                "derivative must contain exactly one of text or asset"
            )
        if content_text is not None:
            derived_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
            if sha256 is not None and sha256 != derived_hash:
                raise ContentInvariantError("derivative hash does not match text")
        else:
            if sha256 is None:
                raise ContentInvariantError("asset derivative requires SHA-256")
            derived_hash = _require_sha256(sha256)
        provenance_json = _canonical_json_object(provenance, label="provenance")
        timestamp = self._timestamp()

        def write(connection):
            if asset_id is not None:
                asset = connection.execute(
                    "SELECT sha256 FROM media_assets WHERE id = ? AND deleted_at IS NULL",
                    (asset_id,),
                ).fetchone()
                if asset is None:
                    raise ContentNotFound("derivative media asset does not exist")
                if str(asset["sha256"]) != derived_hash:
                    raise ContentConflict("derivative hash does not match media asset")
            try:
                row = connection.execute(
                    "INSERT INTO content_derivatives "
                    "(revision_id, kind, renderer_version, content_text, asset_id, "
                    "sha256, diagnostics_json, provenance_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?) RETURNING *",
                    (
                        revision_id,
                        kind,
                        renderer_version,
                        content_text,
                        asset_id,
                        derived_hash,
                        provenance_json,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="content derivative"
                ) from error
            return ContentDerivativeRecord(
                id=int(row["id"]),
                revision_id=int(row["revision_id"]),
                kind=str(row["kind"]),
                renderer_version=str(row["renderer_version"]),
                sha256=str(row["sha256"]),
                content_text=(
                    None if row["content_text"] is None else str(row["content_text"])
                ),
                asset_id=None if row["asset_id"] is None else int(row["asset_id"]),
            )

        return await self._factory.run_write_async(write)

    async def complete_revision_compilation(
        self,
        *,
        public_id: str,
        expected_version: int,
        claim_token: str,
        parser_version: str,
        canonical_document: object,
        diagnostics: Sequence[object],
        derivatives: Sequence[TextDerivativeDraft],
    ) -> ContentRevisionRecord:
        """Atomically persist the complete browser/compatibility derivative set.

        A ready revision must never become visible with only part of the three
        text derivatives.  All inserts and the ``compiling -> ready`` transition
        therefore share one SQLite ``BEGIN IMMEDIATE`` transaction.
        """

        _require_public_id(public_id)
        if expected_version < 1:
            raise ContentInvariantError("expected version must be positive")
        parser_version = _required_text(parser_version, label="parser version")
        claim_token = _required_text(claim_token, label="compile claim token")
        canonical_json = _canonical_json_document(
            canonical_document, label="canonical document"
        )
        diagnostics_json = _canonical_diagnostics(diagnostics)
        required_kinds = {"web_ast", "web_html", "telegram_html"}
        if (
            len(derivatives) != len(required_kinds)
            or {derivative.kind for derivative in derivatives} != required_kinds
        ):
            raise ContentInvariantError(
                "ready compilation requires exactly web_ast, web_html and telegram_html"
            )

        prepared: list[tuple[str, str, str, str, str]] = []
        for derivative in derivatives:
            renderer_version = _required_text(
                derivative.renderer_version, label="renderer version"
            )
            if not isinstance(derivative.content_text, str):
                raise ContentInvariantError("text derivative must contain text")
            provenance_json = _canonical_json_object(
                derivative.provenance, label="provenance"
            )
            derived_hash = hashlib.sha256(
                derivative.content_text.encode("utf-8")
            ).hexdigest()
            prepared.append(
                (
                    derivative.kind,
                    renderer_version,
                    derivative.content_text,
                    derived_hash,
                    provenance_json,
                )
            )
        timestamp = self._timestamp()

        def write(connection):
            current = connection.execute(
                "SELECT * FROM content_revisions WHERE public_id = ?", (public_id,)
            ).fetchone()
            if current is None:
                raise ContentNotFound("content revision does not exist")
            if int(current["version"]) != expected_version:
                raise ContentVersionConflict("content revision version changed")
            if current["compile_claim_token"] != claim_token:
                raise ContentVersionConflict("compile claim changed")
            current_status = RevisionStatus(str(current["status"]))
            require_revision_transition(current_status, RevisionStatus.READY)
            try:
                for kind, renderer, text, derived_hash, provenance_json in prepared:
                    connection.execute(
                        "INSERT INTO content_derivatives "
                        "(revision_id, kind, renderer_version, content_text, asset_id, "
                        "sha256, diagnostics_json, provenance_json, created_at) "
                        "VALUES (?, ?, ?, ?, NULL, ?, '[]', ?, ?)",
                        (
                            current["id"],
                            kind,
                            renderer,
                            text,
                            derived_hash,
                            provenance_json,
                            timestamp,
                        ),
                    )
                row = connection.execute(
                    "UPDATE content_revisions SET status = 'ready', "
                    "parser_version = ?, canonical_json = ?, diagnostics_json = ?, "
                    "compile_claim_token = NULL, compile_lease_expires_at = NULL, "
                    "compile_completed_at = ?, "
                    "version = version + 1 WHERE id = ? AND version = ? RETURNING *",
                    (
                        parser_version,
                        canonical_json,
                        diagnostics_json,
                        timestamp,
                        current["id"],
                        expected_version,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="compiled derivative set"
                ) from error
            if row is None:
                raise ContentVersionConflict("content revision version changed")
            return _content_revision(row)

        return await self._factory.run_write_async(write)

    async def get_active_derivative(
        self, *, revision_id: int, kind: str
    ) -> ContentDerivativeRecord:
        """Return the newest non-invalidated derivative of one exact kind."""

        if kind not in {"web_ast", "web_html", "telegram_html", "pdf", "thumbnail"}:
            raise ContentInvariantError("derivative kind is invalid")

        def read(connection):
            row = connection.execute(
                "SELECT * FROM content_derivatives WHERE revision_id = ? "
                "AND kind = ? AND invalidated_at IS NULL "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (revision_id, kind),
            ).fetchone()
            if row is None:
                raise ContentNotFound("content derivative does not exist")
            return ContentDerivativeRecord(
                id=int(row["id"]),
                revision_id=int(row["revision_id"]),
                kind=str(row["kind"]),
                renderer_version=str(row["renderer_version"]),
                sha256=str(row["sha256"]),
                content_text=(
                    None if row["content_text"] is None else str(row["content_text"])
                ),
                asset_id=None if row["asset_id"] is None else int(row["asset_id"]),
            )

        return await self._factory.run_read_async(read)

    async def invalidate_derivative(self, *, derivative_id: int) -> None:
        timestamp = self._timestamp()

        def write(connection):
            try:
                cursor = connection.execute(
                    "UPDATE content_derivatives SET invalidated_at = ? "
                    "WHERE id = ? AND invalidated_at IS NULL",
                    (timestamp, derivative_id),
                )
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(
                    error, action="derivative invalidation"
                ) from error
            if cursor.rowcount:
                return
            exists = connection.execute(
                "SELECT 1 FROM content_derivatives WHERE id = ?", (derivative_id,)
            ).fetchone()
            if exists is None:
                raise ContentNotFound("content derivative does not exist")
            raise ContentConflict("content derivative is already invalidated")

        await self._factory.run_write_async(write)

    async def get_problem_match_review(
        self, *, revision_public_id: str
    ) -> ProblemMatchReview:
        """Return canonical source identities and same-lesson legacy candidates."""

        _require_public_id(revision_public_id)
        return await self._factory.run_read_async(
            lambda connection: _problem_match_review_from_connection(
                connection, revision_public_id
            )
        )

    async def resolve_problem_matches(
        self,
        *,
        revision_public_id: str,
        expected_review_version: int,
        drafts: Sequence[ProblemMatchDraft],
        actor_user_id: int | None,
    ) -> ProblemMatchReview:
        """Replace the current positional reconciliation batch."""

        _require_public_id(revision_public_id)
        if expected_review_version < 1:
            raise ContentInvariantError("expected review version must be positive")
        prepared = tuple(drafts)
        if len(prepared) > 2_000:
            raise ContentInvariantError("problem match batch is too large")
        timestamp = self._timestamp()

        def write(connection):
            scope = _review_scope_row(connection, revision_public_id)
            revision_id = int(scope["revision_id"])
            try:
                document = json.loads(str(scope["canonical_json"]))
            except (json.JSONDecodeError, RecursionError) as error:
                raise ContentRepositoryError(
                    "content revision canonical AST is invalid"
                ) from error
            sources = _canonical_problem_records(document)
            source_by_identity = {
                (source.source_ordinal, source.source_item): source
                for source in sources
            }
            draft_by_identity = {
                (draft.source_ordinal, draft.source_item): draft for draft in prepared
            }
            if len(draft_by_identity) != len(prepared):
                raise ContentInvariantError("problem match identities are duplicated")
            if set(draft_by_identity) != set(source_by_identity):
                raise ContentInvariantError(
                    "problem match batch must cover the canonical problem list"
                )
            explicit_problem_ids = [
                draft.problem_id for draft in prepared if draft.problem_id is not None
            ]
            if len(set(explicit_problem_ids)) != len(explicit_problem_ids):
                raise ContentInvariantError(
                    "one legacy problem cannot match multiple source problems"
                )

            existing = connection.execute(
                "SELECT source_ordinal, source_item, problem_id, decision "
                "FROM content_problem_matches WHERE content_revision_id = ? "
                "ORDER BY source_ordinal, source_item",
                (revision_id,),
            ).fetchall()
            existing_by_identity = {
                (int(row["source_ordinal"]), str(row["source_item"])): row
                for row in existing
            }
            identical = set(existing_by_identity) == set(draft_by_identity)
            if identical:
                for identity, draft in draft_by_identity.items():
                    row = existing_by_identity[identity]
                    stored_decision = ProblemMatchDecision(str(row["decision"]))
                    stored_problem_id = (
                        None if row["problem_id"] is None else int(row["problem_id"])
                    )
                    if stored_decision is not draft.decision:
                        identical = False
                        break
                    if draft.decision is ProblemMatchDecision.INSERT_NEW:
                        if stored_problem_id is None:
                            identical = False
                            break
                    elif stored_problem_id != draft.problem_id:
                        identical = False
                        break
            if identical:
                return _problem_match_review_from_connection(connection, revision_public_id)
            if _review_version(connection, revision_id) != expected_review_version:
                raise ContentVersionConflict("problem review version changed")

            changed = False
            for identity in sorted(draft_by_identity):
                draft = draft_by_identity[identity]
                source = source_by_identity[identity]
                previous = existing_by_identity.get(identity)
                problem_id = draft.problem_id
                if draft.decision is ProblemMatchDecision.INSERT_NEW:
                    if (
                        previous is not None
                        and str(previous["decision"])
                        == ProblemMatchDecision.INSERT_NEW.value
                        and previous["problem_id"] is not None
                    ):
                        problem_id = int(previous["problem_id"])
                    else:
                        # The compiler's fallback source identity is the ordinal;
                        # legacy ``item`` uses an empty suffix for that ordinary
                        # case. An explicit TeX name remains available as item.
                        legacy_item = (
                            ""
                            if source.source_item == str(source.source_ordinal)
                            else source.source_item
                        )
                        try:
                            created = connection.execute(
                                "INSERT INTO problems "
                                "(group_id, lesson, prob, item, title, prob_text, "
                                "prob_type, ans_type, ans_validation, validation_error, "
                                "cor_ans, cor_ans_checker, wrong_ans, congrat, synonyms) "
                                "VALUES (?, ?, ?, ?, ?, '', ?, NULL, NULL, NULL, NULL, "
                                "NULL, NULL, NULL, '') RETURNING id",
                                (
                                    scope["group_id"],
                                    scope["lesson_number"],
                                    source.source_ordinal,
                                    legacy_item,
                                    source.source_title
                                    or f"Задача {source.display_number}",
                                    source.problem_type,
                                ),
                            ).fetchone()
                        except sqlite3.IntegrityError as error:
                            raise ContentConflict(
                                "problem position already exists; choose an explicit match"
                            ) from error
                        problem_id = int(created["id"])
                elif draft.decision is not ProblemMatchDecision.OMIT:
                    candidate = connection.execute(
                        "SELECT id, prob FROM problems WHERE id = ? "
                        "AND group_id = ? AND lesson = ?",
                        (
                            draft.problem_id,
                            scope["group_id"],
                            scope["lesson_number"],
                        ),
                    ).fetchone()
                    if candidate is None:
                        raise ContentInvariantError(
                            "matched problem is outside the group lesson"
                        )
                    if (
                        draft.decision is ProblemMatchDecision.AUTO_POSITION
                        and int(candidate["prob"]) != source.source_ordinal
                    ):
                        raise ContentInvariantError(
                            "automatic match must preserve source position"
                        )
                if previous is None:
                    try:
                        connection.execute(
                            "INSERT INTO content_problem_matches "
                            "(content_revision_id, source_ordinal, source_item, problem_id, "
                            "decision, resolved_by_user_id, resolved_at, diagnostics_json, "
                            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?)",
                            (
                                revision_id,
                                source.source_ordinal,
                                source.source_item,
                                problem_id,
                                draft.decision.value,
                                actor_user_id,
                                timestamp,
                                timestamp,
                            ),
                        )
                    except sqlite3.IntegrityError as error:
                        raise _translate_integrity(
                            error, action="problem match review"
                        ) from error
                    changed = True
                elif (
                    previous["problem_id"] != problem_id
                    or str(previous["decision"]) != draft.decision.value
                ):
                    connection.execute(
                        "UPDATE content_problem_matches SET problem_id = ?, decision = ?, "
                        "resolved_by_user_id = ?, resolved_at = ? "
                        "WHERE content_revision_id = ? AND source_ordinal = ? "
                        "AND source_item = ?",
                        (
                            problem_id,
                            draft.decision.value,
                            actor_user_id,
                            timestamp,
                            revision_id,
                            source.source_ordinal,
                            source.source_item,
                        ),
                    )
                    changed = True
            if changed and existing:
                _advance_review_version(
                    connection,
                    revision_id=revision_id,
                    expected_version=expected_review_version,
                    timestamp=timestamp,
                    actor_user_id=actor_user_id,
                )
            return _problem_match_review_from_connection(connection, revision_public_id)

        return await self._factory.run_write_async(write)

    async def get_problem_metadata_grid(
        self, *, revision_public_id: str
    ) -> ProblemMetadataGrid:
        _require_public_id(revision_public_id)
        return await self._factory.run_read_async(
            lambda connection: _problem_metadata_grid_from_connection(
                connection, revision_public_id
            )
        )

    async def save_problem_metadata_grid(
        self,
        *,
        revision_public_id: str,
        expected_review_version: int,
        drafts: Sequence[ProblemMetadataDraft],
        actor_user_id: int | None,
    ) -> ProblemMetadataGrid:
        """Confirm a complete grid and update the legacy current projection."""

        _require_public_id(revision_public_id)
        if expected_review_version < 1:
            raise ContentInvariantError("expected review version must be positive")
        prepared = tuple(drafts)
        if len(prepared) > 2_000:
            raise ContentInvariantError("problem metadata batch is too large")
        timestamp = self._timestamp()

        def write(connection):
            current_grid = _problem_metadata_grid_from_connection(
                connection, revision_public_id
            )
            expected_identities = {
                (
                    row.source.source_ordinal,
                    row.source.source_item,
                    row.problem.problem_id,
                )
                for row in current_grid.rows
            }
            draft_by_identity = {
                (draft.source_ordinal, draft.source_item, draft.problem_id): draft
                for draft in prepared
            }
            if len(draft_by_identity) != len(prepared):
                raise ContentInvariantError(
                    "problem metadata identities are duplicated"
                )
            if set(draft_by_identity) != expected_identities:
                raise ContentInvariantError(
                    "metadata grid must cover every matched non-omitted problem"
                )

            if current_grid.review_version != expected_review_version:
                raise ContentVersionConflict("problem review version changed")

            had_reviewed = any(row.reviewed for row in current_grid.rows)
            changed = False
            for identity in sorted(draft_by_identity):
                metadata = draft_by_identity[identity]
                current_row = next(
                    (
                        row
                        for row in current_grid.rows
                        if (
                            row.source.source_ordinal,
                            row.source.source_item,
                            row.problem.problem_id,
                        )
                        == identity
                    ),
                    None,
                )
                if current_row is not None and current_row.reviewed and _metadata_matches_draft(
                    current_row.problem, metadata
                ):
                    continue
                config_version_row = connection.execute(
                    "SELECT coalesce(max(config_version), 0) + 1 AS value "
                    "FROM problem_revisions WHERE problem_id = ?",
                    (metadata.problem_id,),
                ).fetchone()
                base = metadata.as_revision_draft()
                revision_draft = ProblemRevisionDraft(
                    problem_id=base.problem_id,
                    source_ordinal=base.source_ordinal,
                    source_item=base.source_item,
                    display_number=base.display_number,
                    title=base.title,
                    problem_type=base.problem_type,
                    answer_type=base.answer_type,
                    answer_config=base.answer_config,
                    attempt_policy=base.attempt_policy,
                    config_version=int(config_version_row["value"]),
                )
                connection.execute(
                    "UPDATE problems SET title = ?, prob_type = ?, ans_type = ?, "
                    "ans_validation = ?, validation_error = ?, cor_ans = ?, "
                    "cor_ans_checker = ?, wrong_ans = ?, congrat = ? WHERE id = ?",
                    (
                        metadata.title,
                        metadata.problem_type,
                        metadata.answer_type,
                        metadata.answer_validation,
                        metadata.validation_error,
                        metadata.correct_answer,
                        metadata.correct_answer_checker,
                        metadata.wrong_answer,
                        metadata.congratulation,
                        metadata.problem_id,
                    ),
                )
                existing_revision = connection.execute(
                    "SELECT id FROM problem_revisions WHERE content_revision_id = ? "
                    "AND source_ordinal = ? AND source_item = ? AND problem_id = ?",
                    (
                        current_grid.revision_id,
                        metadata.source_ordinal,
                        metadata.source_item,
                        metadata.problem_id,
                    ),
                ).fetchone()
                try:
                    if existing_revision is None:
                        connection.execute(
                            "INSERT INTO problem_revisions "
                            "(problem_id, content_revision_id, source_ordinal, source_item, "
                            "display_number, title, normalized_title, problem_type, "
                            "answer_type, answer_config_json, attempt_policy_json, "
                            "config_version, created_at, created_by_user_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                revision_draft.problem_id,
                                current_grid.revision_id,
                                revision_draft.source_ordinal,
                                revision_draft.source_item,
                                revision_draft.display_number,
                                revision_draft.title,
                                revision_draft.normalized_title,
                                revision_draft.problem_type,
                                revision_draft.answer_type,
                                revision_draft.answer_config_json(),
                                revision_draft.attempt_policy_json(),
                                revision_draft.config_version,
                                timestamp,
                                actor_user_id,
                            ),
                        )
                    else:
                        connection.execute(
                            "UPDATE problem_revisions SET display_number = ?, title = ?, "
                            "normalized_title = ?, problem_type = ?, answer_type = ?, "
                            "answer_config_json = ?, attempt_policy_json = ?, config_version = ?, "
                            "created_at = ?, created_by_user_id = ? WHERE id = ?",
                            (
                                revision_draft.display_number,
                                revision_draft.title,
                                revision_draft.normalized_title,
                                revision_draft.problem_type,
                                revision_draft.answer_type,
                                revision_draft.answer_config_json(),
                                revision_draft.attempt_policy_json(),
                                revision_draft.config_version,
                                timestamp,
                                actor_user_id,
                                int(existing_revision["id"]),
                            ),
                        )
                except sqlite3.IntegrityError as error:
                    raise _translate_integrity(
                        error, action="problem metadata review"
                    ) from error
                changed = True
            if not changed:
                return current_grid
            if had_reviewed:
                _advance_review_version(
                    connection,
                    revision_id=current_grid.revision_id,
                    expected_version=expected_review_version,
                    timestamp=timestamp,
                    actor_user_id=actor_user_id,
                )
            return _problem_metadata_grid_from_connection(
                connection, revision_public_id
            )

        return await self._factory.run_write_async(write)

    async def add_problem_revision(
        self,
        *,
        content_revision_id: int,
        draft: ProblemRevisionDraft,
        decision: ProblemMatchDecision,
        actor_user_id: int | None,
    ) -> ProblemRevisionRecord:
        if decision is ProblemMatchDecision.OMIT:
            raise ContentInvariantError("omitted source item has no problem revision")
        timestamp = self._timestamp()

        def write(connection):
            try:
                connection.execute(
                    "INSERT INTO content_problem_matches "
                    "(content_revision_id, source_ordinal, source_item, problem_id, "
                    "decision, resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?)",
                    (
                        content_revision_id,
                        draft.source_ordinal,
                        draft.source_item.strip(),
                        draft.problem_id,
                        decision.value,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                )
                row = connection.execute(
                    "INSERT INTO problem_revisions "
                    "(problem_id, content_revision_id, source_ordinal, source_item, "
                    "display_number, title, normalized_title, problem_type, answer_type, "
                    "answer_config_json, attempt_policy_json, config_version, created_at, "
                    "created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING *",
                    (
                        draft.problem_id,
                        content_revision_id,
                        draft.source_ordinal,
                        draft.source_item.strip(),
                        draft.display_number.strip(),
                        draft.title.strip(),
                        draft.normalized_title,
                        draft.problem_type,
                        draft.answer_type,
                        draft.answer_config_json(),
                        draft.attempt_policy_json(),
                        draft.config_version,
                        timestamp,
                        actor_user_id,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="problem revision") from error
            return ProblemRevisionRecord(
                id=int(row["id"]),
                problem_id=int(row["problem_id"]),
                content_revision_id=int(row["content_revision_id"]),
                normalized_title=str(row["normalized_title"]),
            )

        return await self._factory.run_write_async(write)

    async def discover_synonym_candidates(
        self, *, course_lesson_id: int
    ) -> tuple[ProblemSynonymCandidate, ...]:
        """Read candidates only; explicit admin merge is a separate mutation."""

        def read(connection):
            rows = connection.execute(
                "SELECT group_lesson.course_lesson_id, group_lesson.id AS group_lesson_id, "
                "problem_revision.problem_id, problem_revision.title "
                "FROM problem_revisions AS problem_revision "
                "JOIN content_revisions AS revision "
                "  ON revision.id = problem_revision.content_revision_id "
                "JOIN content_sources AS source ON source.id = revision.source_id "
                "JOIN group_lessons AS group_lesson "
                "  ON group_lesson.id = source.group_lesson_id "
                "WHERE group_lesson.course_lesson_id = ? "
                "  AND problem_revision.id = ("
                "      SELECT newer.id FROM problem_revisions AS newer "
                "      JOIN content_revisions AS newer_revision "
                "        ON newer_revision.id = newer.content_revision_id "
                "      JOIN content_sources AS newer_source "
                "        ON newer_source.id = newer_revision.source_id "
                "      WHERE newer.problem_id = problem_revision.problem_id "
                "        AND newer_source.group_lesson_id = group_lesson.id "
                "      ORDER BY newer_revision.revision_number DESC, newer.id DESC LIMIT 1"
                "  ) ORDER BY group_lesson.id, problem_revision.problem_id",
                (course_lesson_id,),
            ).fetchall()
            inputs = tuple(
                ProblemTitleCandidateInput(
                    course_lesson_id=int(row["course_lesson_id"]),
                    group_lesson_id=int(row["group_lesson_id"]),
                    problem_id=int(row["problem_id"]),
                    title=str(row["title"]),
                )
                for row in rows
            )
            return find_problem_synonym_candidates(inputs)

        return await self._factory.run_read_async(read)

    async def create_synonym_group(
        self,
        *,
        public_id: str,
        course_lesson_id: int,
        group_key: str,
        display_title: str,
        actor_user_id: int | None,
    ) -> SynonymGroupRecord:
        _require_public_id(public_id)
        group_key = _required_text(group_key, label="synonym group key")
        display_title = _required_text(display_title, label="synonym group title")
        timestamp = self._timestamp()

        def write(connection):
            try:
                row = connection.execute(
                    "INSERT INTO problem_synonym_groups "
                    "(public_id, course_lesson_id, group_key, display_title, status, "
                    "created_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'active', ?, ?, ?) RETURNING *",
                    (
                        public_id,
                        course_lesson_id,
                        group_key,
                        display_title,
                        actor_user_id,
                        timestamp,
                        timestamp,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="synonym group") from error
            return SynonymGroupRecord(
                id=int(row["id"]),
                public_id=str(row["public_id"]),
                course_lesson_id=int(row["course_lesson_id"]),
                group_key=str(row["group_key"]),
                display_title=str(row["display_title"]),
                status=str(row["status"]),
                version=int(row["version"]),
            )

        return await self._factory.run_write_async(write)

    async def add_synonym_member(
        self,
        *,
        synonym_group_id: int,
        group_lesson_id: int,
        problem_id: int,
        actor_user_id: int | None,
    ) -> SynonymMemberRecord:
        timestamp = self._timestamp()

        def write(connection):
            latest = connection.execute(
                "SELECT max(membership_version) AS version "
                "FROM problem_synonym_members "
                "WHERE synonym_group_id = ? AND problem_id = ?",
                (synonym_group_id, problem_id),
            ).fetchone()
            previous = latest["version"]
            membership_version = 1 if previous is None else int(previous) + 1
            try:
                row = connection.execute(
                    "INSERT INTO problem_synonym_members "
                    "(synonym_group_id, group_lesson_id, problem_id, added_by_user_id, "
                    "added_at, membership_version) VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
                    (
                        synonym_group_id,
                        group_lesson_id,
                        problem_id,
                        actor_user_id,
                        timestamp,
                        membership_version,
                    ),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="synonym member") from error
            return SynonymMemberRecord(
                id=int(row["id"]),
                synonym_group_id=int(row["synonym_group_id"]),
                group_lesson_id=int(row["group_lesson_id"]),
                problem_id=int(row["problem_id"]),
                membership_version=int(row["membership_version"]),
                removed_at=_optional_timestamp(row["removed_at"]),
            )

        return await self._factory.run_write_async(write)

    async def remove_synonym_member(
        self,
        *,
        member_id: int,
        actor_user_id: int,
        reason: str,
    ) -> SynonymMemberRecord:
        reason = _required_text(reason, label="synonym split reason")
        timestamp = self._timestamp()

        def write(connection):
            try:
                row = connection.execute(
                    "UPDATE problem_synonym_members SET removed_by_user_id = ?, "
                    "removed_at = ?, reason = ? WHERE id = ? AND removed_at IS NULL "
                    "RETURNING *",
                    (actor_user_id, timestamp, reason, member_id),
                ).fetchone()
            except sqlite3.IntegrityError as error:
                raise _translate_integrity(error, action="synonym split") from error
            if row is not None:
                return SynonymMemberRecord(
                    id=int(row["id"]),
                    synonym_group_id=int(row["synonym_group_id"]),
                    group_lesson_id=int(row["group_lesson_id"]),
                    problem_id=int(row["problem_id"]),
                    membership_version=int(row["membership_version"]),
                    removed_at=_optional_timestamp(row["removed_at"]),
                )
            exists = connection.execute(
                "SELECT 1 FROM problem_synonym_members WHERE id = ?", (member_id,)
            ).fetchone()
            if exists is None:
                raise ContentNotFound("synonym member does not exist")
            raise ContentConflict("synonym member is already removed")

        return await self._factory.run_write_async(write)
