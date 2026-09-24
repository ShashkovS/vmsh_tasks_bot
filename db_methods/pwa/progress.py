"""Direct SQLite reads for personal course progress."""

from __future__ import annotations

import sqlite3


def list_course_result_rows(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    """Return result facts; aggregation belongs to ``models.pwa.progress``."""

    rows = connection.execute(
        """
        WITH problem_scope AS (
            SELECT DISTINCT problem_revision.problem_id,
                            group_lesson.course_id,
                            course_lesson.lesson_number
            FROM problem_revisions AS problem_revision
            JOIN content_revisions AS revision
              ON revision.id = problem_revision.content_revision_id
            JOIN content_sources AS source ON source.id = revision.source_id
            JOIN group_lessons AS group_lesson ON group_lesson.id = source.group_lesson_id
            JOIN course_lessons AS course_lesson
              ON course_lesson.id = group_lesson.course_lesson_id
        )
        SELECT result.id AS result_id,
               result.problem_id,
               result.ts,
               verdict.val AS verdict_weight,
               manual.result_id IS NOT NULL AS manual_override,
               problem_scope.lesson_number,
               CASE
                   WHEN synonym_group.id IS NULL
                   THEN 'problem:' || result.problem_id
                   ELSE 'synonym:' || synonym_group.id
               END AS logical_problem_key
        FROM effective_results AS result
        JOIN verdicts AS verdict ON verdict.id = result.verdict
        LEFT JOIN live_mark_cells AS manual ON manual.result_id = result.id
        JOIN problem_scope ON problem_scope.problem_id = result.problem_id
        LEFT JOIN problem_synonym_members AS synonym_member
          ON synonym_member.problem_id = result.problem_id
         AND synonym_member.removed_at IS NULL
        LEFT JOIN problem_synonym_groups AS synonym_group
          ON synonym_group.id = synonym_member.synonym_group_id
         AND synonym_group.status = 'active'
        WHERE result.student_id = ?
          AND problem_scope.course_id = ?
        ORDER BY result.ts, result.id
        """,
        (student_user_id, course_id),
    ).fetchall()
    return [dict(row) for row in rows]


def list_course_pending_review_rows(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    """Return the student's current written-review queue within one course."""

    rows = connection.execute(
        """
        SELECT queue.problem_id,
               queue.ts,
               problem.lesson AS lesson_number,
               CASE
                   WHEN synonym_group.id IS NULL
                   THEN 'problem:' || queue.problem_id
                   ELSE 'synonym:' || synonym_group.id
               END AS logical_problem_key
        FROM written_tasks_queue AS queue
        JOIN problems AS problem ON problem.id = queue.problem_id
        JOIN groups AS group_record
          ON group_record.group_id = problem.group_id
         AND group_record.course_id = ?
        LEFT JOIN problem_synonym_members AS synonym_member
          ON synonym_member.problem_id = queue.problem_id
         AND synonym_member.removed_at IS NULL
        LEFT JOIN problem_synonym_groups AS synonym_group
          ON synonym_group.id = synonym_member.synonym_group_id
         AND synonym_group.status = 'active'
        WHERE queue.student_id = ?
          AND queue.problem_id > 0
        ORDER BY queue.ts, queue.id
        """,
        (course_id, student_user_id),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = ["list_course_pending_review_rows", "list_course_result_rows"]
