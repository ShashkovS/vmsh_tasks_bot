"""Pure Staff analytics aggregation without cohort-to-student comparison."""

from models.pwa.staff_statistics import summarize_staff_course_metrics


def _row(
    student_id: int,
    lesson: int,
    group_id: str,
    solved: int,
    total: int,
    simple: float,
    complex_: float,
) -> dict[str, object]:
    return {
        "student_user_id": student_id,
        "lesson_number": lesson,
        "group_public_id": group_id,
        "group_code": "н" if group_id == "group.beginner" else "п",
        "group_name": "Начинающие" if group_id == "group.beginner" else "Продолжающие",
        "color_key": "beginner" if group_id == "group.beginner" else "continuing",
        "group_sort_order": 1 if group_id == "group.beginner" else 2,
        "simple_strength": simple,
        "complex_strength": complex_,
        "max_complex_strength": max(complex_, 8.0),
        "solved_items": solved,
        "total_items": total,
    }


def test_staff_statistics_aggregates_lessons_and_anonymous_distributions() -> None:
    lessons = summarize_staff_course_metrics(
        [
            _row(1, 41, "group.beginner", 3, 5, 6.2, 3.2),
            _row(2, 41, "group.beginner", 5, 5, 8.2, 5.2),
            _row(3, 41, "group.continuing", 2, 4, 7.1, 4.1),
            _row(1, 40, "group.beginner", 1, 2, 4.0, 2.0),
        ]
    )

    assert [lesson["lessonNumber"] for lesson in lessons] == [40, 41]
    current = lessons[1]
    assert current == {
        "lessonNumber": 41,
        "studentCount": 3,
        "meanSimpleStrength": 7.2,
        "meanComplexStrength": 4.2,
        "meanMaxComplexStrength": 8.0,
        "meanSolvedItems": 3.3,
        "completionRate": 71.4,
        "solvedDistribution": [2, 3, 5],
        "groups": [
            {
                "groupId": "group.beginner",
                "code": "н",
                "name": "Начинающие",
                "colorKey": "beginner",
                "sortOrder": 1,
                "studentCount": 2,
            },
            {
                "groupId": "group.continuing",
                "code": "п",
                "name": "Продолжающие",
                "colorKey": "continuing",
                "sortOrder": 2,
                "studentCount": 1,
            },
        ],
    }


def test_staff_statistics_filters_before_aggregation_and_handles_empty_totals() -> None:
    lessons = summarize_staff_course_metrics(
        [
            _row(1, 41, "group.beginner", 0, 0, 0, 0),
            _row(2, 41, "group.continuing", 4, 5, 7, 5),
        ],
        allowed_group_public_ids=frozenset({"group.beginner"}),
    )

    assert len(lessons) == 1
    assert lessons[0]["studentCount"] == 1
    assert lessons[0]["completionRate"] is None
    assert lessons[0]["solvedDistribution"] == [0]


def test_staff_statistics_returns_no_rows_for_an_empty_authorized_scope() -> None:
    assert (
        summarize_staff_course_metrics(
            [_row(1, 41, "group.beginner", 3, 5, 6, 3)],
            allowed_group_public_ids=frozenset(),
        )
        == []
    )
