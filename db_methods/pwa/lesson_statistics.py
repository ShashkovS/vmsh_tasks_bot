"""Current course facts for lesson statistics and the a53 step.

See vmshpwa/docs/lesson-statistics.md. Publication membership, not old revisions,
determines the task set. Result corrections already neutralize old verdicts.
"""

import sqlite3


def course_facts(connection: sqlite3.Connection, course_id: int):
    problems = [
        dict(row)
        for row in connection.execute(
            """
        SELECT DISTINCT p.id AS problem_id, p.public_id, p.lesson AS lesson_number,
               p.group_id, g.public_id AS group_public_id, g.short_code AS group_code,
               g.public_name AS group_name, g.sort_order AS group_sort_order,
               g.color_key, p.prob, p.item, p.title, p.prob_type AS problem_type,
               CASE WHEN sg.id IS NULL THEN 'problem:' || p.id
                    ELSE 'synonym:' || sg.id END AS logical_problem_key
        FROM group_lessons gl
        JOIN groups g ON g.group_id = gl.group_id
        JOIN lesson_publications lp ON lp.group_lesson_id = gl.id
          AND lp.kind = 'condition' AND lp.state = 'published'
        JOIN problem_revisions pr ON pr.content_revision_id = lp.revision_id
        JOIN content_problem_matches pm ON pm.content_revision_id = pr.content_revision_id
          AND pm.source_ordinal = pr.source_ordinal AND pm.source_item = pr.source_item
          AND pm.problem_id = pr.problem_id AND pm.resolved_at IS NOT NULL AND pm.decision <> 'omit'
        JOIN problems p ON p.id = pr.problem_id
        LEFT JOIN problem_synonym_members sm ON sm.problem_id = p.id AND sm.removed_at IS NULL
        LEFT JOIN problem_synonym_groups sg ON sg.id = sm.synonym_group_id
          AND sg.status = 'active' AND sg.course_lesson_id = gl.course_lesson_id
        WHERE gl.course_id = ? AND p.prob > 0 AND p.lesson >= 0
        ORDER BY p.lesson, g.sort_order, p.prob, p.item, p.id
    """,
            (course_id,),
        )
    ]
    results = [
        dict(row)
        for row in connection.execute(
            """
        SELECT r.id AS result_id, r.student_id AS student_user_id, r.problem_id,
               r.ts, v.val AS verdict_weight, r.verdict > 0 AS trainable,
               u.public_id AS student_public_id,
               trim(coalesce(u.surname, '') || ' ' || coalesce(u.name, '')) AS student_name
        FROM results r JOIN verdicts v ON v.id = r.verdict
        JOIN users u ON u.id = r.student_id AND u.type IN (1, -2)
        JOIN problems p ON p.id = r.problem_id
        JOIN groups g ON g.group_id = p.group_id
        WHERE g.course_id = ?
          AND (r.res_type <> 1 OR NOT EXISTS (
            SELECT 1 FROM test_attempts ta WHERE ta.student_user_id = r.student_id
              AND ta.problem_id = r.problem_id))
        ORDER BY r.ts, r.id
    """,
            (course_id,),
        )
    ]
    # test_attempts is the current check projection. Rechecks append results,
    # so reading their historical positive results would resurrect revoked credit.
    results.extend(
        dict(row)
        for row in connection.execute(
            """
        SELECT ta.id AS result_id, ta.student_user_id, ta.problem_id,
               ta.server_received_at AS ts, coalesce(v.val, 0) AS verdict_weight,
               ta.check_status = 'checked' AS trainable,
               u.public_id AS student_public_id,
               trim(coalesce(u.surname, '') || ' ' || coalesce(u.name, '')) AS student_name
        FROM test_attempts ta JOIN users u ON u.id = ta.student_user_id AND u.type IN (1, -2)
        JOIN problems p ON p.id = ta.problem_id JOIN groups g ON g.group_id = p.group_id
        LEFT JOIN verdicts v ON v.id = ta.verdict AND ta.check_status = 'checked'
        WHERE g.course_id = ? AND ta.counts_as_attempt = 1
        ORDER BY ta.server_received_at, ta.id
    """,
            (course_id,),
        )
    )
    pending = [
        dict(row)
        for row in connection.execute(
            """
        SELECT DISTINCT q.student_id AS student_user_id, q.problem_id
        FROM written_tasks_queue q JOIN users u ON u.id = q.student_id AND u.type IN (1, -2)
        JOIN problems p ON p.id = q.problem_id
        JOIN groups g ON g.group_id = p.group_id WHERE g.course_id = ?
        UNION
        SELECT DISTINCT t.student_user_id, t.problem_id
        FROM submission_threads t JOIN users u ON u.id = t.student_user_id AND u.type IN (1, -2)
        JOIN problems p ON p.id = t.problem_id JOIN groups g ON g.group_id = p.group_id
        JOIN submission_entries e ON e.thread_id = t.id
          AND e.author_kind = 'student' AND e.entry_kind = 'submission'
          AND e.state IN ('submitted', 'locked')
        WHERE g.course_id = ?
    """,
            (course_id, course_id),
        )
    ]
    return problems, results, pending
