from __future__ import annotations

import pytest

from models.pwa.course_analytics import calculate_course_lesson_metrics


def _problem(problem_id: int, group_id: str, logical_key: str) -> dict[str, object]:
    return {
        "problem_id": problem_id,
        "lesson_number": 4,
        "group_id": group_id,
        "group_sort_order": {"n": 10, "p": 20}[group_id],
        "logical_problem_key": logical_key,
        "for_weak": 0.5,
        "for_strong": 0.5,
    }


def _result(
    result_id: int,
    problem_id: int,
    group_id: str,
    logical_key: str,
    weight: float,
    *,
    problem_type: int = 2,
) -> dict[str, object]:
    return {
        "result_id": result_id,
        "student_user_id": 7,
        "problem_id": problem_id,
        "lesson_number": 4,
        "group_id": group_id,
        "logical_problem_key": logical_key,
        "problem_type": problem_type,
        "verdict_weight": weight,
        "ts": f"2026-10-0{result_id}T12:00:00",
    }


def test_synonym_score_is_applied_to_each_allowed_group_and_best_group_wins():
    problems = [
        _problem(11, "n", "shared"),
        _problem(12, "n", "n-only"),
        _problem(21, "p", "shared"),
    ]
    results = [
        _result(1, 11, "n", "shared", 1.0),
        _result(2, 12, "n", "n-only", 0.0),
    ]
    access = [
        {"student_user_id": 7, "group_id": "n"},
        {"student_user_id": 7, "group_id": "p"},
    ]

    metric = calculate_course_lesson_metrics(problems, results, access)[0]
    assert metric == {
        "student_user_id": 7,
        "lesson_number": 4,
        "group_id": "p",
        "simple_strength": pytest.approx(9.99900009999),
        "complex_strength": 7.5,
        "max_complex_strength": 7.5,
        "solved_items": 1,
        "total_items": 1,
    }


def test_test_attempt_penalty_matches_a53_and_stable_group_order_breaks_tie():
    problems = [_problem(11, "n", "shared"), _problem(21, "p", "shared")]
    results = [
        _result(1, 11, "n", "shared", 0.0, problem_type=1),
        _result(2, 11, "n", "shared", 1.0, problem_type=1),
    ]
    access = [
        {"student_user_id": 7, "group_id": "p"},
        {"student_user_id": 7, "group_id": "n"},
    ]

    metric = calculate_course_lesson_metrics(problems, results, access)[0]
    assert metric["group_id"] == "n"
    assert metric["simple_strength"] == pytest.approx(9.5302969703)
    assert metric["complex_strength"] == pytest.approx(7.1484375)
    assert metric["max_complex_strength"] == 7.5


def test_lessons_without_a_positive_result_do_not_create_chart_points():
    problems = [_problem(11, "n", "only")]
    results = [_result(1, 11, "n", "only", 0.0)]

    assert calculate_course_lesson_metrics(problems, results, []) == []
