"""Focused SQLite statements for Staff-managed Student and Family accounts."""

from __future__ import annotations

import sqlite3


def find_account(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, audience, status, credential_hash, "
        "credential_version FROM auth_accounts WHERE public_id = ? "
        "AND audience IN ('student', 'family')",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def update_status(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    expected_version: int,
    status: str,
    now: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "UPDATE auth_accounts SET status = ?, credential_version = "
        "credential_version + 1, updated_at = ? WHERE id = ? "
        "AND credential_version = ? RETURNING id, public_id, audience, status, "
        "credential_hash, credential_version",
        (status, now, account_id, expected_version),
    ).fetchone()
    return None if row is None else dict(row)


def revoke_sessions(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    now: str,
    reason: str,
) -> int:
    return connection.execute(
        "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = ?, "
        "updated_at = ?, version = version + 1 WHERE account_id = ? "
        "AND revoked_at IS NULL",
        (now, reason, now, account_id),
    ).rowcount


def insert_status_event(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    request_id: str,
    occurred_at: str,
    metadata_json: str,
) -> None:
    connection.execute(
        "INSERT INTO auth_events "
        "(account_id, event_type, occurred_at, request_id, metadata_json) "
        "VALUES (?, 'account.status_changed', ?, ?, ?)",
        (account_id, occurred_at, request_id, metadata_json),
    )


__all__ = [
    "find_account",
    "insert_status_event",
    "revoke_sessions",
    "update_status",
]
