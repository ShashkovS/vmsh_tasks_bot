"""Pure domain policy for PWA test-answer submissions.

This module owns parsing and verdict semantics only.  HTTP, SQLite,
idempotency, attempt limits and Telegram delivery remain adapters around it.
The historical answer vocabulary comes from :mod:`helpers.consts`; the
comparison functions remain shared with the current bot in
:mod:`helpers.checkers`.

Authoritative requirements:
``vmshpwa/dev/development-plan/08-phase-4-test-submissions.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from helpers.checkers import ANS_CHECKER, ANS_REGEX
from helpers.consts import ANS_TYPE, VERDICT
from helpers.pwa.test_checkers import (
    TRUSTED_CHECKER_PATTERN,
    TrustedCheckerExecutor,
    TrustedCheckerStatus,
)


NORMALIZED_ANSWER_SCHEMA_VERSION = 1
CHECKER_POLICY_VERSION = "pwa-test-checker-v1"
SELECT_ONE_COMPATIBILITY_LIMIT = 24


class SubmissionConfigurationError(ValueError):
    """Stored answer metadata cannot be interpreted safely."""


class TestAttemptParseStatus(StrEnum):
    VALID = "valid"
    INVALID_FORMAT = "invalid_format"


class TestAttemptCheckStatus(StrEnum):
    PENDING_CONFIGURATION = "pending_configuration"
    CHECKED = "checked"
    FAILED = "failed"


class TestAnswerOutcome(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    INVALID_FORMAT = "invalid_format"
    PENDING_CONFIGURATION = "pending_configuration"
    CHECKER_FAILED = "checker_failed"


@dataclass(frozen=True, slots=True)
class TestProblemAnswerConfig:
    answer_type: ANS_TYPE
    answer_validation: str | None
    validation_error: str | None
    correct_answer: str | None
    correct_answer_checker: str | None
    wrong_answer: str | None
    congratulation: str | None

    @classmethod
    def from_revision(
        cls,
        *,
        answer_type: int,
        answer_config: Mapping[str, object],
    ) -> "TestProblemAnswerConfig":
        try:
            resolved_type = ANS_TYPE(answer_type)
        except (TypeError, ValueError) as error:
            raise SubmissionConfigurationError("unknown answer type") from error

        def optional_text(name: str) -> str | None:
            value = answer_config.get(name)
            if value is None:
                return None
            if not isinstance(value, str):
                raise SubmissionConfigurationError(f"{name} must be text or null")
            normalized = value.strip()
            return normalized or None

        return cls(
            answer_type=resolved_type,
            answer_validation=optional_text("answerValidation"),
            validation_error=optional_text("validationError"),
            correct_answer=optional_text("correctAnswer"),
            correct_answer_checker=optional_text("correctAnswerChecker"),
            wrong_answer=optional_text("wrongAnswer"),
            congratulation=optional_text("congratulation"),
        )


@dataclass(frozen=True, slots=True)
class TestAnswerEvaluation:
    display_answer: str
    normalized_answer: Mapping[str, object] | None
    parse_status: TestAttemptParseStatus
    counts_as_attempt: bool
    check_status: TestAttemptCheckStatus
    outcome: TestAnswerOutcome
    checker_version: str | None
    verdict: VERDICT | None
    feedback: str | None
    checker_message: str | None = None
    diagnostic_code: str | None = None


@dataclass(frozen=True, slots=True)
class SubmissionClockAssessment:
    skew_seconds: int
    suspicious: bool
    timely: bool


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def assess_submission_clock(
    *,
    client_created_at: datetime,
    server_received_at: datetime,
    submission_closes_at: datetime,
) -> SubmissionClockAssessment:
    """Use client creation time for the cutoff and retain skew diagnostics."""

    client_created_at = _require_aware(client_created_at, label="client creation time")
    server_received_at = _require_aware(server_received_at, label="server receipt time")
    submission_closes_at = _require_aware(
        submission_closes_at, label="submission cutoff"
    )
    skew_seconds = round((server_received_at - client_created_at).total_seconds())
    return SubmissionClockAssessment(
        skew_seconds=skew_seconds,
        suspicious=abs(skew_seconds) > 3600,
        timely=client_created_at <= submission_closes_at,
    )


def normalized_answer_payload(
    *, answer_type: ANS_TYPE, display_answer: str, value: object | None = None
) -> Mapping[str, object]:
    return {
        "schemaVersion": NORMALIZED_ANSWER_SCHEMA_VERSION,
        "answerType": int(answer_type),
        "displayAnswer": display_answer,
        "value": display_answer if value is None else value,
    }


def checker_version(config: TestProblemAnswerConfig) -> str:
    material = {
        "policy": CHECKER_POLICY_VERSION,
        "answerType": int(config.answer_type),
        "answerValidation": config.answer_validation,
        "correctAnswer": config.correct_answer,
        "correctAnswerChecker": config.correct_answer_checker,
    }
    digest = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{CHECKER_POLICY_VERSION}:{digest}"


def _invalid_format(
    config: TestProblemAnswerConfig, display_answer: str
) -> TestAnswerEvaluation:
    return TestAnswerEvaluation(
        display_answer=display_answer,
        normalized_answer=None,
        parse_status=TestAttemptParseStatus.INVALID_FORMAT,
        counts_as_attempt=False,
        check_status=TestAttemptCheckStatus.CHECKED,
        outcome=TestAnswerOutcome.INVALID_FORMAT,
        checker_version=None,
        verdict=None,
        feedback=config.validation_error or "Проверьте формат ответа.",
    )


def _pending_configuration(
    config: TestProblemAnswerConfig,
    display_answer: str,
    *,
    normalized_value: object | None = None,
    diagnostic_code: str,
) -> TestAnswerEvaluation:
    return TestAnswerEvaluation(
        display_answer=display_answer,
        normalized_answer=normalized_answer_payload(
            answer_type=config.answer_type,
            display_answer=display_answer,
            value=normalized_value,
        ),
        parse_status=TestAttemptParseStatus.VALID,
        counts_as_attempt=True,
        check_status=TestAttemptCheckStatus.PENDING_CONFIGURATION,
        outcome=TestAnswerOutcome.PENDING_CONFIGURATION,
        checker_version=None,
        verdict=None,
        feedback="Ответ принят и ожидает настройки проверки.",
        diagnostic_code=diagnostic_code,
    )


def _checked(
    config: TestProblemAnswerConfig,
    display_answer: str,
    *,
    normalized_value: object | None,
    correct: bool,
    checker_message: str | None = None,
) -> TestAnswerEvaluation:
    return TestAnswerEvaluation(
        display_answer=display_answer,
        normalized_answer=normalized_answer_payload(
            answer_type=config.answer_type,
            display_answer=display_answer,
            value=normalized_value,
        ),
        parse_status=TestAttemptParseStatus.VALID,
        counts_as_attempt=True,
        check_status=TestAttemptCheckStatus.CHECKED,
        outcome=(TestAnswerOutcome.CORRECT if correct else TestAnswerOutcome.WRONG),
        checker_version=checker_version(config),
        verdict=VERDICT.SOLVED if correct else VERDICT.WRONG_ANSWER,
        feedback=(
            config.congratulation or "Да, всё верно!"
            if correct
            else config.wrong_answer or "Нет, ответ неверный."
        ),
        checker_message=checker_message,
    )


def _select_one_value(
    config: TestProblemAnswerConfig, display_answer: str
) -> str | None:
    if config.answer_validation is None:
        return None
    needle = display_answer[:SELECT_ONE_COMPATIBILITY_LIMIT].strip().casefold()
    for option in config.answer_validation.split(";"):
        visible = option.strip()
        comparable = visible[:SELECT_ONE_COMPATIBILITY_LIMIT].strip().casefold()
        if needle == comparable:
            return visible
    return None


def _is_select_one_correct(
    config: TestProblemAnswerConfig, display_answer: str
) -> bool | None:
    if config.correct_answer is None:
        return None
    needle = display_answer[:SELECT_ONE_COMPATIBILITY_LIMIT].strip().casefold()
    return any(
        needle == answer.strip()[:SELECT_ONE_COMPATIBILITY_LIMIT].strip().casefold()
        for answer in config.correct_answer.split(";")
    )


def _polynomial_check(
    student_answer: str, correct_answer: str
) -> tuple[bool, str | None]:
    checker = ANS_CHECKER[ANS_TYPE.POLYNOMIAL]
    valid, student_values = checker(student_answer)
    if not valid:
        return False, str(student_values)
    valid_correct, correct_values = checker(correct_answer)
    if not valid_correct:
        raise ValueError("configured polynomial answer is invalid")
    for x, (student_value, correct_value) in enumerate(
        zip(student_values, correct_values, strict=True), start=1
    ):
        if abs(float(student_value) - float(correct_value)) > 1e-8:
            return (
                False,
                f"В точке {x} получилось {student_value}, "
                f"а должно было получиться {correct_value}",
            )
    return True, None


def evaluate_test_answer(
    config: TestProblemAnswerConfig,
    student_answer: str | None,
    *,
    trusted_executor: TrustedCheckerExecutor | None = None,
) -> TestAnswerEvaluation:
    """Validate and check one answer using the historical fullmatch policy."""

    display_answer = "" if student_answer is None else student_answer.strip()

    if config.answer_type is ANS_TYPE.SELECT_ONE:
        selected_value = _select_one_value(config, display_answer)
        if config.answer_validation is None:
            return _pending_configuration(
                config,
                display_answer,
                diagnostic_code="select_options_missing",
            )
        if selected_value is None:
            return _invalid_format(config, display_answer)
        is_correct = _is_select_one_correct(config, selected_value)
        if is_correct is None:
            return _pending_configuration(
                config,
                display_answer,
                normalized_value=selected_value,
                diagnostic_code="correct_answer_missing",
            )
        return _checked(
            config,
            display_answer,
            normalized_value=selected_value,
            correct=is_correct,
        )

    if config.answer_validation is not None:
        try:
            validation = re.compile(config.answer_validation)
        except re.error:
            return _pending_configuration(
                config,
                display_answer,
                diagnostic_code="validation_pattern_invalid",
            )
    else:
        validation = ANS_REGEX.get(config.answer_type)
    if validation is not None and validation.fullmatch(display_answer) is None:
        return _invalid_format(config, display_answer)

    normalized = normalized_answer_payload(
        answer_type=config.answer_type,
        display_answer=display_answer,
    )
    checker_source = config.correct_answer_checker
    if checker_source and TRUSTED_CHECKER_PATTERN.match(checker_source):
        executor = trusted_executor or TrustedCheckerExecutor()
        execution = executor.execute(checker_source, display_answer)
        if execution.status is TrustedCheckerStatus.INVALID_CONFIGURATION:
            return _pending_configuration(
                config,
                display_answer,
                diagnostic_code=execution.diagnostic_code or "trusted_checker_invalid",
            )
        return _checked(
            config,
            display_answer,
            normalized_value=normalized["value"],
            correct=bool(execution.correct),
            checker_message=execution.message,
        )

    if config.correct_answer is None:
        return _pending_configuration(
            config,
            display_answer,
            diagnostic_code="correct_answer_missing",
        )

    try:
        if config.answer_type is ANS_TYPE.POLYNOMIAL:
            correct, checker_message = _polynomial_check(
                display_answer, config.correct_answer
            )
        else:
            standard_checker = ANS_CHECKER[config.answer_type]
            correct = any(
                standard_checker(display_answer, candidate)
                for candidate in config.correct_answer.split(";")
            )
            checker_message = None
    except BaseException:
        return TestAnswerEvaluation(
            display_answer=display_answer,
            normalized_answer=normalized,
            parse_status=TestAttemptParseStatus.VALID,
            counts_as_attempt=True,
            check_status=TestAttemptCheckStatus.FAILED,
            outcome=TestAnswerOutcome.CHECKER_FAILED,
            checker_version=checker_version(config),
            verdict=None,
            feedback="Ответ сохранён, но проверка временно недоступна.",
            diagnostic_code="standard_checker_failed",
        )
    return _checked(
        config,
        display_answer,
        normalized_value=normalized["value"],
        correct=correct,
        checker_message=checker_message,
    )


__all__ = [
    "CHECKER_POLICY_VERSION",
    "NORMALIZED_ANSWER_SCHEMA_VERSION",
    "SubmissionClockAssessment",
    "SubmissionConfigurationError",
    "TestAnswerEvaluation",
    "TestAnswerOutcome",
    "TestAttemptCheckStatus",
    "TestAttemptParseStatus",
    "TestProblemAnswerConfig",
    "assess_submission_clock",
    "checker_version",
    "evaluate_test_answer",
    "normalized_answer_payload",
]
