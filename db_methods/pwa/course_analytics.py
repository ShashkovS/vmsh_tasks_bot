"""Direct SQLite reads and writes for course analytics snapshots."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping


def list_course_problem_rows(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT problem.id AS problem_id,
               problem.lesson AS lesson_number,
               problem.group_id,
               coalesce(group_record.sort_order, 0) AS group_sort_order,
               CASE
                   WHEN synonym_group.id IS NOT NULL THEN 'synonym:' || synonym_group.id
                   WHEN trim(problem.synonyms) <> '' THEN 'legacy:' || problem.synonyms
                   ELSE 'problem:' || problem.id
               END AS logical_problem_key,
               coalesce(complexity.for_weak, 0.5) AS for_weak,
               coalesce(complexity.for_strong, 0.5) AS for_strong
        FROM problems AS problem
        JOIN groups AS group_record ON group_record.group_id = problem.group_id
        LEFT JOIN problem_synonym_members AS synonym_member
          ON synonym_member.problem_id = problem.id AND synonym_member.removed_at IS NULL
        LEFT JOIN problem_synonym_groups AS synonym_group
          ON synonym_group.id = synonym_member.synonym_group_id
         AND synonym_group.status = 'active'
        LEFT JOIN problem_complexity AS complexity
          ON complexity.synonyms = problem.synonyms
        WHERE group_record.course_id = ?
          AND problem.lesson > 0
          AND problem.prob > 0
        ORDER BY problem.lesson, group_record.sort_order, problem.group_id,
                 problem.prob, problem.item, problem.id
        """,
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_course_result_rows(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT result.id AS result_id,
               result.student_id AS student_user_id,
               result.ts,
               verdict.val AS verdict_weight,
               problem.id AS problem_id,
               problem.lesson AS lesson_number,
               problem.group_id,
               problem.prob_type AS problem_type,
               CASE
                   WHEN synonym_group.id IS NOT NULL THEN 'synonym:' || synonym_group.id
                   WHEN trim(problem.synonyms) <> '' THEN 'legacy:' || problem.synonyms
                   ELSE 'problem:' || problem.id
               END AS logical_problem_key
        FROM results AS result
        JOIN verdicts AS verdict ON verdict.id = result.verdict
        JOIN problems AS problem ON problem.id = result.problem_id
        JOIN groups AS group_record ON group_record.group_id = problem.group_id
        LEFT JOIN problem_synonym_members AS synonym_member
          ON synonym_member.problem_id = problem.id AND synonym_member.removed_at IS NULL
        LEFT JOIN problem_synonym_groups AS synonym_group
          ON synonym_group.id = synonym_member.synonym_group_id
         AND synonym_group.status = 'active'
        WHERE group_record.course_id = ?
          AND problem.lesson > 0
          AND problem.prob > 0
        ORDER BY result.student_id, problem.lesson, result.ts, result.id
        """,
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_course_group_access_rows(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT enrollment.student_user_id, access.group_id "
        "FROM course_group_access AS access "
        "JOIN course_enrollments AS enrollment ON enrollment.id = access.enrollment_id "
        "WHERE enrollment.course_id = ? AND enrollment.status = 'active' "
        "AND access.valid_to IS NULL "
        "ORDER BY enrollment.student_user_id, access.group_id",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_completed_course_metrics(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    course_id: int,
    algorithm: str,
    algorithm_version: str,
    input_through_result_id: int,
    completed_at: str,
    metrics: Iterable[Mapping[str, object]],
) -> int:
    """Persist a complete run in one transaction and return its database id."""

    metrics = list(metrics)
    with connection:
        run_id = connection.execute(
            "INSERT INTO analytics_runs "
            "(public_id, course_id, algorithm, algorithm_version, "
            "input_through_result_id, state, started_at, completed_at, diagnostics_json) "
            "VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?) RETURNING id",
            (
                public_id,
                course_id,
                algorithm,
                algorithm_version,
                input_through_result_id,
                completed_at,
                completed_at,
                json.dumps([], separators=(",", ":")),
            ),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO student_lesson_metrics "
            "(run_id, student_user_id, lesson_number, group_id, simple_strength, "
            "complex_strength, max_complex_strength, solved_items, total_items) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    int(metric["student_user_id"]),
                    int(metric["lesson_number"]),
                    str(metric["group_id"]),
                    float(metric["simple_strength"]),
                    float(metric["complex_strength"]),
                    float(metric["max_complex_strength"]),
                    int(metric["solved_items"]),
                    int(metric["total_items"]),
                )
                for metric in metrics
            ],
        )
    return int(run_id)


def latest_student_course_metrics(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    student_user_id: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT run.public_id AS run_public_id,
               run.algorithm,
               run.algorithm_version,
               run.completed_at,
               metric.lesson_number,
               group_record.public_id AS group_public_id,
               group_record.short_code AS group_short_code,
               metric.simple_strength,
               metric.complex_strength,
               metric.max_complex_strength,
               metric.solved_items,
               metric.total_items
        FROM student_lesson_metrics AS metric
        JOIN analytics_runs AS run ON run.id = metric.run_id
        JOIN groups AS group_record ON group_record.group_id = metric.group_id
        WHERE metric.student_user_id = ?
          AND run.id = (
              SELECT id FROM analytics_runs
              WHERE course_id = ? AND state = 'completed'
              ORDER BY completed_at DESC, id DESC LIMIT 1
          )
        ORDER BY metric.lesson_number
        """,
        (student_user_id, course_id),
    ).fetchall()
    return [dict(row) for row in rows]


def find_latest_completed_course_run(
    connection: sqlite3.Connection, *, course_id: int
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, algorithm, algorithm_version, "
        "input_through_result_id, completed_at FROM analytics_runs "
        "WHERE course_id = ? AND state = 'completed' "
        "ORDER BY completed_at DESC, id DESC LIMIT 1",
        (course_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_course_run_metrics(
    connection: sqlite3.Connection, *, run_id: int
) -> list[dict[str, object]]:
    """Return one completed snapshot; aggregation belongs to the domain layer."""
    rows = connection.execute(
        """
        SELECT metric.student_user_id,
               metric.lesson_number,
               group_record.public_id AS group_public_id,
               group_record.short_code AS group_code,
               group_record.public_name AS group_name,
               group_record.color_key,
               group_record.sort_order AS group_sort_order,
               metric.simple_strength,
               metric.complex_strength,
               metric.max_complex_strength,
               metric.solved_items,
               metric.total_items
        FROM student_lesson_metrics AS metric
        JOIN groups AS group_record ON group_record.group_id = metric.group_id
        WHERE metric.run_id = ?
        ORDER BY metric.lesson_number, group_record.sort_order,
                 group_record.group_id, metric.student_user_id
        """,
        (run_id,),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "find_latest_completed_course_run",
    "latest_student_course_metrics",
    "list_course_run_metrics",
    "list_course_group_access_rows",
    "list_course_problem_rows",
    "list_course_result_rows",
    "save_completed_course_metrics",
]
