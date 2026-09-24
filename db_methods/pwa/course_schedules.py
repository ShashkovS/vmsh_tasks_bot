"""Direct SQLite reads for course and group schedule administration."""

from __future__ import annotations

import sqlite3


def list_course_schedule_rules(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT id, public_id, schedule_field, rule_version, day_offset, "
        "local_time, timezone, state, version FROM course_schedule_rules "
        "WHERE course_id = ? AND state IN ('active', 'draft') "
        "ORDER BY schedule_field, CASE state WHEN 'active' THEN 0 ELSE 1 END",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_group_schedule_overrides(
    connection: sqlite3.Connection, *, course_id: int, group_id: str
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT id, public_id, schedule_field, override_version, mode, "
        "day_offset, local_time, timezone, based_on_schedule_rule_id, state, version "
        "FROM group_schedule_overrides WHERE course_id = ? AND group_id = ? "
        "AND state IN ('active', 'draft') "
        "ORDER BY schedule_field, CASE state WHEN 'active' THEN 0 ELSE 1 END",
        (course_id, group_id),
    ).fetchall()
    return [dict(row) for row in rows]


def find_course_schedule_rule(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, course_id, schedule_field, rule_version, day_offset, "
        "local_time, timezone, state, version FROM course_schedule_rules "
        "WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def find_group_schedule_override(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, course_id, group_id, schedule_field, override_version, "
        "mode, day_offset, local_time, timezone, based_on_schedule_rule_id, state, "
        "version FROM group_schedule_overrides WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


__all__ = [
    "find_course_schedule_rule",
    "find_group_schedule_override",
    "list_course_schedule_rules",
    "list_group_schedule_overrides",
]
