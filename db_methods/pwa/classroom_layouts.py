"""Small SQLite operations for in-person events and classroom layouts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def get_in_person_event(
    connection: sqlite3.Connection, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, season_id, name, starts_at, ends_at, status, version "
        "FROM in_person_events WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_event_group_lessons(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT gl.id AS group_lesson_id, gl.public_id AS group_lesson_public_id,
               gl.course_id, gl.group_id, c.public_id AS course_public_id,
               c.name AS course_name, g.public_id AS group_public_id,
               g.public_name AS group_name, g.short_code, g.color_key,
               cl.lesson_number,
               (
                   SELECT count(*)
                   FROM course_enrollments enrollment
                   WHERE enrollment.course_id = gl.course_id
                     AND enrollment.active_group_id = gl.group_id
                     AND enrollment.status = 'active'
                     AND enrollment.attendance_mode = 'in_person'
               ) AS in_person_count
        FROM in_person_event_group_lessons ep
        JOIN group_lessons gl ON gl.id = ep.group_lesson_id
        JOIN course_lessons cl ON cl.id = gl.course_lesson_id
        JOIN courses c ON c.id = gl.course_id
        JOIN groups g ON g.course_id = gl.course_id AND g.group_id = gl.group_id
        WHERE ep.in_person_event_id = ?
        ORDER BY c.sort_order, c.id, g.sort_order, g.group_id, gl.id
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_layout_version(
    connection: sqlite3.Connection, layout_id: int
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, in_person_event_id, base_version_id, state, "
        "created_at, updated_at, confirmed_at, superseded_at, version "
        "FROM classroom_layout_versions WHERE id = ?",
        (layout_id,),
    ).fetchone()
    return None if row is None else dict(row)


def get_layout_version_by_public_id(
    connection: sqlite3.Connection, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, in_person_event_id, base_version_id, state, "
        "created_at, updated_at, confirmed_at, superseded_at, version "
        "FROM classroom_layout_versions WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def find_event_layout(
    connection: sqlite3.Connection, event_id: int, state: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, in_person_event_id, base_version_id, state, "
        "created_at, updated_at, confirmed_at, superseded_at, version "
        "FROM classroom_layout_versions "
        "WHERE in_person_event_id = ? AND state = ? ORDER BY id DESC LIMIT 1",
        (event_id, state),
    ).fetchone()
    return None if row is None else dict(row)


def find_latest_confirmed_layout_for_group(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
    before_starts_at: str,
) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT lv.id AS layout_id, lv.public_id AS layout_public_id,
               gl.id AS source_group_lesson_id, event.public_id AS event_public_id
        FROM classroom_layout_versions lv
        JOIN in_person_events event ON event.id = lv.in_person_event_id
        JOIN in_person_event_group_lessons ep
          ON ep.in_person_event_id = event.id
        JOIN group_lessons gl ON gl.id = ep.group_lesson_id
        WHERE lv.state = 'confirmed'
          AND event.starts_at < ?
          AND gl.course_id = ?
          AND gl.group_id = ?
        ORDER BY event.starts_at DESC, lv.confirmed_at DESC, lv.id DESC
        LIMIT 1
        """,
        (before_starts_at, course_id, group_id),
    ).fetchone()
    return None if row is None else dict(row)


def list_layout_rooms(
    connection: sqlite3.Connection,
    layout_id: int,
    *,
    group_lesson_id: int | None = None,
) -> list[dict[str, object]]:
    group_filter = " AND lr.group_lesson_id = ?" if group_lesson_id is not None else ""
    values: tuple[object, ...] = (
        (layout_id, group_lesson_id) if group_lesson_id is not None else (layout_id,)
    )
    rows = connection.execute(
        """
        SELECT room.public_id AS classroom_public_id, room.name AS classroom_name,
               room.status AS classroom_status, room.version AS classroom_version,
               lr.classroom_id, lr.group_lesson_id, lr.source_layout_version_id,
               source.public_id AS source_layout_public_id
        FROM classroom_layout_rooms lr
        JOIN classrooms room ON room.id = lr.classroom_id
        LEFT JOIN classroom_layout_versions source
          ON source.id = lr.source_layout_version_id
        WHERE lr.layout_version_id = ?
        """
        + group_filter
        + " ORDER BY room.normalized_name, room.id",
        values,
    ).fetchall()
    return [dict(row) for row in rows]


def resolve_layout_room_input(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    classroom_public_id: str,
    group_lesson_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT room.id AS classroom_id, room.status AS classroom_status,
               gl.id AS group_lesson_id
        FROM classrooms room
        JOIN group_lessons gl ON gl.public_id = ?
        JOIN in_person_event_group_lessons ep
          ON ep.group_lesson_id = gl.id AND ep.in_person_event_id = ?
        WHERE room.public_id = ?
        """,
        (group_lesson_public_id, event_id, classroom_public_id),
    ).fetchone()
    return None if row is None else dict(row)


def insert_layout_version(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    event_id: int,
    base_version_id: int | None,
    actor_user_id: int,
    now: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO classroom_layout_versions (
            public_id, in_person_event_id, base_version_id, state,
            created_by_user_id, created_at, updated_at, version
        ) VALUES (?, ?, ?, 'draft', ?, ?, ?, 1)
        """,
        (public_id, event_id, base_version_id, actor_user_id, now, now),
    )
    return int(cursor.lastrowid)


def replace_layout_rooms(
    connection: sqlite3.Connection,
    *,
    layout_id: int,
    rooms: Iterable[tuple[int, int, int | None]],
    now: str,
) -> None:
    connection.execute(
        "DELETE FROM classroom_layout_rooms WHERE layout_version_id = ?",
        (layout_id,),
    )
    connection.executemany(
        """
        INSERT INTO classroom_layout_rooms (
            layout_version_id, classroom_id, group_lesson_id,
            source_layout_version_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (layout_id, classroom_id, group_lesson_id, source_layout_id, now, now)
            for classroom_id, group_lesson_id, source_layout_id in rooms
        ),
    )


def touch_layout_version(
    connection: sqlite3.Connection,
    *,
    layout_id: int,
    expected_version: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE classroom_layout_versions "
        "SET updated_at = ?, version = version + 1 "
        "WHERE id = ? AND state = 'draft' AND version = ?",
        (now, layout_id, expected_version),
    )
    return cursor.rowcount == 1


def supersede_confirmed_layout(
    connection: sqlite3.Connection, *, event_id: int, now: str
) -> None:
    connection.execute(
        "UPDATE classroom_layout_versions "
        "SET state = 'superseded', superseded_at = ?, updated_at = ? "
        "WHERE in_person_event_id = ? AND state = 'confirmed'",
        (now, now, event_id),
    )


def confirm_draft_layout(
    connection: sqlite3.Connection,
    *,
    layout_id: int,
    expected_version: int,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE classroom_layout_versions "
        "SET state = 'confirmed', confirmed_by_user_id = ?, confirmed_at = ?, "
        "updated_at = ?, version = version + 1 "
        "WHERE id = ? AND state = 'draft' AND version = ?",
        (actor_user_id, now, now, layout_id, expected_version),
    )
    return cursor.rowcount == 1


__all__ = [
    "confirm_draft_layout",
    "find_event_layout",
    "find_latest_confirmed_layout_for_group",
    "get_in_person_event",
    "get_layout_version",
    "get_layout_version_by_public_id",
    "insert_layout_version",
    "list_event_group_lessons",
    "list_layout_rooms",
    "replace_layout_rooms",
    "resolve_layout_room_input",
    "supersede_confirmed_layout",
    "touch_layout_version",
]
