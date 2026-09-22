"""Schema proof for versioned classroom student assignments."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from datetime import date
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from models.pwa.classroom_assignments import (
    ClassroomAssignmentConflict,
    InvalidClassroomAssignment,
    confirm_assignment_plan,
    recalculate_assignment_plan,
    read_assignment_history,
    update_assignment_plan,
)
from models.pwa.classroom_layouts import confirm_layout, materialize_layout
from models.pwa.classroom_public import read_student_classroom_assignments


MIGRATION_ID = "0059.pwa_classroom_assignments"
PREFERENCE_MIGRATION_ID = "0097.pwa_classroom_assignment_preferences"
COMPACTION_MIGRATION_ID = "0099.pwa_classroom_assignment_compaction"
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
                "SELECT name FROM sqlite_schema WHERE "
                "(name LIKE 'classroom_assignment_plans%' "
                "OR name LIKE 'classroom_assignments%') "
                "AND name NOT LIKE 'classroom_assignment_delivery%' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_classroom_assignment_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase7-assignments.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0058.pwa_classroom_layouts"
    }
    preceding = {
        item.id
        for item in migrations.values()
        if item.id not in {MIGRATION_ID, PREFERENCE_MIGRATION_ID, COMPACTION_MIGRATION_ID}
    }
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


def test_compaction_migration_prunes_snapshots_and_preserves_referenced_headers(tmp_path):
    database_path = tmp_path / "phase7-assignment-compaction.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[COMPACTION_MIGRATION_ID].depends} == {
        "0098.pwa_account_locale"
    }
    _apply(database_path, set(migrations) - {COMPACTION_MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        current_id = int(
            connection.execute("SELECT id FROM classroom_assignment_plans").fetchone()[0]
        )
        connection.execute(
            "UPDATE classroom_assignment_plans SET state = 'confirmed', "
            "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ? WHERE id = ?",
            (NOW, NOW, current_id),
        )
        plan_ids = [current_id]
        for _index in range(3):
            next_id = int(
                connection.execute(
                    "INSERT INTO classroom_assignment_plans "
                    "(in_person_event_id, layout_version_id, base_plan_id, state, "
                    "created_by_user_id, created_at, updated_at) "
                    "SELECT in_person_event_id, layout_version_id, id, 'draft', 2, ?, ? "
                    "FROM classroom_assignment_plans WHERE id = ? RETURNING id",
                    (NOW, NOW, current_id),
                ).fetchone()[0]
            )
            connection.execute(
                "INSERT INTO classroom_assignments "
                "(plan_id, course_enrollment_id, group_lesson_id, group_id, "
                "classroom_id, status, source, created_at, updated_at) "
                "SELECT ?, course_enrollment_id, group_lesson_id, group_id, "
                "classroom_id, status, source, ?, ? FROM classroom_assignments "
                "WHERE plan_id = ?",
                (next_id, NOW, NOW, current_id),
            )
            connection.execute(
                "UPDATE classroom_assignment_plans SET state = 'superseded', "
                "superseded_at = ?, updated_at = ? WHERE id = ?",
                (NOW, NOW, current_id),
            )
            connection.execute(
                "UPDATE classroom_assignment_plans SET state = 'confirmed', "
                "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ? "
                "WHERE id = ?",
                (NOW, NOW, next_id),
            )
            current_id = next_id
            plan_ids.append(current_id)

        working_id = int(
            connection.execute(
                "INSERT INTO classroom_assignment_plans "
                "(in_person_event_id, layout_version_id, base_plan_id, state, "
                "created_by_user_id, created_at, updated_at) "
                "SELECT in_person_event_id, layout_version_id, id, 'draft', 2, ?, ? "
                "FROM classroom_assignment_plans WHERE id = ? RETURNING id",
                (NOW, NOW, current_id),
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO classroom_assignments "
            "(plan_id, course_enrollment_id, group_lesson_id, group_id, classroom_id, "
            "status, source, created_at, updated_at) "
            "SELECT ?, course_enrollment_id, group_lesson_id, group_id, classroom_id, "
            "status, source, ?, ? FROM classroom_assignments WHERE plan_id = ?",
            (working_id, NOW, NOW, current_id),
        )
        connection.execute(
            "INSERT INTO classroom_assignment_delivery_batches "
            "(assignment_plan_id, assignment_plan_version, requested_by_user_id, "
            "pwa_selected, telegram_selected, recipient_snapshot_hash, recipient_count, "
            "changed_since_previous_count, state, idempotency_key, created_at, completed_at) "
            "VALUES (?, 1, 2, 1, 0, ?, 0, 0, 'completed', 'migration-delivery', ?, ?)",
            (plan_ids[0], "0" * 64, NOW, NOW),
        )
        layout_id = int(
            connection.execute(
                "SELECT layout_version_id FROM classroom_assignment_plans WHERE id = ?",
                (current_id,),
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO classroom_import_receipts "
            "(in_person_event_id, source_sha256, preview_sha256, source_sheet, "
            "source_row_count, classroom_count, assignment_count, layout_version_id, "
            "assignment_plan_id, actor_user_id, applied_at) "
            "SELECT in_person_event_id, ?, ?, 'Assignments', 1, 1, 1, ?, ?, 2, ? "
            "FROM classroom_assignment_plans WHERE id = ?",
            ("1" * 64, "2" * 64, layout_id, plan_ids[1], NOW, current_id),
        )

    _apply(database_path, {COMPACTION_MIGRATION_ID})

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        stored = connection.execute(
            "SELECT id, state, base_plan_id, base_plan_version "
            "FROM classroom_assignment_plans ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in stored] == [
            (plan_ids[0], "superseded", None, None),
            (plan_ids[1], "superseded", None, None),
            (current_id, "confirmed", None, None),
            (working_id, "draft", current_id, 1),
        ]
        assignment_counts = connection.execute(
            "SELECT plan_id, count(*) FROM classroom_assignments GROUP BY plan_id "
            "ORDER BY plan_id"
        ).fetchall()
        assert [tuple(row) for row in assignment_counts] == [
            (current_id, 1),
            (working_id, 1),
        ]
        assert connection.execute(
            "SELECT next_id FROM classroom_assignment_plan_sequence"
        ).fetchone()[0] == working_id + 1
        relevant_tables = {
            "classroom_assignment_plans",
            "classroom_assignments",
            "classroom_assignment_delivery_batches",
            "classroom_import_receipts",
        }
        assignment_violations = [
            tuple(row)
            for row in connection.execute("PRAGMA foreign_key_check")
            if row[0] in relevant_tables
        ]
        assert assignment_violations == []
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def _insert_parents(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO users (id, type, name, surname) "
        "VALUES (1, 1, 'Иван', 'Иванов'), "
        "(2, 128, 'Анна', 'Администратор')"
    )
    connection.execute(
        "INSERT INTO seasons "
        "(id, code, title, starts_on, ends_on, session_expires_on, "
        "status, created_at, updated_at) VALUES "
        "(1, 'assignment', 'Assignment', '2025-09-01', "
        "'2026-05-31', '2026-08-10', 'active', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO courses "
        "(id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(1, 1, 'math', 'Математика', 'math', 'active', 1, "
        "'math', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, course_id, "
        "status, color_key, created_at, updated_at) VALUES "
        "('assignment-n', 'ан', 'Начинающие', 1, 1, 1, 1, 0, 1.0, "
        "1, 'active', 'level-1', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO course_enrollments "
        "(id, student_user_id, course_id, active_group_id, "
        "attendance_mode, status, created_at, updated_at) VALUES "
        "(1, 1, 1, 'assignment-n', "
        "'in_person', 'active', ?, ?)",
        (NOW, NOW),
    )
    course_lesson_id = connection.execute(
        "INSERT INTO course_lessons "
        "(course_id, lesson_number, created_at, updated_at) "
        "VALUES (1, 41, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    group_lesson_id = connection.execute(
        "INSERT INTO group_lessons "
        "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
        "business_timezone, status, created_at, updated_at) VALUES "
        "(?, 1, 'assignment-n', '2026-01-01', "
        "'Europe/Moscow', 'active', ?, ?) RETURNING id",
        (course_lesson_id, NOW, NOW),
    ).fetchone()[0]
    room_id = connection.execute(
        "INSERT INTO classrooms "
        "(name, normalized_name, status, created_by_user_id, "
        "updated_by_user_id, created_at, updated_at) VALUES "
        "('201', '201', 'active', 2, 2, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    event_id = connection.execute(
        "INSERT INTO in_person_events "
        "(season_id, name, starts_at, ends_at, status, "
        "created_by_user_id, updated_by_user_id, created_at, updated_at) VALUES "
        "(1, 'Очное занятие', '2026-02-01T10:00:00Z', "
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
        "(in_person_event_id, state, created_by_user_id, "
        "created_at, updated_at) VALUES "
        "(?, 'draft', 2, ?, ?) RETURNING id",
        (event_id, NOW, NOW),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO classroom_layout_rooms "
        "(layout_version_id, classroom_id, group_lesson_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (layout_id, room_id, group_lesson_id, NOW, NOW),
    )
    connection.execute(
        "UPDATE classroom_layout_versions SET state = 'confirmed', "
        "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ? WHERE id = ?",
        (NOW, NOW, layout_id),
    )
    plan_id = connection.execute(
        "INSERT INTO classroom_assignment_plans "
        "(in_person_event_id, layout_version_id, state, "
        "created_by_user_id, created_at, updated_at) VALUES "
        "(?, ?, 'draft', 2, ?, ?) RETURNING id",
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


def test_assignment_status_matches_room_and_archived_rows_are_immutable(tmp_path):
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
        connection.execute(
            "UPDATE classroom_assignments SET source = 'manual' WHERE plan_id = ?",
            (plan_id,),
        )
        connection.execute(
            "UPDATE classroom_assignment_plans SET state = 'superseded', "
            "superseded_at = ?, updated_at = ? WHERE id = ?",
            (NOW, NOW, plan_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="archived classroom"):
            connection.execute(
                "UPDATE classroom_assignments SET source = 'least-loaded' "
                "WHERE plan_id = ?",
                (plan_id,),
            )


def test_manual_preference_migration_backfills_existing_staff_move(tmp_path):
    database_path = tmp_path / "phase7-assignment-preference-backfill.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute(
            "UPDATE classroom_assignments SET source = 'manual', updated_at = ?",
            ("2026-07-29T13:05:00Z",),
        )

    _rollback(database_path, {PREFERENCE_MIGRATION_ID})
    _apply(database_path, {PREFERENCE_MIGRATION_ID})

    with sqlite3.connect(database_path) as connection:
        preference = connection.execute(
            "SELECT course_enrollment_id, classroom_id, set_by_user_id, "
            "created_at, updated_at, version FROM classroom_assignment_preferences"
        ).fetchone()
        assert preference == (
            1,
            1,
            2,
            "2026-07-29T13:05:00Z",
            "2026-07-29T13:05:00Z",
            1,
        )


def test_assignment_plan_recalculates_and_confirms(tmp_path):
    database_path = tmp_path / "phase7-assignment-plan.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")
        connection.execute(
            "UPDATE users SET birthday = '2013-01-01', grade = 7 WHERE id = 1"
        )
        connection.execute(
            "INSERT INTO student_strength (student_id, simple_prob, compl_prob) "
            "VALUES (1, 0.5, 1.0)"
        )

        preview = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
            today=date(2026, 7, 29),
        )

        assert preview["plan"]["state"] == "draft"
        assert preview["plan"]["version"] == 1
        assert len(preview["students"]) == 1
        assert preview["students"][0]["classroom_name"] == "201"
        assert preview["students"][0]["age_years"] == 13.6
        assert preview["students"][0]["grade"] == 7
        assert preview["students"][0]["strength"] == 8.0

        confirmed = confirm_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(preview["plan"]["public_id"]),
            expected_version=1,
            actor_user_id=2,
            now="2026-07-29T13:01:00Z",
            today=date(2026, 7, 29),
        )

        assert confirmed["plan"]["state"] == "confirmed"
        assert confirmed["plan"]["version"] == 2


def test_fifty_confirmations_keep_one_plan_and_never_reuse_draft_ids(tmp_path):
    database_path = tmp_path / "phase7-assignment-history.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")
        first = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now="2026-07-29T13:01:00Z",
        )
        confirmed = confirm_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(first["plan"]["public_id"]),
            expected_version=int(first["plan"]["version"]),
            actor_user_id=2,
            now="2026-07-29T13:02:00Z",
        )
        confirmed_public_id = str(confirmed["plan"]["public_id"])
        draft_public_ids: set[str] = set()
        for index in range(49):
            draft = recalculate_assignment_plan(
                connection,
                event_public_id="ipe-1",
                plan_public_id=None,
                expected_version=None,
                actor_user_id=2,
                now=f"2026-07-29T14:{index:02d}:00Z",
            )
            draft_public_ids.add(str(draft["plan"]["public_id"]))
            result = confirm_assignment_plan(
                connection,
                event_public_id="ipe-1",
                plan_public_id=str(draft["plan"]["public_id"]),
                expected_version=int(draft["plan"]["version"]),
                actor_user_id=2,
                now=f"2026-07-29T15:{index:02d}:00Z",
            )
            assert result["plan"]["public_id"] == confirmed_public_id

        assert len(draft_public_ids) == 49
        assert confirmed_public_id not in draft_public_ids
        assert connection.execute(
            "SELECT count(*) FROM classroom_assignment_plans"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM classroom_assignments"
        ).fetchone()[0] == 1
        assert tuple(
            connection.execute(
                "SELECT version, confirmed_at FROM classroom_assignment_plans "
                "WHERE state = 'confirmed'"
            ).fetchone()
        ) == (2, "2026-07-29T13:02:00Z")
        enrollment_public_id = str(
            connection.execute(
                "SELECT public_id FROM course_enrollments WHERE id = 1"
            ).fetchone()[0]
        )

        history = read_assignment_history(
            connection,
            event_public_id="ipe-1",
            plan_public_id=confirmed_public_id,
            enrollment_public_id=enrollment_public_id,
        )

        assert len(history) == 1
        assert history[0]["plan_public_id"] == confirmed_public_id


def test_confirmation_updates_same_plan_when_students_join_and_leave(tmp_path):
    database_path = tmp_path / "phase7-assignment-membership-changes.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")

        draft = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now="2026-07-29T13:01:00Z",
        )
        confirmed = confirm_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(draft["plan"]["public_id"]),
            expected_version=int(draft["plan"]["version"]),
            actor_user_id=2,
            now="2026-07-29T13:02:00Z",
        )
        confirmed_id = str(confirmed["plan"]["public_id"])
        initial_version = int(confirmed["plan"]["version"])

        connection.execute(
            "INSERT INTO users (id, type, name, surname) "
            "VALUES (3, 1, 'Пётр', 'Петров')"
        )
        connection.execute(
            "INSERT INTO course_enrollments "
            "(id, student_user_id, course_id, active_group_id, attendance_mode, "
            "status, created_at, updated_at) "
            "VALUES (2, 3, 1, 'assignment-n', 'in_person', 'active', ?, ?)",
            (NOW, NOW),
        )
        joined = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now="2026-07-29T13:03:00Z",
        )
        assert len(joined["students"]) == 2
        joined_result = confirm_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(joined["plan"]["public_id"]),
            expected_version=int(joined["plan"]["version"]),
            actor_user_id=2,
            now="2026-07-29T13:04:00Z",
        )
        assert joined_result["plan"]["public_id"] == confirmed_id
        assert joined_result["plan"]["version"] == initial_version + 1
        assert len(joined_result["students"]) == 2

        connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'online' WHERE id = 1"
        )
        left = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now="2026-07-29T13:05:00Z",
        )
        left_result = confirm_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(left["plan"]["public_id"]),
            expected_version=int(left["plan"]["version"]),
            actor_user_id=2,
            now="2026-07-29T13:06:00Z",
        )
        assert left_result["plan"]["public_id"] == confirmed_id
        assert left_result["plan"]["version"] == initial_version + 2
        assert [student["student_user_id"] for student in left_result["students"]] == [3]
        assert connection.execute(
            "SELECT count(*) FROM classroom_assignment_plans"
        ).fetchone()[0] == 1


def test_confirmation_rejects_draft_based_on_changed_confirmed_plan(tmp_path):
    database_path = tmp_path / "phase7-assignment-concurrent-admins.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")

        first = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )
        confirmed = confirm_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(first["plan"]["public_id"]),
            expected_version=1,
            actor_user_id=2,
            now="2026-07-29T13:01:00Z",
        )
        draft = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now="2026-07-29T13:02:00Z",
        )

        connection.execute(
            "UPDATE classroom_assignment_plans SET version = version + 1, updated_at = ? "
            "WHERE public_id = ?",
            ("2026-07-29T13:03:00Z", confirmed["plan"]["public_id"]),
        )

        with pytest.raises(ClassroomAssignmentConflict):
            confirm_assignment_plan(
                connection,
                event_public_id="ipe-1",
                plan_public_id=str(draft["plan"]["public_id"]),
                expected_version=int(draft["plan"]["version"]),
                actor_user_id=2,
                now="2026-07-29T13:04:00Z",
            )


def test_manual_room_preference_survives_recalculation(tmp_path):
    database_path = tmp_path / "phase7-manual-room-preference.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")
        layout_id = connection.execute(
            "SELECT id FROM classroom_layout_versions WHERE state = 'confirmed'"
        ).fetchone()[0]
        group_lesson_id = connection.execute(
            "SELECT id FROM group_lessons WHERE group_id = 'assignment-n'"
        ).fetchone()[0]
        room_id = connection.execute(
            "INSERT INTO classrooms "
            "(name, normalized_name, status, created_by_user_id, "
            "updated_by_user_id, created_at, updated_at) VALUES "
            "('202', '202', 'active', 2, 2, ?, ?) RETURNING id",
            (NOW, NOW),
        ).fetchone()[0]
        connection.execute(
            "UPDATE classroom_layout_versions SET state = 'draft', "
            "confirmed_by_user_id = NULL, confirmed_at = NULL WHERE id = ?",
            (layout_id,),
        )
        connection.execute(
            "INSERT INTO classroom_layout_rooms "
            "(layout_version_id, classroom_id, group_lesson_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (layout_id, room_id, group_lesson_id, NOW, NOW),
        )
        connection.execute(
            "UPDATE classroom_layout_versions SET state = 'confirmed', "
            "confirmed_by_user_id = 2, confirmed_at = ? WHERE id = ?",
            (NOW, layout_id),
        )

        initial = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )
        enrollment_public_id = str(initial["students"][0]["enrollment_public_id"])
        classroom_public_id = str(
            connection.execute(
                "SELECT public_id FROM classrooms WHERE id = ?", (room_id,)
            ).fetchone()[0]
        )
        moved = update_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(initial["plan"]["public_id"]),
            expected_version=int(initial["plan"]["version"]),
            assignments=((enrollment_public_id, classroom_public_id, False),),
            actor_user_id=2,
            request_id="manual-room-preference",
            now="2026-07-29T13:01:00Z",
        )
        assert moved["students"][0]["classroom_name"] == "202"
        assert moved["students"][0]["source"] == "manual"

        recalculated = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=str(moved["plan"]["public_id"]),
            expected_version=int(moved["plan"]["version"]),
            actor_user_id=2,
            now="2026-07-29T13:02:00Z",
        )

        assert recalculated["students"][0]["classroom_name"] == "202"
        assert recalculated["students"][0]["source"] == "manual"
        preference = connection.execute(
            "SELECT classroom_id, set_by_user_id, version "
            "FROM classroom_assignment_preferences WHERE course_enrollment_id = 1"
        ).fetchone()
        assert tuple(preference) == (room_id, 2, 1)


def test_student_projection_uses_only_current_confirmed_assignment(tmp_path):
    database_path = tmp_path / "phase7-public-assignment.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)

        assert read_student_classroom_assignments(connection, 1)[0]["status"] == (
            "reassigning"
        )

        connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'online' WHERE id = 1"
        )
        online = read_student_classroom_assignments(connection, 1)[0]
        assert online["status"] == "not_applicable"
        assert online["classroom_name"] is None

        connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'in_person' WHERE id = 1"
        )
        connection.execute(
            "UPDATE classroom_assignment_plans SET state = 'confirmed', "
            "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ?",
            (NOW, NOW),
        )
        assigned = read_student_classroom_assignments(connection, 1)[0]
        assert assigned["status"] == "assigned"
        assert assigned["classroom_name"] == "201"
        assert assigned["confirmed_at"] == NOW
        assert assigned["announced_at"] is None

        connection.execute(
            "UPDATE classrooms SET status = 'archived' "
            "WHERE public_id = 'room-1'"
        )
        unavailable = read_student_classroom_assignments(connection, 1)[0]
        assert unavailable["status"] == "reassigning"
        assert unavailable["classroom_name"] is None


def test_assignment_plan_without_room_cannot_be_confirmed(tmp_path):
    database_path = tmp_path / "phase7-assignment-no-room.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")
        layout_id = connection.execute(
            "SELECT id FROM classroom_layout_versions WHERE state = 'confirmed'"
        ).fetchone()[0]
        connection.execute(
            "UPDATE classroom_layout_versions SET state = 'superseded', "
            "superseded_at = ?, updated_at = ? WHERE id = ?",
            (NOW, NOW, layout_id),
        )
        empty_layout_id = connection.execute(
            "INSERT INTO classroom_layout_versions "
            "(in_person_event_id, state, created_by_user_id, created_at, updated_at) "
            "SELECT in_person_event_id, 'draft', 2, ?, ? "
            "FROM classroom_layout_versions WHERE id = ? RETURNING id",
            (NOW, NOW, layout_id),
        ).fetchone()[0]
        connection.execute(
            "UPDATE classroom_layout_versions SET state = 'confirmed', "
            "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ? WHERE id = ?",
            (NOW, NOW, empty_layout_id),
        )

        preview = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )

        assert preview["students"][0]["status"] == "reassigning"
        assert preview["students"][0]["classroom_id"] is None
        with pytest.raises(InvalidClassroomAssignment):
            confirm_assignment_plan(
                connection,
                event_public_id="ipe-1",
                plan_public_id=str(preview["plan"]["public_id"]),
                expected_version=1,
                actor_user_id=2,
                now=NOW,
            )


def test_confirming_new_layout_marks_and_rebases_working_assignment_plan(tmp_path):
    database_path = tmp_path / "phase7-assignment-layout-rebase.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")

        initial = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )
        assert initial["plan"]["version"] == 1
        initial_public_id = str(initial["plan"]["public_id"])

        materialized = materialize_layout(
            connection,
            event_public_id="ipe-1",
            actor_user_id=2,
            now="2026-07-29T13:01:00Z",
        )
        assert materialized["state"] == "draft"
        confirm_layout(
            connection,
            event_public_id="ipe-1",
            layout_public_id="clv-2",
            expected_version=1,
            actor_user_id=2,
            now="2026-07-29T13:02:00Z",
        )
        stale = connection.execute(
            "SELECT state, stale_reason, version FROM classroom_assignment_plans "
            "WHERE public_id = ?",
            (initial_public_id,),
        ).fetchone()
        assert tuple(stale) == ("stale", "layout_changed", 2)

        recalculated = recalculate_assignment_plan(
            connection,
            event_public_id="ipe-1",
            plan_public_id=initial_public_id,
            expected_version=2,
            actor_user_id=2,
            now="2026-07-29T13:03:00Z",
        )
        assert recalculated["plan"]["public_id"] == initial_public_id
        assert (recalculated["plan"]["state"], recalculated["plan"]["version"]) == (
            "draft",
            3,
        )
        assert recalculated["students"][0]["classroom_name"] == "201"
