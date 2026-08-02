"""Short SQLite statements for Staff enrollment administration."""

from __future__ import annotations

import sqlite3

from helpers.consts import USER_TYPE


def list_students(
    connection: sqlite3.Connection,
    *,
    staff_scopes: tuple[tuple[str, str | None], ...] | None = None,
) -> list[dict[str, object]]:
    """Return one row per Student/enrollment, optionally limited by Staff scope.

    The product has roughly 1500 students.  A single admin snapshot is simpler
    and faster here than maintaining cursor state while an operator filters and
    edits the same list. Teachers receive only rows in their course/group scope;
    an admin snapshot also includes unprovisioned users. See Phase 10.
    """

    scope_sql = ""
    parameters: list[object] = [int(USER_TYPE.STUDENT)]
    if staff_scopes is not None:
        clauses: list[str] = []
        for course_public_id, group_public_id in staff_scopes:
            if group_public_id is None:
                clauses.append("course.public_id = ?")
                parameters.append(course_public_id)
            else:
                clauses.append("(course.public_id = ? AND active_group.public_id = ?)")
                parameters.extend((course_public_id, group_public_id))
        scope_sql = f" AND ({' OR '.join(clauses)})" if clauses else " AND 0"

    rows = connection.execute(
        f"""
        SELECT student.id AS student_user_id,
               student.public_id AS student_public_id,
               student.surname,
               student.name,
               student.middlename,
               student.grade,
               student.birthday,
               account.public_id AS account_public_id,
               account.username,
               account.status AS account_status,
               account.credential_version AS account_credential_version,
               enrollment.id AS enrollment_id,
               enrollment.public_id AS enrollment_public_id,
               enrollment.course_id,
               course.public_id AS course_public_id,
               course.code AS course_code,
               course.name AS course_name,
               course.subject_code,
               enrollment.active_group_id,
               active_group.public_id AS active_group_public_id,
               enrollment.attendance_mode,
               enrollment.status AS enrollment_status,
               enrollment.version AS enrollment_version,
               strength.simple_prob,
               strength.compl_prob
        FROM users AS student
        LEFT JOIN auth_accounts AS account
          ON account.linked_user_id = student.id
         AND account.audience = 'student'
        LEFT JOIN course_enrollments AS enrollment
          ON enrollment.student_user_id = student.id
        LEFT JOIN courses AS course ON course.id = enrollment.course_id
        LEFT JOIN groups AS active_group
          ON active_group.course_id = enrollment.course_id
         AND active_group.group_id = enrollment.active_group_id
        LEFT JOIN student_strength AS strength
          ON strength.student_id = student.id
        WHERE student.type = ?{scope_sql}
        ORDER BY student.surname, student.name, student.id,
                 course.sort_order, course.code, enrollment.id
        """,
        parameters,
    ).fetchall()
    return [dict(row) for row in rows]


def list_active_group_access(
    connection: sqlite3.Connection, enrollment_ids: tuple[int, ...]
) -> list[dict[str, object]]:
    if not enrollment_ids:
        return []
    placeholders = ",".join("?" for _ in enrollment_ids)
    rows = connection.execute(
        f"""
        SELECT access.enrollment_id,
               group_record.group_id,
               group_record.public_id AS group_public_id,
               group_record.short_code,
               group_record.public_name,
               group_record.status,
               group_record.color_key,
               group_record.sort_order
        FROM course_group_access AS access
        JOIN groups AS group_record
          ON group_record.course_id = access.course_id
         AND group_record.group_id = access.group_id
        WHERE access.enrollment_id IN ({placeholders})
          AND access.valid_to IS NULL
        ORDER BY access.enrollment_id, group_record.sort_order,
                 group_record.short_code, group_record.group_id
        """,
        enrollment_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def list_family_links(
    connection: sqlite3.Connection, student_user_ids: tuple[int, ...]
) -> list[dict[str, object]]:
    if not student_user_ids:
        return []
    placeholders = ",".join("?" for _ in student_user_ids)
    rows = connection.execute(
        f"""
        SELECT link.student_user_id,
               account.public_id AS account_public_id,
               account.username,
               account.display_name,
               account.status,
               account.credential_version,
               link.relationship_label,
               link.is_primary
        FROM family_student_links AS link
        JOIN auth_accounts AS account ON account.id = link.family_account_id
        WHERE link.student_user_id IN ({placeholders})
          AND link.revoked_at IS NULL
        ORDER BY link.student_user_id, link.is_primary DESC,
                 account.display_name, account.id
        """,
        student_user_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def find_enrollment(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT enrollment.id AS enrollment_id,
               enrollment.public_id AS enrollment_public_id,
               enrollment.student_user_id,
               enrollment.course_id,
               enrollment.active_group_id,
               enrollment.attendance_mode,
               enrollment.status AS enrollment_status,
               enrollment.version AS enrollment_version,
               student.public_id AS student_public_id,
               course.public_id AS course_public_id,
               course.code AS course_code,
               course.name AS course_name,
               course.subject_code,
               active_group.public_id AS active_group_public_id
        FROM course_enrollments AS enrollment
        JOIN users AS student ON student.id = enrollment.student_user_id
        JOIN courses AS course ON course.id = enrollment.course_id
        JOIN groups AS active_group
          ON active_group.course_id = enrollment.course_id
         AND active_group.group_id = enrollment.active_group_id
        WHERE enrollment.public_id = ?
        """,
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_course_groups(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT group_id, public_id, short_code, public_name, status,
               color_key, sort_order
        FROM groups
        WHERE course_id = ?
        ORDER BY sort_order, short_code, group_id
        """,
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_active_access_group_ids(
    connection: sqlite3.Connection, *, enrollment_id: int
) -> set[str]:
    rows = connection.execute(
        "SELECT group_id FROM course_group_access "
        "WHERE enrollment_id = ? AND valid_to IS NULL",
        (enrollment_id,),
    ).fetchall()
    return {str(row["group_id"]) for row in rows}


def update_enrollment(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    expected_version: int,
    active_group_id: str,
    attendance_mode: str,
    status: str,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE course_enrollments SET active_group_id = ?, attendance_mode = ?, "
        "status = ?, updated_at = ?, updated_by = ?, version = version + 1 "
        "WHERE id = ? AND version = ?",
        (
            active_group_id,
            attendance_mode,
            status,
            now,
            actor_user_id,
            enrollment_id,
            expected_version,
        ),
    )
    return cursor.rowcount == 1


def revoke_group_access(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    group_id: str,
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "UPDATE course_group_access SET valid_to = ?, revoked_by = ?, "
        "reason = 'staff_update', updated_at = ?, version = version + 1 "
        "WHERE enrollment_id = ? AND group_id = ? AND valid_to IS NULL",
        (now, actor_user_id, now, enrollment_id, group_id),
    )


def grant_group_access(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    course_id: int,
    group_id: str,
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_group_access "
        "(enrollment_id, course_id, group_id, valid_from, granted_by, reason, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'staff_update', ?, ?)",
        (enrollment_id, course_id, group_id, now, actor_user_id, now, now),
    )


def insert_group_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    enrollment_id: int,
    course_id: int,
    previous_group_id: str,
    new_group_id: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_enrollment_events "
        "(public_id, enrollment_id, course_id, event_type, previous_group_id, "
        "new_group_id, actor_user_id, source, request_id, occurred_at, created_at) "
        "VALUES (?, ?, ?, 'active_group_changed', ?, ?, ?, 'staff', ?, ?, ?)",
        (
            public_id,
            enrollment_id,
            course_id,
            previous_group_id,
            new_group_id,
            actor_user_id,
            request_id,
            now,
            now,
        ),
    )


def insert_mode_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    enrollment_id: int,
    course_id: int,
    previous_mode: str,
    new_mode: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_enrollment_events "
        "(public_id, enrollment_id, course_id, event_type, "
        "previous_attendance_mode, new_attendance_mode, actor_user_id, source, "
        "request_id, occurred_at, created_at) "
        "VALUES (?, ?, ?, 'attendance_mode_changed', ?, ?, ?, 'staff', ?, ?, ?)",
        (
            public_id,
            enrollment_id,
            course_id,
            previous_mode,
            new_mode,
            actor_user_id,
            request_id,
            now,
            now,
        ),
    )


def insert_status_event(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    enrollment_id: int,
    course_id: int,
    previous_status: str,
    new_status: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_enrollment_events "
        "(public_id, enrollment_id, course_id, event_type, previous_status, "
        "new_status, actor_user_id, source, request_id, occurred_at, created_at) "
        "VALUES (?, ?, ?, 'status_changed', ?, ?, ?, 'staff', ?, ?, ?)",
        (
            public_id,
            enrollment_id,
            course_id,
            previous_status,
            new_status,
            actor_user_id,
            request_id,
            now,
            now,
        ),
    )


def list_owner_accounts(
    connection: sqlite3.Connection, *, student_user_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT account.public_id, account.audience
        FROM auth_accounts AS account
        WHERE account.linked_user_id = ?
          AND account.audience = 'student'
          AND account.status = 'active'
        UNION ALL
        SELECT account.public_id, account.audience
        FROM family_student_links AS link
        JOIN auth_accounts AS account ON account.id = link.family_account_id
        WHERE link.student_user_id = ?
          AND link.revoked_at IS NULL
          AND account.status = 'active'
        ORDER BY audience, public_id
        """,
        (student_user_id, student_user_id),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "find_enrollment",
    "grant_group_access",
    "insert_group_event",
    "insert_mode_event",
    "insert_status_event",
    "list_active_access_group_ids",
    "list_active_group_access",
    "list_course_groups",
    "list_family_links",
    "list_owner_accounts",
    "list_students",
    "revoke_group_access",
    "update_enrollment",
]
