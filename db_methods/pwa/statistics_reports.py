"""Scoped report facts; lesson-statistics.md and scoped-reads-20261013.md.

Historical reviews count work, while course_facts supplies current credit.
submission_reviews references results one-to-one: never union both ledgers.
"""

import json

from db_methods.pwa.lesson_statistics import (
    course_facts,
    course_problem_ids,
    PENDING_SQL,
)

REVIEWS_SQL = """
SELECT r.id AS result_id,r.student_id AS student_user_id,r.problem_id
FROM results r JOIN users u ON u.id=r.student_id AND u.type IN (1,-2)
WHERE r.problem_id IN (SELECT value FROM json_each(:problem_ids)) AND r.res_type=2
"""


def report_facts(
    connection,
    course_id,
    *,
    allowed_group_public_ids=None,
    lesson_number=None,
    problems=None,
):
    bounded = (
        problems is not None
        or allowed_group_public_ids is not None
        or lesson_number is not None
    )
    problems, results, submitted = course_facts(
        connection,
        course_id,
        allowed_group_public_ids=allowed_group_public_ids,
        lesson_number=lesson_number,
        problems=problems,
    )
    problem_ids = (
        [p["problem_id"] for p in problems]
        if bounded
        else course_problem_ids(connection, course_id)
    )
    params = {"problem_ids": json.dumps(problem_ids), "exclude_reviewed": 1}
    reviews = [dict(row) for row in connection.execute(REVIEWS_SQL, params)]
    pending = [dict(row) for row in connection.execute(PENDING_SQL, params)]
    participants = {
        row["student_user_id"]
        for rows in (results, submitted, reviews, pending)
        for row in rows
    }
    students = {
        row["id"]: dict(row)
        for row in connection.execute(
            """
        SELECT id,public_id,surname,name,
               trim(coalesce(surname,'') || ' ' || coalesce(name,'')) AS display_name
        FROM users WHERE type IN (1,-2) AND id IN (SELECT value FROM json_each(?))
        """,
            (json.dumps(sorted(participants)),),
        )
    }
    return problems, results, submitted, reviews, pending, students
