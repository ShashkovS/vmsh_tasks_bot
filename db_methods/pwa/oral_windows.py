"""Direct SQLite operations for configured oral-admission windows."""

from __future__ import annotations

import sqlite3


def group_lesson_scope(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT lesson.id AS group_lesson_id, lesson.public_id, lesson.course_lesson_id, "
        "lesson.group_id, course.name AS course_name, "
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
        "FROM oral_windows WHERE id IN (SELECT window_id FROM oral_window_lessons WHERE group_lesson_id = ?) "
        "ORDER BY opens_at, sequence_number, id",
        (group_lesson_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def due_notification_windows(
    connection: sqlite3.Connection,
    *,
    after: str | None,
    through: str,
) -> list[dict[str, object]]:
    """Read active windows that opened in one scheduler interval.

    The first scan also includes a window already open when the process starts.
    """

    if after is None:
        timing = "window.opens_at <= ? AND window.closes_at > ?"
        parameters = (through, through)
    else:
        timing = "window.opens_at > ? AND window.opens_at <= ? AND window.closes_at > ?"
        parameters = (after, through, through)
    rows = connection.execute(
        "SELECT window.public_id, window.opens_at, window.closes_at, "
        "lesson.public_id AS group_lesson_public_id, lesson.course_id, "
        "lesson.group_id, course.public_id AS course_public_id, "
        "group_record.public_id AS group_public_id, course_lesson.lesson_number "
        "FROM oral_windows AS window "
        "JOIN oral_window_lessons AS membership ON membership.window_id = window.id "
        "JOIN group_lessons AS lesson ON lesson.id = membership.group_lesson_id "
        "JOIN course_lessons AS course_lesson "
        "ON course_lesson.id = lesson.course_lesson_id "
        "JOIN courses AS course ON course.id = lesson.course_id "
        "JOIN groups AS group_record ON group_record.course_id = lesson.course_id "
        "AND group_record.group_id = lesson.group_id "
        f"WHERE window.status = 'active' AND {timing} "
        "ORDER BY window.opens_at, window.id",
        parameters,
    ).fetchall()
    return [dict(row) for row in rows]


def insert_window(
    connection: sqlite3.Connection,
    *,
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
) -> str:
    row = connection.execute(
        "INSERT INTO oral_windows "
        "(group_lesson_id, sequence_number, opens_at, closes_at, "
        "join_label, join_url, join_code, status, created_by_user_id, "
        "updated_by_user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING public_id",
        (
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
    ).fetchone()
    return str(row["public_id"])


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
    return (
        None if row is None else dict(row, groups=window_lessons(connection, public_id))
    )


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
        "WHERE id IN (SELECT window_id FROM oral_window_lessons WHERE group_lesson_id = ?) "
        "AND public_id = ? LIMIT 1",
        (scope["group_lesson_id"], window_public_id),
    ).fetchone()
    return None if row is None else dict(row)


def window_lessons(connection, public_id):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT lesson.public_id AS groupLessonId, groups.public_name AS groupName, lesson.group_id "
            "FROM oral_window_lessons link JOIN oral_windows window ON window.id = link.window_id "
            "JOIN group_lessons lesson ON lesson.id = link.group_lesson_id "
            "JOIN groups ON groups.course_id = lesson.course_id AND groups.group_id = lesson.group_id "
            "WHERE window.public_id = ? ORDER BY lesson.id",
            (public_id,),
        )
    ]


def planning_lessons(connection, public_id):
    return [
        dict(row)
        for row in connection.execute(
            "SELECT lesson.public_id AS groupLessonId, groups.public_name AS groupName, lesson.group_id, "
            "course_lesson.lesson_number AS lessonNumber, lesson.course_lesson_id "
            "FROM group_lessons source JOIN course_lessons source_number ON source_number.id = source.course_lesson_id "
            "JOIN course_lessons course_lesson ON course_lesson.course_id = source.course_id "
            "AND (course_lesson.id = source.course_lesson_id OR course_lesson.lesson_number = source_number.lesson_number - 1) "
            "JOIN group_lessons lesson ON lesson.course_lesson_id = course_lesson.id "
            "JOIN groups ON groups.course_id = lesson.course_id AND groups.group_id = lesson.group_id "
            "WHERE source.public_id = ? ORDER BY course_lesson.lesson_number DESC, lesson.id",
            (public_id,),
        )
    ]


def link_window(connection, public_id, lesson_ids):
    connection.executemany(
        "INSERT OR IGNORE INTO oral_window_lessons(window_id, group_lesson_id) "
        "SELECT id, ? FROM oral_windows WHERE public_id = ?",
        [(lesson, public_id) for lesson in lesson_ids],
    )


def batch_receipt(connection, actor, key):
    row = connection.execute(
        "SELECT * FROM oral_window_batches WHERE actor_user_id = ? AND request_key = ?",
        (actor, key),
    ).fetchone()
    return None if row is None else dict(row)


def save_batch_receipt(connection, actor, key, fingerprint, ids_json, now):
    connection.execute(
        "INSERT INTO oral_window_batches VALUES (?, ?, ?, ?, ?)",
        (actor, key, fingerprint, ids_json, now),
    )


__all__ = [
    "due_notification_windows",
    "group_lesson_scope",
    "insert_window",
    "list_windows",
    "student_group_lesson_scope",
    "student_join_window",
    "update_window_row",
    "window_by_public_id",
]
