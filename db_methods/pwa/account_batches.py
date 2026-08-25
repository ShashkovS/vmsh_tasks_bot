"""Short SQLite operations for v1 Student and Family provisioning batches."""

from __future__ import annotations

import sqlite3

from helpers.consts import ONLINE_MODE, USER_TYPE


def account_logins(connection: sqlite3.Connection, *, audience: str) -> set[str]:
    return {
        str(row["username_normalized"])
        for row in connection.execute(
            "SELECT username_normalized FROM auth_accounts WHERE audience = ?",
            (audience,),
        )
    }


def student_tokens(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["token"])
        for row in connection.execute(
            "SELECT token FROM users WHERE type = ? AND token IS NOT NULL",
            (int(USER_TYPE.STUDENT),),
        )
    }


def student_for_login(
    connection: sqlite3.Connection, *, login_normalized: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT account.id AS account_id, user.id AS user_id, "
        "user.public_id AS user_public_id FROM auth_accounts AS account "
        "JOIN users AS user ON user.id = account.linked_user_id "
        "WHERE account.audience = 'student' AND account.username_normalized = ? "
        "AND account.status <> 'archived'",
        (login_normalized,),
    ).fetchone()
    return None if row is None else dict(row)


def course_for_code(
    connection: sqlite3.Connection, *, course_code: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, code, status FROM courses WHERE code = ?",
        (course_code,),
    ).fetchone()
    return None if row is None else dict(row)


def groups_for_course(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT group_id, public_id, short_code, public_name, status, sort_order "
        "FROM groups WHERE course_id = ? "
        "ORDER BY sort_order, short_code, group_id",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def enrollment_for_student_course(
    connection: sqlite3.Connection, *, student_user_id: int, course_id: int
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, status FROM course_enrollments "
        "WHERE student_user_id = ? AND course_id = ?",
        (student_user_id, course_id),
    ).fetchone()
    return None if row is None else dict(row)


def student_has_course_enrollment(
    connection: sqlite3.Connection, *, student_user_id: int
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM course_enrollments WHERE student_user_id = ? LIMIT 1",
            (student_user_id,),
        ).fetchone()
        is not None
    )


def insert_course_enrollment(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
    active_group_id: str,
    actor_user_id: int,
    now: str,
) -> tuple[int, str]:
    row = connection.execute(
        "INSERT INTO course_enrollments "
        "(student_user_id, course_id, active_group_id, "
        "attendance_mode, status, created_at, updated_at, created_by, updated_by) "
        "VALUES (?, ?, ?, 'online', 'active', ?, ?, ?, ?) RETURNING id, public_id",
        (
            student_user_id,
            course_id,
            active_group_id,
            now,
            now,
            actor_user_id,
            actor_user_id,
        ),
    ).fetchone()
    return int(row["id"]), str(row["public_id"])


def insert_imported_group_access(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    course_id: int,
    group_ids: tuple[str, ...],
    actor_user_id: int,
    now: str,
) -> None:
    connection.executemany(
        "INSERT INTO course_group_access "
        "(enrollment_id, course_id, group_id, valid_from, granted_by, reason, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'import', ?, ?)",
        [
            (enrollment_id, course_id, group_id, now, actor_user_id, now, now)
            for group_id in group_ids
        ],
    )


def insert_course_enrollment_created_event(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    course_id: int,
    active_group_id: str,
    actor_user_id: int,
    request_id: str,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO course_enrollment_events "
        "(enrollment_id, course_id, event_type, new_group_id, "
        "new_attendance_mode, new_status, actor_user_id, source, request_id, "
        "occurred_at, created_at) "
        "VALUES (?, ?, 'created', ?, 'online', 'active', ?, 'import', ?, ?, ?)",
        (
            enrollment_id,
            course_id,
            active_group_id,
            actor_user_id,
            request_id,
            now,
            now,
        ),
    )


def sync_first_course_to_legacy_user(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    active_group_id: str,
    allowed_group_ids: tuple[str, ...],
) -> None:
    connection.execute(
        "UPDATE users SET group_id = ?, allowed_groups = ? WHERE id = ?",
        (active_group_id, ";".join(allowed_group_ids), student_user_id),
    )


def available_student_logins(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["username_normalized"])
        for row in connection.execute(
            "SELECT username_normalized FROM auth_accounts "
            "WHERE audience = 'student' AND status <> 'archived'"
        )
    }


def insert_student_user(
    connection: sqlite3.Connection,
    *,
    surname: str,
    name: str,
    patronymic: str,
    token: str,
    grade: int | None,
    birth_date: str | None,
) -> tuple[int, str]:
    row = connection.execute(
        "INSERT INTO users "
        "(type, surname, name, middlename, token, online, grade, birthday) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id, public_id",
        (
            int(USER_TYPE.STUDENT),
            surname,
            name,
            patronymic or None,
            token,
            int(ONLINE_MODE.ONLINE),
            grade,
            birth_date,
        ),
    ).fetchone()
    return int(row["id"]), str(row["public_id"])


def insert_provisioned_account(
    connection: sqlite3.Connection,
    *,
    audience: str,
    username: str,
    username_normalized: str,
    display_name: str,
    credential_kind: str,
    credential_hash: str,
    credential_plaintext: str,
    linked_user_id: int | None,
    now: str,
) -> tuple[int, str]:
    row = connection.execute(
        "INSERT INTO auth_accounts "
        "(audience, username, username_normalized, "
        "username_algorithm_version, provisioning_source, display_name, "
        "credential_kind, credential_hash, provisioning_password_plaintext, "
        "linked_user_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'staff_batch', ?, ?, ?, ?, ?, 'active', ?, ?) "
        "RETURNING id, public_id",
        (
            audience,
            username,
            username_normalized,
            1 if audience == "student" else None,
            display_name,
            credential_kind,
            credential_hash,
            credential_plaintext,
            linked_user_id,
            now,
            now,
        ),
    ).fetchone()
    return int(row["id"]), str(row["public_id"])


def insert_family_emails(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    emails: tuple[str, ...],
    now: str,
) -> None:
    connection.executemany(
        "INSERT INTO family_account_emails "
        "(family_account_id, ordinal, email, email_normalized, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (family_account_id, ordinal, email, email.casefold(), now)
            for ordinal, email in enumerate(emails)
        ],
    )


def insert_family_link(
    connection: sqlite3.Connection,
    *,
    family_account_id: int,
    student_user_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO family_student_links "
        "(family_account_id, student_user_id, relationship_label, is_primary, "
        "created_at, updated_at) VALUES (?, ?, NULL, 0, ?, ?)",
        (family_account_id, student_user_id, now, now),
    )


__all__ = [
    "account_logins",
    "available_student_logins",
    "course_for_code",
    "enrollment_for_student_course",
    "groups_for_course",
    "insert_course_enrollment",
    "insert_course_enrollment_created_event",
    "insert_family_emails",
    "insert_family_link",
    "insert_imported_group_access",
    "insert_provisioned_account",
    "insert_student_user",
    "student_has_course_enrollment",
    "student_for_login",
    "student_tokens",
    "sync_first_course_to_legacy_user",
]
