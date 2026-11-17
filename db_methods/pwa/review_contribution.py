"""Personal PWA-only reads; vmshpwa/docs/review-contribution.md."""


def contribution_rows(connection, teacher_id):
    """Resolve written corrections, retaining the original check's attribution."""
    written = connection.execute(
        """
        WITH RECURSIVE corrections AS MATERIALIZED (
          SELECT review_id, json_extract(payload_json, '$.correctsReviewPublicId') AS source_id
          FROM submission_review_events
          WHERE json_extract(payload_json, '$.correctsReviewPublicId') IS NOT NULL
        ), checks AS (
          SELECT sr.id AS root_id, sr.id, sr.public_id, sr.verdict, sr.created_at,
                 r.ts, r.lesson, c.public_id AS course_id
          FROM submission_reviews sr
          JOIN results r ON r.id = sr.result_id
          JOIN users student ON student.id = r.student_id
          JOIN problems p ON p.id = r.problem_id
          LEFT JOIN groups g ON g.group_id = p.group_id
          LEFT JOIN courses c ON c.id = g.course_id
          WHERE sr.reviewer_user_id = ? AND sr.source = 'staff'
            AND student.type IN (1, -2)
            AND NOT EXISTS (
              SELECT 1 FROM corrections e WHERE e.review_id = sr.id
            )
          UNION ALL
          SELECT checks.root_id, sr.id, sr.public_id, sr.verdict, sr.created_at,
                 checks.ts, checks.lesson, checks.course_id
          FROM checks
          JOIN corrections e ON e.source_id = checks.public_id
          CROSS JOIN submission_reviews sr ON sr.id = e.review_id
          WHERE sr.source = 'staff' AND sr.id > checks.id
        ), latest AS (
          SELECT *, row_number() OVER (
            PARTITION BY root_id ORDER BY created_at DESC, id DESC
          ) AS position FROM checks
        )
        SELECT ts, lesson, course_id, 'written' AS kind, v.val
        FROM latest JOIN verdicts v ON v.id = latest.verdict
        WHERE position = 1 AND latest.verdict != -32768
        """,
        (teacher_id,),
    ).fetchall()
    oral = connection.execute(
        """
        SELECT r.ts, r.lesson, c.public_id AS course_id,
               CASE WHEN r.res_type = 4 THEN 'school' ELSE 'zoom' END AS kind, v.val
        FROM results r
        JOIN users student ON student.id = r.student_id
        JOIN verdicts v ON v.id = r.verdict
        JOIN problems p ON p.id = r.problem_id
        LEFT JOIN groups g ON g.group_id = p.group_id
        LEFT JOIN courses c ON c.id = g.course_id
        WHERE r.teacher_id = ? AND r.res_type IN (3, 4)
          AND student.type IN (1, -2) AND r.verdict != -32768
          AND (EXISTS (SELECT 1 FROM live_mark_results lm WHERE lm.result_id = r.id)
            OR EXISTS (SELECT 1 FROM zoom_conversation z
              WHERE z.id = r.zoom_conversation_id AND z.pwa_idempotency_key IS NOT NULL))
        """,
        (teacher_id,),
    ).fetchall()
    return [dict(row) for row in (*written, *oral)]


def contribution_lessons(connection, scope, now):
    """Published lessons visible through the current Staff grants, even if empty."""
    values = [now]
    clause = ""
    if not scope.global_access:
        courses, groups = (
            sorted(scope.course_public_ids),
            sorted(scope.group_public_ids),
        )
        clause = (
            " AND (c.public_id IN ("
            + ",".join("?" for _ in courses)
            + ") OR g.public_id IN ("
            + ",".join("?" for _ in groups)
            + "))"
        )
        values.extend(courses + groups)
    return [
        dict(row)
        for row in connection.execute(
            """
        SELECT DISTINCT c.public_id AS course_id, c.name AS course_name,
                        cl.lesson_number AS lesson, gl.public_id AS group_lesson_id
        FROM lesson_publications publication
        JOIN group_lessons gl ON gl.id = publication.group_lesson_id
        JOIN course_lessons cl ON cl.id = gl.course_lesson_id
        JOIN courses c ON c.id = gl.course_id
        JOIN groups g ON g.group_id = gl.group_id
        WHERE publication.kind = 'condition' AND publication.state = 'published'
          AND julianday(publication.published_at) <= julianday(?)
        """
            + clause
            + " ORDER BY c.id, cl.lesson_number DESC",
            values,
        ).fetchall()
    ]
