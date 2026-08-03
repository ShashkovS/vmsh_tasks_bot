"""Short SQLite operations for v1 Student and Family provisioning batches."""

from __future__ import annotations

import sqlite3

from helpers.consts import ONLINE_MODE, USER_TYPE


def account_logins(connection: sqlite3.Connection, *, audience: str) -> set[str]:
    return {
        str(row["username_normalized"])
        for row in connection.execute(
            "SELECT username_normalized FROM auth_accounts WHERE audience = ?",
            (audience,),
        )
    }


def student_tokens(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["token"])
        for row in connection.execute(
            "SELECT token FROM users WHERE type = ? AND token IS NOT NULL",
            (int(USER_TYPE.STUDENT),),
        )
    }


def student_for_login(
    connection: sqlite3.Connection, *, login_normalized: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT account.id AS account_id, user.id AS user_id, "
        "user.public_id AS user_public_id FROM auth_accounts AS account "
        "JOIN users AS user ON user.id = account.linked_user_id "
        "WHERE account.audience = 'student' AND account.username_normalized = ? "
        "AND account.status <> 'archived'",
        (login_normalized,),
    ).fetchone()
    return None if row is None else dict(row)


def available_student_logins(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["username_normalized"])
        for row in connection.execute(
            "SELECT username_normalized FROM auth_accounts "
            "WHERE audience = 'student' AND status <> 'archived'"
        )
    }


def insert_student_user(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    surname: str,
    name: str,
    patronymic: str,
    token: str,
    grade: int | None,
    birth_date: str | None,
) -> int:
    row = connection.execute(
        "INSERT INTO users "
        "(public_id, type, surname, name, middlename, token, online, grade, birthday) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            public_id,
            int(USER_TYPE.STUDENT),
            surname,
            name,
            patronymic or None,
            token,
            int(ONLINE_MODE.ONLINE),
            grade,
            birth_date,
        ),
    ).fetchone()
    return int(row["id"])


def insert_provisioned_account(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    audience: str,
    username: str,
    username_normalized: str,
    display_name: str,
    credential_kind: str,
    credential_hash: str,
    credential_plaintext: str,
    linked_user_id: int | None,
    now: str,
) -> int:
    row = connection.execute(
        "INSERT INTO auth_accounts "
        "(public_id, audience, username, username_normalized, "
        "username_algorithm_version, provisioning_source, display_name, "
        "credential_kind, credential_hash, provisioning_password_plaintext, "
        "linked_user_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'staff_batch', ?, ?, ?, ?, ?, 'active', ?, ?) "
        "RETURNING id",
        (
            public_id,
            audience,
            username,
            username_normalized,
            1 if audience == "student" else None,
            display_name,
            credential_kind,
            credential_hash,
            credential_plaintext,
            linked_user_id,
            now,
            now,
        ),
    ).fetchone()
    return int(row["id"])


def insert_family_emails(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    emails: tuple[str, ...],
    now: str,
) -> None:
    connection.executemany(
        "INSERT INTO family_account_emails "
        "(family_account_id, ordinal, email, email_normalized, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (family_account_id, ordinal, email, email.casefold(), now)
            for ordinal, email in enumerate(emails)
        ],
    )


def insert_family_link(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    student_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO family_student_links "
        "(family_account_id, student_user_id, relationship_label, is_primary, "
        "created_at, updated_at) VALUES (?, ?, NULL, 0, ?, ?)",
        (family_account_id, student_user_id, now, now),
    )


__all__ = [
    "account_logins",
    "available_student_logins",
    "insert_family_emails",
    "insert_family_link",
    "insert_provisioned_account",
    "insert_student_user",
    "student_for_login",
    "student_tokens",
]
