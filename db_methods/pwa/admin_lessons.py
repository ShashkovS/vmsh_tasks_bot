"""Focused SQLite writes for creating Staff group lessons."""

from __future__ import annotations

import sqlite3


def find_course_group(
    connection: sqlite3.Connection, *, course_public_id: str, group_public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT course.id AS course_id, course.public_id AS course_public_id, "
        "group_record.group_id, group_record.public_id AS group_public_id "
        "FROM courses AS course JOIN groups AS group_record "
        "ON group_record.course_id = course.id "
        "WHERE course.public_id = ? AND group_record.public_id = ? "
        "AND course.status <> 'archived' AND group_record.status <> 'archived'",
        (course_public_id, group_public_id),
    ).fetchone()
    return None if row is None else dict(row)


def find_course_lesson(
    connection: sqlite3.Connection, *, course_id: int, lesson_number: int
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, title FROM course_lessons "
        "WHERE course_id = ? AND lesson_number = ?",
        (course_id, lesson_number),
    ).fetchone()
    return None if row is None else dict(row)


def insert_course_lesson(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    course_id: int,
    lesson_number: int,
    title: str | None,
    actor_user_id: int,
    now: str,
) -> int:
    row = connection.execute(
        "INSERT INTO course_lessons "
        "(public_id, course_id, lesson_number, title, created_by_user_id, "
        "updated_by_user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "RETURNING id",
        (public_id, course_id, lesson_number, title, actor_user_id, actor_user_id, now, now),
    ).fetchone()
    return int(row["id"])


def insert_group_lesson_with_window(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
    lesson_window_public_id: str,
    course_lesson_id: int,
    course_id: int,
    group_id: str,
    cycle_anchor_date: str,
    business_timezone: str,
    opens_at: str | None,
    submission_closes_at: str,
    hint_scheduled_at: str | None,
    solution_scheduled_at: str | None,
    actor_user_id: int,
    now: str,
) -> None:
    row = connection.execute(
        "INSERT INTO group_lessons "
        "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
        "business_timezone, status, created_by_user_id, updated_by_user_id, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?) "
        "RETURNING id",
        (
            group_lesson_public_id,
            course_lesson_id,
            course_id,
            group_id,
            cycle_anchor_date,
            business_timezone,
            actor_user_id,
            actor_user_id,
            now,
            now,
        ),
    ).fetchone()
    connection.execute(
        "INSERT INTO lesson_windows "
        "(public_id, group_lesson_id, opens_at, submission_closes_at, "
        "hint_scheduled_at, solution_scheduled_at, timezone, source, "
        "created_by_user_id, updated_by_user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'native', ?, ?, ?, ?)",
        (
            lesson_window_public_id,
            int(row["id"]),
            opens_at,
            submission_closes_at,
            hint_scheduled_at,
            solution_scheduled_at,
            business_timezone,
            actor_user_id,
            actor_user_id,
            now,
            now,
        ),
    )


__all__ = [
    "find_course_group",
    "find_course_lesson",
    "insert_course_lesson",
    "insert_group_lesson_with_window",
]
