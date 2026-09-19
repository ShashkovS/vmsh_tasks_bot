"""Direct SQLite access for course achievement facts and earned rows."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping


def list_course_achievement_facts(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    results = connection.execute(
        """
        SELECT 'result' AS source,
               result.id AS event_id,
               result.ts,
               problem.lesson AS lesson_number,
               verdict.val >= 0.8 AS accepted,
               (problem.prob_type = 2 OR result.res_type = 2) AS written
        FROM results AS result
        JOIN verdicts AS verdict ON verdict.id = result.verdict
        JOIN problems AS problem ON problem.id = result.problem_id
        JOIN groups AS group_record ON group_record.group_id = problem.group_id
        WHERE result.student_id = ?
          AND group_record.course_id = ?
          AND problem.lesson > 0
          AND problem.prob > 0
        """,
        (student_user_id, course_id),
    ).fetchall()
    queued = connection.execute(
        """
        SELECT 'written_queue' AS source,
               queue.id AS event_id,
               queue.ts,
               problem.lesson AS lesson_number,
               0 AS accepted,
               1 AS written
        FROM written_tasks_queue AS queue
        JOIN problems AS problem ON problem.id = queue.problem_id
        JOIN groups AS group_record ON group_record.group_id = problem.group_id
        WHERE queue.student_id = ?
          AND queue.problem_id > 0
          AND group_record.course_id = ?
        """,
        (student_user_id, course_id),
    ).fetchall()
    return [dict(row) for row in (*results, *queued)]


def list_course_student_ids(
    connection: sqlite3.Connection, *, course_id: int
) -> list[int]:
    rows = connection.execute(
        "SELECT DISTINCT student_user_id FROM course_enrollments "
        "WHERE course_id = ? ORDER BY student_user_id",
        (course_id,),
    ).fetchall()
    return [int(row["student_user_id"]) for row in rows]


def save_course_achievements(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
    achievements: Iterable[Mapping[str, object]],
) -> None:
    with connection:
        for achievement in achievements:
            connection.execute(
                """
                INSERT INTO user_achievements
                    (definition_id, user_id, course_id, earned_at, evidence_json)
                SELECT id, ?, ?, ?, ?
                FROM achievement_definitions
                WHERE code = ? AND is_active = 1
                ON CONFLICT (definition_id, user_id, course_id) DO UPDATE SET
                    earned_at = excluded.earned_at,
                    evidence_json = excluded.evidence_json
                WHERE excluded.earned_at < user_achievements.earned_at
                """,
                (
                    student_user_id,
                    course_id,
                    str(achievement["earned_at"]),
                    json.dumps(achievement["evidence"], separators=(",", ":")),
                    str(achievement["code"]),
                ),
            )


def list_student_course_achievements(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    course_id: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT definition.code, earned.earned_at "
        "FROM user_achievements AS earned "
        "JOIN achievement_definitions AS definition "
        "ON definition.id = earned.definition_id "
        "WHERE earned.user_id = ? AND earned.course_id = ? "
        "AND definition.is_active = 1 "
        "ORDER BY earned.earned_at, definition.id",
        (student_user_id, course_id),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "list_course_achievement_facts",
    "list_course_student_ids",
    "list_student_course_achievements",
    "save_course_achievements",
]
