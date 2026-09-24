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


def list_in_person_events(
    connection: sqlite3.Connection, *, season_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT id, public_id, season_id, name, starts_at, ends_at, status, version "
        "FROM in_person_events WHERE season_id = ? "
        "ORDER BY starts_at DESC, id DESC",
        (season_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_group_lesson_candidates(
    connection: sqlite3.Connection, *, season_id: int
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
        FROM group_lessons gl
        JOIN course_lessons cl ON cl.id = gl.course_lesson_id
        JOIN courses c ON c.id = gl.course_id
        JOIN groups g ON g.course_id = gl.course_id AND g.group_id = gl.group_id
        WHERE c.season_id = ?
          AND c.status = 'active'
          AND g.status = 'active'
          AND gl.status != 'archived'
        ORDER BY c.sort_order, c.id, cl.lesson_number DESC,
                 g.sort_order, g.group_id, gl.id
        """,
        (season_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def resolve_group_lesson_ids(
    connection: sqlite3.Connection,
    *,
    season_id: int,
    public_ids: tuple[str, ...],
) -> list[int]:
    if not public_ids:
        return []
    placeholders = ",".join("?" for _ in public_ids)
    rows = connection.execute(
        f"""
        SELECT gl.id, gl.public_id
        FROM group_lessons gl
        JOIN courses course ON course.id = gl.course_id
        JOIN groups group_record
          ON group_record.course_id = gl.course_id
         AND group_record.group_id = gl.group_id
        WHERE course.season_id = ?
          AND course.status = 'active'
          AND group_record.status = 'active'
          AND gl.status != 'archived'
          AND gl.public_id IN ({placeholders})
        """,
        (season_id, *public_ids),
    ).fetchall()
    by_public_id = {str(row["public_id"]): int(row["id"]) for row in rows}
    return [by_public_id[public_id] for public_id in public_ids if public_id in by_public_id]


def insert_in_person_event(
    connection: sqlite3.Connection,
    *,
    season_id: int,
    name: str,
    starts_at: str,
    ends_at: str,
    status: str,
    actor_user_id: int,
    now: str,
) -> tuple[int, str]:
    row = connection.execute(
        """
        INSERT INTO in_person_events (
            season_id, name, starts_at, ends_at, status,
            created_by_user_id, updated_by_user_id, created_at, updated_at, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1) RETURNING id, public_id
        """,
        (
            season_id,
            name,
            starts_at,
            ends_at,
            status,
            actor_user_id,
            actor_user_id,
            now,
            now,
        ),
    ).fetchone()
    return int(row["id"]), str(row["public_id"])


def update_in_person_event(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    expected_version: int,
    name: str,
    starts_at: str,
    ends_at: str,
    status: str,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE in_person_events
        SET name = ?, starts_at = ?, ends_at = ?, status = ?,
            updated_by_user_id = ?, updated_at = ?, version = version + 1
        WHERE id = ? AND version = ?
        """,
        (
            name,
            starts_at,
            ends_at,
            status,
            actor_user_id,
            now,
            event_id,
            expected_version,
        ),
    )
    return cursor.rowcount == 1


def replace_event_group_lessons(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    group_lesson_ids: Iterable[int],
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "DELETE FROM in_person_event_group_lessons WHERE in_person_event_id = ?",
        (event_id,),
    )
    connection.executemany(
        "INSERT INTO in_person_event_group_lessons "
        "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
        "VALUES (?, ?, ?, ?)",
        (
            (event_id, group_lesson_id, actor_user_id, now)
            for group_lesson_id in group_lesson_ids
        ),
    )


def event_has_classroom_plan(connection: sqlite3.Connection, *, event_id: int) -> bool:
    row = connection.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM classroom_layout_versions
            WHERE in_person_event_id = ?
            UNION ALL
            SELECT 1 FROM classroom_assignment_plans
            WHERE in_person_event_id = ?
        ) AS present
        """,
        (event_id, event_id),
    ).fetchone()
    return bool(row["present"])


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
    event_id: int,
    base_version_id: int | None,
    actor_user_id: int,
    now: str,
) -> tuple[int, str]:
    row = connection.execute(
        """
        INSERT INTO classroom_layout_versions (
            in_person_event_id, base_version_id, state,
            created_by_user_id, created_at, updated_at, version
        ) VALUES (?, ?, 'draft', ?, ?, ?, 1) RETURNING id, public_id
        """,
        (event_id, base_version_id, actor_user_id, now, now),
    ).fetchone()
    return int(row["id"]), str(row["public_id"])


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
    "event_has_classroom_plan",
    "find_event_layout",
    "find_latest_confirmed_layout_for_group",
    "get_in_person_event",
    "get_layout_version",
    "get_layout_version_by_public_id",
    "insert_in_person_event",
    "insert_layout_version",
    "list_group_lesson_candidates",
    "list_in_person_events",
    "list_event_group_lessons",
    "list_layout_rooms",
    "replace_layout_rooms",
    "replace_event_group_lessons",
    "resolve_group_lesson_ids",
    "resolve_layout_room_input",
    "supersede_confirmed_layout",
    "touch_layout_version",
    "update_in_person_event",
]
