"""Direct SQLite reads for personal course progress."""

from __future__ import annotations

import sqlite3

from .effective_results import scoped_effective_results_ctes


COURSE_RESULTS_SQL = f"""
        WITH problem_scope AS MATERIALIZED (
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
            WHERE group_lesson.course_id = :course_id
              AND problem_revision.problem_id IN (
                  SELECT problem_id FROM results WHERE student_id = :student_user_id
              )
        ), requested_problem_ids AS (
            SELECT DISTINCT problem_id FROM problem_scope
        ), requested_student_ids(student_id) AS (VALUES (:student_user_id)),
        {scoped_effective_results_ctes(students=True, personal=True)}
        SELECT result.id AS result_id,
               result.problem_id,
               result.ts,
               verdict.val AS verdict_weight,
               manual.result_id IS NOT NULL AS manual_override,
               problem_scope.lesson_number,
               problem_group.logical_key AS logical_problem_key
        FROM scoped_effective_results AS result
        JOIN verdicts AS verdict ON verdict.id = result.verdict
        LEFT JOIN live_mark_cells AS manual ON manual.result_id = result.id
        JOIN problem_scope ON problem_scope.problem_id = result.problem_id
        JOIN result_problem_groups AS problem_group
          ON problem_group.problem_id = result.problem_id
        WHERE result.student_id = :student_user_id
          AND problem_scope.course_id = :course_id
        ORDER BY result.ts, result.id
        """


def list_course_result_rows(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    """Return result facts; aggregation belongs to ``models.pwa.progress``."""

    # peak-read-admission-20261019.md: scope before choosing effective results.
    rows = connection.execute(
        COURSE_RESULTS_SQL,
        {"student_user_id": student_user_id, "course_id": course_id},
    ).fetchall()
    return [dict(row) for row in rows]


def list_course_activity_rows(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    """Ledger activity survives current-result replacement (written-result-precedence.md)."""

    rows = connection.execute(
        """SELECT DISTINCT result.ts, scope.lesson_number,
                  problem_group.logical_key AS logical_problem_key
        FROM results AS result
        JOIN result_problem_groups AS problem_group
          ON problem_group.problem_id=result.problem_id
        JOIN (
          SELECT DISTINCT revision.problem_id, lesson.course_id,
                          course_lesson.lesson_number
          FROM problem_revisions revision
          JOIN content_revisions content ON content.id=revision.content_revision_id
          JOIN content_sources source ON source.id=content.source_id
          JOIN group_lessons lesson ON lesson.id=source.group_lesson_id
          JOIN course_lessons course_lesson ON course_lesson.id=lesson.course_lesson_id
          WHERE revision.problem_id IN (
            SELECT problem_id FROM results WHERE student_id=:student_user_id
          )
        ) scope ON scope.problem_id=result.problem_id
        WHERE result.student_id=:student_user_id AND scope.course_id=:course_id
        ORDER BY result.ts""",
        {"student_user_id": student_user_id, "course_id": course_id},
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
               problem_group.logical_key AS logical_problem_key
        FROM written_tasks_queue AS queue
        JOIN problems AS problem ON problem.id = queue.problem_id
        JOIN groups AS group_record
          ON group_record.group_id = problem.group_id
         AND group_record.course_id = ?
        JOIN result_problem_groups AS problem_group
          ON problem_group.problem_id=queue.problem_id
        WHERE queue.student_id = ?
          AND queue.problem_id > 0
        ORDER BY queue.ts, queue.id
        """,
        (course_id, student_user_id),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "list_course_activity_rows",
    "list_course_pending_review_rows",
    "list_course_result_rows",
]
