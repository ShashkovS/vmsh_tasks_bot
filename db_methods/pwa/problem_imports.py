"""Small SQLite reads used by the problem workbook dry-run."""

from __future__ import annotations

import sqlite3


def find_course(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, code, name, status FROM courses WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_course_groups(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT group_id, public_id, short_code, public_name, status "
        "FROM groups WHERE course_id = ? ORDER BY sort_order, group_id",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_course_problems(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT problem.* FROM problems AS problem "
        "JOIN groups AS group_record ON group_record.group_id = problem.group_id "
        "WHERE group_record.course_id = ?",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = ["find_course", "list_course_groups", "list_course_problems"]
