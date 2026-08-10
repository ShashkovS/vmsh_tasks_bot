"""Small SQLite queries for Staff course/group scopes."""

from __future__ import annotations

import sqlite3

from helpers.consts import USER_TYPE


def list_staff_members(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT user.id,
               user.public_id,
               user.name,
               user.surname,
               user.middlename,
               user.type,
               account.public_id AS account_public_id,
               account.username,
               account.status AS account_status
        FROM users AS user
        LEFT JOIN auth_accounts AS account
          ON account.linked_user_id = user.id AND account.audience = 'staff'
        WHERE user.type IN (?, ?) AND user.public_id IS NOT NULL
        ORDER BY user.surname, user.name, user.id
        """,
        (int(USER_TYPE.TEACHER), int(USER_TYPE.ADMIN)),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_teacher(
    connection: sqlite3.Connection,
    *,
    user_public_id: str,
    account_public_id: str,
    surname: str,
    name: str,
    middle_name: str | None,
    username: str,
    username_normalized: str,
    credential_hash: str,
    now: str,
) -> int:
    user_id = connection.execute(
        "INSERT INTO users (public_id, type, surname, name, middlename) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id",
        (user_public_id, int(USER_TYPE.TEACHER), surname, name, middle_name),
    ).fetchone()["id"]
    connection.execute(
        "INSERT INTO auth_accounts "
        "(public_id, audience, username, username_normalized, provisioning_source, "
        "display_name, credential_kind, credential_hash, linked_user_id, status, "
        "created_at, updated_at) VALUES (?, 'staff', ?, ?, 'staff', ?, 'password', "
        "?, ?, 'active', ?, ?)",
        (
            account_public_id,
            username,
            username_normalized,
            f"{name} {surname}",
            credential_hash,
            user_id,
            now,
            now,
        ),
    )
    return int(user_id)


def find_staff_member(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT user.id, user.public_id, user.name, user.surname, user.middlename, "
        "user.type, account.public_id AS account_public_id, account.username, "
        "account.status AS account_status FROM users AS user "
        "LEFT JOIN auth_accounts AS account ON account.linked_user_id = user.id "
        "AND account.audience = 'staff' "
        "WHERE user.public_id = ? AND user.type IN (?, ?)",
        (public_id, int(USER_TYPE.TEACHER), int(USER_TYPE.ADMIN)),
    ).fetchone()
    return None if row is None else dict(row)


def list_teacher_scopes(
    connection: sqlite3.Connection, *, staff_user_ids: tuple[int, ...]
) -> list[dict[str, object]]:
    if not staff_user_ids:
        return []
    placeholders = ",".join("?" for _ in staff_user_ids)
    rows = connection.execute(
        f"""
        SELECT scope.id,
               scope.staff_user_id,
               scope.version,
               course.id AS course_id,
               course.public_id AS course_public_id,
               course.code AS course_code,
               course.name AS course_name,
               course.status AS course_status,
               scope.group_id,
               group_record.public_id AS group_public_id,
               group_record.short_code AS group_code,
               group_record.public_name AS group_name,
               group_record.status AS group_status
        FROM staff_scopes AS scope
        JOIN courses AS course ON course.id = scope.course_id
        LEFT JOIN groups AS group_record
          ON group_record.course_id = scope.course_id
         AND group_record.group_id = scope.group_id
        WHERE scope.staff_user_id IN ({placeholders})
          AND scope.role = 'teacher'
          AND scope.valid_to IS NULL
        ORDER BY course.sort_order, course.id, group_record.sort_order, scope.id
        """,
        staff_user_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def find_scope_target(
    connection: sqlite3.Connection,
    *,
    course_public_id: str,
    group_public_id: str | None,
) -> dict[str, object] | None:
    if group_public_id is None:
        row = connection.execute(
            "SELECT id AS course_id, public_id AS course_public_id, status AS course_status "
            "FROM courses WHERE public_id = ?",
            (course_public_id,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT course.id AS course_id, course.public_id AS course_public_id, "
            "course.status AS course_status, group_record.group_id, "
            "group_record.public_id AS group_public_id, "
            "group_record.status AS group_status "
            "FROM courses AS course JOIN groups AS group_record "
            "ON group_record.course_id = course.id "
            "WHERE course.public_id = ? AND group_record.public_id = ?",
            (course_public_id, group_public_id),
        ).fetchone()
    return None if row is None else dict(row)


def revoke_teacher_scope(
    connection: sqlite3.Connection,
    *,
    scope_id: int,
    expected_version: int,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE staff_scopes SET valid_to = ?, revoked_by = ?, "
        "reason = 'staff_access_editor', updated_at = ?, version = version + 1 "
        "WHERE id = ? AND role = 'teacher' AND valid_to IS NULL AND version = ?",
        (now, actor_user_id, now, scope_id, expected_version),
    )
    return cursor.rowcount == 1


def insert_teacher_scope(
    connection: sqlite3.Connection,
    *,
    staff_user_id: int,
    course_id: int,
    group_id: str | None,
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO staff_scopes "
        "(staff_user_id, course_id, group_id, role, valid_from, granted_by, "
        "created_at, updated_at) VALUES (?, ?, ?, 'teacher', ?, ?, ?, ?)",
        (staff_user_id, course_id, group_id, now, actor_user_id, now, now),
    )


__all__ = [
    "find_scope_target",
    "find_staff_member",
    "insert_teacher_scope",
    "list_staff_members",
    "list_teacher_scopes",
    "revoke_teacher_scope",
]
