"""Migration and inheritance proof for Phase-7 classroom layouts."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from models.pwa.classroom_layouts import (
    ClassroomLayoutConflict,
    InvalidClassroomLayout,
    confirm_layout,
    materialize_layout,
    read_effective_layout,
    replace_draft_layout,
)


MIGRATION_ID = "0058.pwa_classroom_layouts"
NOW = "2026-07-29T09:00:00Z"


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


def _layout_objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE "
                "(name LIKE 'in_person_event%' OR name LIKE 'classroom_layout%') "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_classroom_layout_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase7-layout.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0057.pwa_classroom_catalog"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)
    assert _layout_objects(database_path) == set()

    expected = {
        "in_person_events",
        "in_person_events_season_time_idx",
        "in_person_event_group_lessons",
        "in_person_event_group_lessons_lesson_idx",
        "classroom_layout_versions",
        "classroom_layout_versions_one_draft_uq",
        "classroom_layout_versions_one_confirmed_uq",
        "classroom_layout_versions_event_timeline_idx",
        "classroom_layout_rooms",
        "classroom_layout_rooms_group_idx",
        "classroom_layout_rooms_insert_draft_only",
        "classroom_layout_rooms_update_draft_only",
        "classroom_layout_rooms_delete_draft_only",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _layout_objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _layout_objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
    assert _layout_objects(database_path) == expected


def _insert_course(
    connection: sqlite3.Connection,
    *,
    season_id: int,
    code: str,
    name: str,
    sort_order: int,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO courses "
            "(season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?) RETURNING id",
            (
                season_id,
                code,
                name,
                code,
                sort_order,
                code,
                NOW,
                NOW,
            ),
        ).fetchone()[0]
    )


def _insert_group(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
    name: str,
) -> None:
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, course_id, "
        "status, color_key, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, 1, 0, 0, 0, 1.0, ?, 'active', ?, ?, ?)",
        (
            group_id,
            group_id[:3],
            name,
            course_id,
            group_id,
            NOW,
            NOW,
        ),
    )


def _insert_group_lesson(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
    lesson_number: int,
) -> int:
    course_lesson_id = int(
        connection.execute(
            "INSERT INTO course_lessons "
            "(course_id, lesson_number, created_at, updated_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (
                course_id,
                lesson_number,
                NOW,
                NOW,
            ),
        ).fetchone()[0]
    )
    return int(
        connection.execute(
            "INSERT INTO group_lessons "
            "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) "
            "VALUES (?, ?, ?, '2026-01-01', 'Europe/Moscow', 'active', ?, ?) "
            "RETURNING id",
            (
                course_lesson_id,
                course_id,
                group_id,
                NOW,
                NOW,
            ),
        ).fetchone()[0]
    )


def _insert_event(
    connection: sqlite3.Connection,
    *,
    season_id: int,
    actor_id: int,
    name: str,
    starts_at: str,
    group_lesson_ids: Collection[int],
) -> str:
    event_id = int(
        connection.execute(
            "INSERT INTO in_person_events "
            "(season_id, name, starts_at, ends_at, status, "
            "created_by_user_id, updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'scheduled', ?, ?, ?, ?) RETURNING id, public_id",
            (
                season_id,
                name,
                starts_at,
                starts_at.replace("10:00:00", "13:00:00"),
                actor_id,
                actor_id,
                NOW,
                NOW,
            ),
        ).fetchone()[0]
    )
    connection.executemany(
        "INSERT INTO in_person_event_group_lessons "
        "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
        "VALUES (?, ?, ?, ?)",
        (
            (event_id, group_lesson_id, actor_id, NOW)
            for group_lesson_id in group_lesson_ids
        ),
    )
    return str(connection.execute(
        "SELECT public_id FROM in_person_events WHERE id = ?", (event_id,)
    ).fetchone()[0])


def _confirm_single_room(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    room_public_id: str,
    group_lesson_public_id: str,
    actor_id: int,
) -> None:
    draft = materialize_layout(
        connection,
        event_public_id=event_public_id,
        actor_user_id=actor_id,
        now=NOW,
    )
    layout_public_id = str(draft["layout_public_id"])
    draft = replace_draft_layout(
        connection,
        event_public_id=event_public_id,
        layout_public_id=layout_public_id,
        expected_version=1,
        mappings=[(room_public_id, group_lesson_public_id)],
        now=NOW,
    )
    confirm_layout(
        connection,
        event_public_id=event_public_id,
        layout_public_id=layout_public_id,
        expected_version=int(draft["version"]),
        actor_user_id=actor_id,
        now=NOW,
    )


def test_layout_inherits_selected_groups_from_separate_previous_events(tmp_path):
    database_path = tmp_path / "phase7-layout-inheritance.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        actor_id = int(
            connection.execute(
                "INSERT INTO users (type, name, surname) "
                "VALUES (2, 'Layout', 'Admin') RETURNING id"
            ).fetchone()[0]
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) "
                "VALUES ('layout', 'Layout', '2025-09-01', "
                "'2026-05-31', '2026-08-10', 'active', ?, ?) RETURNING id",
                (NOW, NOW),
            ).fetchone()[0]
        )
        math_id = _insert_course(
            connection,
            season_id=season_id,
            code="math",
            name="Математика",
            sort_order=1,
        )
        physics_id = _insert_course(
            connection,
            season_id=season_id,
            code="physics",
            name="Физика",
            sort_order=2,
        )
        _insert_group(
            connection,
            course_id=math_id,
            group_id="math-beginner",
            name="Начинающие",
        )
        _insert_group(
            connection,
            course_id=physics_id,
            group_id="physics-intro",
            name="Знакомство",
        )
        math_40 = _insert_group_lesson(
            connection, course_id=math_id, group_id="math-beginner", lesson_number=40
        )
        math_41 = _insert_group_lesson(
            connection, course_id=math_id, group_id="math-beginner", lesson_number=41
        )
        physics_8 = _insert_group_lesson(
            connection, course_id=physics_id, group_id="physics-intro", lesson_number=8
        )
        physics_9 = _insert_group_lesson(
            connection, course_id=physics_id, group_id="physics-intro", lesson_number=9
        )
        connection.executemany(
            "INSERT INTO classrooms "
            "(name, normalized_name, status, created_by_user_id, "
            "updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, 'active', ?, ?, ?, ?)",
            (
                ("201", "201", actor_id, actor_id, NOW, NOW),
                ("401", "401", actor_id, actor_id, NOW, NOW),
            ),
        )
        math_event = _insert_event(
            connection,
            season_id=season_id,
            actor_id=actor_id,
            name="Математика 40",
            starts_at="2026-01-18T10:00:00Z",
            group_lesson_ids=[math_40],
        )
        physics_event = _insert_event(
            connection,
            season_id=season_id,
            actor_id=actor_id,
            name="Физика 8",
            starts_at="2026-01-25T10:00:00Z",
            group_lesson_ids=[physics_8],
        )
        _confirm_single_room(
            connection,
            event_public_id=math_event,
            room_public_id="room-1",
            group_lesson_public_id="gl-1",
            actor_id=actor_id,
        )
        _confirm_single_room(
            connection,
            event_public_id=physics_event,
            room_public_id="room-2",
            group_lesson_public_id="gl-3",
            actor_id=actor_id,
        )
        combined_event = _insert_event(
            connection,
            season_id=season_id,
            actor_id=actor_id,
            name="Совмещённое занятие",
            starts_at="2026-02-01T10:00:00Z",
            group_lesson_ids=[math_41, physics_9],
        )

        inherited = read_effective_layout(connection, combined_event)
        assert inherited["state"] == "inherited"
        assert {
            (room["classroom_name"], room["group_lesson_public_id"])
            for room in inherited["rooms"]
        } == {
            ("201", "gl-2"),
            ("401", "gl-4"),
        }
        assert inherited["conflicts"] == []

        draft = materialize_layout(
            connection,
            event_public_id=combined_event,
            actor_user_id=actor_id,
            now="2026-07-29T09:05:00Z",
        )
        assert draft["state"] == "draft"
        assert draft["version"] == 1
        confirmed = confirm_layout(
            connection,
            event_public_id=combined_event,
            layout_public_id=str(draft["layout_public_id"]),
            expected_version=1,
            actor_user_id=actor_id,
            now="2026-07-29T09:06:00Z",
        )
        assert confirmed["state"] == "confirmed"
        assert confirmed["version"] == 2

        with pytest.raises(ClassroomLayoutConflict):
            confirm_layout(
                connection,
                event_public_id=combined_event,
                layout_public_id=str(draft["layout_public_id"]),
                expected_version=1,
                actor_user_id=actor_id,
                now="2026-07-29T09:07:00Z",
            )

        next_draft = materialize_layout(
            connection,
            event_public_id=combined_event,
            actor_user_id=actor_id,
            now="2026-07-29T09:08:00Z",
        )
        assert next_draft["base_version_id"] is not None
        with pytest.raises(InvalidClassroomLayout, match="more than once"):
            replace_draft_layout(
                connection,
                event_public_id=combined_event,
                layout_public_id=str(next_draft["layout_public_id"]),
                expected_version=1,
                mappings=[
                    ("room-1", "gl-2"),
                    ("room-1", "gl-4"),
                ],
                now="2026-07-29T09:09:00Z",
            )
        with pytest.raises(InvalidClassroomLayout, match="non-participating"):
            replace_draft_layout(
                connection,
                event_public_id=combined_event,
                layout_public_id=str(next_draft["layout_public_id"]),
                expected_version=1,
                mappings=[("room-1", "gl-1")],
                now="2026-07-29T09:10:00Z",
            )
        connection.execute(
            "UPDATE classrooms SET status = 'archived' WHERE public_id = 'room-2'"
        )
        with pytest.raises(InvalidClassroomLayout, match="archived"):
            confirm_layout(
                connection,
                event_public_id=combined_event,
                layout_public_id=str(next_draft["layout_public_id"]),
                expected_version=1,
                actor_user_id=actor_id,
                now="2026-07-29T09:11:00Z",
            )
        assert (
            connection.execute(
                "SELECT state FROM classroom_layout_versions WHERE public_id = ?",
                (str(draft["layout_public_id"]),),
            ).fetchone()[0]
            == "confirmed"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM classroom_layout_rooms WHERE layout_version_id = "
                "(SELECT id FROM classroom_layout_versions WHERE public_id = ?)",
                (str(draft["layout_public_id"]),),
            )

        source_count = connection.execute(
            "SELECT count(DISTINCT source_layout_version_id) "
            "FROM classroom_layout_rooms lr "
            "JOIN classroom_layout_versions lv ON lv.id = lr.layout_version_id "
            "WHERE lv.public_id = ?",
            (str(draft["layout_public_id"]),),
        ).fetchone()[0]
        assert source_count == 2
