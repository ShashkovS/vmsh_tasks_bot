"""Scoped published facts; lesson-statistics.md and scoped-reads-20261013.md."""

import json
import sqlite3

from db_methods.pwa.effective_results import scoped_effective_results_ctes
from helpers.prometheus_metrics import PROJECTION_DURATION

PUBLISHED_PROBLEMS_SQL = """
        SELECT DISTINCT p.id AS problem_id, p.public_id, p.lesson AS lesson_number,
               p.group_id, g.public_id AS group_public_id, g.short_code AS group_code,
               g.public_name AS group_name, g.sort_order AS group_sort_order,
               g.color_key, p.prob, p.item, p.title, p.prob_type AS problem_type,
               pr.source_ordinal AS publication_order,
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
        JOIN problem_catalog p ON p.id = pr.problem_id
        LEFT JOIN problem_synonym_members sm ON sm.problem_id = p.id AND sm.removed_at IS NULL
        LEFT JOIN problem_synonym_groups sg ON sg.id = sm.synonym_group_id
          AND sg.status = 'active' AND sg.course_lesson_id = gl.course_lesson_id
        WHERE gl.course_id = :course_id
          AND (:group_ids IS NULL OR g.public_id IN (SELECT value FROM json_each(:group_ids)))
          AND (:lesson_number IS NULL OR p.lesson = :lesson_number) AND p.prob > 0 AND p.lesson >= 0
        ORDER BY p.lesson, g.sort_order, pr.source_ordinal, pr.source_item, p.id
    """

CURRENT_RESULTS_SQL = (
    "WITH requested_problem_ids AS MATERIALIZED (SELECT value problem_id FROM json_each(:problem_ids)), "
    + scoped_effective_results_ctes()
    + """
SELECT r.id AS result_id, r.student_id AS student_user_id, r.problem_id,
       r.ts,r.res_type,v.val AS verdict_weight,r.verdict>0 AS trainable,
       u.public_id AS student_public_id,
       trim(coalesce(u.surname,'') || ' ' || coalesce(u.name,'')) AS student_name
FROM scoped_effective_results r JOIN verdicts v ON v.id=r.verdict
JOIN users u ON u.id=r.student_id AND u.type IN (1,-2)
WHERE r.problem_id IN (SELECT problem_id FROM requested_problem_ids)
  AND (r.res_type<>1 OR NOT EXISTS (
    SELECT 1 FROM test_attempts ta WHERE ta.student_user_id=r.student_id AND ta.problem_id=r.problem_id))
ORDER BY r.ts,r.id
"""
)

CURRENT_ATTEMPTS_SQL = """
SELECT ta.id AS result_id,ta.student_user_id,ta.problem_id,
       current_result.id AS source_result_id,current_result.ts AS source_ts,
       ta.server_received_at AS ts,1 AS res_type,coalesce(v.val,0) AS verdict_weight,
       ta.check_status='checked' AS trainable,u.public_id AS student_public_id,
       trim(coalesce(u.surname,'') || ' ' || coalesce(u.name,'')) AS student_name
FROM test_attempts ta JOIN users u ON u.id=ta.student_user_id AND u.type IN (1,-2)
LEFT JOIN verdicts v ON v.id=ta.verdict AND ta.check_status='checked'
LEFT JOIN results current_result ON current_result.id=ta.result_id
WHERE ta.problem_id IN (SELECT value FROM json_each(:problem_ids)) AND ta.counts_as_attempt=1
  AND NOT EXISTS (SELECT 1 FROM live_mark_cells mc
    WHERE mc.student_id=ta.student_user_id AND mc.problem_id=ta.problem_id AND mc.result_id IS NOT NULL)
ORDER BY ta.server_received_at,ta.id
"""

PENDING_SQL = """
SELECT DISTINCT q.student_id AS student_user_id,q.problem_id
FROM written_tasks_queue q JOIN users u ON u.id=q.student_id AND u.type IN (1,-2)
WHERE q.problem_id IN (SELECT value FROM json_each(:problem_ids))
UNION
SELECT DISTINCT t.student_user_id,t.problem_id
FROM submission_threads t JOIN users u ON u.id=t.student_user_id AND u.type IN (1,-2)
JOIN submission_entries e ON e.thread_id=t.id AND e.author_kind='student'
  AND e.entry_kind='submission' AND e.state IN ('submitted','locked')
WHERE t.problem_id IN (SELECT value FROM json_each(:problem_ids))
  AND (:exclude_reviewed=0 OR NOT EXISTS (
    SELECT 1 FROM submission_review_evidence_entries ev WHERE ev.entry_id=e.id))
"""


def published_problems(
    connection, course_id, *, allowed_group_public_ids=None, lesson_number=None
):
    return [
        dict(row)
        for row in connection.execute(
            PUBLISHED_PROBLEMS_SQL,
            {
                "course_id": course_id,
                "group_ids": None
                if allowed_group_public_ids is None
                else json.dumps(sorted(allowed_group_public_ids)),
                "lesson_number": lesson_number,
            },
        )
    ]


def course_facts(
    connection: sqlite3.Connection,
    course_id: int,
    *,
    allowed_group_public_ids=None,
    lesson_number=None,
    problems=None,
):
    """No HTTP cache here: scheduled a53 calculations always read fresh facts."""
    with PROJECTION_DURATION.labels("statistics_facts").time():
        bounded = (
            problems is not None
            or allowed_group_public_ids is not None
            or lesson_number is not None
        )
        if problems is None:
            problems = published_problems(
                connection,
                course_id,
                allowed_group_public_ids=allowed_group_public_ids,
                lesson_number=lesson_number,
            )
        problem_ids = (
            [p["problem_id"] for p in problems]
            if bounded
            else course_problem_ids(connection, course_id)
        )
        if not problem_ids:
            return problems, [], []
        parameters = {"problem_ids": json.dumps(problem_ids), "exclude_reviewed": 0}
        results = [
            dict(row) for row in connection.execute(CURRENT_RESULTS_SQL, parameters)
        ]
        # Current attempts remain authoritative over their append-only rechecks.
        results.extend(
            dict(row) for row in connection.execute(CURRENT_ATTEMPTS_SQL, parameters)
        )
        pending = [dict(row) for row in connection.execute(PENDING_SQL, parameters)]
        return problems, results, pending


def course_problem_ids(connection, course_id):
    """The default facts interface retains historical course work for legacy jobs."""
    return [
        row["id"]
        for row in connection.execute(
            "SELECT p.id FROM problem_catalog p JOIN groups g ON g.group_id=p.group_id WHERE g.course_id=?",
            (course_id,),
        )
    ]
