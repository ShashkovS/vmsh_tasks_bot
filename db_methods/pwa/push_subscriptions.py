"""Direct SQLite operations for Web Push subscriptions."""

from __future__ import annotations

import sqlite3


def save_subscription(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    session_id: int,
    endpoint: str,
    p256dh: str,
    auth_secret: str,
    expiration_time: int | None,
    user_agent: str | None,
    now: str,
) -> str:
    row = connection.execute(
        "INSERT INTO push_subscriptions "
        "(account_id, session_id, endpoint, p256dh, auth_secret, "
        "expiration_time, user_agent, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(endpoint) DO UPDATE SET "
        "account_id = excluded.account_id, session_id = excluded.session_id, "
        "p256dh = excluded.p256dh, auth_secret = excluded.auth_secret, "
        "expiration_time = excluded.expiration_time, "
        "user_agent = excluded.user_agent, updated_at = excluded.updated_at "
        "RETURNING public_id",
        (
            account_id,
            session_id,
            endpoint,
            p256dh,
            auth_secret,
            expiration_time,
            user_agent,
            now,
            now,
        ),
    ).fetchone()
    return str(row["public_id"])


def delete_subscription(
    connection: sqlite3.Connection, *, account_id: int, endpoint: str
) -> bool:
    cursor = connection.execute(
        "DELETE FROM push_subscriptions WHERE account_id = ? AND endpoint = ?",
        (account_id, endpoint),
    )
    return cursor.rowcount == 1


def list_active_subscriptions(
    connection: sqlite3.Connection, *, account_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT public_id, endpoint, p256dh, auth_secret, expiration_time "
        "FROM push_subscriptions WHERE account_id = ? ORDER BY id",
        (account_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_subscription_by_id(
    connection: sqlite3.Connection, *, subscription_id: int
) -> None:
    connection.execute(
        "DELETE FROM push_subscriptions WHERE id = ?", (subscription_id,)
    )


__all__ = [
    "delete_subscription",
    "delete_subscription_by_id",
    "list_active_subscriptions",
    "save_subscription",
]
