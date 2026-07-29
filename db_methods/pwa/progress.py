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
               problem_scope.lesson_number,
               CASE
                   WHEN synonym_group.id IS NULL
                   THEN 'problem:' || result.problem_id
                   ELSE 'synonym:' || synonym_group.id
               END AS logical_problem_key
        FROM results AS result
        JOIN verdicts AS verdict ON verdict.id = result.verdict
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


__all__ = ["list_course_result_rows"]
