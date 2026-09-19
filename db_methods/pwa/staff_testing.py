"""Staff-owned learner identities; see vmshpwa/docs/staff-testing.md."""

import secrets
import sqlite3

from db_methods.pwa.auth import _account_from_row


def available_groups(connection, staff_account_id, now):
    return connection.execute(
        "SELECT g.course_id, g.group_id, g.public_id, g.public_name AS name, "
        "c.public_id AS course_public_id, c.name AS course_name "
        "FROM auth_accounts a JOIN users u ON u.id=a.linked_user_id "
        "JOIN courses c ON c.status='active' "
        "JOIN groups g ON g.course_id=c.id AND g.status='active' "
        "WHERE a.id=? AND a.audience='staff' AND a.status='active' "
        "AND (u.type=128 OR (u.type=2 AND EXISTS (SELECT 1 FROM staff_scopes s "
        "WHERE s.staff_user_id=u.id AND s.course_id=c.id "
        "AND (s.group_id IS NULL OR s.group_id=g.group_id) "
        "AND s.valid_from<=? AND (s.valid_to IS NULL OR s.valid_to>?)))) "
        "ORDER BY c.sort_order,c.id,g.sort_order,g.group_id",
        (staff_account_id, now, now),
    ).fetchall()


def test_access_is_current(connection, student_user_id, now):
    owner = connection.execute(
        "SELECT t.staff_account_id FROM staff_test_students t "
        "JOIN auth_accounts a ON a.id=t.staff_account_id "
        "JOIN users u ON u.id=a.linked_user_id "
        "WHERE t.student_user_id=? AND a.status='active' AND a.audience='staff' "
        "AND u.type IN (2,128)",
        (student_user_id,),
    ).fetchone()
    if owner is None:
        return False
    allowed = {
        (g["course_id"], g["group_id"])
        for g in available_groups(connection, owner["staff_account_id"], now)
    }
    granted = connection.execute(
        "SELECT a.course_id,a.group_id FROM course_group_access a "
        "JOIN course_enrollments e ON e.id=a.enrollment_id "
        "WHERE e.student_user_id=? AND e.status='active' "
        "AND a.valid_from<=? AND (a.valid_to IS NULL OR a.valid_to>?)",
        (student_user_id, now, now),
    ).fetchall()
    return bool(allowed) and all(
        (g["course_id"], g["group_id"]) in allowed for g in granted
    )


def prepare_test_account(
    connection: sqlite3.Connection, staff_account_id: int, now: str
):
    groups = available_groups(connection, staff_account_id, now)
    if not groups:
        raise PermissionError("No accessible teaching groups")
    staff = connection.execute(
        "SELECT u.id,u.name,u.surname FROM auth_accounts a "
        "JOIN users u ON u.id=a.linked_user_id WHERE a.id=?",
        (staff_account_id,),
    ).fetchone()
    existing = connection.execute(
        "SELECT student_user_id FROM staff_test_students WHERE staff_account_id=?",
        (staff_account_id,),
    ).fetchone()
    if existing is None:
        student_id = connection.execute(
            "INSERT INTO users(type,name,surname,online) VALUES(512,?,?,1) RETURNING id",
            (f"Тест учителя: {staff['name']}", staff["surname"]),
        ).fetchone()["id"]
        username = "staff-test-" + secrets.token_hex(20)
        connection.execute(
            "INSERT INTO auth_accounts(audience,username,username_normalized,"
            "username_algorithm_version,provisioning_source,credential_kind,"
            "credential_hash,linked_user_id,status,created_at,updated_at) "
            "VALUES('student',?,?,1,'staff_testing','telegram_token',?,?,'active',?,?)",
            (
                username,
                username,
                "unusable:" + secrets.token_hex(32),
                student_id,
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO staff_test_students VALUES(?,?)",
            (staff_account_id, student_id),
        )
    else:
        student_id = existing["student_user_id"]
        connection.execute(
            "UPDATE users SET name=?,surname=? WHERE id=?",
            (f"Тест учителя: {staff['name']}", staff["surname"], student_id),
        )
    connection.execute(
        "UPDATE course_enrollments SET status='archived',updated_at=? WHERE student_user_id=?",
        (now, student_id),
    )
    by_course = {}
    for group in groups:
        by_course.setdefault(group["course_id"], []).append(group)
    for course_id, course_groups in by_course.items():
        previous = connection.execute(
            "SELECT active_group_id FROM course_enrollments WHERE student_user_id=? AND course_id=?",
            (student_id, course_id),
        ).fetchone()
        active_group = course_groups[0]["group_id"]
        if previous and previous["active_group_id"] in {
            g["group_id"] for g in course_groups
        }:
            active_group = previous["active_group_id"]
        enrollment = connection.execute(
            "INSERT INTO course_enrollments(student_user_id,course_id,active_group_id,"
            "attendance_mode,status,created_at,updated_at,created_by,updated_by) "
            "VALUES(?,?,?,'online','active',?,?,?,?) "
            "ON CONFLICT(student_user_id,course_id) DO UPDATE SET "
            "active_group_id=excluded.active_group_id,status='active',updated_at=excluded.updated_at,"
            "version=course_enrollments.version+1 RETURNING id",
            (student_id, course_id, active_group, now, now, staff["id"], staff["id"]),
        ).fetchone()
        connection.execute(
            "DELETE FROM course_group_access WHERE enrollment_id=?", (enrollment["id"],)
        )
        for group in course_groups:
            connection.execute(
                "INSERT INTO course_group_access(enrollment_id,course_id,group_id,valid_from,"
                "granted_by,reason,created_at,updated_at) VALUES(?,?,?,?,?,'staff testing',?,?)",
                (
                    enrollment["id"],
                    course_id,
                    group["group_id"],
                    now,
                    staff["id"],
                    now,
                    now,
                ),
            )
    return _account_from_row(
        connection.execute(
            "SELECT * FROM auth_accounts WHERE linked_user_id=? AND audience='student'",
            (student_id,),
        ).fetchone()
    )
