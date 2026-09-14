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


def list_print_course_pupils(
    connection: sqlite3.Connection, course_id: int
) -> list[dict]:
    """Return the active course roster with the legacy mail identity fields."""

    return [
        dict(row)
        for row in connection.execute(
            """
        SELECT student.id, account.username AS login, student.surname, student.name,
               enrollment.active_group_id AS group_id,
               group_record.short_code AS level
        FROM course_enrollments AS enrollment
        JOIN users AS student
          ON student.id = enrollment.student_user_id
         AND student.type = 1
        JOIN groups AS group_record
          ON group_record.course_id = enrollment.course_id
         AND group_record.group_id = enrollment.active_group_id
        LEFT JOIN auth_accounts AS account
          ON account.linked_user_id = student.id
         AND account.audience = 'student'
        WHERE enrollment.course_id = ?
          AND enrollment.status = 'active'
        ORDER BY student.surname, student.name, student.id
        """,
            (course_id,),
        ).fetchall()
    ]


def list_print_lesson_problems(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    group_ids: tuple[str, ...],
    lesson: int,
) -> list[dict]:
    """Return current lesson columns and their analytics logical keys."""

    if not group_ids:
        return []
    placeholders = ", ".join("?" for _ in group_ids)
    rows = connection.execute(
        f"""
        SELECT problem.id AS problem_id,
               problem.lesson AS lesson_number,
               problem.group_id,
               group_record.short_code AS level,
               group_record.sort_order AS group_sort_order,
               problem.prob,
               problem.item,
               problem.prob_type AS problem_type,
               CASE
                   WHEN synonym_group.id IS NOT NULL
                   THEN 'synonym:' || synonym_group.id
                   WHEN trim(problem.synonyms) <> ''
                   THEN 'legacy:' || problem.synonyms
                   ELSE 'problem:' || problem.id
               END AS logical_problem_key,
               coalesce(complexity.for_weak, 0.5) AS for_weak,
               coalesce(complexity.for_strong, 0.5) AS for_strong
        FROM problems AS problem
        JOIN groups AS group_record
          ON group_record.group_id = problem.group_id
         AND group_record.course_id = ?
        LEFT JOIN problem_synonym_members AS synonym_member
          ON synonym_member.problem_id = problem.id
         AND synonym_member.removed_at IS NULL
        LEFT JOIN problem_synonym_groups AS synonym_group
          ON synonym_group.id = synonym_member.synonym_group_id
         AND synonym_group.status = 'active'
        LEFT JOIN problem_complexity AS complexity
          ON complexity.synonyms = problem.synonyms
        WHERE problem.lesson = ?
          AND problem.group_id IN ({placeholders})
          AND problem.prob > 0
        ORDER BY group_record.sort_order, problem.prob, problem.item, problem.id
        """,
        (course_id, lesson, *group_ids),
    ).fetchall()
    return [dict(row) for row in rows]


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
        WITH target_problem AS (
            SELECT problem.id, problem.lesson, problem.group_id, problem.synonyms
            FROM problems AS problem
            WHERE problem.lesson = ?
              AND problem.group_id IN ({placeholders})
        ),
        logical_member AS (
            SELECT target.id AS target_problem_id,
                   target.id AS member_problem_id
            FROM target_problem AS target
            UNION
            SELECT target.id,
                   peer.problem_id
            FROM target_problem AS target
            JOIN problem_synonym_members AS own
              ON own.problem_id = target.id
             AND own.removed_at IS NULL
            JOIN problem_synonym_groups AS synonym_group
              ON synonym_group.id = own.synonym_group_id
             AND synonym_group.status = 'active'
            JOIN problem_synonym_members AS peer
              ON peer.synonym_group_id = synonym_group.id
             AND peer.removed_at IS NULL
            UNION
            SELECT target.id,
                   legacy_peer.id
            FROM target_problem AS target
            JOIN groups AS target_group
              ON target_group.group_id = target.group_id
            JOIN problems AS legacy_peer
              ON legacy_peer.lesson = target.lesson
             AND instr(
                 ';' || target.synonyms || ';',
                 ';' || cast(legacy_peer.id AS text) || ';'
             ) > 0
            JOIN groups AS legacy_group
              ON legacy_group.group_id = legacy_peer.group_id
             AND legacy_group.course_id = target_group.course_id
            WHERE trim(target.synonyms) <> ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM problem_synonym_members AS current_member
                  JOIN problem_synonym_groups AS current_group
                    ON current_group.id = current_member.synonym_group_id
                   AND current_group.status = 'active'
                  WHERE current_member.problem_id = target.id
                    AND current_member.removed_at IS NULL
              )
        )
        SELECT result.student_id,
               logical_member.target_problem_id AS syn_problem_id,
               max(verdict.val) AS max_verdict
        FROM logical_member
        JOIN {source} AS result
          ON result.problem_id = logical_member.member_problem_id
        JOIN verdicts AS verdict ON verdict.id = result.verdict
        JOIN course_enrollments AS enrollment
          ON enrollment.student_user_id = result.student_id
        JOIN classroom_assignments AS assignment
          ON assignment.course_enrollment_id = enrollment.id
         AND assignment.plan_id = ?
         AND assignment.status = 'assigned'
        GROUP BY result.student_id, logical_member.target_problem_id
        ORDER BY result.student_id, logical_member.target_problem_id
        """,
        (lesson, *group_ids, plan_id),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "list_print_course_pupils",
    "list_print_events",
    "list_print_identities",
    "list_print_lesson_problems",
    "list_print_previous_problems",
    "list_print_previous_results",
]
