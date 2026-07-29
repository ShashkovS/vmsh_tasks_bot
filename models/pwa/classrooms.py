"""Small domain rules shared by the Staff classroom catalog boundaries."""

from __future__ import annotations

import unicodedata
import sqlite3

from db_methods.pwa.classroom_assignments import (
    mark_working_plans_using_classroom_stale,
)
from db_methods.pwa.classrooms import set_classroom_status


MAX_CLASSROOM_NAME_LENGTH = 200


class InvalidClassroomName(ValueError):
    """A classroom name cannot be stored or searched safely."""


def prepare_classroom_name(value: str) -> tuple[str, str]:
    """Return the display name and its case-insensitive comparison key."""

    if not isinstance(value, str):
        raise InvalidClassroomName
    name = value.strip()
    normalized_name = unicodedata.normalize("NFKC", name).casefold()
    if not name or len(name) > MAX_CLASSROOM_NAME_LENGTH:
        raise InvalidClassroomName
    return name, normalized_name


def normalize_classroom_search(value: str) -> str:
    """Normalize optional Staff search text with the same rules as names."""

    if not isinstance(value, str):
        raise InvalidClassroomName
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def change_classroom_status(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    event_public_id: str,
    status: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> dict[str, object]:
    item = set_classroom_status(
        connection,
        public_id=public_id,
        expected_version=expected_version,
        event_public_id=event_public_id,
        status=status,
        actor_user_id=actor_user_id,
        request_id=request_id,
        now=now,
    )
    if status == "archived":
        mark_working_plans_using_classroom_stale(
            connection, classroom_public_id=public_id, now=now
        )
    return item


__all__ = [
    "InvalidClassroomName",
    "MAX_CLASSROOM_NAME_LENGTH",
    "change_classroom_status",
    "normalize_classroom_search",
    "prepare_classroom_name",
]
