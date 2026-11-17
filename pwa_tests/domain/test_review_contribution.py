"""Personal milestones/calendar acceptance; vmshpwa/docs/review-contribution.md."""

from datetime import UTC, datetime

import pytest

from models.pwa.review_contribution import (
    calculate_contribution,
    milestone,
    LESSON_MILESTONES,
)


LESSONS = [
    {"course_id": "c-1", "course_name": "Математика", "lesson": n} for n in (11, 10)
]


def row(ts="2026-11-16T12:00:00Z", *, lesson=11, kind="written", val=1.0, course="c-1"):
    return {"ts": ts, "lesson": lesson, "kind": kind, "val": val, "course_id": course}


def calculate(rows=(), lessons=LESSONS, **kwargs):
    return calculate_contribution(
        list(rows), lessons, now=datetime(2026, 11, 17, 12, tzinfo=UTC), **kwargs
    )


def test_totals_plus_dot_partial_and_lesson_are_independent_of_check_day():
    result = calculate(
        [
            row(lesson=10),
            row(val=0.95),
            row(kind="school", val=0.7),
            row(kind="zoom", val=0),
            row(course="archived"),
        ]
    )
    assert result["allTime"]["total"] == 5
    assert result["allTime"]["plus"] == 3
    assert result["lesson"]["number"] == 11
    assert result["lesson"]["counts"]["total"] == 3
    assert result["lesson"]["counts"]["plus"] == 1
    assert result["allTime"]["byKind"]["school"] == {"total": 1, "plus": 0}
    assert calculate([row()], lesson=10)["lesson"]["counts"]["total"] == 0


def test_empty_multiple_courses_and_scope_validation():
    assert calculate()["allTime"]["total"] == 0
    assert calculate(lessons=[])["lesson"] is None
    two = LESSONS + [{"course_id": "c-2", "course_name": "Другой", "lesson": 3}]
    assert calculate(lessons=two)["lesson"] is None
    assert calculate(lessons=two, course="c-2")["lesson"]["number"] == 3
    for query in ({"course": "c-forbidden"}, {"lesson": 999}):
        with pytest.raises(PermissionError):
            calculate(**query)


def test_milestones_continue_beyond_the_initial_ladder():
    for value, reached, upcoming in [(0, [], 1), (1, [1], 10), (10, [1, 10], 25)]:
        assert milestone(value, LESSON_MILESTONES, 1000) == {
            "value": value,
            "reached": reached,
            "next": upcoming,
        }
    assert milestone(2000, LESSON_MILESTONES, 1000)["reached"][-1] == 2000
    assert milestone(2000, LESSON_MILESTONES, 1000)["next"] == 3000


def test_daily_streak_uses_moscow_midnight_and_preserves_yesterday_until_today_ends():
    rows = [row("2026-11-14T21:00:00Z")] * 3 + [row("2026-11-15T21:01:00Z")] * 3
    result = calculate(rows + [row("2026-11-17T08:00:00Z")])
    assert result["daily"]["current"] == result["daily"]["best"] == 2
    assert result["daily"]["periodCount"] == 1
    result = calculate_contribution(
        rows, LESSONS, now=datetime(2026, 11, 17, 21, tzinfo=UTC)
    )
    assert result["daily"]["current"] == 0
    assert result["daily"]["best"] == 2
    assert calculate([row("2026-11-16T20:59:59Z")] * 2)["daily"]["best"] == 0


def test_weekly_streak_crosses_year_and_retains_a_record_after_a_break():
    rows = [row("2026-12-28T12:00:00Z")] * 3 + [row("2027-01-04T12:00:00Z")] * 3
    result = calculate_contribution(
        rows, LESSONS, now=datetime(2027, 1, 11, tzinfo=UTC)
    )
    assert result["weekly"]["current"] == result["weekly"]["best"] == 2
    result = calculate_contribution(
        rows, LESSONS, now=datetime(2027, 1, 18, tzinfo=UTC)
    )
    assert result["weekly"]["current"] == 0
    assert result["weekly"]["best"] == 2
