from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import student_handlers
from helpers.consts import ANS_TYPE, USER_TYPE
from helpers.features import FEATURES
from helpers.pwa.test_checkers import (
    TRUSTED_CHECKER_GLOBALS,
    TRUSTED_CHECKER_PATTERN,
)
from models.pwa import submissions


def _problem(
    answer_type: ANS_TYPE,
    *,
    correct: str = "",
    validation: str = "",
    checker: str = "",
):
    return SimpleNamespace(
        id=179,
        ans_type=answer_type,
        ans_validation=validation,
        validation_error="Введите ответ в указанном формате.",
        cor_ans=correct,
        cor_ans_checker=checker,
        wrong_ans="Нет, ответ неверный.",
        congrat="Да, всё верно!",
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
def test_telegram_adapter_uses_shared_policy_for_every_non_choice_answer_type(
    monkeypatch,
    answer_type,
    student_answer,
    correct_answer,
):
    if answer_type in {ANS_TYPE.SYMB_EXPRESSION, ANS_TYPE.SYMB_EQUIV}:
        monkeypatch.setitem(submissions.ANS_CHECKER, answer_type, lambda *_: True)

    decision = student_handlers.evaluate_telegram_test_problem_answer(
        _problem(answer_type, correct=correct_answer),
        f"  {student_answer}  ",
    )

    assert decision.verdict is student_handlers.ANS_CHECK_VERDICT.CORRECT
    assert decision.display_answer == student_answer
    assert decision.feedback == "Да, всё верно!"
    assert decision.counts_as_attempt is True


def test_telegram_select_one_keeps_visible_label_and_invalid_choice_message():
    problem = _problem(
        ANS_TYPE.SELECT_ONE,
        correct="Нечётное",
        validation="Чётное;Нечётное",
    )

    accepted = student_handlers.evaluate_telegram_test_problem_answer(
        problem,
        "Нечётное",
    )
    rejected = student_handlers.evaluate_telegram_test_problem_answer(problem, "odd")

    assert accepted.verdict is student_handlers.ANS_CHECK_VERDICT.CORRECT
    assert accepted.display_answer == "Нечётное"
    assert rejected.verdict is student_handlers.ANS_CHECK_VERDICT.INCORRECT_SELECT
    assert rejected.counts_as_attempt is False


def test_telegram_checker_failure_is_pending_and_redacted():
    source = "def check(answer):\n    return missing_name(answer)"
    problem = _problem(ANS_TYPE.STRING, checker=source)

    decision = student_handlers.evaluate_telegram_test_problem_answer(
        problem, "secret answer"
    )
    checked, message, diagnostic = student_handlers.run_py_func_checker(
        problem,
        "secret answer",
    )

    assert decision.verdict is student_handlers.ANS_CHECK_VERDICT.PENDING_CONFIGURATION
    assert decision.feedback == "Ответ принят и ожидает настройки проверки."
    assert source not in (decision.diagnostic_message or "")
    assert "secret answer" not in (decision.diagnostic_message or "")
    assert checked is False
    assert message is None
    assert source not in (diagnostic or "")
    assert "secret answer" not in (diagnostic or "")


def test_invalid_format_does_not_trigger_legacy_rate_limit(monkeypatch):
    calls = []
    student = SimpleNamespace(id=17, type=USER_TYPE.STUDENT)
    problem = _problem(ANS_TYPE.INTEGER, correct="7")
    monkeypatch.setattr(
        student_handlers,
        "RATE_LIMIT_MODE",
        FEATURES.RATE_LIMIT_3_AND_6,
    )
    monkeypatch.setattr(
        student_handlers,
        "check_test_ans_rate_limit",
        lambda student_id, problem_id: (
            calls.append((student_id, problem_id)) or "limit"
        ),
    )

    invalid = student_handlers.check_test_problem_answer(problem, student, "7жф")
    limited = student_handlers.check_test_problem_answer(problem, student, "7")

    assert invalid[0] is student_handlers.ANS_CHECK_VERDICT.VALIDATION_NOT_PASSED
    assert calls == [(17, 179)]
    assert limited == (student_handlers.ANS_CHECK_VERDICT.RATE_LIMIT, "limit", None)


def test_historical_checker_symbols_alias_the_shared_policy():
    assert (
        student_handlers.GLOBALS_FOR_TEST_FUNCTION_CREATION is TRUSTED_CHECKER_GLOBALS
    )
    assert student_handlers.is_py_func is TRUSTED_CHECKER_PATTERN
    assert student_handlers.MAX_CALLBACK_PAYLOAD_HOOK_LIMIT == 24
