"""Small personal-progress calculations over stored result facts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping


def summarize_course_results(
    rows: Iterable[Mapping[str, object]],
    pending_review_rows: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Collapse retries and active synonyms using the best recorded verdict."""

    best_weight: dict[tuple[int, str], float] = {}
    pending_review: set[tuple[int, str]] = set()
    activity: dict[str, set[tuple[int, str]]] = defaultdict(set)

    for row in rows:
        lesson_number = int(row["lesson_number"])
        logical_key = str(row["logical_problem_key"])
        key = (lesson_number, logical_key)
        weight = float(row["verdict_weight"])
        best_weight[key] = max(weight, best_weight.get(key, 0.0))
        result_date = str(row["ts"])[:10]
        activity[result_date].add(key)

    for row in pending_review_rows:
        key = (int(row["lesson_number"]), str(row["logical_problem_key"]))
        pending_review.add(key)
        activity[str(row["ts"])[:10]].add(key)

    all_keys = set(best_weight) | pending_review
    lesson_keys: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for key in all_keys:
        lesson_keys[key[0]].append(key)

    def counts(keys: Iterable[tuple[int, str]]) -> dict[str, int]:
        keys = list(keys)
        weights = [best_weight[key] for key in keys if key in best_weight]
        return {
            "attempted": len(keys),
            "accepted": sum(weight >= 0.8 for weight in weights),
            "partial": sum(0 < weight < 0.8 for weight in weights),
            "needsWork": sum(weight == 0 for weight in weights),
            "awaitingReview": sum(key in pending_review for key in keys),
        }

    return {
        "summary": counts(all_keys),
        "lessons": [
            {"lessonNumber": lesson, **counts(lesson_keys[lesson])}
            for lesson in sorted(lesson_keys)
        ],
        "activity": [
            {"date": date, "problemCount": len(activity[date])}
            for date in sorted(activity)
        ],
    }


__all__ = ["summarize_course_results"]
