"""Direct SQLite operations for the existing oral-result ledger."""

from __future__ import annotations

import sqlite3


def oral_lesson(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT lesson.id AS group_lesson_id, lesson.group_id, "
        "course_lesson.lesson_number, course.public_id AS course_public_id, "
        "group_record.public_id AS group_public_id "
        "FROM group_lessons AS lesson "
        "JOIN course_lessons AS course_lesson "
        "ON course_lesson.id = lesson.course_lesson_id "
        "JOIN courses AS course ON course.id = lesson.course_id "
        "JOIN groups AS group_record ON group_record.course_id = lesson.course_id "
        "AND group_record.group_id = lesson.group_id "
        "WHERE lesson.public_id = ? AND lesson.status = 'active' LIMIT 1",
        (group_lesson_public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def online_students(
    connection: sqlite3.Connection,
    *,
    course_public_id: str,
    group_public_id: str,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT student.id AS student_user_id, student.public_id, student.surname, "
        "student.name, student.middlename "
        "FROM course_enrollments AS enrollment "
        "JOIN courses AS course ON course.id = enrollment.course_id "
        "JOIN groups AS group_record ON group_record.course_id = enrollment.course_id "
        "AND group_record.group_id = enrollment.active_group_id "
        "JOIN users AS student ON student.id = enrollment.student_user_id "
        "WHERE course.public_id = ? AND group_record.public_id = ? "
        "AND enrollment.status = 'active' AND enrollment.attendance_mode = 'online' "
        "AND student.public_id IS NOT NULL "
        "ORDER BY student.surname COLLATE NOCASE, student.name COLLATE NOCASE, student.id",
        (course_public_id, group_public_id),
    ).fetchall()
    return [dict(row) for row in rows]


def oral_problems(
    connection: sqlite3.Connection,
    *,
    group_lesson_id: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT problem.id AS problem_id, problem.public_id, "
        "revision.display_number, revision.title "
        "FROM lesson_publications AS publication "
        "JOIN problem_revisions AS revision ON revision.content_revision_id = publication.revision_id "
        "JOIN problems AS problem ON problem.id = revision.problem_id "
        "WHERE publication.group_lesson_id = ? AND publication.kind = 'condition' "
        "AND publication.state = 'published' AND revision.problem_type IN (3, 4) "
        "AND problem.public_id IS NOT NULL "
        "ORDER BY revision.source_ordinal, revision.source_item, problem.id",
        (group_lesson_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def online_student(
    connection: sqlite3.Connection,
    *,
    student_public_id: str,
    course_public_id: str,
    group_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT student.id AS student_user_id, student.public_id, "
        "account.public_id AS account_public_id "
        "FROM course_enrollments AS enrollment "
        "JOIN courses AS course ON course.id = enrollment.course_id "
        "JOIN groups AS group_record ON group_record.course_id = enrollment.course_id "
        "AND group_record.group_id = enrollment.active_group_id "
        "JOIN users AS student ON student.id = enrollment.student_user_id "
        "JOIN auth_accounts AS account ON account.linked_user_id = student.id "
        "AND account.audience = 'student' AND account.status = 'active' "
        "WHERE student.public_id = ? AND course.public_id = ? "
        "AND group_record.public_id = ? AND enrollment.status = 'active' "
        "AND enrollment.attendance_mode = 'online' LIMIT 1",
        (student_public_id, course_public_id, group_public_id),
    ).fetchone()
    return None if row is None else dict(row)


def existing_conversation(
    connection: sqlite3.Connection,
    *,
    idempotency_key: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, student_id, teacher_id, lesson, group_id "
        "FROM zoom_conversation WHERE pwa_idempotency_key = ? LIMIT 1",
        (idempotency_key,),
    ).fetchone()
    return None if row is None else dict(row)


def conversation_marks(
    connection: sqlite3.Connection,
    *,
    conversation_id: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT problem.public_id, result.verdict FROM results AS result "
        "JOIN problems AS problem ON problem.id = result.problem_id "
        "WHERE result.zoom_conversation_id = ? ORDER BY problem.public_id",
        (conversation_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def conversation_reaction_id(
    connection: sqlite3.Connection,
    *,
    conversation_id: int,
) -> int | None:
    row = connection.execute(
        "SELECT reaction_id FROM reactions WHERE zoom_conversation_id = ? "
        "AND reaction_type_id = 300 ORDER BY id LIMIT 1",
        (conversation_id,),
    ).fetchone()
    return None if row is None else int(row["reaction_id"])


def insert_conversation(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    teacher_user_id: int,
    lesson_number: int,
    group_id: str,
    idempotency_key: str,
    now: str,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO zoom_conversation "
            "(ts, student_id, teacher_id, lesson, group_id, pwa_idempotency_key) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (
                now,
                student_user_id,
                teacher_user_id,
                lesson_number,
                group_id,
                idempotency_key,
            ),
        ).fetchone()["id"]
    )


def insert_result(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    teacher_user_id: int,
    problem_id: int,
    lesson_number: int,
    group_id: str,
    verdict: int,
    conversation_id: int,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO results "
        "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, "
        "answer, res_type, zoom_conversation_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 3, ?)",
        (
            student_user_id,
            problem_id,
            group_id,
            lesson_number,
            teacher_user_id,
            now,
            verdict,
            conversation_id,
        ),
    )


def reject_prior_positive_oral_result(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    problem_id: int,
) -> None:
    connection.execute(
        "UPDATE results SET verdict = -2 WHERE student_id = ? AND problem_id = ? "
        "AND res_type IN (3, 4) AND verdict > 0",
        (student_user_id, problem_id),
    )


def remove_written_queue_entry(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    problem_id: int,
) -> None:
    connection.execute(
        "DELETE FROM written_tasks_queue WHERE student_id = ? AND problem_id = ?",
        (student_user_id, problem_id),
    )


def insert_teacher_reaction(
    connection: sqlite3.Connection,
    *,
    conversation_id: int,
    reaction_id: int,
    now: str,
) -> bool:
    cursor = connection.execute(
        "INSERT INTO reactions "
        "(ts, zoom_conversation_id, reaction_id, reaction_type_id) "
        "SELECT ?, ?, reaction_id, reaction_type_id FROM reaction_enum "
        "WHERE reaction_id = ? AND reaction_type_id = 300",
        (now, conversation_id, reaction_id),
    )
    return cursor.rowcount == 1


__all__ = [
    "conversation_marks",
    "conversation_reaction_id",
    "existing_conversation",
    "insert_conversation",
    "insert_result",
    "insert_teacher_reaction",
    "online_student",
    "online_students",
    "oral_lesson",
    "oral_problems",
    "reject_prior_positive_oral_result",
    "remove_written_queue_entry",
]
