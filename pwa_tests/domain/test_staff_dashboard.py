from datetime import UTC, datetime

import pytest

from models.pwa.staff_dashboard import (
    InvalidStaffDashboardData,
    StaffDashboardScope,
    build_staff_dashboard_lessons,
)


NOW = datetime(2026, 8, 2, 10, tzinfo=UTC)


def lesson(
    *,
    internal_id: int,
    public_id: str,
    course_id: str = "course-math",
    group_id: str = "group-beginner",
    anchor: str = "2026-07-27",
    number: int = 41,
    opens_at: str | None = "2026-07-27T13:30:00Z",
    closes_at: str | None = "2026-08-02T10:00:00Z",
) -> dict[str, object]:
    return {
        "group_lesson_id": internal_id,
        "group_lesson_public_id": public_id,
        "cycle_anchor_date": anchor,
        "business_timezone": "Europe/Moscow",
        "course_public_id": course_id,
        "course_code": "MATH",
        "course_name": "Математика 5–7",
        "course_sort_order": 1,
        "group_public_id": group_id,
        "group_code": "н",
        "group_name": "Начинающие",
        "color_key": "beginner",
        "group_sort_order": 1,
        "lesson_number": number,
        "opens_at": opens_at,
        "submission_closes_at": closes_at,
        "hint_scheduled_at": None,
        "solution_scheduled_at": None,
    }


def publication(
    group_lesson_id: int, kind: str, state: str, scheduled_at: str | None = None
) -> dict[str, object]:
    return {
        "group_lesson_id": group_lesson_id,
        "kind": kind,
        "state": state,
        "scheduled_at": scheduled_at,
        "published_at": "2026-08-01T09:00:00Z" if state == "published" else None,
    }


def test_dashboard_selects_latest_started_lesson_and_respects_group_scope() -> None:
    rows = [
        lesson(internal_id=39, public_id="lesson-39", anchor="2026-07-13", number=39),
        lesson(internal_id=41, public_id="lesson-41"),
        lesson(
            internal_id=42,
            public_id="lesson-42",
            anchor="2026-08-03",
            number=42,
        ),
        lesson(
            internal_id=141,
            public_id="physics-lesson-7",
            course_id="course-physics",
            group_id="group-physics",
            number=7,
        ),
    ]
    visible = build_staff_dashboard_lessons(
        rows,
        [publication(41, "condition", "published")],
        [],
        scope=StaffDashboardScope(group_public_ids=frozenset({"group-beginner"})),
        now=NOW,
    )

    assert [item["groupLessonId"] for item in visible] == ["lesson-41"]
    assert visible[0]["phase"] == "submissions_closed"


def test_dashboard_keeps_publications_independent_and_counts_oral_windows() -> None:
    visible = build_staff_dashboard_lessons(
        [
            lesson(
                internal_id=41, public_id="lesson-41", closes_at="2026-08-03T10:00:00Z"
            )
        ],
        [
            publication(41, "condition", "published"),
            publication(41, "hint", "scheduled", "2026-08-02T11:00:00Z"),
            publication(41, "solution", "scheduled", "2026-08-03T11:00:00Z"),
        ],
        [
            {
                "group_lesson_id": 41,
                "opens_at": "2026-08-02T09:00:00Z",
                "closes_at": "2026-08-02T11:00:00Z",
            },
            {
                "group_lesson_id": 41,
                "opens_at": "2026-08-03T09:00:00Z",
                "closes_at": "2026-08-03T11:00:00Z",
            },
        ],
        scope=StaffDashboardScope(global_access=True),
        now=NOW,
    )

    item = visible[0]
    assert item["phase"] == "active"
    assert item["publications"] == {
        "condition": {"state": "published", "scheduledAt": None},
        "hint": {"state": "scheduled", "scheduledAt": "2026-08-02T11:00:00Z"},
        "solution": {
            "state": "scheduled",
            "scheduledAt": "2026-08-03T11:00:00Z",
        },
    }
    assert item["oral"] == {"openWindows": 1, "upcomingWindows": 1}


@pytest.mark.parametrize(
    ("publications", "expected"),
    [
        ([], "draft"),
        (
            [publication(41, "condition", "scheduled", "2026-08-03T09:00:00Z")],
            "scheduled",
        ),
        (
            [
                publication(41, "condition", "published"),
                publication(41, "hint", "published"),
            ],
            "hints_published",
        ),
        (
            [
                publication(41, "condition", "published"),
                publication(41, "solution", "published"),
            ],
            "solutions_published",
        ),
    ],
)
def test_dashboard_phase_follows_the_weekly_lifecycle(
    publications: list[dict[str, object]], expected: str
) -> None:
    row = lesson(
        internal_id=41,
        public_id="lesson-41",
        closes_at="2026-08-03T10:00:00Z",
    )
    if expected == "scheduled":
        row["opens_at"] = "2026-08-03T09:00:00Z"
    result = build_staff_dashboard_lessons(
        [row],
        publications,
        [],
        scope=StaffDashboardScope(global_access=True),
        now=NOW,
    )
    assert result[0]["phase"] == expected


def test_dashboard_rejects_an_unknown_business_timezone() -> None:
    row = lesson(internal_id=41, public_id="lesson-41")
    row["business_timezone"] = "Mars/Olympus"
    with pytest.raises(InvalidStaffDashboardData, match="timezone"):
        build_staff_dashboard_lessons(
            [row],
            [],
            [],
            scope=StaffDashboardScope(global_access=True),
            now=NOW,
        )
