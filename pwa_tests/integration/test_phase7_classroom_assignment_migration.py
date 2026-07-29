"""Schema proof for versioned classroom student assignments."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0059.pwa_classroom_assignments"
NOW = "2026-07-29T13:00:00Z"


def _migrations():
    return yoyo.read_migrations(str(MIGRATIONS_ROOT))


def _apply(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(selected))


def _rollback(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(selected))


def _assignment_objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name LIKE 'classroom_assignment%' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_classroom_assignment_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase7-assignments.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0058.pwa_classroom_layouts"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)
    assert _assignment_objects(database_path) == set()

    expected = {
        "classroom_assignment_plans",
        "classroom_assignment_plans_one_working_uq",
        "classroom_assignment_plans_one_confirmed_uq",
        "classroom_assignment_plans_event_timeline_idx",
        "classroom_assignments",
        "classroom_assignments_enrollment_history_idx",
        "classroom_assignments_room_idx",
        "classroom_assignments_insert_working_only",
        "classroom_assignments_update_working_only",
        "classroom_assignments_delete_working_only",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _assignment_objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _assignment_objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
    assert _assignment_objects(database_path) == expected


def _insert_parents(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO users (id, public_id, type, name, surname) "
        "VALUES (1, 'student-assignment', 1, 'Иван', 'Иванов'), "
        "(2, 'admin-assignment', 128, 'Анна', 'Администратор')"
    )
    connection.execute(
        "INSERT INTO seasons "
        "(id, public_id, code, title, starts_on, ends_on, session_expires_on, "
        "status, created_at, updated_at) VALUES "
        "(1, 'season-assignment', 'assignment', 'Assignment', '2025-09-01', "
        "'2026-05-31', '2026-08-10', 'active', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO courses "
        "(id, public_id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(1, 'course-assignment', 1, 'math', 'Математика', 'math', 'active', 1, "
        "'math', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, public_id, course_id, "
        "status, color_key, created_at, updated_at) VALUES "
        "('assignment-n', 'ан', 'Начинающие', 1, 1, 1, 1, 0, 1.0, "
        "'group-assignment', 1, 'active', 'level-1', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO course_enrollments "
        "(id, public_id, student_user_id, course_id, active_group_id, "
        "attendance_mode, status, created_at, updated_at) VALUES "
        "(1, 'enrollment-assignment', 1, 1, 'assignment-n', "
        "'in_person', 'active', ?, ?)",
        (NOW, NOW),
    )
    course_lesson_id = connection.execute(
        "INSERT INTO course_lessons "
        "(public_id, course_id, lesson_number, created_at, updated_at) "
        "VALUES ('course-lesson-assignment', 1, 41, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    group_lesson_id = connection.execute(
        "INSERT INTO group_lessons "
        "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
        "business_timezone, status, created_at, updated_at) VALUES "
        "('group-lesson-assignment', ?, 1, 'assignment-n', '2026-01-01', "
        "'Europe/Moscow', 'active', ?, ?) RETURNING id",
        (course_lesson_id, NOW, NOW),
    ).fetchone()[0]
    room_id = connection.execute(
        "INSERT INTO classrooms "
        "(public_id, name, normalized_name, status, created_by_user_id, "
        "updated_by_user_id, created_at, updated_at) VALUES "
        "('classroom-assignment', '201', '201', 'active', 2, 2, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    event_id = connection.execute(
        "INSERT INTO in_person_events "
        "(public_id, season_id, name, starts_at, ends_at, status, "
        "created_by_user_id, updated_by_user_id, created_at, updated_at) VALUES "
        "('event-assignment', 1, 'Очное занятие', '2026-02-01T10:00:00Z', "
        "'2026-02-01T13:00:00Z', 'scheduled', 2, 2, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO in_person_event_group_lessons "
        "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
        "VALUES (?, ?, 2, ?)",
        (event_id, group_lesson_id, NOW),
    )
    layout_id = connection.execute(
        "INSERT INTO classroom_layout_versions "
        "(public_id, in_person_event_id, state, created_by_user_id, "
        "confirmed_by_user_id, created_at, updated_at, confirmed_at) VALUES "
        "('layout-assignment', ?, 'confirmed', 2, 2, ?, ?, ?) RETURNING id",
        (event_id, NOW, NOW, NOW),
    ).fetchone()[0]
    plan_id = connection.execute(
        "INSERT INTO classroom_assignment_plans "
        "(public_id, in_person_event_id, layout_version_id, state, "
        "created_by_user_id, created_at, updated_at) VALUES "
        "('plan-assignment', ?, ?, 'draft', 2, ?, ?) RETURNING id",
        (event_id, layout_id, NOW, NOW),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO classroom_assignments "
        "(plan_id, course_enrollment_id, group_lesson_id, group_id, "
        "classroom_id, status, source, "
        "created_at, updated_at) VALUES "
        "(?, 1, ?, 'assignment-n', ?, 'assigned', 'least-loaded', ?, ?)",
        (plan_id, group_lesson_id, room_id, NOW, NOW),
    )


def test_confirmed_assignment_rows_are_immutable_and_status_matches_room(tmp_path):
    database_path = tmp_path / "phase7-assignment-constraints.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        plan_id = connection.execute(
            "SELECT id FROM classroom_assignment_plans"
        ).fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                "UPDATE classroom_assignments SET status = 'assigned', classroom_id = NULL "
                "WHERE plan_id = ?",
                (plan_id,),
            )

        connection.execute(
            "UPDATE classroom_assignment_plans SET state = 'confirmed', "
            "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ? WHERE id = ?",
            (NOW, NOW, plan_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="working classroom"):
            connection.execute(
                "UPDATE classroom_assignments SET source = 'manual' WHERE plan_id = ?",
                (plan_id,),
            )
