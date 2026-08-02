"""Production-size synthetic rehearsal for the Phase-7 classroom planner."""

from __future__ import annotations

import sqlite3
from collections import Counter
from time import perf_counter

from models.pwa.classroom_assignments import (
    confirm_assignment_plan,
    recalculate_assignment_plan,
)
from models.pwa.classroom_layouts import (
    confirm_layout,
    materialize_layout,
    replace_draft_layout,
)
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    NOW,
    _apply,
    _insert_parents,
    _migrations,
)


STUDENT_COUNT = 1_500
ROOM_COUNT = 15


def test_worst_case_in_person_event_recalculates_and_confirms_1500_students(
    tmp_path,
) -> None:
    """The deliberately pessimistic case is larger than current in-person use."""

    database_path = tmp_path / "phase7-classroom-scale.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_parents(connection)
        connection.execute("DELETE FROM classroom_assignments")
        connection.execute("DELETE FROM classroom_assignment_plans")

        connection.executemany(
            "INSERT INTO users "
            "(id, public_id, type, name, surname, grade, birthday) "
            "VALUES (?, ?, 1, ?, ?, ?, ?)",
            (
                (
                    student_id,
                    f"student-scale-{student_id:04d}",
                    f"Имя{student_id:04d}",
                    f"Фамилия{student_id:04d}",
                    5 + student_id % 3,
                    f"201{student_id % 4}-01-01",
                )
                for student_id in range(3, STUDENT_COUNT + 2)
            ),
        )
        connection.executemany(
            "INSERT INTO course_enrollments "
            "(id, public_id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, 'assignment-n', 'in_person', 'active', ?, ?)",
            (
                (
                    enrollment_id,
                    f"enrollment-scale-{enrollment_id:04d}",
                    enrollment_id + 1,
                    NOW,
                    NOW,
                )
                for enrollment_id in range(2, STUDENT_COUNT + 1)
            ),
        )
        room_public_ids = ["classroom-assignment"]
        for room_number in range(2, ROOM_COUNT + 1):
            room_public_id = f"classroom-scale-{room_number:02d}"
            connection.execute(
                "INSERT INTO classrooms "
                "(public_id, name, normalized_name, status, "
                "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', 2, 2, ?, ?)",
                (
                    room_public_id,
                    str(200 + room_number),
                    str(200 + room_number),
                    NOW,
                    NOW,
                ),
            )
            room_public_ids.append(room_public_id)
        draft = materialize_layout(
            connection,
            event_public_id="event-assignment",
            layout_public_id="layout-scale",
            actor_user_id=2,
            now=NOW,
        )
        draft = replace_draft_layout(
            connection,
            event_public_id="event-assignment",
            layout_public_id="layout-scale",
            expected_version=int(draft["version"]),
            mappings=[
                (room_public_id, "group-lesson-assignment")
                for room_public_id in room_public_ids
            ],
            now=NOW,
        )
        confirm_layout(
            connection,
            event_public_id="event-assignment",
            layout_public_id="layout-scale",
            expected_version=int(draft["version"]),
            actor_user_id=2,
            now=NOW,
        )
        connection.commit()

        started = perf_counter()
        preview = recalculate_assignment_plan(
            connection,
            event_public_id="event-assignment",
            plan_public_id="plan-scale",
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )
        recalculation_seconds = perf_counter() - started

        assert len(preview["students"]) == STUDENT_COUNT
        assert all(student["status"] == "assigned" for student in preview["students"])
        assert all(
            student["classroom_id"] is not None for student in preview["students"]
        )
        loads = Counter(student["classroom_id"] for student in preview["students"])
        assert len(loads) == ROOM_COUNT
        assert set(loads.values()) == {STUDENT_COUNT // ROOM_COUNT}
        # This is a regression alarm, not a tight latency promise. The current
        # local run is far below it, while a pathological query plan is not.
        assert recalculation_seconds < 5

        started = perf_counter()
        confirmed = confirm_assignment_plan(
            connection,
            event_public_id="event-assignment",
            plan_public_id="plan-scale",
            expected_version=int(preview["plan"]["version"]),
            actor_user_id=2,
            now="2026-07-29T13:00:01Z",
        )
        confirmation_seconds = perf_counter() - started

        assert confirmed["plan"]["state"] == "confirmed"
        assert len(confirmed["students"]) == STUDENT_COUNT
        assert confirmation_seconds < 5
