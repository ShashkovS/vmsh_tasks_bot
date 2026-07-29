"""Short SQLite operations for the Phase-7 classroom catalog.

Naming rules, authorization and translated messages deliberately live outside
this module. Every mutating function expects an already-open transaction.
"""

from __future__ import annotations

import sqlite3
from typing import Literal


ClassroomStatus = Literal["active", "archived"]


class ClassroomNotFound(LookupError):
    pass


class ClassroomVersionConflict(RuntimeError):
    pass


class ClassroomNameConflict(RuntimeError):
    pass


def _record_event(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    classroom_id: int,
    action: str,
    before: dict[str, object] | None,
    after: dict[str, object],
    actor_user_id: int,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        """
        INSERT INTO classroom_events (
            public_id, classroom_id, action,
            before_name, before_normalized_name, before_status,
            after_name, after_normalized_name, after_status, version_after,
            actor_user_id, request_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_public_id,
            classroom_id,
            action,
            None if before is None else before["name"],
            None if before is None else before["normalized_name"],
            None if before is None else before["status"],
            after["name"],
            after["normalized_name"],
            after["status"],
            after["version"],
            actor_user_id,
            request_id,
            now,
        ),
    )


def list_classrooms(
    connection: sqlite3.Connection,
    *,
    status: ClassroomStatus | None,
    normalized_search: str = "",
) -> list[dict[str, object]]:
    clauses: list[str] = []
    values: list[object] = []
    if status is not None:
        clauses.append("status = ?")
        values.append(status)
    if normalized_search:
        escaped = (
            normalized_search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        clauses.append("normalized_name LIKE ? ESCAPE '\\'")
        values.append(f"%{escaped}%")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        "SELECT public_id, name, status, created_at, updated_at, version "
        f"FROM classrooms{where} ORDER BY normalized_name, id",
        values,
    ).fetchall()
    return [dict(row) for row in rows]


def get_classroom(
    connection: sqlite3.Connection, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, name, normalized_name, status, created_at, "
        "updated_at, version FROM classrooms WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def find_classroom_by_normalized_name(
    connection: sqlite3.Connection, normalized_name: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT public_id, name, status, version FROM classrooms "
        "WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    return None if row is None else dict(row)


def create_classroom(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    event_public_id: str,
    name: str,
    normalized_name: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> dict[str, object]:
    try:
        cursor = connection.execute(
            """
            INSERT INTO classrooms (
                public_id, name, normalized_name, status,
                created_by_user_id, updated_by_user_id,
                created_at, updated_at, version
            ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, 1)
            """,
            (
                public_id,
                name,
                normalized_name,
                actor_user_id,
                actor_user_id,
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError as error:
        if "classrooms.normalized_name" in str(error):
            raise ClassroomNameConflict from error
        raise
    row = get_classroom(connection, public_id)
    assert row is not None
    _record_event(
        connection,
        event_public_id=event_public_id,
        classroom_id=cursor.lastrowid,
        action="created",
        before=None,
        after=row,
        actor_user_id=actor_user_id,
        request_id=request_id,
        now=now,
    )
    row.pop("id")
    row.pop("normalized_name")
    return row


def rename_classroom(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    event_public_id: str,
    name: str,
    normalized_name: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> dict[str, object]:
    before = get_classroom(connection, public_id)
    if before is None:
        raise ClassroomNotFound
    if before["version"] != expected_version:
        raise ClassroomVersionConflict
    try:
        cursor = connection.execute(
            """
            UPDATE classrooms
            SET name = ?, normalized_name = ?, updated_by_user_id = ?,
                updated_at = ?, version = version + 1
            WHERE id = ? AND version = ?
            """,
            (
                name,
                normalized_name,
                actor_user_id,
                now,
                before["id"],
                expected_version,
            ),
        )
    except sqlite3.IntegrityError as error:
        if "classrooms.normalized_name" in str(error):
            raise ClassroomNameConflict from error
        raise
    if cursor.rowcount != 1:
        raise ClassroomVersionConflict
    after = get_classroom(connection, public_id)
    assert after is not None
    _record_event(
        connection,
        event_public_id=event_public_id,
        classroom_id=int(before["id"]),
        action="renamed",
        before=before,
        after=after,
        actor_user_id=actor_user_id,
        request_id=request_id,
        now=now,
    )
    after.pop("id")
    after.pop("normalized_name")
    return after


def set_classroom_status(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    event_public_id: str,
    status: ClassroomStatus,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> dict[str, object]:
    before = get_classroom(connection, public_id)
    if before is None:
        raise ClassroomNotFound
    if before["version"] != expected_version:
        raise ClassroomVersionConflict
    cursor = connection.execute(
        """
        UPDATE classrooms
        SET status = ?, updated_by_user_id = ?, updated_at = ?, version = version + 1
        WHERE id = ? AND version = ?
        """,
        (status, actor_user_id, now, before["id"], expected_version),
    )
    if cursor.rowcount != 1:
        raise ClassroomVersionConflict
    after = get_classroom(connection, public_id)
    assert after is not None
    _record_event(
        connection,
        event_public_id=event_public_id,
        classroom_id=int(before["id"]),
        action="archived" if status == "archived" else "restored",
        before=before,
        after=after,
        actor_user_id=actor_user_id,
        request_id=request_id,
        now=now,
    )
    after.pop("id")
    after.pop("normalized_name")
    return after


__all__ = [
    "ClassroomNameConflict",
    "ClassroomNotFound",
    "ClassroomVersionConflict",
    "create_classroom",
    "find_classroom_by_normalized_name",
    "get_classroom",
    "list_classrooms",
    "rename_classroom",
    "set_classroom_status",
]
