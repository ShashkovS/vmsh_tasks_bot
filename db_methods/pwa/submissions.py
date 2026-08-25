"""Atomic SQLite repository for Phase-4 test submissions.

The repository resolves the exact published problem revision visible to the
student, evaluates outside the SQLite writer transaction, then revalidates the
revision before atomically writing the append-only attempt, one legacy result
and the completed idempotency response.  See
``vmshpwa/dev/development-plan/08-phase-4-test-submissions.md``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from helpers.consts import ANS_TYPE, RES_TYPE, VERDICT
from helpers.pwa.test_checkers import TrustedCheckerExecutor
from models.pwa.submissions import (
    SubmissionConfigurationError,
    TestAnswerEvaluation,
    TestAnswerOutcome,
    TestAttemptPolicy,
    TestProblemAnswerConfig,
    assess_submission_clock,
    checker_version,
    evaluate_test_answer,
)

from .connection import PwaConnectionFactory


IDEMPOTENCY_OPERATION = "test-attempt:create"
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")


class TestSubmissionRepositoryError(RuntimeError):
    """Base class for expected test-submission failures."""


class TestSubmissionRejected(TestSubmissionRepositoryError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        http_status: int,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = dict(details or {})

    def response_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }
        if self.details:
            error = payload["error"]
            assert isinstance(error, dict)
            error["details"] = self.details
        return payload

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object], http_status: int
    ) -> "TestSubmissionRejected":
        error = payload.get("error")
        if not isinstance(error, Mapping):
            raise TestSubmissionRepositoryError(
                "stored idempotency error response is invalid"
            )
        code = error.get("code")
        message = error.get("message")
        details = error.get("details")
        if not isinstance(code, str) or not isinstance(message, str):
            raise TestSubmissionRepositoryError(
                "stored idempotency error response is invalid"
            )
        return cls(
            code=code,
            message=message,
            http_status=http_status,
            details=details if isinstance(details, Mapping) else None,
        )


class IdempotencyPayloadMismatch(TestSubmissionRejected):
    def __init__(self) -> None:
        super().__init__(
            code="idempotency_payload_mismatch",
            message="Этот ключ уже использован для другого ответа.",
            http_status=409,
        )


@dataclass(frozen=True, slots=True)
class SubmitTestAnswerCommand:
    account_id: int
    problem_public_id: str
    display_answer: str
    client_created_at: datetime
    idempotency_key: str
    expected_condition_revision_public_id: str | None = None
    expected_config_version: int | None = None

    def __post_init__(self) -> None:
        if self.account_id < 1:
            raise ValueError("account ID must be positive")
        if not _PUBLIC_ID.fullmatch(self.problem_public_id):
            raise ValueError("problem public ID is invalid")
        if not isinstance(self.display_answer, str):
            raise TypeError("display answer must be text")
        key = self.idempotency_key
        if not isinstance(key, str) or not 1 <= len(key) <= 200 or key != key.strip():
            raise ValueError("idempotency key must be canonical")
        if (
            self.client_created_at.tzinfo is None
            or self.client_created_at.utcoffset() is None
        ):
            raise ValueError("client creation time must be timezone-aware")
        if (self.expected_condition_revision_public_id is None) != (
            self.expected_config_version is None
        ):
            raise ValueError("expected problem revision must be complete")
        if self.expected_condition_revision_public_id is not None:
            if not _PUBLIC_ID.fullmatch(self.expected_condition_revision_public_id):
                raise ValueError("expected condition revision public ID is invalid")
            if (
                type(self.expected_config_version) is not int
                or self.expected_config_version < 1
            ):
                raise ValueError("expected problem config version must be positive")


@dataclass(frozen=True, slots=True)
class AttemptLimitReceipt:
    used_this_hour: int
    remaining_this_hour: int | None
    used_today: int
    remaining_today: int | None
    unlimited: bool

    def payload(self) -> dict[str, object]:
        return {
            "usedThisHour": self.used_this_hour,
            "remainingThisHour": self.remaining_this_hour,
            "usedToday": self.used_today,
            "remainingToday": self.remaining_today,
            "unlimited": self.unlimited,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "AttemptLimitReceipt":
        try:
            return cls(
                used_this_hour=int(payload["usedThisHour"]),
                remaining_this_hour=(
                    None
                    if payload["remainingThisHour"] is None
                    else int(payload["remainingThisHour"])
                ),
                used_today=int(payload["usedToday"]),
                remaining_today=(
                    None
                    if payload["remainingToday"] is None
                    else int(payload["remainingToday"])
                ),
                unlimited=bool(payload["unlimited"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise TestSubmissionRepositoryError(
                "stored attempt limit response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class TestAttemptReceipt:
    attempt_public_id: str
    problem_public_id: str
    condition_revision_public_id: str
    config_version: int
    outcome: str
    display_answer: str
    feedback: str | None
    checker_message: str | None
    verdict: int | None
    client_created_at: str
    server_received_at: str
    clock_suspicious: bool
    attempts: AttemptLimitReceipt
    replayed: bool = field(default=False, compare=False)

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "attemptId": self.attempt_public_id,
            "problemId": self.problem_public_id,
            "problemRevision": {
                "conditionRevisionId": self.condition_revision_public_id,
                "configVersion": self.config_version,
            },
            "outcome": self.outcome,
            "displayAnswer": self.display_answer,
            "feedback": self.feedback,
            "checkerMessage": self.checker_message,
            "verdict": self.verdict,
            "clientCreatedAt": self.client_created_at,
            "serverReceivedAt": self.server_received_at,
            "clockSuspicious": self.clock_suspicious,
            "attempts": self.attempts.payload(),
        }

    @classmethod
    def from_response(cls, payload: Mapping[str, object]) -> "TestAttemptReceipt":
        revision = payload.get("problemRevision")
        attempts = payload.get("attempts")
        if not isinstance(revision, Mapping) or not isinstance(attempts, Mapping):
            raise TestSubmissionRepositoryError(
                "stored idempotency success response is invalid"
            )
        try:
            feedback = payload["feedback"]
            checker_message = payload["checkerMessage"]
            verdict = payload["verdict"]
            if feedback is not None and not isinstance(feedback, str):
                raise TypeError
            if checker_message is not None and not isinstance(checker_message, str):
                raise TypeError
            return cls(
                attempt_public_id=str(payload["attemptId"]),
                problem_public_id=str(payload["problemId"]),
                condition_revision_public_id=str(revision["conditionRevisionId"]),
                config_version=int(revision["configVersion"]),
                outcome=str(payload["outcome"]),
                display_answer=str(payload["displayAnswer"]),
                feedback=feedback,
                checker_message=checker_message,
                verdict=None if verdict is None else int(verdict),
                client_created_at=str(payload["clientCreatedAt"]),
                server_received_at=str(payload["serverReceivedAt"]),
                clock_suspicious=bool(payload["clockSuspicious"]),
                attempts=AttemptLimitReceipt.from_payload(attempts),
                replayed=True,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise TestSubmissionRepositoryError(
                "stored idempotency success response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class TestAttemptHistoryRecord:
    """Student-safe projection of one immutable test attempt."""

    attempt_public_id: str
    problem_public_id: str
    condition_revision_public_id: str
    config_version: int
    outcome: str
    check_status: str
    display_answer: str
    feedback: str | None
    checker_message: str | None
    verdict: int | None
    result_version: int | None
    client_created_at: str
    server_received_at: str
    clock_suspicious: bool

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "attemptId": self.attempt_public_id,
            "problemId": self.problem_public_id,
            "problemRevision": {
                "conditionRevisionId": self.condition_revision_public_id,
                "configVersion": self.config_version,
            },
            "outcome": self.outcome,
            "checkStatus": self.check_status,
            "displayAnswer": self.display_answer,
            "feedback": self.feedback,
            "checkerMessage": self.checker_message,
            "verdict": self.verdict,
            # Legacy results are immutable test verdict events. Their initial
            # API projection is version 1; a future recheck migration must
            # advance this value rather than overwriting history implicitly.
            "resultVersion": self.result_version,
            "clientCreatedAt": self.client_created_at,
            "serverReceivedAt": self.server_received_at,
            "clockSuspicious": self.clock_suspicious,
            "threadInvalidationKey": (
                f"problems/{self.problem_public_id}/test-attempts"
            ),
        }


@dataclass(frozen=True, slots=True)
class TestAttemptHistoryPage:
    problem_public_id: str
    attempts: tuple[TestAttemptHistoryRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class TestAnswerInputRecord:
    """Student-safe input configuration without answers or checker source."""

    problem_public_id: str
    condition_revision_public_id: str
    config_version: int
    answer_type: int
    validation_pattern: str | None
    validation_error: str | None
    options: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TestAttemptRecheckPreview:
    """Current published checker revision and its unresolved attempt count."""

    problem_public_id: str
    condition_revision_public_id: str
    config_version: int
    course_public_id: str
    group_public_id: str
    pending_attempts: int


@dataclass(frozen=True, slots=True)
class TestAttemptRecheckReceipt:
    """Monotonic result of applying the current checker to pending attempts."""

    problem_public_id: str
    condition_revision_public_id: str
    config_version: int
    pending_before: int
    checked: int
    correct: int
    wrong: int
    still_pending: int
    skipped_concurrent: int
    owner_account_public_ids: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class _SubmissionContext:
    account_id: int
    student_user_id: int
    problem_id: int
    problem_public_id: str
    problem_revision_id: int
    condition_revision_public_id: str
    config_version: int
    group_id: str
    lesson_number: int
    business_timezone: str
    submission_closes_at: datetime
    answer_config: TestProblemAnswerConfig
    attempt_policy: TestAttemptPolicy


@dataclass(frozen=True, slots=True)
class _RecheckContext:
    problem_id: int
    problem_public_id: str
    problem_revision_id: int
    condition_revision_public_id: str
    config_version: int
    course_public_id: str
    group_public_id: str
    group_id: str
    lesson_number: int
    answer_config: TestProblemAnswerConfig


@dataclass(frozen=True, slots=True)
class _PendingAttempt:
    id: int
    student_user_id: int
    display_answer: str


@dataclass(frozen=True, slots=True)
class _IdempotencyReplay:
    state: str
    http_status: int
    response: Mapping[str, object]


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise TestSubmissionRepositoryError(f"stored {label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TestSubmissionRepositoryError(f"stored {label} is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TestSubmissionRepositoryError(f"stored {label} is invalid")
    return parsed.astimezone(UTC)


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _request_payload(command: SubmitTestAnswerCommand) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "problemId": command.problem_public_id,
        "displayAnswer": command.display_answer.strip(),
        "clientCreatedAt": _timestamp(command.client_created_at),
    }
    if command.expected_condition_revision_public_id is not None:
        payload["problemRevision"] = {
            "conditionRevisionId": command.expected_condition_revision_public_id,
            "configVersion": command.expected_config_version,
        }
    return payload


def _payload_hash(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


_SUBMISSION_CONTEXT_SELECT = """
SELECT account.id AS account_id,
       account.linked_user_id AS student_user_id,
       problem.id AS problem_id,
       problem.public_id AS problem_public_id,
       problem_revision.id AS problem_revision_id,
       condition_revision.public_id AS condition_revision_public_id,
       problem_revision.config_version,
       group_lesson.group_id,
       course_lesson.lesson_number,
       group_lesson.business_timezone,
       lesson_window.submission_closes_at,
       problem_revision.answer_type,
       problem_revision.answer_config_json,
       problem_revision.attempt_policy_json
FROM auth_accounts AS account
JOIN course_enrollments AS enrollment
  ON enrollment.student_user_id = account.linked_user_id
 AND enrollment.status = 'active'
JOIN course_group_access AS access
  ON access.enrollment_id = enrollment.id
 AND access.course_id = enrollment.course_id
JOIN group_lessons AS group_lesson
  ON group_lesson.course_id = enrollment.course_id
 AND group_lesson.group_id = access.group_id
 AND group_lesson.status = 'active'
JOIN course_lessons AS course_lesson
  ON course_lesson.id = group_lesson.course_lesson_id
JOIN groups AS group_record
  ON group_record.course_id = group_lesson.course_id
 AND group_record.group_id = group_lesson.group_id
 AND group_record.status = 'active'
JOIN courses AS course
  ON course.id = group_lesson.course_id
 AND course.status = 'active'
JOIN lesson_windows AS lesson_window
  ON lesson_window.group_lesson_id = group_lesson.id
JOIN lesson_publications AS publication
  ON publication.group_lesson_id = group_lesson.id
 AND publication.kind = 'condition'
 AND publication.state = 'published'
JOIN content_revisions AS condition_revision
  ON condition_revision.id = publication.revision_id
 AND condition_revision.status = 'ready'
JOIN problem_revisions AS problem_revision
  ON problem_revision.content_revision_id = condition_revision.id
 AND problem_revision.problem_type = 1
 AND problem_revision.answer_type IS NOT NULL
JOIN content_problem_matches AS problem_match
  ON problem_match.content_revision_id = problem_revision.content_revision_id
 AND problem_match.source_ordinal = problem_revision.source_ordinal
 AND problem_match.source_item = problem_revision.source_item
 AND problem_match.problem_id = problem_revision.problem_id
 AND problem_match.resolved_at IS NOT NULL
 AND problem_match.decision <> 'omit'
JOIN problems AS problem
  ON problem.id = problem_revision.problem_id
WHERE account.id = :account_id
  AND account.audience = 'student'
  AND account.status = 'active'
  AND problem.public_id = :problem_public_id
  AND access.valid_from <= :now
  AND (access.valid_to IS NULL OR access.valid_to > :now)
  AND EXISTS (
      SELECT 1
      FROM content_derivatives AS derivative
      WHERE derivative.revision_id = condition_revision.id
        AND derivative.kind = 'web_ast'
        AND derivative.invalidated_at IS NULL
  )
"""


_RECHECK_CONTEXT_SELECT = """
SELECT problem.id AS problem_id,
       problem.public_id AS problem_public_id,
       problem_revision.id AS problem_revision_id,
       condition_revision.public_id AS condition_revision_public_id,
       problem_revision.config_version,
       course.public_id AS course_public_id,
       group_record.public_id AS group_public_id,
       group_lesson.group_id,
       course_lesson.lesson_number,
       problem_revision.answer_type,
       problem_revision.answer_config_json
FROM problems AS problem
JOIN problem_revisions AS problem_revision
  ON problem_revision.problem_id = problem.id
 AND problem_revision.problem_type = 1
 AND problem_revision.answer_type IS NOT NULL
JOIN content_problem_matches AS problem_match
  ON problem_match.content_revision_id = problem_revision.content_revision_id
 AND problem_match.source_ordinal = problem_revision.source_ordinal
 AND problem_match.source_item = problem_revision.source_item
 AND problem_match.problem_id = problem_revision.problem_id
 AND problem_match.resolved_at IS NOT NULL
 AND problem_match.decision <> 'omit'
JOIN content_revisions AS condition_revision
  ON condition_revision.id = problem_revision.content_revision_id
 AND condition_revision.status = 'ready'
JOIN content_sources AS source
  ON source.id = condition_revision.source_id
 AND source.kind = 'condition'
JOIN group_lessons AS group_lesson
  ON group_lesson.id = source.group_lesson_id
 AND group_lesson.status = 'active'
JOIN course_lessons AS course_lesson
  ON course_lesson.id = group_lesson.course_lesson_id
JOIN groups AS group_record
  ON group_record.course_id = group_lesson.course_id
 AND group_record.group_id = group_lesson.group_id
 AND group_record.status = 'active'
JOIN courses AS course
  ON course.id = group_lesson.course_id
 AND course.status = 'active'
JOIN lesson_publications AS publication
  ON publication.group_lesson_id = group_lesson.id
 AND publication.kind = 'condition'
 AND publication.revision_id = condition_revision.id
 AND publication.state = 'published'
WHERE problem.public_id = :problem_public_id
"""


def _context_from_row(row: Mapping[str, object]) -> _SubmissionContext:
    try:
        answer_config_raw = json.loads(str(row["answer_config_json"]))
        attempt_policy_raw = json.loads(str(row["attempt_policy_json"]))
    except (json.JSONDecodeError, KeyError, RecursionError) as error:
        raise SubmissionConfigurationError(
            "stored test problem configuration is invalid"
        ) from error
    if not isinstance(answer_config_raw, dict) or not isinstance(
        attempt_policy_raw, dict
    ):
        raise SubmissionConfigurationError(
            "stored test problem configuration must be objects"
        )
    return _SubmissionContext(
        account_id=int(row["account_id"]),
        student_user_id=int(row["student_user_id"]),
        problem_id=int(row["problem_id"]),
        problem_public_id=str(row["problem_public_id"]),
        problem_revision_id=int(row["problem_revision_id"]),
        condition_revision_public_id=str(row["condition_revision_public_id"]),
        config_version=int(row["config_version"]),
        group_id=str(row["group_id"]),
        lesson_number=int(row["lesson_number"]),
        business_timezone=str(row["business_timezone"]),
        submission_closes_at=_parse_timestamp(
            row["submission_closes_at"], label="submission cutoff"
        ),
        answer_config=TestProblemAnswerConfig.from_revision(
            answer_type=int(row["answer_type"]),
            answer_config=answer_config_raw,
        ),
        attempt_policy=TestAttemptPolicy.from_revision(attempt_policy_raw),
    )


def _recheck_context_from_row(row: Mapping[str, object]) -> _RecheckContext:
    try:
        answer_config_raw = json.loads(str(row["answer_config_json"]))
    except (json.JSONDecodeError, KeyError, RecursionError) as error:
        raise SubmissionConfigurationError(
            "stored recheck configuration is invalid"
        ) from error
    if not isinstance(answer_config_raw, dict):
        raise SubmissionConfigurationError(
            "stored recheck configuration must be an object"
        )
    return _RecheckContext(
        problem_id=int(row["problem_id"]),
        problem_public_id=str(row["problem_public_id"]),
        problem_revision_id=int(row["problem_revision_id"]),
        condition_revision_public_id=str(row["condition_revision_public_id"]),
        config_version=int(row["config_version"]),
        course_public_id=str(row["course_public_id"]),
        group_public_id=str(row["group_public_id"]),
        group_id=str(row["group_id"]),
        lesson_number=int(row["lesson_number"]),
        answer_config=TestProblemAnswerConfig.from_revision(
            answer_type=int(row["answer_type"]),
            answer_config=answer_config_raw,
        ),
    )


def _resolve_recheck_context(
    connection: sqlite3.Connection, *, problem_public_id: str
) -> _RecheckContext:
    rows = connection.execute(
        _RECHECK_CONTEXT_SELECT,
        {"problem_public_id": problem_public_id},
    ).fetchall()
    if len(rows) != 1:
        raise TestSubmissionRejected(
            code="test_problem_not_found",
            message="Тестовая задача недоступна для перепроверки.",
            http_status=404,
        )
    return _recheck_context_from_row(rows[0])


def _recheckable_attempts(
    connection: sqlite3.Connection,
    *,
    problem_id: int,
    current_checker_version: str,
) -> tuple[_PendingAttempt, ...]:
    rows = connection.execute(
        "SELECT id, student_user_id, answer_payload_json "
        "FROM test_attempts WHERE problem_id = ? AND ("
        "check_status = 'pending_configuration' "
        "OR (check_status = 'checked' AND checker_version <> ?)) "
        "ORDER BY server_received_at, id",
        (problem_id, current_checker_version),
    ).fetchall()
    attempts: list[_PendingAttempt] = []
    for row in rows:
        try:
            answer_payload = json.loads(str(row["answer_payload_json"]))
        except (json.JSONDecodeError, RecursionError) as error:
            raise TestSubmissionRepositoryError(
                "stored test attempt payload is invalid"
            ) from error
        if not isinstance(answer_payload, dict) or not isinstance(
            answer_payload.get("displayAnswer"), str
        ):
            raise TestSubmissionRepositoryError(
                "stored test attempt display answer is invalid"
            )
        attempts.append(
            _PendingAttempt(
                id=int(row["id"]),
                student_user_id=int(row["student_user_id"]),
                display_answer=str(answer_payload["displayAnswer"]),
            )
        )
    return tuple(attempts)


def _resolve_context(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    problem_public_id: str,
    now: datetime,
) -> _SubmissionContext:
    rows = connection.execute(
        _SUBMISSION_CONTEXT_SELECT,
        {
            "account_id": account_id,
            "problem_public_id": problem_public_id,
            "now": _timestamp(now),
        },
    ).fetchall()
    if len(rows) != 1:
        raise TestSubmissionRejected(
            code="test_problem_not_found",
            message="Тестовая задача недоступна.",
            http_status=404,
        )
    return _context_from_row(rows[0])


def _require_expected_revision(
    command: SubmitTestAnswerCommand,
    context: _SubmissionContext,
) -> None:
    expected_revision = command.expected_condition_revision_public_id
    if expected_revision is None:
        return
    if (
        context.condition_revision_public_id != expected_revision
        or context.config_version != command.expected_config_version
    ):
        raise TestSubmissionRejected(
            code="test_problem_revision_changed",
            message="Условие задачи изменилось. Обновите страницу.",
            http_status=409,
        )


def _read_idempotency(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    idempotency_key: str,
    payload_sha256: str,
) -> _IdempotencyReplay | None:
    row = connection.execute(
        "SELECT payload_sha256, state, http_status, response_json "
        "FROM idempotency_records WHERE audience = 'student' "
        "AND account_id = ? AND operation = ? AND idempotency_key = ?",
        (account_id, IDEMPOTENCY_OPERATION, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    if row["payload_sha256"] != payload_sha256:
        raise IdempotencyPayloadMismatch()
    if row["state"] == "processing":
        raise TestSubmissionRejected(
            code="idempotency_request_in_progress",
            message="Этот ответ уже обрабатывается.",
            http_status=409,
        )
    try:
        response = json.loads(str(row["response_json"]))
    except (json.JSONDecodeError, RecursionError) as error:
        raise TestSubmissionRepositoryError(
            "stored idempotency response is invalid"
        ) from error
    if not isinstance(response, dict) or row["http_status"] is None:
        raise TestSubmissionRepositoryError("stored idempotency response is incomplete")
    return _IdempotencyReplay(
        state=str(row["state"]),
        http_status=int(row["http_status"]),
        response=response,
    )


def _return_or_raise_replay(replay: _IdempotencyReplay) -> TestAttemptReceipt:
    if replay.state == "completed":
        return TestAttemptReceipt.from_response(replay.response)
    raise TestSubmissionRejected.from_response(replay.response, replay.http_status)


def _attempt_boundaries(now: datetime, timezone: str) -> tuple[datetime, datetime]:
    try:
        local_now = now.astimezone(ZoneInfo(timezone))
    except ZoneInfoNotFoundError as error:
        raise SubmissionConfigurationError(
            "group lesson timezone is invalid"
        ) from error
    hour_start = local_now.replace(minute=0, second=0, microsecond=0)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return hour_start.astimezone(UTC), day_start.astimezone(UTC)


def _attempt_counts(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    problem_id: int,
    hour_start: datetime,
    day_start: datetime,
) -> tuple[int, int]:
    row = connection.execute(
        "SELECT count(*) FILTER (WHERE server_received_at >= ? AND verdict = -1) "
        "AS hour_count, "
        "count(*) FILTER (WHERE server_received_at >= ?) AS day_count "
        "FROM test_attempts WHERE student_user_id = ? AND problem_id = ? "
        "AND counts_as_attempt = 1",
        (
            _timestamp(hour_start),
            _timestamp(day_start),
            student_user_id,
            problem_id,
        ),
    ).fetchone()
    return int(row["hour_count"]), int(row["day_count"])


def _limit_receipt(
    policy: TestAttemptPolicy, *, hour_count: int, day_count: int
) -> AttemptLimitReceipt:
    return AttemptLimitReceipt(
        used_this_hour=hour_count,
        remaining_this_hour=(
            None
            if policy.max_per_hour is None
            else max(policy.max_per_hour - hour_count, 0)
        ),
        used_today=day_count,
        remaining_today=(
            None
            if policy.max_per_day is None
            else max(policy.max_per_day - day_count, 0)
        ),
        unlimited=policy.max_per_hour is None and policy.max_per_day is None,
    )


def _raise_if_limited(
    policy: TestAttemptPolicy, *, hour_count: int, day_count: int
) -> None:
    if policy.max_per_hour is not None and hour_count >= policy.max_per_hour:
        raise TestSubmissionRejected(
            code="test_attempt_hour_limit",
            message="За этот час уже было три неверных ответа.",
            http_status=429,
            details=_limit_receipt(
                policy, hour_count=hour_count, day_count=day_count
            ).payload(),
        )
    if policy.max_per_day is not None and day_count >= policy.max_per_day:
        raise TestSubmissionRejected(
            code="test_attempt_day_limit",
            message="На сегодня попытки закончились.",
            http_status=429,
            details=_limit_receipt(
                policy, hour_count=hour_count, day_count=day_count
            ).payload(),
        )


def _history_outcome(
    *, parse_status: str, check_status: str, verdict: int | None
) -> str:
    if parse_status == "invalid_format":
        if check_status != "checked" or verdict is not None:
            raise TestSubmissionRepositoryError(
                "stored invalid-format attempt state is inconsistent"
            )
        return "invalid_format"
    if parse_status != "valid":
        raise TestSubmissionRepositoryError("stored attempt parse status is invalid")
    if check_status == "pending_configuration":
        if verdict is not None:
            raise TestSubmissionRepositoryError(
                "stored pending attempt exposes a verdict"
            )
        return "pending_configuration"
    if check_status == "failed":
        if verdict is not None:
            raise TestSubmissionRepositoryError(
                "stored failed attempt exposes a verdict"
            )
        return "checker_failed"
    if check_status == "checked":
        if verdict == int(VERDICT.SOLVED):
            return "correct"
        if verdict == int(VERDICT.WRONG_ANSWER):
            return "wrong"
        raise TestSubmissionRepositoryError("stored checked attempt verdict is invalid")
    if check_status == "pending":
        raise TestSubmissionRepositoryError(
            "pending asynchronous check has no Student outcome contract yet"
        )
    raise TestSubmissionRepositoryError("stored attempt check status is invalid")


def _stored_attempt_messages(
    response_json: object,
    *,
    attempt_public_id: str,
    current_outcome: str,
) -> tuple[str | None, str | None]:
    if response_json is None:
        return None, None
    try:
        payload = json.loads(str(response_json))
    except json.JSONDecodeError, RecursionError:
        return None, None
    if (
        not isinstance(payload, dict)
        or payload.get("attemptId") != attempt_public_id
        or payload.get("outcome") != current_outcome
    ):
        # A future admin recheck can change authoritative attempt state. Never
        # pair it with stale user-facing copy from the original receipt.
        return None, None
    feedback = payload.get("feedback")
    checker_message = payload.get("checkerMessage")
    return (
        feedback if isinstance(feedback, str) else None,
        checker_message if isinstance(checker_message, str) else None,
    )


def _history_record(row: Mapping[str, object]) -> TestAttemptHistoryRecord:
    try:
        answer_payload = json.loads(str(row["answer_payload_json"]))
    except (json.JSONDecodeError, KeyError, RecursionError) as error:
        raise TestSubmissionRepositoryError(
            "stored test attempt answer payload is invalid"
        ) from error
    if not isinstance(answer_payload, dict) or not isinstance(
        answer_payload.get("displayAnswer"), str
    ):
        raise TestSubmissionRepositoryError(
            "stored test attempt display answer is invalid"
        )
    verdict = None if row["verdict"] is None else int(row["verdict"])
    outcome = _history_outcome(
        parse_status=str(row["parse_status"]),
        check_status=str(row["check_status"]),
        verdict=verdict,
    )
    attempt_public_id = str(row["attempt_public_id"])
    feedback, checker_message = _stored_attempt_messages(
        row["response_json"],
        attempt_public_id=attempt_public_id,
        current_outcome=outcome,
    )
    return TestAttemptHistoryRecord(
        attempt_public_id=attempt_public_id,
        problem_public_id=str(row["problem_public_id"]),
        condition_revision_public_id=str(row["condition_revision_public_id"]),
        config_version=int(row["config_version"]),
        outcome=outcome,
        check_status=str(row["check_status"]),
        display_answer=str(answer_payload["displayAnswer"]),
        feedback=feedback,
        checker_message=checker_message,
        verdict=verdict,
        result_version=None if row["result_id"] is None else 1,
        client_created_at=str(row["client_created_at"]),
        server_received_at=str(row["server_received_at"]),
        clock_suspicious=bool(row["clock_suspicious"]),
    )


def _list_test_attempt_history(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    problem_public_id: str,
    cursor: str | None,
    limit: int,
    now: datetime,
) -> TestAttemptHistoryPage:
    account = connection.execute(
        "SELECT linked_user_id FROM auth_accounts WHERE id = ? "
        "AND audience = 'student' AND status = 'active' "
        "AND linked_user_id IS NOT NULL",
        (account_id,),
    ).fetchone()
    if account is None:
        raise TestSubmissionRejected(
            code="test_problem_not_found",
            message="Тестовая задача недоступна.",
            http_status=404,
        )
    student_user_id = int(account["linked_user_id"])
    problem = connection.execute(
        "SELECT id FROM problems WHERE public_id = ?",
        (problem_public_id,),
    ).fetchone()
    if problem is None:
        raise TestSubmissionRejected(
            code="test_problem_not_found",
            message="Тестовая задача недоступна.",
            http_status=404,
        )
    problem_id = int(problem["id"])
    has_history = connection.execute(
        "SELECT 1 FROM test_attempts WHERE student_user_id = ? "
        "AND problem_id = ? LIMIT 1",
        (student_user_id, problem_id),
    ).fetchone()
    if has_history is None:
        # An empty history is visible only while the exact published problem
        # remains available. Historical attempts themselves are sufficient
        # authority after group access is later revoked.
        _resolve_context(
            connection,
            account_id=account_id,
            problem_public_id=problem_public_id,
            now=now,
        )

    cursor_timestamp: str | None = None
    cursor_id: int | None = None
    if cursor is not None:
        cursor_row = connection.execute(
            "SELECT id, server_received_at FROM test_attempts "
            "WHERE public_id = ? AND student_user_id = ? AND problem_id = ?",
            (cursor, student_user_id, problem_id),
        ).fetchone()
        if cursor_row is None:
            raise TestSubmissionRejected(
                code="test_attempt_cursor_invalid",
                message="История ответов изменилась. Обновите страницу.",
                http_status=422,
            )
        cursor_timestamp = str(cursor_row["server_received_at"])
        cursor_id = int(cursor_row["id"])

    rows = connection.execute(
        "SELECT attempt.id AS attempt_id, "
        "attempt.public_id AS attempt_public_id, "
        "problem.public_id AS problem_public_id, "
        "condition_revision.public_id AS condition_revision_public_id, "
        "problem_revision.config_version, attempt.answer_payload_json, "
        "attempt.parse_status, attempt.check_status, attempt.client_created_at, "
        "attempt.server_received_at, attempt.clock_suspicious, attempt.verdict, "
        "attempt.result_id, "
        "(SELECT idempotency.response_json "
        " FROM idempotency_records AS idempotency "
        " JOIN auth_accounts AS attempt_account "
        "   ON attempt_account.id = idempotency.account_id "
        "  AND attempt_account.audience = 'student' "
        "  AND attempt_account.linked_user_id = attempt.student_user_id "
        " WHERE idempotency.operation = ? "
        "   AND idempotency.idempotency_key = attempt.idempotency_key "
        "   AND idempotency.payload_sha256 = attempt.payload_sha256 "
        "   AND idempotency.state = 'completed' "
        " ORDER BY idempotency.id DESC LIMIT 1) AS response_json "
        "FROM test_attempts AS attempt "
        "JOIN problems AS problem ON problem.id = attempt.problem_id "
        "JOIN problem_revisions AS problem_revision "
        "  ON problem_revision.id = attempt.problem_revision_id "
        " AND problem_revision.problem_id = attempt.problem_id "
        "JOIN content_revisions AS condition_revision "
        "  ON condition_revision.id = problem_revision.content_revision_id "
        "WHERE attempt.student_user_id = ? AND attempt.problem_id = ? "
        "AND (? IS NULL OR attempt.server_received_at < ? "
        "     OR (attempt.server_received_at = ? AND attempt.id < ?)) "
        "ORDER BY attempt.server_received_at DESC, attempt.id DESC LIMIT ?",
        (
            IDEMPOTENCY_OPERATION,
            student_user_id,
            problem_id,
            cursor_timestamp,
            cursor_timestamp,
            cursor_timestamp,
            cursor_id,
            limit + 1,
        ),
    ).fetchall()
    page_rows = rows[:limit]
    attempts = tuple(_history_record(row) for row in page_rows)
    next_cursor = (
        None if len(rows) <= limit or not attempts else attempts[-1].attempt_public_id
    )
    return TestAttemptHistoryPage(
        problem_public_id=problem_public_id,
        attempts=attempts,
        next_cursor=next_cursor,
    )


class PwaTestSubmissionRepository:
    """Async-facing submission repository with transaction-scoped retries."""

    def __init__(
        self,
        factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        trusted_checker_executor: TrustedCheckerExecutor | None = None,
    ) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._trusted_checker_executor = (
            trusted_checker_executor or TrustedCheckerExecutor()
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("submission repository clock must be timezone-aware")
        return now.astimezone(UTC)

    async def get_test_answer_input(
        self,
        *,
        account_id: int,
        problem_public_id: str,
    ) -> TestAnswerInputRecord:
        """Return only the safe input affordance for the current revision."""

        if account_id < 1:
            raise ValueError("account ID must be positive")
        if not _PUBLIC_ID.fullmatch(problem_public_id):
            raise ValueError("problem public ID is invalid")
        context = await self._factory.run_read_async(
            lambda connection: _resolve_context(
                connection,
                account_id=account_id,
                problem_public_id=problem_public_id,
                now=self._now(),
            )
        )
        config = context.answer_config
        if config.answer_type is ANS_TYPE.SELECT_ONE:
            options = tuple(
                option.strip()
                for option in (config.answer_validation or "").split(";")
                if option.strip()
            )
            if not options:
                raise SubmissionConfigurationError(
                    "select-one problem has no visible options"
                )
            validation_pattern = None
        else:
            options = ()
            validation_pattern = config.answer_validation
        return TestAnswerInputRecord(
            problem_public_id=context.problem_public_id,
            condition_revision_public_id=context.condition_revision_public_id,
            config_version=context.config_version,
            answer_type=int(config.answer_type),
            validation_pattern=validation_pattern,
            validation_error=config.validation_error,
            options=options,
        )

    async def submit_test_answer(
        self, command: SubmitTestAnswerCommand
    ) -> TestAttemptReceipt:
        now = self._now()
        request_payload = _request_payload(command)
        payload_sha256 = _payload_hash(request_payload)

        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            return _return_or_raise_replay(replay)

        context = await self._factory.run_read_async(
            lambda connection: _resolve_context(
                connection,
                account_id=command.account_id,
                problem_public_id=command.problem_public_id,
                now=now,
            )
        )
        _require_expected_revision(command, context)
        evaluation = await asyncio.to_thread(
            evaluate_test_answer,
            context.answer_config,
            command.display_answer,
            trusted_executor=self._trusted_checker_executor,
        )

        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_submission(
                connection,
                command=command,
                initial_context=context,
                evaluation=evaluation,
                now=now,
                request_payload=request_payload,
                payload_sha256=payload_sha256,
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    async def list_test_attempts(
        self,
        *,
        account_id: int,
        problem_public_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> TestAttemptHistoryPage:
        if account_id < 1:
            raise ValueError("account ID must be positive")
        if not _PUBLIC_ID.fullmatch(problem_public_id):
            raise ValueError("problem public ID is invalid")
        if cursor is not None and not _PUBLIC_ID.fullmatch(cursor):
            raise ValueError("test attempt cursor is invalid")
        if not 1 <= limit <= 50:
            raise ValueError("test attempt history limit must be between 1 and 50")
        now = self._now()
        return await self._factory.run_read_async(
            lambda connection: _list_test_attempt_history(
                connection,
                account_id=account_id,
                problem_public_id=problem_public_id,
                cursor=cursor,
                limit=limit,
                now=now,
            )
        )

    async def get_test_attempt_recheck_preview(
        self, *, problem_public_id: str
    ) -> TestAttemptRecheckPreview:
        """Return the current published checker revision and all saved attempts."""

        if not _PUBLIC_ID.fullmatch(problem_public_id):
            raise ValueError("problem public ID is invalid")

        def read(connection: sqlite3.Connection) -> TestAttemptRecheckPreview:
            context = _resolve_recheck_context(
                connection, problem_public_id=problem_public_id
            )
            attempts = connection.execute(
                "SELECT count(*) AS n FROM test_attempts "
                "WHERE problem_id = ?",
                (context.problem_id,),
            ).fetchone()
            return TestAttemptRecheckPreview(
                problem_public_id=context.problem_public_id,
                condition_revision_public_id=(context.condition_revision_public_id),
                config_version=context.config_version,
                course_public_id=context.course_public_id,
                group_public_id=context.group_public_id,
                pending_attempts=int(attempts["n"]),
            )

        return await self._factory.run_read_async(read)

    async def recheck_pending_test_attempts(
        self,
        *,
        problem_public_id: str,
        expected_condition_revision_public_id: str,
        expected_config_version: int,
        actor_user_id: int,
    ) -> TestAttemptRecheckReceipt:
        """Re-evaluate every saved answer against the current configuration.

        Answer payloads stay immutable, but verdicts are current projections:
        a corrected answer key can turn an old success into a wrong answer.
        """

        if not _PUBLIC_ID.fullmatch(problem_public_id):
            raise ValueError("problem public ID is invalid")
        if not _PUBLIC_ID.fullmatch(expected_condition_revision_public_id):
            raise ValueError("expected condition revision public ID is invalid")
        if type(expected_config_version) is not int or expected_config_version < 1:
            raise ValueError("expected config version must be positive")
        if actor_user_id < 1:
            raise ValueError("actor user ID must be positive")

        def read_recheck(
            connection: sqlite3.Connection,
        ) -> tuple[_RecheckContext, tuple[_PendingAttempt, ...]]:
            current = _resolve_recheck_context(
                connection, problem_public_id=problem_public_id
            )
            return current, _recheckable_attempts(
                connection,
                problem_id=current.problem_id,
                current_checker_version=checker_version(current.answer_config),
            )

        context, pending_attempts = await self._factory.run_read_async(read_recheck)
        if (
            context.condition_revision_public_id
            != expected_condition_revision_public_id
            or context.config_version != expected_config_version
        ):
            raise TestSubmissionRejected(
                code="test_problem_revision_changed",
                message="Настройки задачи изменились. Обновите страницу.",
                http_status=409,
            )

        evaluations = await asyncio.to_thread(
            lambda: tuple(
                (
                    attempt,
                    evaluate_test_answer(
                        context.answer_config,
                        attempt.display_answer,
                        trusted_executor=self._trusted_checker_executor,
                    ),
                )
                for attempt in pending_attempts
            )
        )
        checked_at = self._now()
        return await self._factory.run_write_async(
            lambda connection: self._write_recheck(
                connection,
                initial_context=context,
                expected_condition_revision_public_id=(
                    expected_condition_revision_public_id
                ),
                expected_config_version=expected_config_version,
                actor_user_id=actor_user_id,
                checked_at=checked_at,
                evaluations=evaluations,
            )
        )

    @staticmethod
    def _write_recheck(
        connection: sqlite3.Connection,
        *,
        initial_context: _RecheckContext,
        expected_condition_revision_public_id: str,
        expected_config_version: int,
        actor_user_id: int,
        checked_at: datetime,
        evaluations: tuple[tuple[_PendingAttempt, TestAnswerEvaluation], ...],
    ) -> TestAttemptRecheckReceipt:
        context = _resolve_recheck_context(
            connection,
            problem_public_id=initial_context.problem_public_id,
        )
        if (
            context != initial_context
            or context.condition_revision_public_id
            != expected_condition_revision_public_id
            or context.config_version != expected_config_version
        ):
            raise TestSubmissionRejected(
                code="test_problem_revision_changed",
                message="Настройки задачи изменились. Обновите страницу.",
                http_status=409,
            )

        checked_timestamp = _timestamp(checked_at)
        checked = correct = wrong = skipped_concurrent = 0
        affected_student_user_ids: set[int] = set()
        for attempt, evaluation in evaluations:
            if evaluation.outcome not in {
                TestAnswerOutcome.CORRECT,
                TestAnswerOutcome.WRONG,
            }:
                continue
            current = connection.execute(
                "SELECT id FROM test_attempts WHERE id = ? AND problem_id = ? AND ("
                "check_status = 'pending_configuration' "
                "OR (check_status = 'checked' AND checker_version <> ?))",
                (
                    attempt.id,
                    context.problem_id,
                    evaluation.checker_version,
                ),
            ).fetchone()
            if current is None:
                skipped_concurrent += 1
                continue
            if evaluation.verdict is None or evaluation.checker_version is None:
                raise TestSubmissionRepositoryError(
                    "checked re-evaluation has no verdict or checker version"
                )
            result_id = int(
                connection.execute(
                    "INSERT INTO results "
                    "(student_id, problem_id, group_id, lesson, teacher_id, ts, "
                    "verdict, answer, res_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "RETURNING id",
                    (
                        attempt.student_user_id,
                        context.problem_id,
                        context.group_id,
                        context.lesson_number,
                        actor_user_id,
                        checked_timestamp,
                        int(evaluation.verdict),
                        attempt.display_answer,
                        int(RES_TYPE.TEST),
                    ),
                ).fetchone()["id"]
            )
            connection.execute(
                "UPDATE test_attempts SET check_status = 'checked', "
                "checker_version = ?, verdict = ?, result_id = ?, checked_at = ? "
                "WHERE id = ?",
                (
                    evaluation.checker_version,
                    int(evaluation.verdict),
                    result_id,
                    checked_timestamp,
                    attempt.id,
                ),
            )
            checked += 1
            if evaluation.outcome is TestAnswerOutcome.CORRECT:
                correct += 1
            else:
                wrong += 1
            affected_student_user_ids.add(attempt.student_user_id)

        pending = connection.execute(
            "SELECT count(*) AS n FROM test_attempts WHERE problem_id = ? "
            "AND check_status = 'pending_configuration'",
            (context.problem_id,),
        ).fetchone()
        account_public_ids: tuple[str, ...] = ()
        if affected_student_user_ids:
            placeholders = ",".join("?" for _ in affected_student_user_ids)
            rows = connection.execute(
                "SELECT public_id FROM auth_accounts WHERE audience = 'student' "
                "AND linked_user_id IN (" + placeholders + ") ORDER BY public_id",
                tuple(sorted(affected_student_user_ids)),
            ).fetchall()
            account_public_ids = tuple(str(row["public_id"]) for row in rows)
        return TestAttemptRecheckReceipt(
            problem_public_id=context.problem_public_id,
            condition_revision_public_id=context.condition_revision_public_id,
            config_version=context.config_version,
            pending_before=len(evaluations),
            checked=checked,
            correct=correct,
            wrong=wrong,
            still_pending=int(pending["n"]),
            skipped_concurrent=skipped_concurrent,
            owner_account_public_ids=account_public_ids,
        )

    def _write_submission(
        self,
        connection: sqlite3.Connection,
        *,
        command: SubmitTestAnswerCommand,
        initial_context: _SubmissionContext,
        evaluation: TestAnswerEvaluation,
        now: datetime,
        request_payload: Mapping[str, object],
        payload_sha256: str,
    ) -> tuple[TestAttemptReceipt | None, TestSubmissionRejected | None]:
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
        )
        if replay is not None:
            try:
                return _return_or_raise_replay(replay), None
            except TestSubmissionRejected as error:
                return None, error

        created_at = _timestamp(now)
        record_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, "
                "payload_sha256, state, created_at) VALUES "
                "('student', ?, ?, ?, ?, 'processing', ?) RETURNING id",
                (
                    command.account_id,
                    IDEMPOTENCY_OPERATION,
                    command.idempotency_key,
                    payload_sha256,
                    created_at,
                ),
            ).fetchone()["id"]
        )

        try:
            context = _resolve_context(
                connection,
                account_id=command.account_id,
                problem_public_id=command.problem_public_id,
                now=now,
            )
            if context != initial_context:
                raise TestSubmissionRejected(
                    code="test_problem_revision_changed",
                    message="Условие задачи изменилось. Обновите страницу.",
                    http_status=409,
                )
            clock = assess_submission_clock(
                client_created_at=command.client_created_at,
                server_received_at=now,
                submission_closes_at=context.submission_closes_at,
            )
            if not clock.timely:
                raise TestSubmissionRejected(
                    code="submission_deadline_passed",
                    message="Срок сдачи этой задачи уже закончился.",
                    http_status=409,
                    details={
                        "submissionClosesAt": _timestamp(context.submission_closes_at)
                    },
                )

            hour_start, day_start = _attempt_boundaries(now, context.business_timezone)
            hour_count, day_count = _attempt_counts(
                connection,
                student_user_id=context.student_user_id,
                problem_id=context.problem_id,
                hour_start=hour_start,
                day_start=day_start,
            )
            if evaluation.counts_as_attempt:
                _raise_if_limited(
                    context.attempt_policy,
                    hour_count=hour_count,
                    day_count=day_count,
                )

            result_id: int | None = None
            checked_at: str | None = None
            if evaluation.verdict is not None:
                result_id = int(
                    connection.execute(
                        "INSERT INTO results "
                        "(student_id, problem_id, group_id, lesson, teacher_id, "
                        "ts, verdict, answer, res_type) VALUES "
                        "(?, ?, ?, ?, NULL, ?, ?, ?, ?) RETURNING id",
                        (
                            context.student_user_id,
                            context.problem_id,
                            context.group_id,
                            context.lesson_number,
                            created_at,
                            int(evaluation.verdict),
                            evaluation.display_answer,
                            int(RES_TYPE.TEST),
                        ),
                    ).fetchone()["id"]
                )
                checked_at = created_at
            elif evaluation.check_status.value in {"checked", "failed"}:
                checked_at = created_at

            row = connection.execute(
                "INSERT INTO test_attempts "
                "(student_user_id, problem_id, problem_revision_id, "
                "answer_payload_json, normalized_answer_json, parse_status, "
                "counts_as_attempt, check_status, client_created_at, "
                "server_received_at, clock_skew_seconds, clock_suspicious, "
                "idempotency_key, payload_sha256, checker_version, verdict, "
                "result_id, created_at, checked_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "RETURNING public_id",
                (
                    context.student_user_id,
                    context.problem_id,
                    context.problem_revision_id,
                    _canonical_json(request_payload),
                    (
                        None
                        if evaluation.normalized_answer is None
                        else _canonical_json(evaluation.normalized_answer)
                    ),
                    evaluation.parse_status.value,
                    int(evaluation.counts_as_attempt),
                    evaluation.check_status.value,
                    _timestamp(command.client_created_at),
                    created_at,
                    clock.skew_seconds,
                    int(clock.suspicious),
                    command.idempotency_key,
                    payload_sha256,
                    evaluation.checker_version,
                    None if evaluation.verdict is None else int(evaluation.verdict),
                    result_id,
                    created_at,
                    checked_at,
                ),
            ).fetchone()
            attempt_public_id = str(row["public_id"])
            if evaluation.counts_as_attempt:
                if evaluation.verdict == VERDICT.WRONG_ANSWER:
                    hour_count += 1
                day_count += 1
            receipt = TestAttemptReceipt(
                attempt_public_id=attempt_public_id,
                problem_public_id=context.problem_public_id,
                condition_revision_public_id=(context.condition_revision_public_id),
                config_version=context.config_version,
                outcome=evaluation.outcome.value,
                display_answer=evaluation.display_answer,
                feedback=evaluation.feedback,
                checker_message=evaluation.checker_message,
                verdict=(
                    None if evaluation.verdict is None else int(evaluation.verdict)
                ),
                client_created_at=_timestamp(command.client_created_at),
                server_received_at=created_at,
                clock_suspicious=clock.suspicious,
                attempts=_limit_receipt(
                    context.attempt_policy,
                    hour_count=hour_count,
                    day_count=day_count,
                ),
            )
        except TestSubmissionRejected as error:
            self._complete_idempotency(
                connection,
                record_id=record_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=created_at,
            )
            return None, error

        self._complete_idempotency(
            connection,
            record_id=record_id,
            state="completed",
            http_status=201,
            response=receipt.response_payload(),
            completed_at=created_at,
        )
        return receipt, None

    @staticmethod
    def _complete_idempotency(
        connection: sqlite3.Connection,
        *,
        record_id: int,
        state: str,
        http_status: int,
        response: Mapping[str, object],
        completed_at: str,
    ) -> None:
        connection.execute(
            "UPDATE idempotency_records SET state = ?, http_status = ?, "
            "response_json = ?, completed_at = ? WHERE id = ?",
            (
                state,
                http_status,
                _canonical_json(response),
                completed_at,
                record_id,
            ),
        )


__all__ = [
    "IDEMPOTENCY_OPERATION",
    "AttemptLimitReceipt",
    "IdempotencyPayloadMismatch",
    "PwaTestSubmissionRepository",
    "SubmitTestAnswerCommand",
    "TestAttemptHistoryPage",
    "TestAttemptHistoryRecord",
    "TestAttemptRecheckPreview",
    "TestAttemptRecheckReceipt",
    "TestAttemptReceipt",
    "TestSubmissionRejected",
    "TestSubmissionRepositoryError",
]
