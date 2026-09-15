"""Small notification rules above the SQLite storage operations."""

from __future__ import annotations

import json
import re
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db_methods.pwa.notifications import (
    list_course_preferences,
    list_events,
    list_preferences,
    mark_event_read,
    save_course_preference,
    save_preference,
    student_notification_course,
)


NOTIFICATION_CATEGORIES = (
    "lesson_published",
    "hint_published",
    "solution_published",
    "review_completed",
    "thread_updated",
    "oral_window",
    "classroom_assignment",
    "deadline",
    "news",
    "group_announcement",
)
_TIME = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")


class NotificationNotFound(Exception):
    pass


class InvalidNotificationPreference(Exception):
    pass


class NotificationCourseNotFound(Exception):
    pass


def _default_preference(category: str) -> dict[str, object]:
    enabled = category != "oral_window"
    return {
        "category": category,
        "in_app_enabled": enabled,
        "push_enabled": enabled,
        "sound_enabled": enabled,
        "quiet_starts_local": "21:00",
        "quiet_ends_local": "09:00",
        "timezone": "Europe/Moscow",
        "updated_at": None,
    }


def read_preferences(
    connection: sqlite3.Connection, account_id: int
) -> list[dict[str, object]]:
    stored = {
        str(item["category"]): item for item in list_preferences(connection, account_id)
    }
    return [
        stored.get(category, _default_preference(category))
        for category in NOTIFICATION_CATEGORIES
    ]


def update_preference(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    category: str,
    in_app_enabled: bool,
    push_enabled: bool,
    sound_enabled: bool,
    quiet_starts_local: str,
    quiet_ends_local: str,
    timezone: str,
    now: str,
) -> dict[str, object]:
    if category not in NOTIFICATION_CATEGORIES:
        raise InvalidNotificationPreference("unknown_category")
    if not _TIME.fullmatch(quiet_starts_local) or not _TIME.fullmatch(quiet_ends_local):
        raise InvalidNotificationPreference("invalid_quiet_hours")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidNotificationPreference("invalid_timezone") from error
    save_preference(
        connection,
        account_id=account_id,
        category=category,
        in_app_enabled=in_app_enabled,
        push_enabled=push_enabled,
        sound_enabled=sound_enabled,
        quiet_starts_local=quiet_starts_local,
        quiet_ends_local=quiet_ends_local,
        timezone=timezone,
        updated_at=now,
    )
    return next(
        item
        for item in read_preferences(connection, account_id)
        if item["category"] == category
    )


def read_course_preferences(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    course = student_notification_course(
        connection,
        account_id=account_id,
        course_public_id=course_public_id,
    )
    if course is None:
        raise NotificationCourseNotFound
    stored = {
        str(item["category"]): item
        for item in list_course_preferences(
            connection,
            account_id=account_id,
            course_id=int(course["id"]),
        )
    }
    items = []
    for global_preference in read_preferences(connection, account_id):
        category = str(global_preference["category"])
        override = stored.get(category)
        items.append(
            {
                "category": category,
                "push_enabled": (
                    global_preference["push_enabled"]
                    if override is None
                    else override["push_enabled"]
                ),
                "inherited": override is None,
                "updated_at": None if override is None else override["updated_at"],
            }
        )
    return course, items


def update_course_preference(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
    category: str,
    push_enabled: bool | None,
    now: str,
) -> dict[str, object]:
    if category not in NOTIFICATION_CATEGORIES:
        raise InvalidNotificationPreference("unknown_category")
    course, _items = read_course_preferences(
        connection,
        account_id=account_id,
        course_public_id=course_public_id,
    )
    save_course_preference(
        connection,
        account_id=account_id,
        course_id=int(course["id"]),
        category=category,
        push_enabled=push_enabled,
        updated_at=now,
    )
    _course, items = read_course_preferences(
        connection,
        account_id=account_id,
        course_public_id=course_public_id,
    )
    return next(item for item in items if item["category"] == category)


def read_events(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    limit: int,
    unread_only: bool,
    now: str,
) -> list[dict[str, object]]:
    items = list_events(
        connection,
        account_id=account_id,
        limit=limit,
        unread_only=unread_only,
        now=now,
    )
    for item in items:
        item["payload"] = json.loads(str(item.pop("payload_json")))
    return items


def acknowledge_event(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    event_public_id: str,
    session_id: int,
    now: str,
) -> dict[str, object]:
    item = mark_event_read(
        connection,
        account_id=account_id,
        event_public_id=event_public_id,
        session_id=session_id,
        read_at=now,
    )
    if item is None:
        raise NotificationNotFound
    return item


__all__ = [
    "InvalidNotificationPreference",
    "NOTIFICATION_CATEGORIES",
    "NotificationNotFound",
    "NotificationCourseNotFound",
    "acknowledge_event",
    "read_events",
    "read_course_preferences",
    "read_preferences",
    "update_preference",
    "update_course_preference",
]
