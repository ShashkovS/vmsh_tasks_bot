"""Business rules for inherited classroom layouts.

The functions operate inside the caller's SQLite transaction. Data access is
kept in ``db_methods.pwa.classroom_layouts``.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Sequence

from db_methods.pwa.classroom_layouts import (
    confirm_draft_layout,
    find_event_layout,
    find_latest_confirmed_layout_for_group,
    get_in_person_event,
    get_layout_version_by_public_id,
    insert_layout_version,
    list_event_group_lessons,
    list_layout_rooms,
    replace_layout_rooms,
    resolve_layout_room_input,
    supersede_confirmed_layout,
    touch_layout_version,
)


class ClassroomLayoutNotFound(LookupError):
    pass


class ClassroomLayoutConflict(RuntimeError):
    pass


class InvalidClassroomLayout(ValueError):
    pass


def _layout_response(
    *,
    event: dict[str, object],
    groups: list[dict[str, object]],
    header: dict[str, object] | None,
    state: str,
    rooms: list[dict[str, object]],
    conflicts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    groups_by_id = {int(group["group_lesson_id"]): group for group in groups}
    projected_rooms = []
    for room in rooms:
        group = groups_by_id[int(room["group_lesson_id"])]
        projected_rooms.append(
            {
                "classroom_public_id": room["classroom_public_id"],
                "classroom_name": room["classroom_name"],
                "classroom_status": room["classroom_status"],
                "group_lesson_public_id": group["group_lesson_public_id"],
                "course_public_id": group["course_public_id"],
                "group_public_id": group["group_public_id"],
                "group_name": group["group_name"],
                "source_layout_public_id": room.get("source_layout_public_id"),
            }
        )
    return {
        "event": event,
        "state": state,
        "layout_public_id": None if header is None else header["public_id"],
        "version": None if header is None else header["version"],
        "base_version_id": None if header is None else header["base_version_id"],
        "groups": groups,
        "rooms": projected_rooms,
        "conflicts": conflicts or [],
    }


def read_effective_layout(
    connection: sqlite3.Connection, event_public_id: str
) -> dict[str, object]:
    event = get_in_person_event(connection, event_public_id)
    if event is None:
        raise ClassroomLayoutNotFound
    event_id = int(event["id"])
    groups = list_event_group_lessons(connection, event_id)

    for state in ("draft", "confirmed"):
        header = find_event_layout(connection, event_id, state)
        if header is not None:
            rooms = list_layout_rooms(connection, int(header["id"]))
            return _layout_response(
                event=event,
                groups=groups,
                header=header,
                state=state,
                rooms=rooms,
            )

    inherited_rooms: list[dict[str, object]] = []
    for group in groups:
        source = find_latest_confirmed_layout_for_group(
            connection,
            course_id=int(group["course_id"]),
            group_id=str(group["group_id"]),
            before_starts_at=str(event["starts_at"]),
        )
        if source is None:
            continue
        source_rooms = list_layout_rooms(
            connection,
            int(source["layout_id"]),
            group_lesson_id=int(source["source_group_lesson_id"]),
        )
        for room in source_rooms:
            inherited_rooms.append(
                {
                    **room,
                    "group_lesson_id": group["group_lesson_id"],
                    "source_layout_version_id": source["layout_id"],
                    "source_layout_public_id": source["layout_public_id"],
                }
            )

    room_counts = Counter(int(room["classroom_id"]) for room in inherited_rooms)
    conflicts = [
        {
            "classroom_public_id": room["classroom_public_id"],
            "classroom_name": room["classroom_name"],
        }
        for room in inherited_rooms
        if room_counts[int(room["classroom_id"])] > 1
    ]
    unique_conflicts = list(
        {
            str(conflict["classroom_public_id"]): conflict for conflict in conflicts
        }.values()
    )
    return _layout_response(
        event=event,
        groups=groups,
        header=None,
        state="inherited",
        rooms=inherited_rooms,
        conflicts=unique_conflicts,
    )


def materialize_layout(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    layout_public_id: str,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    effective = read_effective_layout(connection, event_public_id)
    if effective["state"] == "draft":
        return effective

    event = effective["event"]
    event_id = int(event["id"])
    current = find_event_layout(connection, event_id, "confirmed")
    base_version_id = None if current is None else int(current["id"])
    layout_id = insert_layout_version(
        connection,
        public_id=layout_public_id,
        event_id=event_id,
        base_version_id=base_version_id,
        actor_user_id=actor_user_id,
        now=now,
    )

    groups_by_public_id = {
        str(group["group_lesson_public_id"]): int(group["group_lesson_id"])
        for group in effective["groups"]
    }
    conflicted_rooms = {
        str(conflict["classroom_public_id"]) for conflict in effective["conflicts"]
    }
    room_ids_by_public_id: dict[str, int] = {}
    if base_version_id is not None:
        room_ids_by_public_id = {
            str(room["classroom_public_id"]): int(room["classroom_id"])
            for room in list_layout_rooms(connection, base_version_id)
        }
    if base_version_id is None:
        for room in effective["rooms"]:
            resolved = resolve_layout_room_input(
                connection,
                event_id=event_id,
                classroom_public_id=str(room["classroom_public_id"]),
                group_lesson_public_id=str(room["group_lesson_public_id"]),
            )
            if resolved is not None:
                room_ids_by_public_id[str(room["classroom_public_id"])] = int(
                    resolved["classroom_id"]
                )

    source_ids: dict[str, int] = {}
    rows = []
    for room in effective["rooms"]:
        classroom_public_id = str(room["classroom_public_id"])
        if classroom_public_id in conflicted_rooms:
            continue
        source_layout_id = base_version_id
        source_public_id = room.get("source_layout_public_id")
        if source_layout_id is None and isinstance(source_public_id, str):
            if source_public_id not in source_ids:
                source = get_layout_version_by_public_id(connection, source_public_id)
                if source is not None:
                    source_ids[source_public_id] = int(source["id"])
            source_layout_id = source_ids.get(source_public_id)
        rows.append(
            (
                room_ids_by_public_id[classroom_public_id],
                groups_by_public_id[str(room["group_lesson_public_id"])],
                source_layout_id,
            )
        )
    replace_layout_rooms(connection, layout_id=layout_id, rooms=rows, now=now)
    return read_effective_layout(connection, event_public_id)


def replace_draft_layout(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    layout_public_id: str,
    expected_version: int,
    mappings: Sequence[tuple[str, str]],
    now: str,
) -> dict[str, object]:
    event = get_in_person_event(connection, event_public_id)
    if event is None:
        raise ClassroomLayoutNotFound
    header = find_event_layout(connection, int(event["id"]), "draft")
    if header is None or header["public_id"] != layout_public_id:
        raise ClassroomLayoutNotFound
    if int(header["version"]) != expected_version:
        raise ClassroomLayoutConflict

    seen_rooms: set[int] = set()
    rows: list[tuple[int, int, int | None]] = []
    for classroom_public_id, group_lesson_public_id in mappings:
        resolved = resolve_layout_room_input(
            connection,
            event_id=int(event["id"]),
            classroom_public_id=classroom_public_id,
            group_lesson_public_id=group_lesson_public_id,
        )
        if resolved is None:
            raise InvalidClassroomLayout(
                "unknown room or non-participating group lesson"
            )
        if resolved["classroom_status"] != "active":
            raise InvalidClassroomLayout("archived room cannot be assigned")
        classroom_id = int(resolved["classroom_id"])
        if classroom_id in seen_rooms:
            raise InvalidClassroomLayout("room is assigned more than once")
        seen_rooms.add(classroom_id)
        rows.append((classroom_id, int(resolved["group_lesson_id"]), None))

    replace_layout_rooms(connection, layout_id=int(header["id"]), rooms=rows, now=now)
    if not touch_layout_version(
        connection,
        layout_id=int(header["id"]),
        expected_version=expected_version,
        now=now,
    ):
        raise ClassroomLayoutConflict
    return read_effective_layout(connection, event_public_id)


def confirm_layout(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    layout_public_id: str,
    expected_version: int,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    event = get_in_person_event(connection, event_public_id)
    if event is None:
        raise ClassroomLayoutNotFound
    event_id = int(event["id"])
    header = find_event_layout(connection, event_id, "draft")
    if header is None:
        confirmed = find_event_layout(connection, event_id, "confirmed")
        if confirmed is not None and confirmed["public_id"] == layout_public_id:
            raise ClassroomLayoutConflict
        raise ClassroomLayoutNotFound
    if header["public_id"] != layout_public_id:
        raise ClassroomLayoutNotFound
    if int(header["version"]) != expected_version:
        raise ClassroomLayoutConflict
    rooms = list_layout_rooms(connection, int(header["id"]))
    if any(room["classroom_status"] != "active" for room in rooms):
        raise InvalidClassroomLayout("archived room cannot be confirmed")

    supersede_confirmed_layout(connection, event_id=event_id, now=now)
    if not confirm_draft_layout(
        connection,
        layout_id=int(header["id"]),
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        now=now,
    ):
        raise ClassroomLayoutConflict
    return read_effective_layout(connection, event_public_id)


__all__ = [
    "ClassroomLayoutConflict",
    "ClassroomLayoutNotFound",
    "InvalidClassroomLayout",
    "confirm_layout",
    "materialize_layout",
    "read_effective_layout",
    "replace_draft_layout",
]
