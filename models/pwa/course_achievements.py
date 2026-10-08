"""Small fixed set of calm, course-scoped achievement rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def calculate_initial_course_achievements(
    facts: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    ordered = sorted(
        facts,
        key=lambda fact: (
            str(fact["ts"]),
            str(fact["source"]),
            int(fact["event_id"]),
        ),
    )
    if not ordered:
        return []

    rules = (
        ("first_submission", lambda _fact: True),
        ("first_accepted", lambda fact: bool(fact["accepted"])),
        ("first_written_submission", lambda fact: bool(fact["written"])),
    )
    earned = []
    for code, matches in rules:
        fact = next((candidate for candidate in ordered if matches(candidate)), None)
        if fact is None:
            continue
        earned.append(
            {
                "code": code,
                "earned_at": str(fact["ts"]),
                "evidence": {"lessonNumber": int(fact["lesson_number"])},
            }
        )
    return earned


__all__ = ["calculate_initial_course_achievements"]
