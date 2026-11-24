"""Small SQLite operations for the initial global administrator."""

from __future__ import annotations

import sqlite3

from .audit import insert_audit_event


def global_admin_exists(
    connection: sqlite3.Connection,
    *,
    admin_user_type: int,
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM users WHERE type = ? LIMIT 1",
            (admin_user_type,),
        ).fetchone()
        is not None
    )


def insert_first_global_admin(
    connection: sqlite3.Connection,
    *,
    admin_user_type: int,
    username: str,
    display_name: str,
    user_name: str,
    user_surname: str,
    credential_hash: str,
    audit_action: str,
    audit_after_json: str,
    occurred_at: str,
) -> bool:
    """Insert the bootstrap account unless another worker already did it."""

    if global_admin_exists(connection, admin_user_type=admin_user_type):
        return False

    user = connection.execute(
        "INSERT INTO users (type, name, surname) "
        "VALUES (?, ?, ?) RETURNING id, public_id",
        (admin_user_type, user_name, user_surname),
    ).fetchone()
    account = connection.execute(
        "INSERT INTO auth_accounts "
        "(audience, username, username_normalized, "
        "provisioning_source, display_name, credential_kind, credential_hash, "
        "linked_user_id, status, created_at, updated_at) "
        "VALUES ('staff', ?, ?, 'startup_first_admin', ?, "
        "'password', ?, ?, 'active', ?, ?) RETURNING id, public_id",
        (
            username,
            username,
            display_name,
            credential_hash,
            user["id"],
            occurred_at,
            occurred_at,
        ),
    ).fetchone()
    insert_audit_event(
        connection,
        actor_user_id=None,
        actor_account_public_id=None,
        audience="system",
        action=audit_action,
        object_type="auth_account",
        object_id=str(account["public_id"]),
        request_id="startup:first-admin",
        before_json=None,
        after_json=audit_after_json,
        occurred_at=occurred_at,
    )
    return True


__all__ = ["global_admin_exists", "insert_first_global_admin"]
