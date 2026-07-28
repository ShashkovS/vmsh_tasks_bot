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
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from helpers.consts import RES_TYPE
from helpers.pwa.test_checkers import TrustedCheckerExecutor
from models.pwa.submissions import (
    SubmissionConfigurationError,
    TestAnswerEvaluation,
    TestAttemptPolicy,
    TestProblemAnswerConfig,
    assess_submission_clock,
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
            )
        except (KeyError, TypeError, ValueError) as error:
            raise TestSubmissionRepositoryError(
                "stored idempotency success response is invalid"
            ) from error


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
    return {
        "schemaVersion": 1,
        "problemId": command.problem_public_id,
        "displayAnswer": command.display_answer.strip(),
        "clientCreatedAt": _timestamp(command.client_created_at),
    }


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
        "SELECT count(*) FILTER (WHERE server_received_at >= ?) AS hour_count, "
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
            message="Слишком много попыток за последний час.",
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


class PwaTestSubmissionRepository:
    """Async-facing submission repository with transaction-scoped retries."""

    def __init__(
        self,
        factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        public_id_factory: Callable[[], str] | None = None,
        trusted_checker_executor: TrustedCheckerExecutor | None = None,
    ) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._public_id_factory = public_id_factory or (
            lambda: f"attempt-{uuid.uuid4().hex}"
        )
        self._trusted_checker_executor = (
            trusted_checker_executor or TrustedCheckerExecutor()
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("submission repository clock must be timezone-aware")
        return now.astimezone(UTC)

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

            attempt_public_id = self._public_id_factory()
            if not _PUBLIC_ID.fullmatch(attempt_public_id):
                raise TestSubmissionRepositoryError(
                    "attempt public ID factory returned an invalid value"
                )
            connection.execute(
                "INSERT INTO test_attempts "
                "(public_id, student_user_id, problem_id, problem_revision_id, "
                "answer_payload_json, normalized_answer_json, parse_status, "
                "counts_as_attempt, check_status, client_created_at, "
                "server_received_at, clock_skew_seconds, clock_suspicious, "
                "idempotency_key, payload_sha256, checker_version, verdict, "
                "result_id, created_at, checked_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_public_id,
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
            )
            if evaluation.counts_as_attempt:
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
    "TestAttemptReceipt",
    "TestSubmissionRejected",
    "TestSubmissionRepositoryError",
]
