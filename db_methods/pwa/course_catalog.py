"""Direct SQLite statements for the Staff course/group catalog."""

from __future__ import annotations

import sqlite3


def find_season(
    connection: sqlite3.Connection, *, public_id: str | None
) -> dict[str, object] | None:
    if public_id is None:
        row = connection.execute(
            "SELECT id, public_id, code, title, status FROM seasons "
            "WHERE status = 'active' ORDER BY starts_on DESC, id DESC LIMIT 1"
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT id, public_id, code, title, status FROM seasons WHERE public_id = ?",
            (public_id,),
        ).fetchone()
    return None if row is None else dict(row)


def list_courses(
    connection: sqlite3.Connection, *, season_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT course.id,
               course.public_id,
               course.code,
               course.name,
               course.subject_code,
               course.status,
               course.sort_order,
               course.accent_key,
               course.version,
               count(DISTINCT enrollment.student_user_id) AS active_students
        FROM courses AS course
        LEFT JOIN course_enrollments AS enrollment
          ON enrollment.course_id = course.id AND enrollment.status = 'active'
        WHERE course.season_id = ?
        GROUP BY course.id
        ORDER BY course.sort_order, course.code, course.id
        """,
        (season_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_groups(
    connection: sqlite3.Connection, *, course_ids: tuple[int, ...]
) -> list[dict[str, object]]:
    if not course_ids:
        return []
    placeholders = ",".join("?" for _ in course_ids)
    rows = connection.execute(
        f"""
        SELECT group_record.course_id,
               group_record.public_id,
               group_record.short_code,
               group_record.public_name,
               group_record.status,
               group_record.color_key,
               group_record.sort_order,
               group_record.allow_self_switch,
               group_record.is_default,
               group_record.is_system,
               group_record.score_weight,
               group_record.version,
               count(DISTINCT enrollment.student_user_id) AS active_students
        FROM groups AS group_record
        LEFT JOIN course_enrollments AS enrollment
          ON enrollment.course_id = group_record.course_id
         AND enrollment.active_group_id = group_record.group_id
         AND enrollment.status = 'active'
        WHERE group_record.course_id IN ({placeholders})
        GROUP BY group_record.group_id
        ORDER BY group_record.course_id,
                 group_record.sort_order,
                 group_record.short_code,
                 group_record.group_id
        """,
        course_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def find_course(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT course.id, course.public_id, course.season_id, course.code, "
        "course.name, course.subject_code, course.status, course.sort_order, "
        "course.accent_key, course.version, "
        "(SELECT count(DISTINCT enrollment.student_user_id) "
        " FROM course_enrollments AS enrollment "
        " WHERE enrollment.course_id = course.id AND enrollment.status = 'active') "
        "AS active_students FROM courses AS course WHERE course.public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def insert_course(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    season_id: int,
    code: str,
    name: str,
    subject_code: str,
    status: str,
    sort_order: int,
    accent_key: str,
    actor_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO courses "
        "(public_id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at, created_by, updated_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            public_id,
            season_id,
            code,
            name,
            subject_code,
            status,
            sort_order,
            accent_key,
            now,
            now,
            actor_user_id,
            actor_user_id,
        ),
    )


def update_course(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    code: str,
    name: str,
    subject_code: str,
    status: str,
    sort_order: int,
    accent_key: str,
    actor_user_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE courses SET code = ?, name = ?, subject_code = ?, status = ?, "
        "sort_order = ?, accent_key = ?, updated_at = ?, updated_by = ?, "
        "version = version + 1 WHERE public_id = ? AND version = ?",
        (
            code,
            name,
            subject_code,
            status,
            sort_order,
            accent_key,
            now,
            actor_user_id,
            public_id,
            expected_version,
        ),
    )
    return cursor.rowcount == 1


def find_group(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT group_record.group_id, group_record.public_id, "
        "group_record.course_id, group_record.short_code, group_record.public_name, "
        "group_record.status, group_record.color_key, group_record.sort_order, "
        "group_record.allow_self_switch, group_record.is_default, "
        "group_record.is_system, group_record.score_weight, group_record.version, "
        "(SELECT count(DISTINCT enrollment.student_user_id) "
        " FROM course_enrollments AS enrollment "
        " WHERE enrollment.course_id = group_record.course_id "
        "   AND enrollment.active_group_id = group_record.group_id "
        "   AND enrollment.status = 'active') AS active_students "
        "FROM groups AS group_record WHERE group_record.public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def insert_group(
    connection: sqlite3.Connection,
    *,
    group_id: str,
    public_id: str,
    course_id: int,
    short_code: str,
    name: str,
    status: str,
    color_key: str,
    sort_order: int,
    allow_self_switch: bool,
    score_weight: float,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, public_id, course_id, status, "
        "color_key, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?, 0, ?, ?, ?, ?, ?, ?, ?)",
        (
            group_id,
            short_code,
            name,
            sort_order,
            int(status == "active"),
            int(allow_self_switch),
            score_weight,
            public_id,
            course_id,
            status,
            color_key,
            now,
            now,
        ),
    )


def update_group(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    short_code: str,
    name: str,
    status: str,
    color_key: str,
    sort_order: int,
    allow_self_switch: bool,
    score_weight: float,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE groups SET short_code = ?, public_name = ?, status = ?, "
        "is_active = ?, color_key = ?, sort_order = ?, allow_self_switch = ?, "
        "score_weight = ?, updated_at = ?, version = version + 1 "
        "WHERE public_id = ? AND version = ?",
        (
            short_code,
            name,
            status,
            int(status == "active"),
            color_key,
            sort_order,
            int(allow_self_switch),
            score_weight,
            now,
            public_id,
            expected_version,
        ),
    )
    return cursor.rowcount == 1


__all__ = [
    "find_course",
    "find_group",
    "find_season",
    "insert_course",
    "insert_group",
    "list_courses",
    "list_groups",
    "update_course",
    "update_group",
]
