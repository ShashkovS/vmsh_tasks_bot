"""Direct SQLite writes for Family-owned course enrollment changes."""

from __future__ import annotations

import sqlite3


def update_enrollment(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    expected_version: int,
    active_group_id: str,
    attendance_mode: str,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE course_enrollments SET active_group_id = ?, attendance_mode = ?, "
        "updated_at = ?, version = version + 1 "
        "WHERE id = ? AND version = ? AND status = 'active'",
        (active_group_id, attendance_mode, now, enrollment_id, expected_version),
    )
    return cursor.rowcount == 1


def insert_group_change_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    enrollment_id: int,
    course_id: int,
    previous_value: str,
    new_value: str,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_enrollment_events "
        "(public_id, enrollment_id, course_id, event_type, "
        "previous_group_id, new_group_id, "
        "source, request_id, occurred_at, created_at) "
        "VALUES (?, ?, ?, 'active_group_changed', ?, ?, 'pwa', ?, ?, ?)",
        (
            public_id,
            enrollment_id,
            course_id,
            previous_value,
            new_value,
            request_id,
            now,
            now,
        ),
    )


def insert_mode_change_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    enrollment_id: int,
    course_id: int,
    previous_value: str,
    new_value: str,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_enrollment_events "
        "(public_id, enrollment_id, course_id, event_type, "
        "previous_attendance_mode, new_attendance_mode, "
        "source, request_id, occurred_at, created_at) "
        "VALUES (?, ?, ?, 'attendance_mode_changed', ?, ?, 'pwa', ?, ?, ?)",
        (
            public_id,
            enrollment_id,
            course_id,
            previous_value,
            new_value,
            request_id,
            now,
            now,
        ),
    )


def mark_working_classroom_plans_stale(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    now: str,
) -> None:
    connection.execute(
        """
        UPDATE classroom_assignment_plans
        SET state = 'stale', stale_reason = 'enrollment_changed',
            updated_at = ?, version = version + 1
        WHERE state IN ('draft', 'stale')
          AND EXISTS (
              SELECT 1
              FROM in_person_event_group_lessons AS event_lesson
              JOIN group_lessons AS lesson ON lesson.id = event_lesson.group_lesson_id
              JOIN in_person_events AS event
                ON event.id = event_lesson.in_person_event_id
              WHERE event.id = classroom_assignment_plans.in_person_event_id
                AND lesson.course_id = ?
                AND event.status = 'scheduled'
          )
        """,
        (now, course_id),
    )


def sync_legacy_single_course_user(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    active_group_id: str,
    attendance_mode: str,
    group_changed: bool,
    mode_changed: bool,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE users SET group_id = ?, online = ? WHERE id = ? "
        "AND (SELECT count(*) FROM course_enrollments "
        "WHERE student_user_id = ? AND status = 'active') = 1",
        (
            active_group_id,
            1 if attendance_mode == "online" else 2,
            student_user_id,
            student_user_id,
        ),
    )
    if cursor.rowcount != 1:
        return False
    if group_changed:
        connection.execute(
            "INSERT INTO user_changes_log (ts, user_id, change_type, new_value) "
            "VALUES (?, ?, 'G', ?)",
            (now, student_user_id, active_group_id),
        )
    if mode_changed:
        connection.execute(
            "INSERT INTO user_changes_log (ts, user_id, change_type, new_value) "
            "VALUES (?, ?, 'O', ?)",
            (now, student_user_id, "1" if attendance_mode == "online" else "2"),
        )
    return True


__all__ = [
    "insert_group_change_event",
    "insert_mode_change_event",
    "mark_working_classroom_plans_stale",
    "sync_legacy_single_course_user",
    "update_enrollment",
]
