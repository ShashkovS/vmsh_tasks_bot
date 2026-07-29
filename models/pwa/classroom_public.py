"""Student and Family projection of confirmed classroom assignments."""

from __future__ import annotations

import sqlite3

from db_methods.pwa.classroom_assignments import list_student_classroom_events


def read_student_classroom_assignments(
    connection: sqlite3.Connection, student_user_id: int
) -> list[dict[str, object]]:
    """Return only published room state; drafts and other students stay private."""

    items = []
    for row in list_student_classroom_events(connection, student_user_id):
        status = _public_status(row)
        assigned = status == "assigned"
        items.append(
            {
                "event_public_id": row["event_public_id"],
                "event_name": row["event_name"],
                "starts_at": row["starts_at"],
                "ends_at": row["ends_at"],
                "course_public_id": row["course_public_id"],
                "course_name": row["course_name"],
                "group_public_id": row["group_public_id"],
                "group_name": row["group_name"],
                "group_lesson_public_id": row["group_lesson_public_id"],
                "attendance_mode": row["attendance_mode"],
                "status": status,
                "classroom_public_id": row["classroom_public_id"] if assigned else None,
                "classroom_name": row["classroom_name"] if assigned else None,
                "confirmed_at": row["confirmed_at"] if assigned else None,
                # Phase 7D delivery is a separate explicit admin action. Until
                # its receipt exists, confirmation must not look like delivery.
                "announced_at": None,
            }
        )
    return items


def _public_status(row: dict[str, object]) -> str:
    if row["attendance_mode"] == "online":
        return "not_applicable"
    if (
        row["layout_state"] != "confirmed"
        or row["assignment_status"] != "assigned"
        or row["assigned_group_lesson_id"] != row["group_lesson_id"]
        or row["assigned_group_id"] != row["active_group_id"]
        or row["classroom_status"] != "active"
    ):
        return "reassigning"
    return "assigned"


__all__ = ["read_student_classroom_assignments"]
