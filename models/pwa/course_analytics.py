"""Pure course-progress calculations compatible with the current a53 formulas."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping


SIMPLE_CALC_WEIGHT = 9999.0
SIMPLE_ONE_WEIGHT = 1.0
COMPLEX_CALC_WEIGHT = 2.0
COMPLEX_ONE_WEIGHT = 1.0


def _problem_key(row: Mapping[str, object]) -> tuple[int, str]:
    return int(row["lesson_number"]), str(row["logical_problem_key"])


def _best_problem_scores(
    result_rows: Iterable[Mapping[str, object]],
) -> tuple[dict[tuple[int, int, str], float], dict[tuple[int, int], set[str]]]:
    attempts: dict[tuple[int, int, str], list[Mapping[str, object]]] = defaultdict(list)
    direct_groups: dict[tuple[int, int], set[str]] = defaultdict(set)

    for row in result_rows:
        student_id = int(row["student_user_id"])
        lesson_number, logical_key = _problem_key(row)
        attempts[(student_id, lesson_number, logical_key)].append(row)
        direct_groups[(student_id, lesson_number)].add(str(row["group_id"]))

    scores: dict[tuple[int, int, str], float] = {}
    for key, rows in attempts.items():
        rows.sort(key=lambda row: (str(row["ts"]), int(row["result_id"])))
        best_weight = max(float(row["verdict_weight"]) for row in rows)
        best_attempt = next(
            (index, row)
            for index, row in enumerate(rows, start=1)
            if float(row["verdict_weight"]) == best_weight
        )
        attempt_number, row = best_attempt
        if int(row["problem_type"]) == 1:
            attempt_factor = max(33.0 / 64.0, 1.0 - (attempt_number - 1) * 3.0 / 64.0)
            best_weight *= attempt_factor
        scores[key] = best_weight

    return scores, direct_groups


def _group_metric(
    problem_rows: list[Mapping[str, object]],
    scores: Mapping[tuple[int, int, str], float],
    *,
    student_id: int,
    lesson_number: int,
) -> dict[str, float | int]:
    values = [
        (
            scores.get(
                (student_id, lesson_number, str(problem["logical_problem_key"])),
                0.0,
            ),
            float(problem["for_weak"]),
            float(problem["for_strong"]),
        )
        for problem in problem_rows
    ]

    weak_count = sum(for_weak > 0 for _, for_weak, _ in values)
    weak_sum = sum(for_weak for _, for_weak, _ in values)
    simple_denominator = (
        SIMPLE_CALC_WEIGHT * (weak_count - weak_sum) + SIMPLE_ONE_WEIGHT * weak_count
    )
    simple_numerator = sum(score * (1.0 - for_weak) for score, for_weak, _ in values)

    strong_count = sum(for_strong > 0 for _, _, for_strong in values)
    strong_sum = sum(for_strong for _, _, for_strong in values)
    complex_denominator = COMPLEX_CALC_WEIGHT * strong_sum + strong_count
    complex_numerator = sum(score * for_strong for score, _, for_strong in values)

    def scaled(numerator: float, denominator: float, combined_weight: float) -> float:
        if denominator <= 0:
            return 0.0
        return min(10.0, max(0.0, 10.0 * numerator * combined_weight / denominator))

    return {
        "simple_strength": scaled(
            simple_numerator,
            simple_denominator,
            SIMPLE_CALC_WEIGHT + SIMPLE_ONE_WEIGHT,
        ),
        "complex_strength": scaled(
            complex_numerator,
            complex_denominator,
            COMPLEX_CALC_WEIGHT + COMPLEX_ONE_WEIGHT,
        ),
        "max_complex_strength": scaled(
            strong_sum,
            complex_denominator,
            COMPLEX_CALC_WEIGHT + COMPLEX_ONE_WEIGHT,
        ),
        "solved_items": sum(score > 0 for score, _, _ in values),
        "total_items": strong_count,
    }


def calculate_course_lesson_metrics(
    problem_rows: Iterable[Mapping[str, object]],
    result_rows: Iterable[Mapping[str, object]],
    access_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Choose each lesson's strongest allowed group and calculate its metrics."""

    problems_by_group: dict[tuple[int, str], list[Mapping[str, object]]] = defaultdict(
        list
    )
    group_order: dict[str, int] = {}
    seen_problem_items: set[tuple[int, str, int]] = set()
    for row in problem_rows:
        lesson_number, _ = _problem_key(row)
        group_id = str(row["group_id"])
        problem_id = int(row["problem_id"])
        item_key = (lesson_number, group_id, problem_id)
        if item_key in seen_problem_items:
            continue
        seen_problem_items.add(item_key)
        problems_by_group[(lesson_number, group_id)].append(row)
        group_order[group_id] = int(row["group_sort_order"])

    allowed_groups: dict[int, set[str]] = defaultdict(set)
    for row in access_rows:
        allowed_groups[int(row["student_user_id"])].add(str(row["group_id"]))

    result_rows = list(result_rows)
    scores, direct_groups = _best_problem_scores(result_rows)
    student_lessons = {
        (int(row["student_user_id"]), int(row["lesson_number"]))
        for row in result_rows
        if float(row["verdict_weight"]) > 0
    }

    metrics: list[dict[str, object]] = []
    for student_id, lesson_number in sorted(student_lessons):
        candidates = (
            allowed_groups.get(student_id, set())
            | direct_groups[(student_id, lesson_number)]
        )
        candidates = {
            group_id
            for group_id in candidates
            if (lesson_number, group_id) in problems_by_group
        }
        calculated = [
            (
                group_id,
                _group_metric(
                    problems_by_group[(lesson_number, group_id)],
                    scores,
                    student_id=student_id,
                    lesson_number=lesson_number,
                ),
            )
            for group_id in candidates
        ]
        if not calculated:
            continue
        group_id, metric = min(
            calculated,
            key=lambda item: (
                -(
                    float(item[1]["complex_strength"]) * 3.0
                    + float(item[1]["simple_strength"]) * 2.0
                ),
                group_order.get(item[0], 0),
                item[0],
            ),
        )
        metrics.append(
            {
                "student_user_id": student_id,
                "lesson_number": lesson_number,
                "group_id": group_id,
                **metric,
            }
        )

    return metrics


__all__ = ["calculate_course_lesson_metrics"]
