"""Direct SQLite operations for account-scoped notifications."""

from __future__ import annotations

import sqlite3


def list_events(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    limit: int,
    unread_only: bool,
) -> list[dict[str, object]]:
    unread_clause = "AND read_at IS NULL" if unread_only else ""
    rows = connection.execute(
        f"SELECT event.public_id, event.category, event.route, event.payload_json, "
        f"event.occurred_at, event.deliver_after, event.read_at "
        f"FROM notification_events AS event "
        f"LEFT JOIN notification_preferences AS preference "
        f"ON preference.account_id = event.account_id "
        f"AND preference.category = event.category "
        f"WHERE event.account_id = ? {unread_clause} "
        f"AND coalesce(preference.in_app_enabled, "
        f"CASE WHEN event.category = 'oral_window' THEN 0 ELSE 1 END) = 1 "
        f"ORDER BY event.occurred_at DESC, event.id DESC LIMIT ?",
        (account_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def mark_event_read(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    event_public_id: str,
    session_id: int,
    read_at: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, read_at FROM notification_events "
        "WHERE account_id = ? AND public_id = ?",
        (account_id, event_public_id),
    ).fetchone()
    if row is None:
        return None
    if row["read_at"] is None:
        connection.execute(
            "UPDATE notification_events SET read_at = ?, read_by_session_id = ? "
            "WHERE id = ? AND read_at IS NULL",
            (read_at, session_id, row["id"]),
        )
        return {"public_id": row["public_id"], "read_at": read_at}
    return {"public_id": row["public_id"], "read_at": row["read_at"]}


def list_preferences(
    connection: sqlite3.Connection, account_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT category, in_app_enabled, push_enabled, sound_enabled, "
        "quiet_starts_local, quiet_ends_local, timezone, updated_at "
        "FROM notification_preferences WHERE account_id = ? ORDER BY category",
        (account_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_preference(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    category: str,
    in_app_enabled: bool,
    push_enabled: bool,
    sound_enabled: bool,
    quiet_starts_local: str,
    quiet_ends_local: str,
    timezone: str,
    updated_at: str,
) -> None:
    connection.execute(
        "INSERT INTO notification_preferences "
        "(account_id, category, in_app_enabled, push_enabled, sound_enabled, "
        "quiet_starts_local, quiet_ends_local, timezone, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(account_id, category) DO UPDATE SET "
        "in_app_enabled = excluded.in_app_enabled, "
        "push_enabled = excluded.push_enabled, "
        "sound_enabled = excluded.sound_enabled, "
        "quiet_starts_local = excluded.quiet_starts_local, "
        "quiet_ends_local = excluded.quiet_ends_local, "
        "timezone = excluded.timezone, updated_at = excluded.updated_at",
        (
            account_id,
            category,
            int(in_app_enabled),
            int(push_enabled),
            int(sound_enabled),
            quiet_starts_local,
            quiet_ends_local,
            timezone,
            updated_at,
        ),
    )


def student_notification_course(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT course.id, course.public_id, course.name "
        "FROM auth_accounts AS account "
        "JOIN course_enrollments AS enrollment "
        "ON enrollment.student_user_id = account.linked_user_id "
        "JOIN courses AS course ON course.id = enrollment.course_id "
        "WHERE account.id = ? AND account.audience = 'student' "
        "AND account.status = 'active' AND enrollment.status = 'active' "
        "AND course.public_id = ? LIMIT 1",
        (account_id, course_public_id),
    ).fetchone()
    return None if row is None else dict(row)


def list_course_preferences(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT category, push_enabled, updated_at "
        "FROM notification_course_preferences "
        "WHERE account_id = ? AND course_id = ? ORDER BY category",
        (account_id, course_id),
    ).fetchall()
    return [dict(row) for row in rows]


def save_course_preference(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_id: int,
    category: str,
    push_enabled: bool | None,
    updated_at: str,
) -> None:
    if push_enabled is None:
        connection.execute(
            "DELETE FROM notification_course_preferences "
            "WHERE account_id = ? AND course_id = ? AND category = ?",
            (account_id, course_id, category),
        )
        return
    connection.execute(
        "INSERT INTO notification_course_preferences "
        "(account_id, course_id, category, push_enabled, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(account_id, course_id, category) DO UPDATE SET "
        "push_enabled = excluded.push_enabled, updated_at = excluded.updated_at",
        (account_id, course_id, category, int(push_enabled), updated_at),
    )


def insert_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    account_id: int,
    category: str,
    dedupe_key: str,
    route: str,
    payload_json: str,
    occurred_at: str,
    deliver_after: str,
    created_at: str,
) -> bool:
    cursor = connection.execute(
        "INSERT INTO notification_events "
        "(public_id, account_id, category, dedupe_key, route, payload_json, "
        "occurred_at, deliver_after, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(account_id, category, dedupe_key) DO NOTHING",
        (
            public_id,
            account_id,
            category,
            dedupe_key,
            route,
            payload_json,
            occurred_at,
            deliver_after,
            created_at,
        ),
    )
    return cursor.rowcount == 1


def active_student_accounts(
    connection: sqlite3.Connection,
    *,
    public_ids: tuple[str, ...],
) -> list[dict[str, object]]:
    """Return active Student accounts named by the review receipt."""

    if not public_ids:
        return []
    placeholders = ", ".join("?" for _ in public_ids)
    rows = connection.execute(
        f"SELECT id, public_id FROM auth_accounts "
        f"WHERE audience = 'student' AND status = 'active' "
        f"AND public_id IN ({placeholders}) ORDER BY id",
        public_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def latest_staff_support_entry(
    connection: sqlite3.Connection,
    *,
    thread_public_id: str,
) -> dict[str, object] | None:
    """Return the newest committed teacher/admin entry in one thread."""

    row = connection.execute(
        "SELECT entry.public_id, entry.server_received_at "
        "FROM support_threads AS thread "
        "JOIN support_entries AS entry ON entry.thread_id = thread.id "
        "WHERE thread.public_id = ? "
        "AND entry.author_kind IN ('teacher', 'admin') "
        "ORDER BY entry.server_received_at DESC, entry.id DESC LIMIT 1",
        (thread_public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def pending_review_batch(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    occurred_at: str,
) -> dict[str, object] | None:
    """Find the account's still-open 30-minute review batch."""

    row = connection.execute(
        "SELECT id, payload_json FROM notification_events "
        "WHERE account_id = ? AND category = 'review_completed' "
        "AND deliver_after > ? "
        "ORDER BY deliver_after DESC, id DESC LIMIT 1",
        (account_id, occurred_at),
    ).fetchone()
    return None if row is None else dict(row)


def update_review_batch(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    payload_json: str,
    occurred_at: str,
) -> None:
    connection.execute(
        "UPDATE notification_events SET payload_json = ?, occurred_at = ?, "
        "read_at = NULL, read_by_session_id = NULL "
        "WHERE id = ?",
        (payload_json, occurred_at, event_id),
    )


def published_content_event_source(
    connection: sqlite3.Connection,
    *,
    group_lesson_id: int,
    kind: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT publication.public_id AS publication_public_id, "
        "publication.published_at, course.public_id AS course_public_id, "
        "group_record.public_id AS group_public_id, "
        "group_lesson.public_id AS group_lesson_public_id, "
        "course_lesson.lesson_number "
        "FROM lesson_publications AS publication "
        "JOIN group_lessons AS group_lesson "
        "ON group_lesson.id = publication.group_lesson_id "
        "JOIN course_lessons AS course_lesson "
        "ON course_lesson.id = group_lesson.course_lesson_id "
        "JOIN courses AS course ON course.id = group_lesson.course_id "
        "JOIN groups AS group_record "
        "ON group_record.course_id = group_lesson.course_id "
        "AND group_record.group_id = group_lesson.group_id "
        "WHERE publication.group_lesson_id = ? AND publication.kind = ? "
        "AND publication.state = 'published' LIMIT 1",
        (group_lesson_id, kind),
    ).fetchone()
    return None if row is None else dict(row)


def active_group_notification_accounts(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "WITH recipient_students AS ("
        "SELECT enrollment.student_user_id, student.public_id AS student_public_id "
        "FROM course_enrollments AS enrollment "
        "JOIN users AS student ON student.id = enrollment.student_user_id "
        "WHERE enrollment.course_id = ? AND enrollment.active_group_id = ? "
        "AND enrollment.status = 'active') "
        "SELECT account.id AS account_id, account.public_id AS account_public_id, "
        "account.audience, student.student_public_id "
        "FROM recipient_students AS student "
        "JOIN auth_accounts AS account "
        "ON account.linked_user_id = student.student_user_id "
        "AND account.audience = 'student' AND account.status = 'active' "
        "UNION ALL "
        "SELECT account.id, account.public_id, account.audience, "
        "student.student_public_id FROM recipient_students AS student "
        "JOIN family_student_links AS link "
        "ON link.student_user_id = student.student_user_id AND link.revoked_at IS NULL "
        "JOIN auth_accounts AS account ON account.id = link.family_account_id "
        "AND account.audience = 'family' AND account.status = 'active' "
        "ORDER BY account_id, student_public_id",
        (course_id, group_id),
    ).fetchall()
    return [dict(row) for row in rows]
