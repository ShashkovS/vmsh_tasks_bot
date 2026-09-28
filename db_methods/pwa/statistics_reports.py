"""Report facts; see vmshpwa/docs/lesson-statistics.md, Staff reporting.

The result ledger counts work, while course_facts supplies current credit.
submission_reviews references results one-to-one: never union both ledgers.
"""

from db_methods.pwa.lesson_statistics import course_facts


def report_facts(connection, course_id):
    problems, results, submitted = course_facts(connection, course_id)
    reviews = [
        dict(row)
        for row in connection.execute(
            """
        SELECT r.id AS result_id, r.student_id AS student_user_id, r.problem_id
        FROM results r JOIN problems p ON p.id=r.problem_id
        JOIN groups g ON g.group_id=p.group_id
        JOIN users u ON u.id=r.student_id AND u.type IN (1,-2)
        WHERE g.course_id=? AND r.res_type=2
    """,
            (course_id,),
        )
    ]
    pending = [
        dict(row)
        for row in connection.execute(
            """
        SELECT q.student_id AS student_user_id, q.problem_id
        FROM written_tasks_queue q JOIN problems p ON p.id=q.problem_id
        JOIN groups g ON g.group_id=p.group_id
        JOIN users u ON u.id=q.student_id AND u.type IN (1,-2)
        WHERE g.course_id=?
        UNION
        SELECT t.student_user_id, t.problem_id
        FROM submission_threads t JOIN problems p ON p.id=t.problem_id
        JOIN groups g ON g.group_id=p.group_id
        JOIN users u ON u.id=t.student_user_id AND u.type IN (1,-2)
        JOIN submission_entries e ON e.thread_id=t.id
        WHERE g.course_id=? AND e.author_kind='student'
          AND e.entry_kind='submission' AND e.state IN ('submitted','locked')
          AND NOT EXISTS (SELECT 1 FROM submission_review_evidence_entries ev
                          WHERE ev.entry_id=e.id)
    """,
            (course_id, course_id),
        )
    ]
    students = {
        row["id"]: dict(row)
        for row in connection.execute("""
        SELECT id, public_id, surname, name,
               trim(coalesce(surname,'') || ' ' || coalesce(name,'')) AS display_name
        FROM users WHERE type IN (1,-2)
    """)
    }
    return problems, results, submitted, reviews, pending, students
