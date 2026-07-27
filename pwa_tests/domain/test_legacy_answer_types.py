"""Characterize answer parsing that PWA test submissions must preserve."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from helpers import checkers
from helpers.consts import ANS_TYPE, ANS_TYPES_DECODER


EXPECTED_ANSWER_TYPE_IDS = {
    "DIGIT": 1,
    "NATURAL": 2,
    "INTEGER": 3,
    "RATIO": 4,
    "FLOAT": 5,
    "FRACTION": 6,
    "INT_SEQ": 7,
    "INT_2": 8,
    "INT_3": 9,
    "INT_4": 10,
    "INT_SET": 11,
    "POLYNOMIAL": 12,
    "FLOAT_EPS": 13,
    "TIME": 14,
    "DATE": 15,
    "WEEKDAY": 16,
    "FRAC_SEQ": 17,
    "MULTISET": 18,
    "MIXED_FRACTION": 19,
    "SYMB_EXPRESSION": 20,
    "SYMB_EQUIV": 21,
    "SELECT_ONE": 98,
    "STRING": 99,
}


@dataclass(frozen=True)
class ValidationCase:
    answer_type: ANS_TYPE
    accepted: str
    rejected: str | None


VALIDATION_CASES = (
    ValidationCase(ANS_TYPE.DIGIT, "7", "17"),
    ValidationCase(ANS_TYPE.NATURAL, "179", "-1"),
    ValidationCase(ANS_TYPE.INTEGER, "-179", "1.5"),
    ValidationCase(ANS_TYPE.RATIO, "-179/1", "1/2/3"),
    ValidationCase(ANS_TYPE.FLOAT, "3.14", "3,14"),
    ValidationCase(ANS_TYPE.FRACTION, "-7/3", "3,14"),
    ValidationCase(ANS_TYPE.MIXED_FRACTION, "-1 2/3", "1 2/3 4"),
    ValidationCase(ANS_TYPE.INT_SEQ, "1, 7, -9", "нет чисел"),
    ValidationCase(ANS_TYPE.INT_2, "1, 7", "1"),
    ValidationCase(ANS_TYPE.INT_3, "1, 7, 9", "1, 7"),
    ValidationCase(ANS_TYPE.INT_4, "0, 1, 7, 9", "0, 1, 7"),
    ValidationCase(ANS_TYPE.INT_SET, "{1, 7, -9}", "пусто"),
    ValidationCase(ANS_TYPE.POLYNOMIAL, "2n^2+n(n+1)/2", "a+1"),
    ValidationCase(ANS_TYPE.FLOAT_EPS, "3.14", "3,14"),
    ValidationCase(ANS_TYPE.TIME, "12:08", "12"),
    ValidationCase(ANS_TYPE.DATE, "2025-02-16", "2025"),
    ValidationCase(ANS_TYPE.WEEKDAY, "Суббота", "Monday"),
    ValidationCase(ANS_TYPE.FRAC_SEQ, "2/5, 3.75, -1", "нет чисел"),
    ValidationCase(ANS_TYPE.MULTISET, "1, 1, 2/5, -1.2", "нет чисел"),
    ValidationCase(ANS_TYPE.SYMB_EXPRESSION, "a + b^2", None),
    ValidationCase(ANS_TYPE.SYMB_EQUIV, "a + b^2", None),
    ValidationCase(ANS_TYPE.SELECT_ONE, "Нечётное", None),
    ValidationCase(ANS_TYPE.STRING, "любой текст", None),
)


def test_answer_type_ids_decoders_and_handlers_are_complete():
    assert {answer_type.name: int(answer_type) for answer_type in ANS_TYPE} == (
        EXPECTED_ANSWER_TYPE_IDS
    )
    assert len(ANS_TYPE) == 23
    assert set(ANS_TYPES_DECODER.values()) == set(ANS_TYPE)
    assert set(checkers.ANS_CHECKER) == set(ANS_TYPE)
    assert set(checkers.ANS_REGEX) == set(ANS_TYPE)
    assert all(answer_type.descr is not None for answer_type in ANS_TYPE)


@pytest.mark.parametrize(
    "case", VALIDATION_CASES, ids=lambda case: case.answer_type.name
)
def test_answer_validation_uses_historical_fullmatch_contract(case: ValidationCase):
    validation = checkers.ANS_REGEX[case.answer_type]
    if case.answer_type in {ANS_TYPE.SELECT_ONE, ANS_TYPE.STRING}:
        assert validation is None
        return

    assert validation is not None
    assert validation.fullmatch(case.accepted.strip()) is not None
    if case.rejected is not None:
        assert validation.fullmatch(case.rejected.strip()) is None


@pytest.mark.parametrize(
    ("answer_type", "student_answer", "correct_answer", "expected"),
    (
        (ANS_TYPE.DIGIT, "07", "7", True),
        (ANS_TYPE.NATURAL, " 179 ", "179", True),
        (ANS_TYPE.INTEGER, "+7", "7", True),
        (ANS_TYPE.RATIO, "10/6", "5/3", True),
        (ANS_TYPE.FLOAT, "3.50", "7/2", True),
        (ANS_TYPE.FRACTION, "-1.5", "-3/2", True),
        (ANS_TYPE.MIXED_FRACTION, "1 2/3", "5/3", True),
        (ANS_TYPE.INT_SEQ, "1, 2, 3", "1 2 3", True),
        (ANS_TYPE.INT_SEQ, "3, 2, 1", "1, 2, 3", False),
        (ANS_TYPE.INT_2, "1; 2", "1 2", True),
        (ANS_TYPE.INT_3, "1; 2; 3", "1 2 3", True),
        (ANS_TYPE.INT_4, "1; 2; 3; 4", "1 2 3 4", True),
        (ANS_TYPE.INT_SET, "3, 1, 1, 2", "1, 2, 3", True),
        (ANS_TYPE.FLOAT_EPS, "0.2", "0.3+-0.1", True),
        (ANS_TYPE.TIME, "12:08", "12 ч 08 мин 00 сек", True),
        (ANS_TYPE.DATE, "2025-02-16", "16.02.2025", True),
        (ANS_TYPE.WEEKDAY, "сб", "Суббота", True),
        (ANS_TYPE.FRAC_SEQ, "1, 2/4, -3", "1; 1/2; -3", True),
        (ANS_TYPE.FRAC_SEQ, "-3, 1/2, 1", "1; 1/2; -3", False),
        (ANS_TYPE.MULTISET, "2/4, 1, 1", "1, 1/2, 1", True),
        (ANS_TYPE.MULTISET, "1, 1/2", "1, 1/2, 1", False),
        # The production SELECT_ONE branch compares visible options itself; this
        # mapping remains relevant to historical re-check helpers only.
        (ANS_TYPE.SELECT_ONE, "Odd", "odd", True),
        (ANS_TYPE.STRING, "СОК", "COK", True),
    ),
)
def test_standard_answer_checkers_preserve_normalization(
    answer_type: ANS_TYPE,
    student_answer: str,
    correct_answer: str,
    expected: bool,
):
    checker = checkers.ANS_CHECKER[answer_type]
    assert checker(student_answer, correct_answer) is expected


def test_polynomial_checker_compares_values_on_one_through_ten():
    valid, values = checkers.ANS_CHECKER[ANS_TYPE.POLYNOMIAL]("n(n+1)/2")
    assert valid is True
    assert values == [1.0, 3.0, 6.0, 10.0, 15.0, 21.0, 28.0, 36.0, 45.0, 55.0]

    valid, message = checkers.ANS_CHECKER[ANS_TYPE.POLYNOMIAL]("n**10")
    assert valid is False
    assert message == "Allowed exponents are from 1 to 9"


def test_symbolic_checker_keeps_strict_and_maybe_modes_distinct(monkeypatch):
    verdicts = iter(
        (
            checkers.CompareVerdict.EQUAL,
            checkers.CompareVerdict.MAY_BE,
            checkers.CompareVerdict.MAY_BE,
        )
    )
    monkeypatch.setattr(
        checkers.worker,
        "strict_compare_v2",
        lambda *_args, **_kwargs: next(verdicts),
    )

    assert checkers.ANS_CHECKER[ANS_TYPE.SYMB_EXPRESSION]("a", "a") is True
    assert checkers.ANS_CHECKER[ANS_TYPE.SYMB_EXPRESSION]("a", "b") is False
    assert checkers.ANS_CHECKER[ANS_TYPE.SYMB_EQUIV]("a", "b") is True
