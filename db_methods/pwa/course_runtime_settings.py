"""Focused SQLite reads/writes for course runtime settings."""

from __future__ import annotations

import sqlite3


def find_course_runtime_settings(
    connection: sqlite3.Connection, *, course_id: int
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT schema_version, values_json, updated_by_user_id, updated_at, version "
        "FROM course_runtime_settings WHERE course_id = ?",
        (course_id,),
    ).fetchone()
    return None if row is None else dict(row)


def insert_course_runtime_settings(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    values_json: str,
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_runtime_settings "
        "(course_id, schema_version, values_json, updated_by_user_id, updated_at) "
        "VALUES (?, 1, ?, ?, ?)",
        (course_id, values_json, actor_user_id, now),
    )


def update_course_runtime_settings(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    expected_version: int,
    values_json: str,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE course_runtime_settings SET values_json = ?, "
        "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
        "WHERE course_id = ? AND version = ?",
        (values_json, actor_user_id, now, course_id, expected_version),
    )
    return cursor.rowcount == 1


__all__ = [
    "find_course_runtime_settings",
    "insert_course_runtime_settings",
    "update_course_runtime_settings",
]
