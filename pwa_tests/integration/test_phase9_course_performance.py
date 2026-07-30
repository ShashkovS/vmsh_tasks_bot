"""Production-size characterization for the Phase-9 course analytics job."""

from __future__ import annotations

import sqlite3
from time import perf_counter

from db_methods.pwa.course_analytics import (
    latest_student_course_metrics,
    list_course_group_access_rows,
    list_course_problem_rows,
    list_course_result_rows,
    save_completed_course_metrics,
)
from models.pwa.course_analytics import calculate_course_lesson_metrics


STUDENT_COUNT = 1_500
LESSON_COUNT = 38
GROUPS = ("beginner", "continuing", "expert")
PROBLEMS_PER_GROUP_LESSON = 6


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY);
        CREATE TABLE courses (id INTEGER PRIMARY KEY);
        CREATE TABLE groups (
            group_id TEXT PRIMARY KEY,
            course_id INTEGER NOT NULL,
            public_id TEXT NOT NULL,
            short_code TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );
        CREATE TABLE problems (
            id INTEGER PRIMARY KEY,
            lesson INTEGER NOT NULL,
            group_id TEXT NOT NULL,
            prob INTEGER NOT NULL,
            item TEXT NOT NULL DEFAULT '',
            prob_type INTEGER NOT NULL,
            synonyms TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE problem_complexity (
            synonyms TEXT PRIMARY KEY,
            for_weak REAL NOT NULL,
            for_strong REAL NOT NULL
        );
        CREATE TABLE verdicts (id INTEGER PRIMARY KEY, val REAL NOT NULL);
        CREATE TABLE results (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            verdict INTEGER NOT NULL
        );
        CREATE INDEX results_by_student_problem ON results (student_id, problem_id);
        CREATE TABLE problem_synonym_groups (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL
        );
        CREATE TABLE problem_synonym_members (
            problem_id INTEGER NOT NULL,
            synonym_group_id INTEGER NOT NULL,
            removed_at TEXT
        );
        CREATE UNIQUE INDEX problem_synonym_members_problem_active_uq
            ON problem_synonym_members (problem_id) WHERE removed_at IS NULL;
        CREATE TABLE course_enrollments (
            id INTEGER PRIMARY KEY,
            student_user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        CREATE INDEX course_enrollments_course_status_idx
            ON course_enrollments (course_id, status, student_user_id);
        CREATE TABLE course_group_access (
            enrollment_id INTEGER NOT NULL,
            group_id TEXT NOT NULL,
            valid_to TEXT
        );
        CREATE INDEX course_group_access_enrollment_history_idx
            ON course_group_access (enrollment_id, valid_to);
        CREATE TABLE analytics_runs (
            id INTEGER PRIMARY KEY,
            public_id TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            algorithm TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            input_through_result_id INTEGER NOT NULL,
            state TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            diagnostics_json TEXT NOT NULL
        );
        CREATE INDEX analytics_runs_course_latest_idx
            ON analytics_runs (course_id, state, completed_at DESC, id DESC);
        CREATE TABLE student_lesson_metrics (
            run_id INTEGER NOT NULL,
            student_user_id INTEGER NOT NULL,
            lesson_number INTEGER NOT NULL,
            group_id TEXT NOT NULL,
            simple_strength REAL NOT NULL,
            complex_strength REAL NOT NULL,
            max_complex_strength REAL NOT NULL,
            solved_items INTEGER NOT NULL,
            total_items INTEGER NOT NULL,
            PRIMARY KEY (run_id, student_user_id, lesson_number)
        );
        CREATE INDEX student_lesson_metrics_student_run_idx
            ON student_lesson_metrics (student_user_id, run_id, lesson_number);
        """
    )


def _seed_course(connection: sqlite3.Connection) -> None:
    connection.execute("INSERT INTO courses (id) VALUES (1)")
    connection.execute("INSERT INTO verdicts (id, val) VALUES (1, 1.0)")
    connection.executemany(
        "INSERT INTO groups (group_id, course_id, public_id, short_code, sort_order) "
        "VALUES (?, 1, ?, ?, ?)",
        [
            (group_id, f"group-{group_id}", group_id[0], sort_order)
            for sort_order, group_id in enumerate(GROUPS, start=1)
        ],
    )

    problems: list[tuple[int, int, str, int, int, str]] = []
    problem_ids: dict[tuple[int, str, int], int] = {}
    next_problem_id = 1
    for lesson in range(1, LESSON_COUNT + 1):
        for group_id in GROUPS:
            for number in range(1, PROBLEMS_PER_GROUP_LESSON + 1):
                synonym = f"lesson-{lesson}-problem-{number}"
                problems.append((next_problem_id, lesson, group_id, number, 1, synonym))
                problem_ids[(lesson, group_id, number)] = next_problem_id
                next_problem_id += 1
    connection.executemany(
        "INSERT INTO problems "
        "(id, lesson, group_id, prob, prob_type, synonyms) VALUES (?, ?, ?, ?, ?, ?)",
        problems,
    )
    connection.executemany(
        "INSERT INTO problem_complexity (synonyms, for_weak, for_strong) "
        "VALUES (?, 0.5, 0.5)",
        [
            (f"lesson-{lesson}-problem-{number}",)
            for lesson in range(1, 39)
            for number in range(1, 7)
        ],
    )

    connection.executemany(
        "INSERT INTO users (id) VALUES (?)",
        [(student_id,) for student_id in range(1, STUDENT_COUNT + 1)],
    )
    connection.executemany(
        "INSERT INTO course_enrollments (id, student_user_id, course_id, status) "
        "VALUES (?, ?, 1, 'active')",
        [(student_id, student_id) for student_id in range(1, STUDENT_COUNT + 1)],
    )
    connection.executemany(
        "INSERT INTO course_group_access (enrollment_id, group_id, valid_to) "
        "VALUES (?, ?, NULL)",
        [
            (student_id, group_id)
            for student_id in range(1, STUDENT_COUNT + 1)
            for group_id in GROUPS
        ],
    )

    results: list[tuple[int, int, int, str, int]] = []
    next_result_id = 1
    for student_id in range(1, STUDENT_COUNT + 1):
        group_id = GROUPS[(student_id - 1) % len(GROUPS)]
        for lesson in range(1, LESSON_COUNT + 1):
            results.append(
                (
                    next_result_id,
                    student_id,
                    problem_ids[(lesson, group_id, 1)],
                    f"2026-01-{(lesson - 1) % 28 + 1:02d}T12:00:00Z",
                    1,
                )
            )
            next_result_id += 1
    connection.executemany(
        "INSERT INTO results (id, student_id, problem_id, ts, verdict) "
        "VALUES (?, ?, ?, ?, ?)",
        results,
    )
    connection.commit()


def test_course_analytics_handles_1500_students_and_38_lessons(tmp_path):
    database = tmp_path / "phase9-performance.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        _create_schema(connection)
        _seed_course(connection)

        traced: list[str] = []
        connection.set_trace_callback(traced.append)
        started = perf_counter()
        problem_rows = list_course_problem_rows(connection, course_id=1)
        result_rows = list_course_result_rows(connection, course_id=1)
        access_rows = list_course_group_access_rows(connection, course_id=1)
        connection.set_trace_callback(None)
        metrics = calculate_course_lesson_metrics(
            problem_rows,
            result_rows,
            access_rows,
        )
        save_completed_course_metrics(
            connection,
            public_id="analytics-phase9-performance",
            course_id=1,
            algorithm="a53-course",
            algorithm_version="1",
            input_through_result_id=len(result_rows),
            completed_at="2026-07-30T12:00:00Z",
            metrics=metrics,
        )
        elapsed = perf_counter() - started

        assert (
            len(problem_rows) == LESSON_COUNT * len(GROUPS) * PROBLEMS_PER_GROUP_LESSON
        )
        assert len(result_rows) == STUDENT_COUNT * LESSON_COUNT
        assert len(access_rows) == STUDENT_COUNT * len(GROUPS)
        assert len(metrics) == STUDENT_COUNT * LESSON_COUNT
        assert (
            len(
                latest_student_course_metrics(
                    connection, course_id=1, student_user_id=1
                )
            )
            == 38
        )
        # This is a regression tripwire, not a latency SLO. The job runs only
        # every few hours and should stay comfortably below this on a dev Mac.
        assert elapsed < 15.0

        plan_markers = {
            "problems": "FROM problems AS problem",
            "results": "FROM results AS result",
            "access": "FROM course_group_access AS access",
        }
        plans = {
            name: [
                str(row[3])
                for row in connection.execute(
                    "EXPLAIN QUERY PLAN "
                    + next(statement for statement in traced if marker in statement)
                )
            ]
            for name, marker in plan_markers.items()
        }
        assert any(
            "course_enrollments_course_status_idx" in item for item in plans["access"]
        )
        assert all("AUTOMATIC" not in item for plan in plans.values() for item in plan)
        print(f"phase9 analytics elapsed={elapsed:.3f}s; plans={plans}")
