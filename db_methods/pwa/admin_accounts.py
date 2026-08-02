"""Focused SQLite statements for Staff-managed Student and Family accounts."""

from __future__ import annotations

import sqlite3

from helpers.consts import USER_TYPE


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


def find_student(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id FROM users WHERE public_id = ? AND type = ?",
        (public_id, int(USER_TYPE.STUDENT)),
    ).fetchone()
    return None if row is None else dict(row)


def find_family_account_by_username(
    connection: sqlite3.Connection, *, username_normalized: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, username, display_name, status, credential_version "
        "FROM auth_accounts WHERE audience = 'family' AND username_normalized = ?",
        (username_normalized,),
    ).fetchone()
    return None if row is None else dict(row)


def insert_family_account(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    username: str,
    username_normalized: str,
    display_name: str,
    credential_hash: str,
    now: str,
) -> dict[str, object]:
    row = connection.execute(
        "INSERT INTO auth_accounts "
        "(public_id, audience, username, username_normalized, provisioning_source, "
        "display_name, credential_kind, credential_hash, status, created_at, updated_at) "
        "VALUES (?, 'family', ?, ?, 'staff', ?, 'password', ?, 'active', ?, ?) "
        "RETURNING id, public_id, username, display_name, status, credential_version",
        (
            public_id,
            username,
            username_normalized,
            display_name,
            credential_hash,
            now,
            now,
        ),
    ).fetchone()
    return dict(row)


def save_family_link(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    student_user_id: int,
    relationship_label: str,
    is_primary: bool,
    now: str,
) -> dict[str, object]:
    connection.execute(
        "INSERT INTO family_student_links "
        "(family_account_id, student_user_id, relationship_label, is_primary, "
        "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?, NULL) "
        "ON CONFLICT (family_account_id, student_user_id) DO UPDATE SET "
        "relationship_label = excluded.relationship_label, "
        "is_primary = excluded.is_primary, updated_at = excluded.updated_at, "
        "revoked_at = NULL",
        (
            family_account_id,
            student_user_id,
            relationship_label,
            int(is_primary),
            now,
            now,
        ),
    )
    row = connection.execute(
        "SELECT relationship_label, is_primary, revoked_at "
        "FROM family_student_links WHERE family_account_id = ? AND student_user_id = ?",
        (family_account_id, student_user_id),
    ).fetchone()
    return dict(row)


def revoke_family_link(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    student_user_id: int,
    now: str,
) -> bool:
    return (
        connection.execute(
            "UPDATE family_student_links SET revoked_at = ?, updated_at = ? "
            "WHERE family_account_id = ? AND student_user_id = ? AND revoked_at IS NULL",
            (now, now, family_account_id, student_user_id),
        ).rowcount
        == 1
    )


def insert_account_event(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    event_type: str,
    request_id: str,
    occurred_at: str,
    metadata_json: str,
) -> None:
    connection.execute(
        "INSERT INTO auth_events "
        "(account_id, event_type, occurred_at, request_id, metadata_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (account_id, event_type, occurred_at, request_id, metadata_json),
    )


__all__ = [
    "find_account",
    "find_family_account_by_username",
    "find_student",
    "insert_account_event",
    "insert_family_account",
    "insert_status_event",
    "revoke_family_link",
    "revoke_sessions",
    "save_family_link",
    "update_status",
]
