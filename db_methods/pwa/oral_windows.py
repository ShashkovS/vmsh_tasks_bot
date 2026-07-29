"""Direct SQLite operations for configured oral-admission windows."""

from __future__ import annotations

import sqlite3


def group_lesson_scope(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT lesson.id AS group_lesson_id, lesson.public_id, "
        "course.public_id AS course_public_id, "
        "group_record.public_id AS group_public_id "
        "FROM group_lessons AS lesson "
        "JOIN courses AS course ON course.id = lesson.course_id "
        "JOIN groups AS group_record "
        "ON group_record.course_id = lesson.course_id "
        "AND group_record.group_id = lesson.group_id "
        "WHERE lesson.public_id = ? LIMIT 1",
        (group_lesson_public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_windows(
    connection: sqlite3.Connection,
    *,
    group_lesson_id: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT public_id, sequence_number, opens_at, closes_at, join_label, "
        "join_url, join_code, status, created_at, updated_at, version "
        "FROM oral_windows WHERE group_lesson_id = ? "
        "ORDER BY opens_at, sequence_number, id",
        (group_lesson_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_window(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    group_lesson_id: int,
    sequence_number: int,
    opens_at: str,
    closes_at: str,
    join_label: str,
    join_url: str,
    join_code: str | None,
    status: str,
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO oral_windows "
        "(public_id, group_lesson_id, sequence_number, opens_at, closes_at, "
        "join_label, join_url, join_code, status, created_by_user_id, "
        "updated_by_user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            public_id,
            group_lesson_id,
            sequence_number,
            opens_at,
            closes_at,
            join_label,
            join_url,
            join_code,
            status,
            actor_user_id,
            actor_user_id,
            now,
            now,
        ),
    )


def window_by_public_id(
    connection: sqlite3.Connection,
    *,
    public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT window.*, course.public_id AS course_public_id, "
        "group_record.public_id AS group_public_id, "
        "lesson.public_id AS group_lesson_public_id "
        "FROM oral_windows AS window "
        "JOIN group_lessons AS lesson ON lesson.id = window.group_lesson_id "
        "JOIN courses AS course ON course.id = lesson.course_id "
        "JOIN groups AS group_record ON group_record.course_id = lesson.course_id "
        "AND group_record.group_id = lesson.group_id "
        "WHERE window.public_id = ? LIMIT 1",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def update_window_row(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    sequence_number: int,
    opens_at: str,
    closes_at: str,
    join_label: str,
    join_url: str,
    join_code: str | None,
    status: str,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE oral_windows SET sequence_number = ?, opens_at = ?, closes_at = ?, "
        "join_label = ?, join_url = ?, join_code = ?, status = ?, "
        "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
        "WHERE public_id = ? AND version = ?",
        (
            sequence_number,
            opens_at,
            closes_at,
            join_label,
            join_url,
            join_code,
            status,
            actor_user_id,
            now,
            public_id,
            expected_version,
        ),
    )
    return cursor.rowcount == 1


def student_group_lesson_scope(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
    group_lesson_public_id: str,
    at: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT lesson.id AS group_lesson_id, lesson.public_id, "
        "course.public_id AS course_public_id, "
        "group_record.public_id AS group_public_id "
        "FROM auth_accounts AS account "
        "JOIN course_enrollments AS enrollment "
        "ON enrollment.student_user_id = account.linked_user_id "
        "JOIN courses AS course ON course.id = enrollment.course_id "
        "JOIN group_lessons AS lesson ON lesson.course_id = course.id "
        "JOIN groups AS group_record ON group_record.course_id = course.id "
        "AND group_record.group_id = lesson.group_id "
        "WHERE account.id = ? AND account.audience = 'student' "
        "AND account.status = 'active' AND enrollment.status = 'active' "
        "AND enrollment.attendance_mode = 'online' "
        "AND course.public_id = ? AND lesson.public_id = ? "
        "AND (lesson.group_id = enrollment.active_group_id OR EXISTS ("
        "SELECT 1 FROM course_group_access AS access "
        "WHERE access.enrollment_id = enrollment.id "
        "AND access.course_id = enrollment.course_id "
        "AND access.group_id = lesson.group_id AND access.valid_from <= ? "
        "AND (access.valid_to IS NULL OR access.valid_to > ?))) LIMIT 1",
        (account_id, course_public_id, group_lesson_public_id, at, at),
    ).fetchone()
    return None if row is None else dict(row)


def student_join_window(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
    group_lesson_public_id: str,
    window_public_id: str,
    at: str,
) -> dict[str, object] | None:
    scope = student_group_lesson_scope(
        connection,
        account_id=account_id,
        course_public_id=course_public_id,
        group_lesson_public_id=group_lesson_public_id,
        at=at,
    )
    if scope is None:
        return None
    row = connection.execute(
        "SELECT public_id, sequence_number, opens_at, closes_at, join_label, "
        "join_url, join_code, status, version FROM oral_windows "
        "WHERE group_lesson_id = ? AND public_id = ? LIMIT 1",
        (scope["group_lesson_id"], window_public_id),
    ).fetchone()
    return None if row is None else dict(row)


__all__ = [
    "group_lesson_scope",
    "insert_window",
    "list_windows",
    "student_group_lesson_scope",
    "student_join_window",
    "update_window_row",
    "window_by_public_id",
]
