"""Lesson material reads; vmshpwa/docs/ai-review-assistant.md, prior curriculum."""

LESSONS = """SELECT gl.id,gl.public_id AS lesson_id,gl.group_id,gl.status,
cl.lesson_number AS number,cl.title,g.public_id AS group_public_id,
g.public_name AS group_name,c.public_id AS course_public_id,c.id AS course_id
FROM group_lessons gl JOIN course_lessons cl ON cl.id=gl.course_lesson_id
JOIN groups g ON g.group_id=gl.group_id JOIN courses c ON c.id=gl.course_id"""


def lesson(connection, public_id):
    return connection.execute(
        LESSONS + " WHERE gl.public_id=?", (public_id,)
    ).fetchone()


def previous_lessons(connection, selected):
    return connection.execute(
        LESSONS
        + """ WHERE gl.course_id=? AND gl.group_id=? AND cl.lesson_number<?
        AND gl.status IN ('active','archived') ORDER BY cl.lesson_number DESC""",
        (selected["course_id"], selected["group_id"], selected["number"]),
    ).fetchall()


def material_revisions(connection, lesson_id):
    return connection.execute(
        """SELECT cs.id AS source_id,cs.public_id AS source_public_id,cs.kind,
        cs.logical_filename,cr.id,cr.public_id AS revision_id,cr.revision_number,
        cr.version,cr.status,cr.latex_text,lp.published_at,
        (SELECT d.content_text FROM content_derivatives d WHERE d.revision_id=cr.id
          AND d.kind='web_ast' AND d.invalidated_at IS NULL ORDER BY d.id DESC LIMIT 1) AS document
        FROM content_sources cs JOIN content_revisions cr ON cr.source_id=cs.id
        LEFT JOIN lesson_publications lp ON lp.group_lesson_id=cs.group_lesson_id
          AND lp.kind=cs.kind AND lp.revision_id=cr.id AND lp.state='published'
        WHERE cs.group_lesson_id=? AND cs.kind IN ('condition','hint','solution')
          AND (cs.archived_at IS NULL OR lp.id IS NOT NULL)
        ORDER BY cs.kind,cs.logical_filename,cs.id,cr.revision_number DESC""",
        (lesson_id,),
    ).fetchall()


def problem_bindings(connection, revision_id):
    return connection.execute(
        """SELECT m.source_ordinal,m.source_item,m.decision,p.public_id AS problem_id,
        p.title,pr.answer_type,pr.answer_config_json,pr.config_version
        FROM content_problem_matches m
        JOIN content_revisions cr ON cr.id=m.content_revision_id
        JOIN content_sources cs ON cs.id=cr.source_id
        JOIN group_lessons gl ON gl.id=cs.group_lesson_id
        JOIN course_lessons cl ON cl.id=gl.course_lesson_id
        LEFT JOIN problem_catalog p ON p.id=m.problem_id
          AND p.group_id=gl.group_id AND p.lesson=cl.lesson_number
        LEFT JOIN problem_revisions pr ON pr.problem_id=p.id
          AND pr.content_revision_id=m.content_revision_id
        WHERE m.content_revision_id=? AND m.resolved_at IS NOT NULL AND m.decision<>'omit'
        ORDER BY m.source_ordinal,m.id""",
        (revision_id,),
    ).fetchall()
