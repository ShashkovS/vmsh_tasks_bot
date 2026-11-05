from models.pwa.progress import summarize_course_results


def test_progress_collapses_retries_and_active_synonyms():
    rows = [
        {
            "lesson_number": 1,
            "logical_problem_key": "synonym:7",
            "verdict_weight": 0.0,
            "ts": "2026-01-10T12:00:00",
        },
        {
            "lesson_number": 1,
            "logical_problem_key": "synonym:7",
            "verdict_weight": 1.0,
            "ts": "2026-01-11T12:00:00",
        },
        {
            "lesson_number": 1,
            "logical_problem_key": "problem:8",
            "verdict_weight": 0.5,
            "ts": "2026-01-11T13:00:00",
        },
    ]

    pending = [
        {
            "lesson_number": 1,
            "logical_problem_key": "problem:9",
            "ts": "2026-01-11T14:00:00",
        }
    ]
    assert summarize_course_results(rows, pending) == {
        "summary": {
            "attempted": 3,
            "accepted": 1,
            "partial": 1,
            "needsWork": 0,
            "awaitingReview": 1,
        },
        "lessons": [
            {
                "lessonNumber": 1,
                "attempted": 3,
                "accepted": 1,
                "partial": 1,
                "needsWork": 0,
                "awaitingReview": 1,
            }
        ],
        "activity": [
            {"date": "2026-01-10", "problemCount": 1},
            {"date": "2026-01-11", "problemCount": 3},
        ],
    }


def test_progress_has_an_explicit_empty_state():
    assert summarize_course_results([]) == {
        "summary": {
            "attempted": 0,
            "accepted": 0,
            "partial": 0,
            "needsWork": 0,
            "awaitingReview": 0,
        },
        "lessons": [],
        "activity": [],
    }
