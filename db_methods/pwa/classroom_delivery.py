"""SQLite operations for explicit classroom-assignment announcements."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def find_confirmed_plan(
    connection: sqlite3.Connection, plan_public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT plan.id, plan.public_id, plan.version, plan.state, "
        "plan.in_person_event_id, event.public_id AS event_public_id, "
        "event.name AS event_name "
        "FROM classroom_assignment_plans plan "
        "JOIN in_person_events event ON event.id = plan.in_person_event_id "
        "WHERE plan.public_id = ?",
        (plan_public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_recipients(
    connection: sqlite3.Connection, plan_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT assignment.course_enrollment_id,
               enrollment.student_user_id,
               assignment.group_lesson_id, assignment.group_id,
               assignment.classroom_id, assignment.status,
               enrollment.public_id AS enrollment_public_id,
               enrollment.attendance_mode, enrollment.status AS enrollment_status,
               enrollment.active_group_id,
               student.public_id AS student_public_id,
               student.surname, student.name, student.chat_id AS telegram_chat_id,
               account.id AS student_account_id,
               event.public_id AS event_public_id, event.name AS event_name,
               course.public_id AS course_public_id, course.name AS course_name,
               groups.public_id AS group_public_id,
               groups.public_name AS group_name,
               lesson.public_id AS group_lesson_public_id,
               room.public_id AS classroom_public_id,
               room.name AS classroom_name, room.status AS classroom_status
        FROM classroom_assignments assignment
        JOIN classroom_assignment_plans plan ON plan.id = assignment.plan_id
        JOIN in_person_events event ON event.id = plan.in_person_event_id
        JOIN course_enrollments enrollment
          ON enrollment.id = assignment.course_enrollment_id
        JOIN users student ON student.id = enrollment.student_user_id
        JOIN group_lessons lesson ON lesson.id = assignment.group_lesson_id
        JOIN courses course ON course.id = lesson.course_id
        JOIN groups ON groups.group_id = assignment.group_id
                   AND groups.course_id = lesson.course_id
        LEFT JOIN classrooms room ON room.id = assignment.classroom_id
        LEFT JOIN auth_accounts account
          ON account.audience = 'student'
         AND account.linked_user_id = enrollment.student_user_id
         AND account.status = 'active'
        WHERE assignment.plan_id = ?
        ORDER BY student.surname, student.name, enrollment.id
        """,
        (plan_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_previous_recipient_rooms(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT recipient.course_enrollment_id, recipient.classroom_id, "
        "batch.id AS batch_id "
        "FROM classroom_assignment_delivery_recipients recipient "
        "JOIN classroom_assignment_delivery_batches batch "
        "ON batch.id = recipient.batch_id "
        "JOIN classroom_assignment_plans plan "
        "ON plan.id = batch.assignment_plan_id "
        "WHERE plan.in_person_event_id = ? "
        "ORDER BY batch.id DESC, recipient.course_enrollment_id",
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def find_batch_by_idempotency_key(
    connection: sqlite3.Connection, *, actor_user_id: int, idempotency_key: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM classroom_assignment_delivery_batches "
        "WHERE requested_by_user_id = ? AND idempotency_key = ?",
        (actor_user_id, idempotency_key),
    ).fetchone()
    return None if row is None else dict(row)


def insert_batch(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    plan_id: int,
    plan_version: int,
    actor_user_id: int,
    pwa_selected: bool,
    telegram_selected: bool,
    snapshot_hash: str,
    recipient_count: int,
    changed_count: int,
    state: str,
    idempotency_key: str,
    now: str,
) -> int:
    cursor = connection.execute(
        "INSERT INTO classroom_assignment_delivery_batches "
        "(public_id, assignment_plan_id, assignment_plan_version, "
        "requested_by_user_id, pwa_selected, telegram_selected, "
        "recipient_snapshot_hash, recipient_count, changed_since_previous_count, "
        "state, idempotency_key, created_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            public_id,
            plan_id,
            plan_version,
            actor_user_id,
            int(pwa_selected),
            int(telegram_selected),
            snapshot_hash,
            recipient_count,
            changed_count,
            state,
            idempotency_key,
            now,
            now if state == "completed" else None,
        ),
    )
    return int(cursor.lastrowid)


def insert_recipients(
    connection: sqlite3.Connection,
    rows: Iterable[tuple[object, ...]],
) -> None:
    connection.executemany(
        "INSERT INTO classroom_assignment_delivery_recipients "
        "(batch_id, student_user_id, course_enrollment_id, group_lesson_id, "
        "classroom_id, student_public_id, student_display_name, event_public_id, "
        "event_name, course_public_id, course_name, group_public_id, group_name, "
        "classroom_public_id, classroom_name, student_account_id, telegram_chat_id, "
        "pwa_state, pwa_error_code, pwa_sent_at, telegram_state, "
        "telegram_error_code, telegram_sent_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?)",
        rows,
    )


def find_batch(
    connection: sqlite3.Connection, batch_public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT batch.*, plan.public_id AS plan_public_id "
        "FROM classroom_assignment_delivery_batches batch "
        "JOIN classroom_assignment_plans plan ON plan.id = batch.assignment_plan_id "
        "WHERE batch.public_id = ?",
        (batch_public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def find_latest_batch_for_event(
    connection: sqlite3.Connection, plan_public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT batch.*, sent_plan.public_id AS plan_public_id "
        "FROM classroom_assignment_plans current_plan "
        "JOIN classroom_assignment_plans sent_plan "
        "ON sent_plan.in_person_event_id = current_plan.in_person_event_id "
        "JOIN classroom_assignment_delivery_batches batch "
        "ON batch.assignment_plan_id = sent_plan.id "
        "WHERE current_plan.public_id = ? ORDER BY batch.id DESC LIMIT 1",
        (plan_public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_batch_recipients(
    connection: sqlite3.Connection, batch_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT student_public_id, student_display_name, event_public_id, event_name, "
        "course_public_id, course_name, group_public_id, group_name, "
        "classroom_public_id, classroom_name, pwa_state, pwa_error_code, "
        "pwa_sent_at, telegram_state, telegram_error_code, telegram_sent_at "
        "FROM classroom_assignment_delivery_recipients WHERE batch_id = ? "
        "ORDER BY student_display_name, course_name, student_public_id",
        (batch_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def claim_next_telegram_recipient(
    connection: sqlite3.Connection, batch_public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT recipient.batch_id, recipient.course_enrollment_id, "
        "recipient.telegram_chat_id, recipient.student_display_name, "
        "recipient.event_name, recipient.course_name, recipient.group_name, "
        "recipient.classroom_name "
        "FROM classroom_assignment_delivery_recipients recipient "
        "JOIN classroom_assignment_delivery_batches batch "
        "ON batch.id = recipient.batch_id "
        "WHERE batch.public_id = ? AND recipient.telegram_state = 'queued' "
        "AND recipient.telegram_error_code IS NULL "
        "ORDER BY recipient.student_display_name, recipient.course_enrollment_id "
        "LIMIT 1",
        (batch_public_id,),
    ).fetchone()
    if row is None:
        return None
    claimed = connection.execute(
        "UPDATE classroom_assignment_delivery_recipients "
        "SET telegram_error_code = 'processing' "
        "WHERE batch_id = ? AND course_enrollment_id = ? "
        "AND telegram_state = 'queued' AND telegram_error_code IS NULL",
        (row["batch_id"], row["course_enrollment_id"]),
    ).rowcount
    return dict(row) if claimed == 1 else None


def finish_telegram_recipient(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    course_enrollment_id: int,
    state: str,
    error_code: str | None,
    sent_at: str | None,
) -> bool:
    changed = connection.execute(
        "UPDATE classroom_assignment_delivery_recipients "
        "SET telegram_state = ?, telegram_error_code = ?, telegram_sent_at = ? "
        "WHERE batch_id = ? AND course_enrollment_id = ? "
        "AND telegram_error_code = 'processing'",
        (state, error_code, sent_at, batch_id, course_enrollment_id),
    ).rowcount
    return changed == 1


def finish_telegram_batch(
    connection: sqlite3.Connection, batch_public_id: str, now: str
) -> None:
    states = connection.execute(
        "SELECT recipient.telegram_state, recipient.pwa_state "
        "FROM classroom_assignment_delivery_recipients recipient "
        "JOIN classroom_assignment_delivery_batches batch "
        "ON batch.id = recipient.batch_id WHERE batch.public_id = ?",
        (batch_public_id,),
    ).fetchall()
    if any(row["telegram_state"] == "queued" for row in states):
        state = "queued"
        completed_at = None
    elif any(
        row["telegram_state"] == "failed" or row["pwa_state"] == "failed"
        for row in states
    ):
        state = "completed_with_errors"
        completed_at = now
    else:
        state = "completed"
        completed_at = now
    connection.execute(
        "UPDATE classroom_assignment_delivery_batches "
        "SET state = ?, completed_at = ?, version = version + 1 "
        "WHERE public_id = ?",
        (state, completed_at, batch_public_id),
    )


def find_retry_by_idempotency_key(
    connection: sqlite3.Connection, *, actor_user_id: int, idempotency_key: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT retry.*, batch.public_id AS batch_public_id "
        "FROM classroom_assignment_delivery_retries retry "
        "JOIN classroom_assignment_delivery_batches batch ON batch.id = retry.batch_id "
        "WHERE retry.requested_by_user_id = ? AND retry.idempotency_key = ?",
        (actor_user_id, idempotency_key),
    ).fetchone()
    return None if row is None else dict(row)


def queue_failed_telegram_recipients(
    connection: sqlite3.Connection, batch_id: int
) -> int:
    return connection.execute(
        "UPDATE classroom_assignment_delivery_recipients "
        "SET telegram_state = 'queued', telegram_error_code = NULL, "
        "telegram_sent_at = NULL WHERE batch_id = ? AND telegram_state = 'failed'",
        (batch_id,),
    ).rowcount


def insert_delivery_retry(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    actor_user_id: int,
    idempotency_key: str,
    expected_batch_version: int,
    recipient_count: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO classroom_assignment_delivery_retries "
        "(batch_id, requested_by_user_id, idempotency_key, "
        "expected_batch_version, recipient_count, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            batch_id,
            actor_user_id,
            idempotency_key,
            expected_batch_version,
            recipient_count,
            now,
        ),
    )


def reopen_delivery_batch(connection: sqlite3.Connection, batch_id: int) -> None:
    connection.execute(
        "UPDATE classroom_assignment_delivery_batches "
        "SET state = 'queued', completed_at = NULL, version = version + 1 "
        "WHERE id = ?",
        (batch_id,),
    )


__all__ = [
    "claim_next_telegram_recipient",
    "find_batch",
    "find_batch_by_idempotency_key",
    "find_confirmed_plan",
    "find_latest_batch_for_event",
    "find_retry_by_idempotency_key",
    "finish_telegram_batch",
    "finish_telegram_recipient",
    "insert_batch",
    "insert_recipients",
    "insert_delivery_retry",
    "list_batch_recipients",
    "list_previous_recipient_rooms",
    "list_recipients",
    "queue_failed_telegram_recipients",
    "reopen_delivery_batch",
]
