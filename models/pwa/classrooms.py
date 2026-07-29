"""Small domain rules shared by the Staff classroom catalog boundaries."""

from __future__ import annotations

import unicodedata


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


__all__ = [
    "InvalidClassroomName",
    "MAX_CLASSROOM_NAME_LENGTH",
    "normalize_classroom_search",
    "prepare_classroom_name",
]
