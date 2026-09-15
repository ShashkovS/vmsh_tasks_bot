"""Small rules for Telegram binding ownership and inheritance."""

from __future__ import annotations

import sqlite3

from db_methods.pwa.telegram_bindings import (
    find_course_id,
    find_group_id,
    insert_binding,
    list_verified_context_bindings,
    update_binding,
)


class InvalidTelegramBinding(ValueError):
    pass


class TelegramBindingOwnerNotFound(LookupError):
    pass


def _values(
    connection: sqlite3.Connection,
    *,
    owner_type: object,
    owner_public_id: object,
    purpose: object,
    chat_id: object,
    message_thread_id: object,
    title_cached: object,
) -> tuple[str, int | None, str | None, str, int, int | None, str | None]:
    if owner_type not in {"course", "group"}:
        raise InvalidTelegramBinding("owner_type")
    if not isinstance(owner_public_id, str) or not owner_public_id:
        raise InvalidTelegramBinding("owner_public_id")
    if purpose not in {"news_source", "materials_target"}:
        raise InvalidTelegramBinding("purpose")
    if isinstance(chat_id, bool) or not isinstance(chat_id, int) or chat_id == 0:
        raise InvalidTelegramBinding("chat_id")
    if message_thread_id is not None and (
        isinstance(message_thread_id, bool)
        or not isinstance(message_thread_id, int)
        or message_thread_id < 1
    ):
        raise InvalidTelegramBinding("message_thread_id")
    if title_cached is not None:
        if not isinstance(title_cached, str):
            raise InvalidTelegramBinding("title_cached")
        title_cached = title_cached.strip()
        if not title_cached or len(title_cached) > 200:
            raise InvalidTelegramBinding("title_cached")

    owner_course_id = None
    owner_group_id = None
    if owner_type == "course":
        owner_course_id = find_course_id(connection, owner_public_id)
        if owner_course_id is None:
            raise TelegramBindingOwnerNotFound
    else:
        owner_group_id = find_group_id(connection, owner_public_id)
        if owner_group_id is None:
            raise TelegramBindingOwnerNotFound
    return (
        owner_type,
        owner_course_id,
        owner_group_id,
        purpose,
        chat_id,
        message_thread_id,
        title_cached,
    )


def create_binding(
    connection: sqlite3.Connection,
    *,
    owner_type: object,
    owner_public_id: object,
    purpose: object,
    chat_id: object,
    message_thread_id: object,
    title_cached: object,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    values = _values(
        connection,
        owner_type=owner_type,
        owner_public_id=owner_public_id,
        purpose=purpose,
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        title_cached=title_cached,
    )
    return insert_binding(
        connection,
        owner_type=values[0],
        owner_course_id=values[1],
        owner_group_id=values[2],
        purpose=values[3],
        chat_id=values[4],
        message_thread_id=values[5],
        title_cached=values[6],
        actor_user_id=actor_user_id,
        now=now,
    )


def edit_binding(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    owner_type: object,
    owner_public_id: object,
    purpose: object,
    chat_id: object,
    message_thread_id: object,
    title_cached: object,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    values = _values(
        connection,
        owner_type=owner_type,
        owner_public_id=owner_public_id,
        purpose=purpose,
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        title_cached=title_cached,
    )
    return update_binding(
        connection,
        public_id=public_id,
        expected_version=expected_version,
        owner_type=values[0],
        owner_course_id=values[1],
        owner_group_id=values[2],
        purpose=values[3],
        chat_id=values[4],
        message_thread_id=values[5],
        title_cached=values[6],
        actor_user_id=actor_user_id,
        now=now,
    )


def effective_bindings(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_id: str,
    purpose: str,
) -> list[dict[str, object]]:
    if purpose not in {"news_source", "materials_target"}:
        raise InvalidTelegramBinding("purpose")
    items = list_verified_context_bindings(
        connection,
        course_id=course_id,
        group_id=group_id,
        purpose=purpose,
    )
    if purpose == "news_source":
        return items
    group_items = [item for item in items if item["owner_type"] == "group"]
    return group_items or items


__all__ = [
    "InvalidTelegramBinding",
    "TelegramBindingOwnerNotFound",
    "create_binding",
    "edit_binding",
    "effective_bindings",
]
