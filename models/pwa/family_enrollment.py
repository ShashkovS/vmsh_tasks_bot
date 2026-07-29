"""Family course group/mode change transaction."""

from __future__ import annotations

import sqlite3
import uuid

from db_methods.pwa.family_enrollment import (
    insert_group_change_event,
    insert_mode_change_event,
    mark_working_classroom_plans_stale,
    sync_legacy_single_course_user,
    update_enrollment,
)


def change_family_enrollment(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    course_id: int,
    student_user_id: int,
    expected_version: int,
    previous_group_id: str,
    active_group_id: str,
    previous_attendance_mode: str,
    attendance_mode: str,
    request_id: str,
    now: str,
) -> int | None:
    """Apply one checked change; return the new version or ``None`` on conflict."""

    group_changed = previous_group_id != active_group_id
    mode_changed = previous_attendance_mode != attendance_mode
    if not group_changed and not mode_changed:
        return expected_version

    if not update_enrollment(
        connection,
        enrollment_id=enrollment_id,
        expected_version=expected_version,
        active_group_id=active_group_id,
        attendance_mode=attendance_mode,
        now=now,
    ):
        return None

    if group_changed:
        insert_group_change_event(
            connection,
            public_id=f"course-enrollment-event.{uuid.uuid4().hex}",
            enrollment_id=enrollment_id,
            course_id=course_id,
            previous_value=previous_group_id,
            new_value=active_group_id,
            request_id=f"{request_id}.group",
            now=now,
        )
    if mode_changed:
        insert_mode_change_event(
            connection,
            public_id=f"course-enrollment-event.{uuid.uuid4().hex}",
            enrollment_id=enrollment_id,
            course_id=course_id,
            previous_value=previous_attendance_mode,
            new_value=attendance_mode,
            request_id=f"{request_id}.mode",
            now=now,
        )

    mark_working_classroom_plans_stale(connection, course_id=course_id, now=now)
    sync_legacy_single_course_user(
        connection,
        student_user_id=student_user_id,
        active_group_id=active_group_id,
        attendance_mode=attendance_mode,
        group_changed=group_changed,
        mode_changed=mode_changed,
        now=now,
    )
    return expected_version + 1


__all__ = ["change_family_enrollment"]
