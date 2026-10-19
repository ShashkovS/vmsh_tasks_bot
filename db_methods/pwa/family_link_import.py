"""Focused SQLite reads for the Family-link import preview."""

from __future__ import annotations

import sqlite3

from helpers.consts import USER_TYPE


def find_family_account_id(
    connection: sqlite3.Connection,
    *,
    username_normalized: str,
) -> int | None:
    row = connection.execute(
        "SELECT id FROM auth_accounts "
        "WHERE audience = 'family' AND username_normalized = ?",
        (username_normalized,),
    ).fetchone()
    return None if row is None else int(row["id"])


def find_student_user_id(
    connection: sqlite3.Connection,
    *,
    public_id: str,
) -> int | None:
    row = connection.execute(
        "SELECT id FROM users WHERE public_id = ? AND type = ?",
        (public_id, int(USER_TYPE.STUDENT)),
    ).fetchone()
    return None if row is None else int(row["id"])


def find_family_link(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    student_user_id: int,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT relationship_label, is_primary, revoked_at "
        "FROM family_student_links "
        "WHERE family_account_id = ? AND student_user_id = ?",
        (family_account_id, student_user_id),
    ).fetchone()
    return None if row is None else dict(row)


__all__ = [
    "find_family_account_id",
    "find_family_link",
    "find_student_user_id",
]
