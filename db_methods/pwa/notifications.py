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
