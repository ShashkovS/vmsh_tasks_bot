"""Pure Phase-2 lesson/content rules, independent of SQLite and HTTP.

The authoritative requirements are Phase 2 in
``vmshpwa/dev/development-plan/06-phase-2-content.md`` and the content section
of ``02-data-model.md``.  In particular, equal problem titles only produce a
candidate: this module never merges concrete problems or their history.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from itertools import combinations
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ContentInvariantError(ValueError):
    """Raised when a proposed content-domain value violates a stable rule."""


class ContentKind(StrEnum):
    CONDITION = "condition"
    HINT = "hint"
    SOLUTION = "solution"
    TEACHER_NOTE = "teacher_note"


class RevisionStatus(StrEnum):
    UPLOADED = "uploaded"
    COMPILING = "compiling"
    READY = "ready"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


class WindowSource(StrEnum):
    NATIVE = "native"
    LEGACY_SCHEDULE = "legacy_schedule"
    MANUAL_BACKFILL = "manual_backfill"


class ScheduleField(StrEnum):
    OPENS_AT = "opens_at"
    HINT_SCHEDULED_AT = "hint_scheduled_at"
    SUBMISSION_CLOSES_AT = "submission_closes_at"
    SOLUTION_SCHEDULED_AT = "solution_scheduled_at"


class ScheduleOverrideMode(StrEnum):
    INHERIT = "inherit"
    OVERRIDE = "override"
    DISABLED = "disabled"


class StudentLessonPhase(StrEnum):
    PUBLISHED = "published"
    SOLVING = "solving"
    HINTS = "hints"
    CHECKING = "checking"
    SOLUTIONS = "solutions"


class PublicationState(StrEnum):
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    HIDDEN = "hidden"


class ProblemMatchDecision(StrEnum):
    AUTO_POSITION = "auto_position"
    MANUAL_MATCH = "manual_match"
    INSERT_NEW = "insert_new"
    OMIT = "omit"


PROBLEM_TYPE_VALUES = frozenset({1, 2, 3, 4})
ANSWER_TYPE_VALUES = frozenset(
    {
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        98,
        99,
    }
)


_PUBLICATION_TRANSITIONS: Mapping[PublicationState, frozenset[PublicationState]] = {
    PublicationState.SCHEDULED: frozenset(
        {
            PublicationState.PUBLISHED,
            PublicationState.HIDDEN,
            PublicationState.SUPERSEDED,
        }
    ),
    PublicationState.PUBLISHED: frozenset(
        {PublicationState.HIDDEN, PublicationState.SUPERSEDED}
    ),
    PublicationState.HIDDEN: frozenset(),
    PublicationState.SUPERSEDED: frozenset(),
}

_REVISION_TRANSITIONS: Mapping[RevisionStatus, frozenset[RevisionStatus]] = {
    RevisionStatus.UPLOADED: frozenset(
        {RevisionStatus.COMPILING, RevisionStatus.INVALID}
    ),
    RevisionStatus.COMPILING: frozenset({RevisionStatus.READY, RevisionStatus.INVALID}),
    RevisionStatus.READY: frozenset({RevisionStatus.SUPERSEDED}),
    RevisionStatus.INVALID: frozenset(),
    RevisionStatus.SUPERSEDED: frozenset(),
}


def require_aware_datetime(value: datetime, *, label: str) -> datetime:
    """Return an aware value in UTC; naive business timestamps are rejected."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ContentInvariantError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def format_utc_timestamp(value: datetime) -> str:
    return (
        require_aware_datetime(value, label="timestamp")
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def parse_utc_timestamp(value: str) -> datetime:
    if not value:
        raise ContentInvariantError("stored timestamp must not be empty")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContentInvariantError("stored timestamp is invalid") from error
    return require_aware_datetime(parsed, label="stored timestamp")


def resolve_local_wall_time(value: str, *, timezone: str) -> datetime:
    """Resolve an exact minute in the lesson timezone, rejecting DST traps.

    HTML ``datetime-local`` deliberately carries no offset.  Publication and
    lesson-window APIs therefore submit the wall-clock value together with the
    authoritative group-lesson timezone; accepting the administrator browser's
    local timezone would make remote administration non-deterministic.  See
    Phase 2 ``SCHEDULE-01`` in
    ``vmshpwa/dev/development-plan/06-phase-2-content.md``.
    """

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d", value) is None:
        raise ContentInvariantError("schedule local date-time is invalid")
    timezone = timezone.strip()
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ContentInvariantError("schedule timezone is unknown") from error
    try:
        local_naive = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as error:
        raise ContentInvariantError("schedule local date-time is invalid") from error

    first = local_naive.replace(tzinfo=zone, fold=0)
    second = local_naive.replace(tzinfo=zone, fold=1)
    first_roundtrip = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    second_roundtrip = second.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    valid_first = first_roundtrip == local_naive
    valid_second = second_roundtrip == local_naive
    if not valid_first and not valid_second:
        raise ContentInvariantError("schedule local date-time does not exist")
    if valid_first and valid_second and first.utcoffset() != second.utcoffset():
        raise ContentInvariantError("schedule local date-time is ambiguous")
    return (first if valid_first else second).astimezone(UTC)


def normalize_problem_title(value: str) -> str:
    """Normalize a title only for candidate discovery, never as identity."""

    normalized = " ".join(
        unicodedata.normalize("NFKC", value).strip().casefold().split()
    )
    if not normalized:
        raise ContentInvariantError("problem title must not be empty")
    return normalized


def _canonical_object(
    value: Mapping[str, object], *, label: str, allow_empty: bool = True
) -> dict[str, object]:
    if not value and not allow_empty:
        raise ContentInvariantError(f"{label} must not be empty")
    if any(not isinstance(key, str) or not key for key in value):
        raise ContentInvariantError(f"{label} keys must be non-empty strings")
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
    decoded = json.loads(serialized)
    if not isinstance(decoded, dict):
        raise ContentInvariantError(f"{label} must be an object")
    return decoded


@dataclass(frozen=True, slots=True)
class SourceRevisionPayload:
    """Decoded LaTeX plus the hash/provenance of the exact uploaded bytes."""

    latex_text: str
    source_encoding: str
    source_sha256: str
    source_byte_length: int
    provenance: Mapping[str, object]

    @classmethod
    def from_bytes(
        cls,
        source: bytes,
        *,
        encoding: str,
        provenance: Mapping[str, object],
    ) -> SourceRevisionPayload:
        if not source:
            raise ContentInvariantError("LaTeX source must not be empty")
        normalized_encoding = encoding.strip().casefold().replace("_", "-")
        # Detection itself belongs to the compiler adapter.  This constructor
        # is the single explicit vocabulary boundary after detection: it
        # canonicalizes the stored label while preserving the exact raw-byte
        # hash (including a UTF-8 BOM, when present).
        aliases = {
            "utf8": ("utf-8", "utf-8"),
            "utf-8": ("utf-8", "utf-8"),
            "utf-8-sig": ("utf-8-sig", "utf-8"),
            "cp1251": ("cp1251", "cp1251"),
            "windows-1251": ("cp1251", "cp1251"),
        }
        encoding_pair = aliases.get(normalized_encoding)
        if encoding_pair is None:
            raise ContentInvariantError("source encoding must be UTF-8 or CP1251")
        decoder_encoding, canonical_encoding = encoding_pair
        try:
            latex_text = source.decode(decoder_encoding, errors="strict")
        except UnicodeDecodeError as error:
            raise ContentInvariantError(
                f"source bytes are not valid {canonical_encoding}"
            ) from error
        # A BOM is transport metadata, not part of the LaTeX document.  The
        # exact uploaded bytes (including the BOM) are nevertheless hashed and
        # measured below for reproducible provenance.
        latex_text = latex_text.removeprefix("\ufeff")
        canonical_provenance = _canonical_object(
            provenance, label="provenance", allow_empty=False
        )
        for reserved_key, expected in (
            ("sourceEncoding", canonical_encoding),
            ("sourceByteLength", len(source)),
        ):
            existing = canonical_provenance.get(reserved_key, expected)
            if existing != expected:
                raise ContentInvariantError(
                    f"provenance {reserved_key} contradicts uploaded bytes"
                )
            canonical_provenance[reserved_key] = expected
        return cls(
            latex_text=latex_text,
            source_encoding=canonical_encoding,
            source_sha256=hashlib.sha256(source).hexdigest(),
            source_byte_length=len(source),
            provenance=MappingProxyType(canonical_provenance),
        )

    def provenance_json(self) -> str:
        return json.dumps(
            dict(self.provenance),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


@dataclass(frozen=True, slots=True)
class LessonWindowDraft:
    opens_at: datetime | None
    submission_closes_at: datetime
    hint_scheduled_at: datetime | None
    solution_scheduled_at: datetime | None
    timezone: str
    source: WindowSource = WindowSource.NATIVE

    def __post_init__(self) -> None:
        timezone = self.timezone.strip()
        if not timezone:
            raise ContentInvariantError("lesson window timezone must not be empty")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as error:
            raise ContentInvariantError("lesson window timezone is unknown") from error
        close = require_aware_datetime(
            self.submission_closes_at, label="submission close"
        )
        if self.opens_at is not None:
            opens = require_aware_datetime(self.opens_at, label="lesson open")
            if opens >= close:
                raise ContentInvariantError(
                    "lesson open must be earlier than submission close"
                )
        for value, label in (
            (self.hint_scheduled_at, "hint schedule"),
            (self.solution_scheduled_at, "solution schedule"),
        ):
            if value is not None:
                require_aware_datetime(value, label=label)
        object.__setattr__(self, "timezone", timezone)


@dataclass(frozen=True, slots=True)
class ScheduleRuleValue:
    """One explicit field rule relative to a group lesson's cycle anchor."""

    day_offset: int
    local_time: time
    timezone: str

    def __post_init__(self) -> None:
        if self.local_time.tzinfo is not None:
            raise ContentInvariantError("schedule local time must not carry timezone")
        timezone = self.timezone.strip()
        if not timezone:
            raise ContentInvariantError("schedule timezone must not be empty")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as error:
            raise ContentInvariantError("schedule timezone is unknown") from error
        object.__setattr__(self, "timezone", timezone)

    @property
    def local_time_text(self) -> str:
        return self.local_time.isoformat(timespec="seconds")

    @classmethod
    def from_text(
        cls, *, day_offset: int, local_time: str, timezone: str
    ) -> ScheduleRuleValue:
        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", local_time) is None:
            raise ContentInvariantError("schedule local time is invalid")
        try:
            parsed_time = time.fromisoformat(local_time)
        except (TypeError, ValueError) as error:
            raise ContentInvariantError("schedule local time is invalid") from error
        return cls(
            day_offset=day_offset,
            local_time=parsed_time,
            timezone=timezone,
        )

    def resolve(self, cycle_anchor_date: date) -> datetime:
        local_naive = datetime.combine(
            cycle_anchor_date + timedelta(days=self.day_offset), self.local_time
        )
        zone = ZoneInfo(self.timezone)
        first = local_naive.replace(tzinfo=zone, fold=0)
        second = local_naive.replace(tzinfo=zone, fold=1)
        first_roundtrip = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        second_roundtrip = second.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        valid_first = first_roundtrip == local_naive
        valid_second = second_roundtrip == local_naive
        if not valid_first and not valid_second:
            raise ContentInvariantError("schedule local time does not exist")
        if valid_first and valid_second and first.utcoffset() != second.utcoffset():
            raise ContentInvariantError("schedule local time is ambiguous")
        return (first if valid_first else second).astimezone(UTC)


def materialize_lesson_window(
    *,
    cycle_anchor_date: date,
    business_timezone: str,
    rules: Mapping[ScheduleField, ScheduleRuleValue | None],
) -> LessonWindowDraft:
    business_timezone = business_timezone.strip()
    if not business_timezone:
        raise ContentInvariantError("business timezone must not be empty")
    try:
        ZoneInfo(business_timezone)
    except ZoneInfoNotFoundError as error:
        raise ContentInvariantError("business timezone is unknown") from error

    def resolve_optional(field: ScheduleField) -> datetime | None:
        value = rules.get(field)
        return None if value is None else value.resolve(cycle_anchor_date)

    close_rule = rules.get(ScheduleField.SUBMISSION_CLOSES_AT)
    if close_rule is None:
        raise ContentInvariantError("submission close schedule cannot be disabled")
    return LessonWindowDraft(
        opens_at=resolve_optional(ScheduleField.OPENS_AT),
        submission_closes_at=close_rule.resolve(cycle_anchor_date),
        hint_scheduled_at=resolve_optional(ScheduleField.HINT_SCHEDULED_AT),
        solution_scheduled_at=resolve_optional(ScheduleField.SOLUTION_SCHEDULED_AT),
        timezone=business_timezone,
        source=WindowSource.NATIVE,
    )


def resolve_student_lesson_phase(
    *,
    now: datetime,
    opens_at: datetime | None,
    submission_closes_at: datetime | None,
    hint_published: bool,
    solution_published: bool,
) -> StudentLessonPhase:
    """Resolve the quiet Student home label from authoritative facts.

    The close boundary and solution publication are intentionally independent:
    moving either one never changes the other implicitly. A lesson without a
    materialized window remains readable but is labelled only as published.
    """

    now = require_aware_datetime(now, label="student home time")
    opens_at = (
        None
        if opens_at is None
        else require_aware_datetime(opens_at, label="lesson opening")
    )
    submission_closes_at = (
        None
        if submission_closes_at is None
        else require_aware_datetime(
            submission_closes_at, label="submission cutoff"
        )
    )
    if solution_published:
        return StudentLessonPhase.SOLUTIONS
    if submission_closes_at is None:
        return StudentLessonPhase.PUBLISHED
    if opens_at is not None and now < opens_at:
        return StudentLessonPhase.PUBLISHED
    if now >= submission_closes_at:
        return StudentLessonPhase.CHECKING
    if hint_published:
        return StudentLessonPhase.HINTS
    return StudentLessonPhase.SOLVING


@dataclass(frozen=True, slots=True)
class ProblemRevisionDraft:
    problem_id: int
    source_ordinal: int
    source_item: str
    display_number: str
    title: str
    problem_type: int
    answer_type: int | None
    answer_config: Mapping[str, object]
    attempt_policy: Mapping[str, object]
    config_version: int = 1

    def __post_init__(self) -> None:
        if self.source_ordinal < 0:
            raise ContentInvariantError("source ordinal must be non-negative")
        for value, label in (
            (self.source_item, "source item"),
            (self.display_number, "display number"),
            (self.title, "problem title"),
        ):
            if not value.strip():
                raise ContentInvariantError(f"{label} must not be empty")
        if self.config_version < 1:
            raise ContentInvariantError("problem config version must be positive")
        _canonical_object(self.answer_config, label="answer config")
        _canonical_object(self.attempt_policy, label="attempt policy")

    @property
    def normalized_title(self) -> str:
        return normalize_problem_title(self.title)

    def answer_config_json(self) -> str:
        return json.dumps(
            _canonical_object(self.answer_config, label="answer config"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def attempt_policy_json(self) -> str:
        return json.dumps(
            _canonical_object(self.attempt_policy, label="attempt policy"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class ProblemMatchDraft:
    """One explicit decision for a canonical LaTeX problem identity."""

    source_ordinal: int
    source_item: str
    decision: ProblemMatchDecision
    problem_id: int | None

    def __post_init__(self) -> None:
        if self.source_ordinal < 0:
            raise ContentInvariantError("source ordinal must be non-negative")
        source_item = self.source_item.strip()
        if not source_item:
            raise ContentInvariantError("source item must not be empty")
        if self.decision is ProblemMatchDecision.OMIT:
            if self.problem_id is not None:
                raise ContentInvariantError("omitted problem must not have problem ID")
        elif self.decision is ProblemMatchDecision.INSERT_NEW:
            if self.problem_id is not None:
                raise ContentInvariantError("new problem must not have problem ID")
        elif self.problem_id is None or self.problem_id == 0:
            raise ContentInvariantError("matched problem requires a non-zero problem ID")
        object.__setattr__(self, "source_item", source_item)


@dataclass(frozen=True, slots=True)
class ProblemMetadataDraft:
    """Reviewed Staff-grid values before they become an immutable revision."""

    problem_id: int
    source_ordinal: int
    source_item: str
    display_number: str
    title: str
    problem_type: int
    answer_type: int | None
    answer_validation: str | None
    validation_error: str | None
    correct_answer: str | None
    correct_answer_checker: str | None
    wrong_answer: str | None
    congratulation: str | None

    def __post_init__(self) -> None:
        if self.problem_id == 0:
            raise ContentInvariantError("problem ID must be non-zero")
        if self.source_ordinal < 0:
            raise ContentInvariantError("source ordinal must be non-negative")
        for field_name, value, label, limit in (
            ("source_item", self.source_item, "source item", 80),
            ("display_number", self.display_number, "display number", 80),
            ("title", self.title, "problem title", 500),
        ):
            normalized = value.strip()
            if not normalized:
                raise ContentInvariantError(f"{label} must not be empty")
            if len(normalized) > limit:
                raise ContentInvariantError(f"{label} is too long")
            object.__setattr__(self, field_name, normalized)
        if self.problem_type not in PROBLEM_TYPE_VALUES:
            raise ContentInvariantError("problem type is invalid")
        if self.problem_type == 1:
            if self.answer_type not in ANSWER_TYPE_VALUES:
                raise ContentInvariantError("test problem requires an answer type")
        elif self.answer_type is not None:
            raise ContentInvariantError("non-test problem must not have an answer type")
        for field_name in (
            "answer_validation",
            "validation_error",
            "correct_answer",
            "wrong_answer",
            "congratulation",
        ):
            value = getattr(self, field_name)
            if value is not None:
                normalized = value.strip()
                if len(normalized) > 4_000:
                    raise ContentInvariantError(f"{field_name} is too long")
                object.__setattr__(self, field_name, normalized or None)
        if self.correct_answer_checker is not None:
            checker = self.correct_answer_checker.strip()
            if len(checker) > 65_536:
                raise ContentInvariantError("correct answer checker is too long")
            object.__setattr__(
                self, "correct_answer_checker", checker or None
            )
        if self.problem_type != 1 and any(
            getattr(self, field_name) is not None
            for field_name in (
                "answer_validation",
                "validation_error",
                "correct_answer",
                "correct_answer_checker",
                "wrong_answer",
                "congratulation",
            )
        ):
            raise ContentInvariantError(
                "non-test problem must not keep test answer configuration"
            )

    @property
    def answer_config(self) -> Mapping[str, object]:
        return {
            "schemaVersion": 1,
            "source": "staff-metadata-v1",
            "answerType": self.answer_type,
            "answerValidation": self.answer_validation,
            "validationError": self.validation_error,
            "correctAnswer": self.correct_answer,
            "correctAnswerChecker": self.correct_answer_checker,
            "wrongAnswer": self.wrong_answer,
            "congratulation": self.congratulation,
        }

    def as_revision_draft(self) -> ProblemRevisionDraft:
        return ProblemRevisionDraft(
            problem_id=self.problem_id,
            source_ordinal=self.source_ordinal,
            source_item=self.source_item,
            display_number=self.display_number,
            title=self.title,
            problem_type=self.problem_type,
            answer_type=self.answer_type,
            answer_config=self.answer_config,
            attempt_policy={
                "schemaVersion": 1,
                "source": "staff-metadata-v1",
            },
        )


@dataclass(frozen=True, slots=True, order=True)
class ProblemTitleCandidateInput:
    course_lesson_id: int
    group_lesson_id: int
    problem_id: int
    title: str


@dataclass(frozen=True, slots=True, order=True)
class ProblemSynonymCandidate:
    course_lesson_id: int
    normalized_title: str
    first_group_lesson_id: int
    first_problem_id: int
    second_group_lesson_id: int
    second_problem_id: int


def find_problem_synonym_candidates(
    problems: tuple[ProblemTitleCandidateInput, ...],
) -> tuple[ProblemSynonymCandidate, ...]:
    """Return deterministic cross-group candidates without mutating anything."""

    buckets: dict[
        tuple[int, str], dict[tuple[int, int], ProblemTitleCandidateInput]
    ] = {}
    for problem in problems:
        key = (problem.course_lesson_id, normalize_problem_title(problem.title))
        buckets.setdefault(key, {})[(problem.group_lesson_id, problem.problem_id)] = (
            problem
        )

    candidates: list[ProblemSynonymCandidate] = []
    for (course_lesson_id, normalized_title), unique_problems in sorted(
        buckets.items()
    ):
        ordered = sorted(unique_problems.values())
        for first, second in combinations(ordered, 2):
            if first.group_lesson_id == second.group_lesson_id:
                continue
            candidates.append(
                ProblemSynonymCandidate(
                    course_lesson_id=course_lesson_id,
                    normalized_title=normalized_title,
                    first_group_lesson_id=first.group_lesson_id,
                    first_problem_id=first.problem_id,
                    second_group_lesson_id=second.group_lesson_id,
                    second_problem_id=second.problem_id,
                )
            )
    return tuple(candidates)


def require_publication_transition(
    current: PublicationState, target: PublicationState
) -> None:
    if target not in _PUBLICATION_TRANSITIONS[current]:
        raise ContentInvariantError(
            f"publication cannot transition from {current.value} to {target.value}"
        )


def require_revision_transition(
    current: RevisionStatus, target: RevisionStatus
) -> None:
    if target not in _REVISION_TRANSITIONS[current]:
        raise ContentInvariantError(
            f"revision cannot transition from {current.value} to {target.value}"
        )
