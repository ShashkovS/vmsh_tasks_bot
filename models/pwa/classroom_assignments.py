"""Classroom assignment preview and confirmation rules."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from datetime import date

from db_methods.pwa.classroom_assignments import (
    confirm_plan,
    find_plan,
    find_plan_by_public_id,
    find_previous_classroom,
    grant_group_access,
    insert_plan,
    insert_group_change_event,
    insert_legacy_group_change,
    list_eligible_students,
    list_plan_assignments,
    replace_assignments,
    supersede_confirmed_plan,
    touch_plan,
    update_assignment_group_and_room,
    update_assignment_room,
    update_enrollment_group,
    update_legacy_group_if_current,
)
from db_methods.pwa.classroom_layouts import (
    find_event_layout,
    get_in_person_event,
    list_event_group_lessons,
    list_layout_rooms,
)
from helpers.pwa.classroom_assignment import (
    AssignmentRoom,
    StudentToAssign,
    age_in_years,
    classroom_strength,
    distribute_students,
)


class ClassroomAssignmentNotFound(Exception):
    pass


class ClassroomAssignmentConflict(Exception):
    pass


class InvalidClassroomAssignment(Exception):
    pass


def _event(connection: sqlite3.Connection, public_id: str) -> dict[str, object]:
    event = get_in_person_event(connection, public_id)
    if event is None:
        raise ClassroomAssignmentNotFound
    return event


def read_assignment_plan(
    connection: sqlite3.Connection,
    event_public_id: str,
    *,
    today: date | None = None,
) -> dict[str, object]:
    event = _event(connection, event_public_id)
    event_id = int(event["id"])
    groups = list_event_group_lessons(connection, event_id)
    plan = find_plan(connection, event_id, ("draft", "stale"))
    if plan is None:
        plan = find_plan(connection, event_id, ("confirmed",))
    if plan is None:
        layout = find_event_layout(connection, event_id, "confirmed")
        rooms = (
            [] if layout is None else list_layout_rooms(connection, int(layout["id"]))
        )
        return {
            "event": event,
            "plan": None,
            "groups": groups,
            "rooms": rooms,
            "students": [],
        }

    rooms = list_layout_rooms(connection, int(plan["layout_version_id"]))
    current_day = date.today() if today is None else today
    students = []
    for row in list_plan_assignments(connection, int(plan["id"])):
        students.append(
            {
                **row,
                "age_years": age_in_years(
                    None if row["birthday"] is None else str(row["birthday"]),
                    today=current_day,
                ),
                "strength": classroom_strength(
                    None if row["simple_prob"] is None else float(row["simple_prob"]),
                    None if row["compl_prob"] is None else float(row["compl_prob"]),
                ),
            }
        )
    return {
        "event": event,
        "plan": plan,
        "groups": groups,
        "rooms": rooms,
        "students": students,
    }


def recalculate_assignment_plan(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    plan_public_id: str,
    expected_version: int | None,
    actor_user_id: int,
    now: str,
    today: date | None = None,
) -> dict[str, object]:
    event = _event(connection, event_public_id)
    event_id = int(event["id"])
    layout = find_event_layout(connection, event_id, "confirmed")
    if layout is None:
        raise InvalidClassroomAssignment("confirmed layout is required")

    working = find_plan(connection, event_id, ("draft", "stale"))
    if working is None:
        if expected_version is not None:
            raise ClassroomAssignmentConflict
        confirmed = find_plan(connection, event_id, ("confirmed",))
        plan_id = insert_plan(
            connection,
            public_id=plan_public_id,
            event_id=event_id,
            layout_id=int(layout["id"]),
            base_plan_id=None if confirmed is None else int(confirmed["id"]),
            actor_user_id=actor_user_id,
            now=now,
        )
    else:
        if expected_version != int(working["version"]):
            raise ClassroomAssignmentConflict
        if int(working["layout_version_id"]) != int(layout["id"]):
            raise InvalidClassroomAssignment("working plan uses another layout")
        plan_id = int(working["id"])

    students = list_eligible_students(connection, event_id)
    layout_rooms = list_layout_rooms(connection, int(layout["id"]))
    decisions = distribute_students(
        [
            StudentToAssign(
                enrollment_id=int(student["enrollment_id"]),
                group_lesson_id=int(student["group_lesson_id"]),
                surname=str(student["surname"]),
                name=str(student["name"]),
                previous_classroom_id=find_previous_classroom(
                    connection,
                    enrollment_id=int(student["enrollment_id"]),
                    group_id=str(student["group_id"]),
                    before_starts_at=str(event["starts_at"]),
                ),
            )
            for student in students
        ],
        [
            AssignmentRoom(
                classroom_id=int(room["classroom_id"]),
                group_lesson_id=int(room["group_lesson_id"]),
                name=str(room["classroom_name"]),
            )
            for room in layout_rooms
            if room["classroom_status"] == "active"
        ],
    )
    decisions_by_enrollment = {item.enrollment_id: item for item in decisions}
    replace_assignments(
        connection,
        plan_id=plan_id,
        rows=(
            (
                int(student["enrollment_id"]),
                int(student["group_lesson_id"]),
                str(student["group_id"]),
                decisions_by_enrollment[int(student["enrollment_id"])].classroom_id,
                (
                    "assigned"
                    if decisions_by_enrollment[
                        int(student["enrollment_id"])
                    ].classroom_id
                    is not None
                    else "reassigning"
                ),
                decisions_by_enrollment[int(student["enrollment_id"])].source
                or "least-loaded",
            )
            for student in students
        ),
        now=now,
    )
    if working is not None and not touch_plan(
        connection,
        plan_id=plan_id,
        expected_version=int(working["version"]),
        now=now,
    ):
        raise ClassroomAssignmentConflict
    return read_assignment_plan(connection, event_public_id, today=today)


def confirm_assignment_plan(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    plan_public_id: str,
    expected_version: int,
    actor_user_id: int,
    now: str,
    today: date | None = None,
) -> dict[str, object]:
    event = _event(connection, event_public_id)
    event_id = int(event["id"])
    plan = find_plan_by_public_id(connection, plan_public_id)
    if plan is None or int(plan["in_person_event_id"]) != event_id:
        raise ClassroomAssignmentNotFound
    if plan["state"] != "draft" or int(plan["version"]) != expected_version:
        raise ClassroomAssignmentConflict
    layout = find_event_layout(connection, event_id, "confirmed")
    if layout is None or int(plan["layout_version_id"]) != int(layout["id"]):
        raise InvalidClassroomAssignment("plan layout is no longer current")

    students = list_eligible_students(connection, event_id)
    eligible = {int(student["enrollment_id"]): student for student in students}
    assignments = list_plan_assignments(connection, int(plan["id"]))
    if {int(row["course_enrollment_id"]) for row in assignments} != set(eligible):
        raise InvalidClassroomAssignment("plan does not cover every in-person student")
    valid_rooms = {
        (int(room["classroom_id"]), int(room["group_lesson_id"]))
        for room in list_layout_rooms(connection, int(layout["id"]))
        if room["classroom_status"] == "active"
    }
    for assignment in assignments:
        student = eligible[int(assignment["course_enrollment_id"])]
        room_id = assignment["classroom_id"]
        group_lesson_id = int(assignment["group_lesson_id"])
        if (
            assignment["status"] != "assigned"
            or room_id is None
            or (int(room_id), group_lesson_id) not in valid_rooms
            or group_lesson_id != int(student["group_lesson_id"])
            or assignment["group_id"] != student["group_id"]
        ):
            raise InvalidClassroomAssignment(
                "student assignment is incomplete or stale"
            )

    supersede_confirmed_plan(connection, event_id=event_id, now=now)
    if not confirm_plan(
        connection,
        plan_id=int(plan["id"]),
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        now=now,
    ):
        raise ClassroomAssignmentConflict
    return read_assignment_plan(connection, event_public_id, today=today)


def update_assignment_plan(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    plan_public_id: str,
    expected_version: int,
    assignments: Sequence[tuple[str, str, bool]],
    actor_user_id: int,
    request_id: str,
    now: str,
    today: date | None = None,
) -> dict[str, object]:
    event = _event(connection, event_public_id)
    plan = find_plan_by_public_id(connection, plan_public_id)
    if plan is None or int(plan["in_person_event_id"]) != int(event["id"]):
        raise ClassroomAssignmentNotFound
    if plan["state"] != "draft" or int(plan["version"]) != expected_version:
        raise ClassroomAssignmentConflict
    layout = find_event_layout(connection, int(event["id"]), "confirmed")
    if layout is None or int(plan["layout_version_id"]) != int(layout["id"]):
        raise InvalidClassroomAssignment("plan layout is no longer current")

    current = {
        str(row["enrollment_public_id"]): row
        for row in list_plan_assignments(connection, int(plan["id"]))
    }
    rooms = {
        str(room["classroom_public_id"]): room
        for room in list_layout_rooms(connection, int(layout["id"]))
        if room["classroom_status"] == "active"
    }
    event_groups = {
        int(group["group_lesson_id"]): group
        for group in list_event_group_lessons(connection, int(event["id"]))
    }
    if len(
        {enrollment_id for enrollment_id, _room_id, _confirmed in assignments}
    ) != len(assignments):
        raise InvalidClassroomAssignment("student appears more than once")
    for enrollment_public_id, classroom_public_id, confirm_group_change in assignments:
        assignment = current.get(enrollment_public_id)
        room = rooms.get(classroom_public_id)
        if assignment is None or room is None:
            raise InvalidClassroomAssignment("unknown student or classroom")
        target_group = event_groups[int(room["group_lesson_id"])]
        if int(assignment["group_lesson_id"]) == int(room["group_lesson_id"]):
            update_assignment_room(
                connection,
                plan_id=int(plan["id"]),
                enrollment_id=int(assignment["course_enrollment_id"]),
                classroom_id=int(room["classroom_id"]),
                now=now,
            )
            continue
        if not confirm_group_change:
            raise InvalidClassroomAssignment("group change requires confirmation")
        if int(assignment["course_id"]) != int(target_group["course_id"]):
            raise InvalidClassroomAssignment("classroom belongs to another course")
        previous_group_id = str(assignment["group_id"])
        new_group_id = str(target_group["group_id"])
        enrollment_id = int(assignment["course_enrollment_id"])
        if not update_enrollment_group(
            connection,
            enrollment_id=enrollment_id,
            course_id=int(assignment["course_id"]),
            previous_group_id=previous_group_id,
            new_group_id=new_group_id,
            actor_user_id=actor_user_id,
            now=now,
        ):
            raise ClassroomAssignmentConflict
        grant_group_access(
            connection,
            enrollment_id=enrollment_id,
            course_id=int(assignment["course_id"]),
            group_id=new_group_id,
            actor_user_id=actor_user_id,
            now=now,
        )
        insert_group_change_event(
            connection,
            public_id=f"course-enrollment-event.{uuid.uuid4().hex}",
            enrollment_id=enrollment_id,
            course_id=int(assignment["course_id"]),
            previous_group_id=previous_group_id,
            new_group_id=new_group_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            now=now,
        )
        if update_legacy_group_if_current(
            connection,
            student_user_id=int(assignment["student_user_id"]),
            previous_group_id=previous_group_id,
            new_group_id=new_group_id,
        ):
            insert_legacy_group_change(
                connection,
                student_user_id=int(assignment["student_user_id"]),
                new_group_id=new_group_id,
                now=now,
            )
        update_assignment_group_and_room(
            connection,
            plan_id=int(plan["id"]),
            enrollment_id=enrollment_id,
            group_lesson_id=int(room["group_lesson_id"]),
            group_id=new_group_id,
            classroom_id=int(room["classroom_id"]),
            now=now,
        )
    if not touch_plan(
        connection,
        plan_id=int(plan["id"]),
        expected_version=expected_version,
        now=now,
    ):
        raise ClassroomAssignmentConflict
    return read_assignment_plan(connection, event_public_id, today=today)


__all__ = [
    "ClassroomAssignmentConflict",
    "ClassroomAssignmentNotFound",
    "InvalidClassroomAssignment",
    "confirm_assignment_plan",
    "read_assignment_plan",
    "recalculate_assignment_plan",
    "update_assignment_plan",
]
