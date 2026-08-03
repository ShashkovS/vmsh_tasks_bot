"""Focused SQLite reads for the explicit Family lesson digest."""

from __future__ import annotations

import sqlite3


def find_group_lesson(
    connection: sqlite3.Connection,
    *,
    public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT group_lesson.id, group_lesson.public_id, group_lesson.status, "
        "course.id AS course_id, course.public_id AS course_public_id, "
        "course.name AS course_name, group_record.group_id, "
        "group_record.public_id AS group_public_id, "
        "group_record.public_name AS group_name, course_lesson.lesson_number "
        "FROM group_lessons AS group_lesson "
        "JOIN course_lessons AS course_lesson "
        "ON course_lesson.id = group_lesson.course_lesson_id "
        "JOIN courses AS course ON course.id = group_lesson.course_id "
        "JOIN groups AS group_record "
        "ON group_record.course_id = group_lesson.course_id "
        "AND group_record.group_id = group_lesson.group_id "
        "WHERE group_lesson.public_id = ? LIMIT 1",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_group_students(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT student.id AS student_user_id, student.public_id, "
        "trim(coalesce(student.surname, '') || ' ' || "
        "coalesce(student.name, '')) AS display_name "
        "FROM course_enrollments AS enrollment "
        "JOIN users AS student ON student.id = enrollment.student_user_id "
        "WHERE enrollment.course_id = ? AND enrollment.active_group_id = ? "
        "AND enrollment.status = 'active' "
        "ORDER BY student.surname COLLATE NOCASE, student.name COLLATE NOCASE, student.id",
        (course_id, group_id),
    ).fetchall()
    return [dict(row) for row in rows]


def list_group_family_accounts(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
    dedupe_key: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT family.id AS account_id, family.public_id AS account_public_id, "
        "family.display_name, student.public_id AS student_public_id, "
        "event.occurred_at AS sent_at "
        "FROM course_enrollments AS enrollment "
        "JOIN users AS student ON student.id = enrollment.student_user_id "
        "JOIN family_student_links AS link "
        "ON link.student_user_id = student.id AND link.revoked_at IS NULL "
        "JOIN auth_accounts AS family ON family.id = link.family_account_id "
        "AND family.audience = 'family' AND family.status = 'active' "
        "LEFT JOIN notification_events AS event "
        "ON event.account_id = family.id AND event.category = 'review_completed' "
        "AND event.dedupe_key = ? "
        "WHERE enrollment.course_id = ? AND enrollment.active_group_id = ? "
        "AND enrollment.status = 'active' "
        "ORDER BY family.id, student.surname COLLATE NOCASE, "
        "student.name COLLATE NOCASE, student.id",
        (dedupe_key, course_id, group_id),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "find_group_lesson",
    "list_group_family_accounts",
    "list_group_students",
]
