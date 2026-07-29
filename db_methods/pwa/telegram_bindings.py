"""Direct SQLite operations for course/group Telegram bindings."""

from __future__ import annotations

import sqlite3


class TelegramBindingNotFound(LookupError):
    pass


class TelegramBindingVersionConflict(RuntimeError):
    pass


class TelegramBindingDuplicate(RuntimeError):
    pass


_SELECT = """
SELECT binding.id, binding.public_id, binding.owner_type,
       course.public_id AS owner_course_public_id,
       course.name AS owner_course_name,
       owner_group.public_id AS owner_group_public_id,
       owner_group.public_name AS owner_group_name,
       group_course.public_id AS group_course_public_id,
       group_course.name AS group_course_name,
       binding.purpose, binding.chat_id, binding.message_thread_id,
       binding.title_cached, binding.status, binding.verified_at,
       binding.created_at, binding.updated_at, binding.version
FROM telegram_bindings binding
LEFT JOIN courses course ON course.id = binding.owner_course_id
LEFT JOIN groups owner_group ON owner_group.group_id = binding.owner_group_id
LEFT JOIN courses group_course ON group_course.id = owner_group.course_id
"""


def list_bindings(
    connection: sqlite3.Connection, *, course_public_id: str | None = None
) -> list[dict[str, object]]:
    where = ""
    values: tuple[object, ...] = ()
    if course_public_id is not None:
        where = "WHERE course.public_id = ? OR group_course.public_id = ?"
        values = (course_public_id, course_public_id)
    rows = connection.execute(
        _SELECT
        + where
        + " ORDER BY coalesce(course.sort_order, group_course.sort_order), "
        "coalesce(course.id, group_course.id), binding.owner_type, "
        "owner_group.sort_order, binding.purpose, binding.id",
        values,
    ).fetchall()
    return [dict(row) for row in rows]


def list_binding_owners(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT course.public_id AS course_public_id, course.name AS course_name, "
        "course.status AS course_status, course.sort_order AS course_sort_order, "
        "owner_group.public_id AS group_public_id, "
        "owner_group.public_name AS group_name, owner_group.status AS group_status, "
        "owner_group.sort_order AS group_sort_order "
        "FROM courses course LEFT JOIN groups owner_group "
        "ON owner_group.course_id = course.id "
        "ORDER BY course.sort_order, course.id, owner_group.sort_order, owner_group.group_id"
    ).fetchall()
    return [dict(row) for row in rows]


def get_binding(
    connection: sqlite3.Connection, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        _SELECT + " WHERE binding.public_id = ?", (public_id,)
    ).fetchone()
    return None if row is None else dict(row)


def find_course_id(connection: sqlite3.Connection, public_id: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM courses WHERE public_id = ?", (public_id,)
    ).fetchone()
    return None if row is None else int(row["id"])


def find_group_id(connection: sqlite3.Connection, public_id: str) -> str | None:
    row = connection.execute(
        "SELECT group_id FROM groups WHERE public_id = ? AND course_id IS NOT NULL",
        (public_id,),
    ).fetchone()
    return None if row is None else str(row["group_id"])


def list_verified_context_bindings(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
    purpose: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT public_id, owner_type, purpose, chat_id, message_thread_id, "
        "title_cached, verified_at FROM telegram_bindings "
        "WHERE status = 'verified' AND purpose = ? AND "
        "((owner_type = 'course' AND owner_course_id = ?) OR "
        "(owner_type = 'group' AND owner_group_id = ?)) ORDER BY id",
        (purpose, course_id, group_id),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_binding(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    owner_type: str,
    owner_course_id: int | None,
    owner_group_id: str | None,
    purpose: str,
    chat_id: int,
    message_thread_id: int | None,
    title_cached: str | None,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    try:
        connection.execute(
            "INSERT INTO telegram_bindings "
            "(public_id, owner_type, owner_course_id, owner_group_id, purpose, "
            "chat_id, message_thread_id, title_cached, status, "
            "created_by_user_id, updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)",
            (
                public_id,
                owner_type,
                owner_course_id,
                owner_group_id,
                purpose,
                chat_id,
                message_thread_id,
                title_cached,
                actor_user_id,
                actor_user_id,
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError as error:
        if "telegram_bindings_owner_destination_uq" in str(error):
            raise TelegramBindingDuplicate from error
        raise
    item = get_binding(connection, public_id)
    assert item is not None
    return item


def update_binding(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    owner_type: str,
    owner_course_id: int | None,
    owner_group_id: str | None,
    purpose: str,
    chat_id: int,
    message_thread_id: int | None,
    title_cached: str | None,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    try:
        cursor = connection.execute(
            "UPDATE telegram_bindings SET owner_type = ?, owner_course_id = ?, "
            "owner_group_id = ?, purpose = ?, chat_id = ?, message_thread_id = ?, "
            "title_cached = ?, status = 'draft', verified_at = NULL, "
            "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
            "WHERE public_id = ? AND version = ?",
            (
                owner_type,
                owner_course_id,
                owner_group_id,
                purpose,
                chat_id,
                message_thread_id,
                title_cached,
                actor_user_id,
                now,
                public_id,
                expected_version,
            ),
        )
    except sqlite3.IntegrityError as error:
        if "telegram_bindings_owner_destination_uq" in str(error):
            raise TelegramBindingDuplicate from error
        raise
    if cursor.rowcount != 1:
        if get_binding(connection, public_id) is None:
            raise TelegramBindingNotFound
        raise TelegramBindingVersionConflict
    item = get_binding(connection, public_id)
    assert item is not None
    return item


def set_binding_status(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    status: str,
    verified_at: str | None,
    title_cached: str | None,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    cursor = connection.execute(
        "UPDATE telegram_bindings SET status = ?, verified_at = ?, "
        "title_cached = coalesce(?, title_cached), updated_by_user_id = ?, "
        "updated_at = ?, version = version + 1 "
        "WHERE public_id = ? AND version = ?",
        (
            status,
            verified_at,
            title_cached,
            actor_user_id,
            now,
            public_id,
            expected_version,
        ),
    )
    if cursor.rowcount != 1:
        if get_binding(connection, public_id) is None:
            raise TelegramBindingNotFound
        raise TelegramBindingVersionConflict
    item = get_binding(connection, public_id)
    assert item is not None
    return item


__all__ = [
    "TelegramBindingDuplicate",
    "TelegramBindingNotFound",
    "TelegramBindingVersionConflict",
    "find_course_id",
    "find_group_id",
    "get_binding",
    "insert_binding",
    "list_bindings",
    "list_binding_owners",
    "list_verified_context_bindings",
    "set_binding_status",
    "update_binding",
]
