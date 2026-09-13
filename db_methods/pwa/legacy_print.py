"""Read-only legacy print queries; see docs/printing/legacy-api.md."""

import sqlite3

from db_methods.pwa.effective_results import result_source


def list_print_events(connection: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            """
        SELECT event.public_id AS event_id, event.name, event.starts_at,
               event.status, plan.public_id AS plan_id, plan.version AS plan_version,
               group_concat(DISTINCT lesson.lesson_number) AS lesson_numbers
        FROM in_person_events event
        LEFT JOIN classroom_assignment_plans plan
          ON plan.in_person_event_id = event.id AND plan.state = 'confirmed'
        LEFT JOIN in_person_event_group_lessons event_lesson
          ON event_lesson.in_person_event_id = event.id
        LEFT JOIN group_lessons group_lesson
          ON group_lesson.id = event_lesson.group_lesson_id
        LEFT JOIN course_lessons lesson
          ON lesson.id = group_lesson.course_lesson_id
        WHERE event.status != 'cancelled'
          AND event.season_id = (
              SELECT id FROM seasons WHERE status = 'active'
              ORDER BY starts_on DESC, id DESC LIMIT 1
          )
        GROUP BY event.id, plan.id
        ORDER BY event.starts_at DESC, event.id DESC LIMIT 100
        """
        ).fetchall()
    ]


def list_print_identities(connection: sqlite3.Connection, plan_id: int) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            """
        SELECT enrollment.id AS enrollment_id, account.username
        FROM classroom_assignments assignment
        JOIN course_enrollments enrollment
          ON enrollment.id = assignment.course_enrollment_id
        LEFT JOIN auth_accounts account
          ON account.linked_user_id = enrollment.student_user_id
         AND account.audience = 'student'
        WHERE assignment.plan_id = ?
        """,
            (plan_id,),
        ).fetchall()
    ]


def list_print_previous_problems(
    connection: sqlite3.Connection,
    *,
    group_ids: tuple[str, ...],
    lesson: int,
) -> list[dict]:
    """Return the legacy problem columns used by ``a13``."""

    if not group_ids:
        return []
    placeholders = ", ".join("?" for _ in group_ids)
    rows = connection.execute(
        f"""
        SELECT problem.id, problem.lesson, problem.group_id, problem.prob,
               problem.item,
               problem.prob || '<br>' || problem.item AS full_prob,
               problem.prob_type
        FROM problems AS problem
        WHERE problem.lesson = ?
          AND problem.group_id IN ({placeholders})
        ORDER BY problem.group_id, problem.prob, problem.item, problem.id
        """,
        (lesson, *group_ids),
    ).fetchall()
    return [dict(row) for row in rows]


def list_print_previous_results(
    connection: sqlite3.Connection,
    *,
    plan_id: int,
    group_ids: tuple[str, ...],
    lesson: int,
) -> list[dict]:
    """Project roster results onto the previous lesson's synonym columns."""

    if not group_ids:
        return []
    placeholders = ", ".join("?" for _ in group_ids)
    source = result_source(connection)
    rows = connection.execute(
        f"""
        SELECT result.student_id,
               target_problem.id AS syn_problem_id,
               max(verdict.val) AS max_verdict
        FROM {source} AS result
        JOIN problems AS source_problem ON source_problem.id = result.problem_id
        JOIN problems AS target_problem
          ON target_problem.synonyms = source_problem.synonyms
        JOIN verdicts AS verdict ON verdict.id = result.verdict
        JOIN course_enrollments AS enrollment
          ON enrollment.student_user_id = result.student_id
        JOIN classroom_assignments AS assignment
          ON assignment.course_enrollment_id = enrollment.id
         AND assignment.plan_id = ?
         AND assignment.status = 'assigned'
        WHERE target_problem.lesson = ?
          AND target_problem.group_id IN ({placeholders})
        GROUP BY result.student_id, target_problem.id
        ORDER BY result.student_id, target_problem.id
        """,
        (plan_id, lesson, *group_ids),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "list_print_events",
    "list_print_identities",
    "list_print_previous_problems",
    "list_print_previous_results",
]
