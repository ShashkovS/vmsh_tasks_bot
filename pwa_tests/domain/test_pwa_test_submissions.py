"""Phase 4 domain tests for every historical test-answer family."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from helpers.consts import ANS_TYPE, VERDICT
from helpers.pwa.test_checkers import (
    TRUSTED_CHECKER_GLOBALS,
    TrustedCheckerExecutor,
    TrustedCheckerStatus,
)
from models.pwa import submissions
from models.pwa.submissions import (
    SubmissionConfigurationError,
    TestAnswerOutcome as AnswerOutcome,
    TestAttemptCheckStatus as AttemptCheckStatus,
    TestAttemptPolicy as AttemptPolicy,
    TestAttemptParseStatus as AttemptParseStatus,
    TestProblemAnswerConfig as ProblemAnswerConfig,
    assess_submission_clock,
    evaluate_test_answer,
)


def answer_config(
    answer_type: ANS_TYPE,
    *,
    correct: str | None,
    validation: str | None = None,
    checker: str | None = None,
) -> ProblemAnswerConfig:
    return ProblemAnswerConfig(
        answer_type=answer_type,
        answer_validation=validation,
        validation_error="Введите ответ в указанном формате.",
        correct_answer=correct,
        correct_answer_checker=checker,
        wrong_answer="Нет, ответ неверный.",
        congratulation="Да, всё верно!",
    )


@pytest.mark.parametrize(
    ("answer_type", "student_answer", "correct_answer"),
    (
        (ANS_TYPE.DIGIT, "7", "7"),
        (ANS_TYPE.NATURAL, "179", "179"),
        (ANS_TYPE.INTEGER, "+7", "7"),
        (ANS_TYPE.RATIO, "10/6", "5/3"),
        (ANS_TYPE.FLOAT, "3.50", "7/2"),
        (ANS_TYPE.FRACTION, "-1.5", "-3/2"),
        (ANS_TYPE.MIXED_FRACTION, "1 2/3", "5/3"),
        (ANS_TYPE.INT_SEQ, "1, 2, 3", "1 2 3"),
        (ANS_TYPE.INT_SET, "3, 1, 1, 2", "1, 2, 3"),
        (ANS_TYPE.INT_2, "1; 2", "1 2"),
        (ANS_TYPE.INT_3, "1; 2; 3", "1 2 3"),
        (ANS_TYPE.INT_4, "1; 2; 3; 4", "1 2 3 4"),
        (ANS_TYPE.POLYNOMIAL, "n(n+1)/2", "(n^2+n)/2"),
        (ANS_TYPE.FLOAT_EPS, "0.2", "0.3+-0.1"),
        (ANS_TYPE.TIME, "12:08", "12 ч 08 мин 00 сек"),
        (ANS_TYPE.DATE, "2025-02-16", "16.02.2025"),
        (ANS_TYPE.WEEKDAY, "сб", "Суббота"),
        (ANS_TYPE.FRAC_SEQ, "1, 2/4, -3", "1, 1/2, -3"),
        (ANS_TYPE.MULTISET, "2/4, 1, 1", "1, 1/2, 1"),
        (ANS_TYPE.SYMB_EXPRESSION, "a + b", "b + a"),
        (ANS_TYPE.SYMB_EQUIV, "a + b", "b + a"),
        (ANS_TYPE.STRING, "СОК", "COK"),
    ),
    ids=lambda value: value.name if isinstance(value, ANS_TYPE) else None,
)
def test_every_non_choice_answer_type_reaches_a_checked_verdict(
    monkeypatch: pytest.MonkeyPatch,
    answer_type: ANS_TYPE,
    student_answer: str,
    correct_answer: str,
):
    if answer_type in {ANS_TYPE.SYMB_EXPRESSION, ANS_TYPE.SYMB_EQUIV}:
        monkeypatch.setitem(submissions.ANS_CHECKER, answer_type, lambda *_: True)

    result = evaluate_test_answer(
        answer_config(answer_type, correct=correct_answer),
        f"  {student_answer}  ",
    )

    assert result.display_answer == student_answer
    assert result.parse_status is AttemptParseStatus.VALID
    assert result.counts_as_attempt is True
    assert result.check_status is AttemptCheckStatus.CHECKED
    assert result.outcome is AnswerOutcome.CORRECT
    assert result.verdict is VERDICT.SOLVED
    assert result.checker_version is not None
    assert result.normalized_answer == {
        "schemaVersion": 1,
        "answerType": int(answer_type),
        "displayAnswer": student_answer,
        "value": student_answer,
    }


def test_select_one_preserves_the_visible_label_without_hidden_values():
    config = answer_config(
        ANS_TYPE.SELECT_ONE,
        correct="Нечётное",
        validation="Чётное;Нечётное",
    )

    result = evaluate_test_answer(config, "Нечётное")

    assert result.outcome is AnswerOutcome.CORRECT
    assert result.display_answer == "Нечётное"
    assert result.normalized_answer == {
        "schemaVersion": 1,
        "answerType": int(ANS_TYPE.SELECT_ONE),
        "displayAnswer": "Нечётное",
        "value": "Нечётное",
    }
    assert "odd" not in str(result.normalized_answer).casefold()


def test_select_one_keeps_historical_casefold_and_callback_length_compatibility():
    long_option = "Очень длинная видимая формулировка первого варианта"
    config = answer_config(
        ANS_TYPE.SELECT_ONE,
        correct=long_option,
        validation=f"{long_option};Другой вариант",
    )

    result = evaluate_test_answer(config, long_option[:24].swapcase())

    assert result.outcome is AnswerOutcome.CORRECT
    assert result.normalized_answer is not None
    assert result.normalized_answer["value"] == long_option


def test_custom_validation_uses_fullmatch_after_trimming():
    config = answer_config(
        ANS_TYPE.STRING,
        correct="179 орехов",
        validation=r"\d+ орех(?:а|ов)",
    )

    accepted = evaluate_test_answer(config, "  179 орехов  ")
    rejected = evaluate_test_answer(config, "ответ: 179 орехов")

    assert accepted.outcome is AnswerOutcome.CORRECT
    assert rejected.outcome is AnswerOutcome.INVALID_FORMAT
    assert rejected.counts_as_attempt is False
    assert rejected.checker_version is None
    assert rejected.normalized_answer is None
    assert rejected.feedback == config.validation_error


def test_multiple_semicolon_separated_correct_answers_are_supported():
    config = answer_config(ANS_TYPE.INTEGER, correct="7;-7;179")

    assert evaluate_test_answer(config, "-7").outcome is AnswerOutcome.CORRECT
    assert evaluate_test_answer(config, "8").outcome is AnswerOutcome.WRONG


@pytest.mark.parametrize(
    ("configuration", "diagnostic"),
    (
        (
            answer_config(ANS_TYPE.INTEGER, correct=None),
            "correct_answer_missing",
        ),
        (
            answer_config(
                ANS_TYPE.SELECT_ONE,
                correct="Да",
                validation=None,
            ),
            "select_options_missing",
        ),
        (
            answer_config(
                ANS_TYPE.STRING,
                correct="x",
                validation="[",
            ),
            "validation_pattern_invalid",
        ),
    ),
)
def test_missing_or_invalid_metadata_is_pending_configuration(
    configuration: ProblemAnswerConfig,
    diagnostic: str,
):
    result = evaluate_test_answer(configuration, "7")

    assert result.parse_status is AttemptParseStatus.VALID
    assert result.counts_as_attempt is True
    assert result.check_status is AttemptCheckStatus.PENDING_CONFIGURATION
    assert result.outcome is AnswerOutcome.PENDING_CONFIGURATION
    assert result.verdict is None
    assert result.checker_version is None
    assert result.diagnostic_code == diagnostic


def test_revision_config_parser_is_strict_and_does_not_retain_blank_metadata():
    config = ProblemAnswerConfig.from_revision(
        answer_type=int(ANS_TYPE.INTEGER),
        answer_config={
            "answerValidation": "  ",
            "validationError": " Число ",
            "correctAnswer": " 7 ",
            "correctAnswerChecker": None,
            "wrongAnswer": " Нет ",
            "congratulation": " Да ",
        },
    )

    assert config.answer_type is ANS_TYPE.INTEGER
    assert config.answer_validation is None
    assert config.correct_answer == "7"
    assert config.validation_error == "Число"
    with pytest.raises(SubmissionConfigurationError, match="unknown answer type"):
        ProblemAnswerConfig.from_revision(
            answer_type=404,
            answer_config={},
        )
    with pytest.raises(SubmissionConfigurationError, match="unknown answer type"):
        ProblemAnswerConfig.from_revision(
            answer_type=True,
            answer_config={},
        )
    with pytest.raises(SubmissionConfigurationError, match="must be text"):
        ProblemAnswerConfig.from_revision(
            answer_type=int(ANS_TYPE.INTEGER),
            answer_config={"correctAnswer": 7},
        )


def test_trusted_checker_uses_trimmed_answer_and_returns_optional_message():
    source = """
def check_answer(answer):
    return answer == '179', 'Проверено специальной функцией'
"""
    executor = TrustedCheckerExecutor()
    config = answer_config(
        ANS_TYPE.STRING,
        correct=None,
        checker=source,
    )

    result = evaluate_test_answer(config, " 179 ", trusted_executor=executor)

    assert result.outcome is AnswerOutcome.CORRECT
    assert result.checker_message == "Проверено специальной функцией"
    assert result.checker_version is not None
    assert executor.cache_size == 1
    assert (
        evaluate_test_answer(config, "179", trusted_executor=executor).outcome
        is AnswerOutcome.CORRECT
    )
    assert executor.cache_size == 1


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    (
        ("def broken(", "compile_or_exec_failed"),
        (
            "def check(answer):\n    return True, None\nlater = 179",
            "created_value_not_callable",
        ),
        (
            "def check(answer):\n    return missing_name(answer)",
            "call_failed",
        ),
        (
            "def check(answer):\n    return True",
            "invalid_result_shape",
        ),
        (
            "def check(answer):\n    return 1, None",
            "invalid_result_shape",
        ),
    ),
)
def test_trusted_checker_failures_are_redacted_pending_configuration(
    source: str,
    diagnostic: str,
):
    result = evaluate_test_answer(
        answer_config(ANS_TYPE.STRING, correct=None, checker=source),
        "179",
    )

    assert result.outcome is AnswerOutcome.PENDING_CONFIGURATION
    assert result.check_status is AttemptCheckStatus.PENDING_CONFIGURATION
    assert result.diagnostic_code == diagnostic
    assert source not in (result.feedback or "")
    assert "traceback" not in (result.feedback or "").casefold()


def test_trusted_checker_globals_match_the_historical_allowlist():
    assert set(TRUSTED_CHECKER_GLOBALS) == {
        "__builtins__",
        "re",
        "bool",
        "float",
        "int",
        "list",
        "range",
        "set",
        "str",
        "tuple",
        "abs",
        "all",
        "any",
        "bin",
        "enumerate",
        "format",
        "len",
        "max",
        "min",
        "round",
        "sorted",
        "sum",
        "map",
        "literal_eval",
    }
    executor = TrustedCheckerExecutor()
    execution = executor.execute(
        "def check(answer):\n    return bool(re.fullmatch(r'\\d+', answer)), None",
        "179",
    )
    assert execution.status is TrustedCheckerStatus.CHECKED
    assert execution.correct is True


def test_non_function_checker_text_keeps_legacy_standard_checker_fallback():
    config = answer_config(
        ANS_TYPE.INTEGER,
        correct="179",
        checker="return True",
    )

    result = evaluate_test_answer(config, "179")

    assert result.outcome is AnswerOutcome.CORRECT
    direct = TrustedCheckerExecutor().execute("return True", "179")
    assert direct.status is TrustedCheckerStatus.INVALID_CONFIGURATION
    assert direct.diagnostic_code == "not_a_function"


def test_standard_checker_failure_is_recorded_without_a_false_verdict(
    monkeypatch: pytest.MonkeyPatch,
):
    def fail(*_args):
        raise RuntimeError("synthetic checker failure")

    monkeypatch.setitem(submissions.ANS_CHECKER, ANS_TYPE.STRING, fail)
    result = evaluate_test_answer(
        answer_config(ANS_TYPE.STRING, correct="179"),
        "179",
    )

    assert result.check_status is AttemptCheckStatus.FAILED
    assert result.outcome is AnswerOutcome.CHECKER_FAILED
    assert result.verdict is None
    assert result.checker_version is not None
    assert "synthetic" not in (result.feedback or "")


def test_clock_uses_client_creation_time_for_deadline_and_marks_large_skew():
    cutoff = datetime(2026, 7, 25, 21, 0, tzinfo=UTC)

    queued_offline = assess_submission_clock(
        client_created_at=cutoff,
        server_received_at=cutoff + timedelta(days=1),
        submission_closes_at=cutoff,
    )
    late = assess_submission_clock(
        client_created_at=cutoff + timedelta(microseconds=1),
        server_received_at=cutoff + timedelta(minutes=5),
        submission_closes_at=cutoff,
    )

    assert queued_offline.timely is True
    assert queued_offline.suspicious is True
    assert queued_offline.skew_seconds == 24 * 60 * 60
    assert late.timely is False
    assert late.suspicious is False


def test_clock_rejects_naive_datetimes():
    aware = datetime(2026, 7, 25, 21, 0, tzinfo=UTC)
    naive = aware.replace(tzinfo=None)

    with pytest.raises(ValueError, match="client creation time"):
        assess_submission_clock(
            client_created_at=naive,
            server_received_at=aware,
            submission_closes_at=aware,
        )


def test_checker_version_changes_with_material_configuration():
    base = answer_config(ANS_TYPE.INTEGER, correct="7")
    first = evaluate_test_answer(base, "7")
    second = evaluate_test_answer(replace(base, correct_answer="8"), "7")

    assert first.checker_version is not None
    assert second.checker_version is not None
    assert first.checker_version != second.checker_version


def test_attempt_policy_preserves_legacy_defaults_and_explicit_unlimited_mode():
    assert AttemptPolicy.from_revision({"schemaVersion": 1}) == AttemptPolicy(
        max_per_hour=3,
        max_per_day=5,
    )
    assert AttemptPolicy.from_revision({"unlimited": True}) == AttemptPolicy(
        max_per_hour=None,
        max_per_day=None,
    )
    assert AttemptPolicy.from_revision(
        {"maxPerHour": 5, "maxPerDay": None}
    ) == AttemptPolicy(max_per_hour=5, max_per_day=None)


@pytest.mark.parametrize(
    "payload",
    (
        {"maxPerHour": 0},
        {"maxPerDay": True},
        {"maxPerHour": "3"},
        {"unlimited": 1},
        {"unlimited": True, "maxPerDay": 6},
    ),
)
def test_attempt_policy_rejects_ambiguous_or_invalid_metadata(payload):
    with pytest.raises(SubmissionConfigurationError):
        AttemptPolicy.from_revision(payload)
