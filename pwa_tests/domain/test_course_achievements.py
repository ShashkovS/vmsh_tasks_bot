from models.pwa.course_achievements import calculate_initial_course_achievements


def test_initial_achievements_use_the_earliest_matching_course_fact():
    facts = [
        {
            "source": "result",
            "event_id": 2,
            "ts": "2026-09-16T10:00:00",
            "lesson_number": 2,
            "accepted": True,
            "written": False,
        },
        {
            "source": "written_queue",
            "event_id": 1,
            "ts": "2026-09-15T10:00:00",
            "lesson_number": 1,
            "accepted": False,
            "written": True,
        },
    ]

    assert calculate_initial_course_achievements(facts) == [
        {
            "code": "first_submission",
            "earned_at": "2026-09-15T10:00:00",
            "evidence": {"lessonNumber": 1},
        },
        {
            "code": "first_accepted",
            "earned_at": "2026-09-16T10:00:00",
            "evidence": {"lessonNumber": 2},
        },
        {
            "code": "first_written_submission",
            "earned_at": "2026-09-15T10:00:00",
            "evidence": {"lessonNumber": 1},
        },
    ]


def test_no_course_activity_earns_nothing():
    assert calculate_initial_course_achievements([]) == []
