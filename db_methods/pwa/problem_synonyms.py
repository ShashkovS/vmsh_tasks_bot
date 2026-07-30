"""Small SQLite operations for logical problem synonyms.

Storage shape: ``vmshpwa/dev/development-plan/02-data-model.md``.
"""

from __future__ import annotations

import sqlite3


def _problem_rows(
    connection: sqlite3.Connection, where: str, parameters: tuple[object, ...]
) -> list[dict[str, object]]:
    rows = connection.execute(
        f"""
        WITH latest AS (
            SELECT problem.id AS problem_id,
                   problem.public_id AS problem_public_id,
                   problem.prob AS problem_number,
                   problem.item AS problem_item,
                   revision.title,
                   revision.normalized_title,
                   revision.problem_type,
                   revision.answer_type,
                   group_lesson.id AS group_lesson_id,
                   group_lesson.public_id AS group_lesson_public_id,
                   course_lesson.id AS course_lesson_id,
                   course_lesson.public_id AS course_lesson_public_id,
                   course_lesson.lesson_number,
                   course.public_id AS course_public_id,
                   course.name AS course_name,
                   group_record.public_id AS group_public_id,
                   group_record.public_name AS group_name,
                   group_record.short_code AS group_code,
                   row_number() OVER (
                       PARTITION BY problem.id
                       ORDER BY content_revision.revision_number DESC, revision.id DESC
                   ) AS position
            FROM problems AS problem
            JOIN problem_revisions AS revision ON revision.problem_id = problem.id
            JOIN content_revisions AS content_revision
              ON content_revision.id = revision.content_revision_id
            JOIN content_sources AS source
              ON source.id = content_revision.source_id
             AND source.kind = 'condition'
             AND source.archived_at IS NULL
            JOIN group_lessons AS group_lesson ON group_lesson.id = source.group_lesson_id
            JOIN course_lessons AS course_lesson
              ON course_lesson.id = group_lesson.course_lesson_id
            JOIN courses AS course ON course.id = course_lesson.course_id
            JOIN groups AS group_record ON group_record.group_id = group_lesson.group_id
            WHERE {where}
        )
        SELECT latest.*,
               synonym.public_id AS synonym_public_id,
               synonym.display_title AS synonym_display_title,
               synonym.status AS synonym_status,
               synonym.version AS synonym_version,
               member.id AS synonym_member_id,
               member.membership_version,
               (SELECT count(*) FROM test_attempts AS attempt
                WHERE attempt.problem_id = latest.problem_id)
               +
               (SELECT count(*)
                FROM submission_entries AS entry
                JOIN submission_threads AS thread ON thread.id = entry.thread_id
                WHERE thread.problem_id = latest.problem_id
                  AND entry.author_kind = 'student'
                  AND entry.state IN ('submitted', 'locked')) AS submission_count,
               (SELECT count(DISTINCT evidence.review_id)
                FROM submission_review_evidence_entries AS evidence
                WHERE evidence.problem_id = latest.problem_id) AS review_count
        FROM latest
        LEFT JOIN problem_synonym_members AS member
          ON member.problem_id = latest.problem_id AND member.removed_at IS NULL
        LEFT JOIN problem_synonym_groups AS synonym
          ON synonym.id = member.synonym_group_id
        WHERE latest.position = 1
        ORDER BY latest.group_name, latest.problem_id
        """,
        parameters,
    ).fetchall()
    return [dict(row) for row in rows]


def find_problems(
    connection: sqlite3.Connection, public_ids: tuple[str, ...]
) -> list[dict[str, object]]:
    if not public_ids:
        return []
    placeholders = ",".join("?" for _value in public_ids)
    return _problem_rows(
        connection,
        f"problem.public_id IN ({placeholders})",
        public_ids,
    )


def list_course_lesson_problems(
    connection: sqlite3.Connection, *, course_lesson_public_id: str
) -> list[dict[str, object]]:
    return _problem_rows(
        connection,
        "course_lesson.public_id = ?",
        (course_lesson_public_id,),
    )


def course_lesson_exists(
    connection: sqlite3.Connection, *, course_lesson_public_id: str
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM course_lessons WHERE public_id = ?",
            (course_lesson_public_id,),
        ).fetchone()
        is not None
    )


def find_synonym_group(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM problem_synonym_groups WHERE public_id = ?", (public_id,)
    ).fetchone()
    return None if row is None else dict(row)


def list_synonym_problem_ids(
    connection: sqlite3.Connection, *, synonym_group_id: int
) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT problem.public_id FROM problem_synonym_members AS member "
        "JOIN problems AS problem ON problem.id = member.problem_id "
        "WHERE member.synonym_group_id = ? AND member.removed_at IS NULL "
        "ORDER BY member.id",
        (synonym_group_id,),
    ).fetchall()
    return tuple(str(row["public_id"]) for row in rows)


def insert_synonym_group(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    course_lesson_id: int,
    group_key: str,
    display_title: str,
    actor_user_id: int,
    now: str,
) -> int:
    cursor = connection.execute(
        "INSERT INTO problem_synonym_groups "
        "(public_id, course_lesson_id, group_key, display_title, status, "
        "created_by_user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'active', ?, ?, ?)",
        (
            public_id,
            course_lesson_id,
            group_key,
            display_title,
            actor_user_id,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def insert_synonym_member(
    connection: sqlite3.Connection,
    *,
    synonym_group_id: int,
    group_lesson_id: int,
    problem_id: int,
    actor_user_id: int,
    now: str,
) -> None:
    row = connection.execute(
        "SELECT max(membership_version) AS value FROM problem_synonym_members "
        "WHERE synonym_group_id = ? AND problem_id = ?",
        (synonym_group_id, problem_id),
    ).fetchone()
    version = 1 if row["value"] is None else int(row["value"]) + 1
    connection.execute(
        "INSERT INTO problem_synonym_members "
        "(synonym_group_id, group_lesson_id, problem_id, added_by_user_id, "
        "added_at, membership_version) VALUES (?, ?, ?, ?, ?, ?)",
        (synonym_group_id, group_lesson_id, problem_id, actor_user_id, now, version),
    )


def remove_synonym_member(
    connection: sqlite3.Connection,
    *,
    member_id: int,
    actor_user_id: int,
    reason: str,
    now: str,
) -> None:
    connection.execute(
        "UPDATE problem_synonym_members SET removed_by_user_id = ?, removed_at = ?, "
        "reason = ? WHERE id = ? AND removed_at IS NULL",
        (actor_user_id, now, reason, member_id),
    )


def update_synonym_group(
    connection: sqlite3.Connection,
    *,
    group_id: int,
    expected_version: int,
    status: str,
    now: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE problem_synonym_groups SET status = ?, updated_at = ?, "
        "version = version + 1 WHERE id = ? AND version = ?",
        (status, now, group_id, expected_version),
    )
    return cursor.rowcount == 1


__all__ = [
    "course_lesson_exists",
    "find_problems",
    "find_synonym_group",
    "insert_synonym_group",
    "insert_synonym_member",
    "list_course_lesson_problems",
    "list_synonym_problem_ids",
    "remove_synonym_member",
    "update_synonym_group",
]
