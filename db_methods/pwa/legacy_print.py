"""Read-only legacy print queries; see docs/printing/legacy-api.md."""

import sqlite3


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
