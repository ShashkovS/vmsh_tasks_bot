"""Production-size characterization for the Phase-10 Student directory."""

from __future__ import annotations

import sqlite3
from time import perf_counter

from db_methods.pwa.admin_enrollments import (
    list_active_group_access,
    list_family_links,
    list_students,
)
from helpers.consts import USER_TYPE


STUDENT_COUNT = 1_500


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            public_id TEXT NOT NULL,
            surname TEXT NOT NULL,
            name TEXT NOT NULL,
            middlename TEXT,
            grade INTEGER,
            birthday TEXT,
            type INTEGER NOT NULL
        );
        CREATE TABLE auth_accounts (
            id INTEGER PRIMARY KEY,
            public_id TEXT NOT NULL,
            audience TEXT NOT NULL,
            username TEXT NOT NULL,
            status TEXT NOT NULL,
            credential_version INTEGER NOT NULL,
            display_name TEXT,
            linked_user_id INTEGER
        );
        CREATE UNIQUE INDEX auth_accounts_linked_user_audience_uq
            ON auth_accounts (linked_user_id, audience)
            WHERE linked_user_id IS NOT NULL;
        CREATE TABLE courses (
            id INTEGER PRIMARY KEY,
            public_id TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            subject_code TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );
        CREATE TABLE groups (
            group_id TEXT PRIMARY KEY,
            course_id INTEGER NOT NULL,
            public_id TEXT NOT NULL,
            short_code TEXT NOT NULL,
            public_name TEXT NOT NULL,
            status TEXT NOT NULL,
            color_key TEXT,
            sort_order INTEGER NOT NULL
        );
        CREATE TABLE course_enrollments (
            id INTEGER PRIMARY KEY,
            public_id TEXT NOT NULL,
            student_user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            active_group_id TEXT NOT NULL,
            attendance_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            version INTEGER NOT NULL,
            UNIQUE (student_user_id, course_id)
        );
        CREATE TABLE course_group_access (
            enrollment_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            group_id TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_to TEXT
        );
        CREATE INDEX course_group_access_enrollment_history_idx
            ON course_group_access (enrollment_id, valid_from, valid_to);
        CREATE TABLE student_strength (
            student_id INTEGER PRIMARY KEY,
            simple_prob REAL NOT NULL,
            compl_prob REAL NOT NULL
        );
        CREATE TABLE family_student_links (
            family_account_id INTEGER NOT NULL,
            student_user_id INTEGER NOT NULL,
            relationship_label TEXT,
            is_primary INTEGER NOT NULL,
            revoked_at TEXT
        );
        CREATE INDEX family_student_links_student_revoked_idx
            ON family_student_links (student_user_id, revoked_at);
        """
    )


def _seed_directory(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO courses VALUES (1, 'course-math', 'math', 'Математика', 'math', 1)"
    )
    connection.execute(
        "INSERT INTO groups VALUES "
        "('beginner', 1, 'group-beginner', 'н', 'Начинающие', 'active', 'beginner', 1)"
    )
    connection.executemany(
        "INSERT INTO users VALUES (?, ?, ?, ?, NULL, ?, NULL, ?)",
        [
            (
                student_id,
                f"student-{student_id}",
                f"Ученик{student_id:04d}",
                "Тестовый",
                5 + student_id % 3,
                int(USER_TYPE.STUDENT),
            )
            for student_id in range(1, STUDENT_COUNT + 1)
        ],
    )
    connection.executemany(
        "INSERT INTO auth_accounts VALUES (?, ?, 'student', ?, 'active', 1, NULL, ?)",
        [
            (
                student_id,
                f"student-account-{student_id}",
                f"student{student_id}",
                student_id,
            )
            for student_id in range(1, STUDENT_COUNT + 1)
        ],
    )
    connection.executemany(
        "INSERT INTO auth_accounts VALUES (?, ?, 'family', ?, 'active', 1, ?, NULL)",
        [
            (
                STUDENT_COUNT + student_id,
                f"family-account-{student_id}",
                f"family{student_id}",
                f"Семья {student_id}",
            )
            for student_id in range(1, STUDENT_COUNT + 1)
        ],
    )
    connection.executemany(
        "INSERT INTO course_enrollments VALUES "
        "(?, ?, ?, 1, 'beginner', 'online', 'active', 1)",
        [
            (student_id, f"enrollment-{student_id}", student_id)
            for student_id in range(1, STUDENT_COUNT + 1)
        ],
    )
    connection.executemany(
        "INSERT INTO course_group_access VALUES (?, 1, 'beginner', '2026-01-01', NULL)",
        [(student_id,) for student_id in range(1, STUDENT_COUNT + 1)],
    )
    connection.executemany(
        "INSERT INTO student_strength VALUES (?, 5.0, 5.0)",
        [(student_id,) for student_id in range(1, STUDENT_COUNT + 1)],
    )
    connection.executemany(
        "INSERT INTO family_student_links VALUES (?, ?, 'родитель', 1, NULL)",
        [
            (STUDENT_COUNT + student_id, student_id)
            for student_id in range(1, STUDENT_COUNT + 1)
        ],
    )
    connection.commit()


def test_student_directory_handles_1500_students_without_automatic_indexes(tmp_path):
    database = tmp_path / "phase10-directory-performance.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        _create_schema(connection)
        _seed_directory(connection)

        traced: list[str] = []
        connection.set_trace_callback(traced.append)
        started = perf_counter()
        students = list_students(connection)
        enrollment_ids = tuple(int(row["enrollment_id"]) for row in students)
        student_ids = tuple(int(row["student_user_id"]) for row in students)
        group_access = list_active_group_access(connection, enrollment_ids)
        family_links = list_family_links(connection, student_ids)
        elapsed = perf_counter() - started
        connection.set_trace_callback(None)

        assert len(students) == STUDENT_COUNT
        assert len(group_access) == STUDENT_COUNT
        assert len(family_links) == STUDENT_COUNT
        # Regression tripwire rather than a production latency SLO. The entire
        # directory is intentionally one snapshot at this product size.
        assert elapsed < 3.0

        markers = {
            "students": "FROM users AS student",
            "access": "FROM course_group_access AS access",
            "families": "FROM family_student_links AS link",
        }
        plans = {
            name: [
                str(row[3])
                for row in connection.execute(
                    "EXPLAIN QUERY PLAN "
                    + next(statement for statement in traced if marker in statement)
                )
            ]
            for name, marker in markers.items()
        }
        assert any(
            "course_group_access_enrollment_history_idx" in item
            for item in plans["access"]
        )
        assert any(
            "family_student_links_student_revoked_idx" in item
            for item in plans["families"]
        )
        assert all("AUTOMATIC" not in item for plan in plans.values() for item in plan)
        print(f"phase10 directory elapsed={elapsed:.3f}s; plans={plans}")
