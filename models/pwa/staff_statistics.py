"""Small aggregate read model for the Staff course statistics page.

The immutable analytics run is authoritative. This module only groups its rows
for display and never recalculates individual student strength.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping


def _one_decimal(value: float) -> float:
    return round(value + 1e-12, 1)


def _mean(values: list[float]) -> float | None:
    return None if not values else _one_decimal(sum(values) / len(values))


def summarize_staff_course_metrics(
    rows: Iterable[Mapping[str, object]],
    *,
    allowed_group_public_ids: frozenset[str] | None = None,
) -> list[dict[str, object]]:
    """Aggregate anonymous lesson distributions inside the authorized scope."""

    by_lesson: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        group_id = str(row["group_public_id"])
        if (
            allowed_group_public_ids is not None
            and group_id not in allowed_group_public_ids
        ):
            continue
        by_lesson[int(row["lesson_number"])].append(row)

    lessons: list[dict[str, object]] = []
    for lesson_number, lesson_rows in sorted(by_lesson.items()):
        groups: dict[str, dict[str, object]] = {}
        for row in lesson_rows:
            group_id = str(row["group_public_id"])
            group = groups.setdefault(
                group_id,
                {
                    "groupId": group_id,
                    "code": str(row["group_code"]),
                    "name": str(row["group_name"]),
                    "colorKey": str(row["color_key"] or "neutral"),
                    "sortOrder": int(row["group_sort_order"]),
                    "studentCount": 0,
                },
            )
            group["studentCount"] = int(group["studentCount"]) + 1

        solved = [int(row["solved_items"]) for row in lesson_rows]
        totals = [int(row["total_items"]) for row in lesson_rows]
        total_items = sum(totals)
        lessons.append(
            {
                "lessonNumber": lesson_number,
                "studentCount": len(lesson_rows),
                "meanSimpleStrength": _mean(
                    [float(row["simple_strength"]) for row in lesson_rows]
                ),
                "meanComplexStrength": _mean(
                    [float(row["complex_strength"]) for row in lesson_rows]
                ),
                "meanMaxComplexStrength": _mean(
                    [float(row["max_complex_strength"]) for row in lesson_rows]
                ),
                "meanSolvedItems": _mean([float(value) for value in solved]),
                "completionRate": (
                    None
                    if total_items == 0
                    else _one_decimal(100.0 * sum(solved) / total_items)
                ),
                "solvedDistribution": sorted(solved),
                "groups": sorted(
                    groups.values(),
                    key=lambda group: (
                        int(group["sortOrder"]),
                        str(group["code"]),
                        str(group["groupId"]),
                    ),
                ),
            }
        )
    return lessons


__all__ = ["summarize_staff_course_metrics"]
