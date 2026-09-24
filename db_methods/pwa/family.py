"""Small direct SQLite reads used by the Family PWA."""

from __future__ import annotations

import sqlite3


def latest_published_lesson(
    connection: sqlite3.Connection,
    *,
    course_public_id: str,
    group_public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT group_lesson.public_id AS group_lesson_public_id, "
        "course_lesson.public_id AS course_lesson_public_id, "
        "course_lesson.lesson_number, course_lesson.title, "
        "group_lesson.cycle_anchor_date, group_lesson.business_timezone, "
        "(SELECT count(*) FROM problem_revisions AS problem_revision "
        " WHERE problem_revision.content_revision_id = revision.id) AS problem_count "
        "FROM group_lessons AS group_lesson "
        "JOIN course_lessons AS course_lesson "
        "ON course_lesson.id = group_lesson.course_lesson_id "
        "JOIN courses AS course ON course.id = group_lesson.course_id "
        "JOIN groups AS group_record ON group_record.course_id = group_lesson.course_id "
        "AND group_record.group_id = group_lesson.group_id "
        "JOIN lesson_publications AS publication "
        "ON publication.group_lesson_id = group_lesson.id "
        "AND publication.kind = 'condition' AND publication.state = 'published' "
        "JOIN content_revisions AS revision ON revision.id = publication.revision_id "
        "AND revision.status = 'ready' "
        "WHERE course.public_id = ? AND group_record.public_id = ? "
        "AND group_lesson.status = 'active' "
        "AND EXISTS (SELECT 1 FROM content_derivatives AS derivative "
        " WHERE derivative.revision_id = revision.id "
        " AND derivative.kind = 'web_ast' AND derivative.invalidated_at IS NULL) "
        "ORDER BY course_lesson.lesson_number DESC, group_lesson.id DESC LIMIT 1",
        (course_public_id, group_public_id),
    ).fetchone()
    return None if row is None else dict(row)


__all__ = ["latest_published_lesson"]
