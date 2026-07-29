"""Pure classroom distribution rules for one in-person event."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Literal


AssignmentSource = Literal["previous-room", "least-loaded"]


@dataclass(frozen=True)
class StudentToAssign:
    enrollment_id: int
    group_lesson_id: int
    surname: str
    name: str
    previous_classroom_id: int | None = None


@dataclass(frozen=True)
class AssignmentRoom:
    classroom_id: int
    group_lesson_id: int
    name: str


@dataclass(frozen=True)
class AssignmentDecision:
    enrollment_id: int
    classroom_id: int | None
    source: AssignmentSource | None


def _natural_name(value: str) -> tuple[tuple[int, object], ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", normalized)
        if part
    )


def distribute_students(
    students: list[StudentToAssign], rooms: list[AssignmentRoom]
) -> list[AssignmentDecision]:
    """Keep valid previous rooms, then balance the remaining students."""

    rooms_by_group: dict[int, list[AssignmentRoom]] = {}
    for room in rooms:
        rooms_by_group.setdefault(room.group_lesson_id, []).append(room)
    for group_rooms in rooms_by_group.values():
        group_rooms.sort(key=lambda room: (_natural_name(room.name), room.classroom_id))

    ordered_students = sorted(
        students,
        key=lambda student: (
            unicodedata.normalize("NFKC", student.surname).casefold(),
            unicodedata.normalize("NFKC", student.name).casefold(),
            student.enrollment_id,
        ),
    )
    loads = {room.classroom_id: 0 for room in rooms}
    decisions: dict[int, AssignmentDecision] = {}

    for student in ordered_students:
        valid_room_ids = {
            room.classroom_id
            for room in rooms_by_group.get(student.group_lesson_id, [])
        }
        if student.previous_classroom_id in valid_room_ids:
            classroom_id = student.previous_classroom_id
            assert classroom_id is not None
            loads[classroom_id] += 1
            decisions[student.enrollment_id] = AssignmentDecision(
                enrollment_id=student.enrollment_id,
                classroom_id=classroom_id,
                source="previous-room",
            )

    for student in ordered_students:
        if student.enrollment_id in decisions:
            continue
        candidates = rooms_by_group.get(student.group_lesson_id, [])
        if not candidates:
            decisions[student.enrollment_id] = AssignmentDecision(
                enrollment_id=student.enrollment_id,
                classroom_id=None,
                source=None,
            )
            continue
        room = min(
            candidates,
            key=lambda candidate: (
                loads[candidate.classroom_id],
                _natural_name(candidate.name),
                candidate.classroom_id,
            ),
        )
        loads[room.classroom_id] += 1
        decisions[student.enrollment_id] = AssignmentDecision(
            enrollment_id=student.enrollment_id,
            classroom_id=room.classroom_id,
            source="least-loaded",
        )

    return [decisions[student.enrollment_id] for student in ordered_students]


def age_in_years(birthday: str | None, *, today: date) -> float | None:
    if birthday is None:
        return None
    try:
        born = date.fromisoformat(birthday)
    except ValueError:
        return None
    if born > today:
        return None
    return round((today - born).days / 365.25, 1)


__all__ = [
    "AssignmentDecision",
    "AssignmentRoom",
    "StudentToAssign",
    "age_in_years",
    "distribute_students",
]
