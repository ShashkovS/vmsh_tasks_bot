"""Focused SQLite reads and writes for the Staff audit timeline."""

from __future__ import annotations

import sqlite3


def insert_audit_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    actor_user_id: int | None,
    actor_account_public_id: str | None,
    audience: str,
    action: str,
    object_type: str,
    object_id: str,
    request_id: str,
    before_json: str | None,
    after_json: str | None,
    occurred_at: str,
    ip_prefix: str | None = None,
) -> None:
    connection.execute(
        "INSERT INTO audit_events "
        "(public_id, actor_user_id, actor_account_id, audience, action, "
        "object_type, object_id, request_id, before_json, after_json, "
        "occurred_at, ip_prefix) VALUES (?, ?, "
        "(SELECT id FROM auth_accounts WHERE public_id = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            public_id,
            actor_user_id,
            actor_account_public_id,
            audience,
            action,
            object_type,
            object_id,
            request_id,
            before_json,
            after_json,
            occurred_at,
            ip_prefix,
        ),
    )


def find_audit_cursor(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, occurred_at FROM audit_events WHERE public_id = ?", (public_id,)
    ).fetchone()
    return None if row is None else dict(row)


def list_audit_events(
    connection: sqlite3.Connection,
    *,
    source: str,
    query: str,
    cursor: dict[str, object] | None,
    limit: int,
) -> list[dict[str, object]]:
    conditions: list[str] = []
    parameters: list[object] = []
    if source != "all":
        conditions.append("event.object_type = ?")
        parameters.append(source)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            "(event.request_id LIKE ? ESCAPE '\\' OR event.action LIKE ? ESCAPE '\\' "
            "OR event.object_id LIKE ? ESCAPE '\\')"
        )
        parameters.extend((pattern, pattern, pattern))
    if cursor is not None:
        conditions.append(
            "(event.occurred_at < ? OR (event.occurred_at = ? AND event.id < ?))"
        )
        parameters.extend((cursor["occurred_at"], cursor["occurred_at"], cursor["id"]))
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = connection.execute(
        f"""
        SELECT event.public_id,
               event.audience,
               event.action,
               event.object_type,
               event.object_id,
               event.request_id,
               event.before_json,
               event.after_json,
               event.occurred_at,
               actor.public_id AS actor_user_public_id,
               actor.name AS actor_name,
               actor.surname AS actor_surname,
               account.public_id AS actor_account_public_id
        FROM audit_events AS event
        LEFT JOIN users AS actor ON actor.id = event.actor_user_id
        LEFT JOIN auth_accounts AS account ON account.id = event.actor_account_id
        {where}
        ORDER BY event.occurred_at DESC, event.id DESC
        LIMIT ?
        """,
        (*parameters, limit),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = ["find_audit_cursor", "insert_audit_event", "list_audit_events"]
