"""SQLite reads and writes for classroom student-assignment plans."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def find_plan(
    connection: sqlite3.Connection, event_id: int, states: tuple[str, ...]
) -> dict[str, object] | None:
    placeholders = ", ".join("?" for _state in states)
    row = connection.execute(
        "SELECT id, public_id, in_person_event_id, layout_version_id, base_plan_id, "
        "state, stale_reason, created_at, updated_at, confirmed_at, version "
        f"FROM classroom_assignment_plans WHERE in_person_event_id = ? "
        f"AND state IN ({placeholders}) ORDER BY id DESC LIMIT 1",
        (event_id, *states),
    ).fetchone()
    return None if row is None else dict(row)


def find_plan_by_public_id(
    connection: sqlite3.Connection, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, in_person_event_id, layout_version_id, base_plan_id, "
        "state, stale_reason, created_at, updated_at, confirmed_at, version "
        "FROM classroom_assignment_plans WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_eligible_students(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT enrollment.id AS enrollment_id,
               enrollment.public_id AS enrollment_public_id,
               enrollment.student_user_id, enrollment.course_id,
               enrollment.active_group_id AS group_id,
               lesson.id AS group_lesson_id,
               lesson.public_id AS group_lesson_public_id,
               user.public_id AS student_public_id,
               user.surname, user.name, user.grade, user.birthday,
               strength.simple_prob, strength.compl_prob
        FROM in_person_event_group_lessons event_lesson
        JOIN group_lessons lesson ON lesson.id = event_lesson.group_lesson_id
        JOIN course_enrollments enrollment
          ON enrollment.course_id = lesson.course_id
         AND enrollment.active_group_id = lesson.group_id
        JOIN users user ON user.id = enrollment.student_user_id
        LEFT JOIN student_strength strength
          ON strength.student_id = enrollment.student_user_id
        WHERE event_lesson.in_person_event_id = ?
          AND enrollment.status = 'active'
          AND enrollment.attendance_mode = 'in_person'
        ORDER BY user.surname, user.name, enrollment.id
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def find_previous_classroom(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    group_id: str,
    before_starts_at: str,
) -> int | None:
    row = connection.execute(
        """
        SELECT assignment.classroom_id
        FROM classroom_assignments assignment
        JOIN classroom_assignment_plans plan ON plan.id = assignment.plan_id
        JOIN in_person_events event ON event.id = plan.in_person_event_id
        WHERE assignment.course_enrollment_id = ?
          AND assignment.group_id = ?
          AND assignment.status = 'assigned'
          AND plan.state = 'confirmed'
          AND event.starts_at < ?
        ORDER BY event.starts_at DESC, plan.confirmed_at DESC, plan.id DESC
        LIMIT 1
        """,
        (enrollment_id, group_id, before_starts_at),
    ).fetchone()
    return None if row is None else int(row["classroom_id"])


def insert_plan(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    event_id: int,
    layout_id: int,
    base_plan_id: int | None,
    actor_user_id: int,
    now: str,
) -> int:
    cursor = connection.execute(
        "INSERT INTO classroom_assignment_plans "
        "(public_id, in_person_event_id, layout_version_id, base_plan_id, state, "
        "created_by_user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'draft', ?, ?, ?)",
        (public_id, event_id, layout_id, base_plan_id, actor_user_id, now, now),
    )
    return int(cursor.lastrowid)


def replace_assignments(
    connection: sqlite3.Connection,
    *,
    plan_id: int,
    rows: Iterable[tuple[int, int, str, int | None, str, str]],
    now: str,
) -> None:
    connection.execute(
        "DELETE FROM classroom_assignments WHERE plan_id = ?", (plan_id,)
    )
    connection.executemany(
        "INSERT INTO classroom_assignments "
        "(plan_id, course_enrollment_id, group_lesson_id, group_id, classroom_id, "
        "status, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                plan_id,
                enrollment_id,
                group_lesson_id,
                group_id,
                room_id,
                status,
                source,
                now,
                now,
            )
            for enrollment_id, group_lesson_id, group_id, room_id, status, source in rows
        ),
    )


def list_plan_assignments(
    connection: sqlite3.Connection, plan_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT assignment.course_enrollment_id, assignment.group_lesson_id,
               assignment.group_id, assignment.classroom_id,
               assignment.status, assignment.source,
               enrollment.public_id AS enrollment_public_id,
               enrollment.student_user_id, user.public_id AS student_public_id,
               user.surname, user.name, user.grade, user.birthday,
               strength.simple_prob, strength.compl_prob,
               lesson.public_id AS group_lesson_public_id,
               room.public_id AS classroom_public_id,
               room.name AS classroom_name
        FROM classroom_assignments assignment
        JOIN course_enrollments enrollment
          ON enrollment.id = assignment.course_enrollment_id
        JOIN users user ON user.id = enrollment.student_user_id
        JOIN group_lessons lesson ON lesson.id = assignment.group_lesson_id
        LEFT JOIN classrooms room ON room.id = assignment.classroom_id
        LEFT JOIN student_strength strength ON strength.student_id = user.id
        WHERE assignment.plan_id = ?
        ORDER BY user.surname, user.name, enrollment.id
        """,
        (plan_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def touch_plan(
    connection: sqlite3.Connection,
    *,
    plan_id: int,
    expected_version: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE classroom_assignment_plans "
        "SET state = 'draft', stale_reason = NULL, updated_at = ?, version = version + 1 "
        "WHERE id = ? AND state IN ('draft', 'stale') AND version = ?",
        (now, plan_id, expected_version),
    )
    return cursor.rowcount == 1


def supersede_confirmed_plan(
    connection: sqlite3.Connection, *, event_id: int, now: str
) -> None:
    connection.execute(
        "UPDATE classroom_assignment_plans "
        "SET state = 'superseded', superseded_at = ?, updated_at = ? "
        "WHERE in_person_event_id = ? AND state = 'confirmed'",
        (now, now, event_id),
    )


def confirm_plan(
    connection: sqlite3.Connection,
    *,
    plan_id: int,
    expected_version: int,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE classroom_assignment_plans "
        "SET state = 'confirmed', confirmed_by_user_id = ?, confirmed_at = ?, "
        "updated_at = ?, version = version + 1 "
        "WHERE id = ? AND state = 'draft' AND version = ?",
        (actor_user_id, now, now, plan_id, expected_version),
    )
    return cursor.rowcount == 1


__all__ = [
    "confirm_plan",
    "find_plan",
    "find_plan_by_public_id",
    "find_previous_classroom",
    "insert_plan",
    "list_eligible_students",
    "list_plan_assignments",
    "replace_assignments",
    "supersede_confirmed_plan",
    "touch_plan",
]
