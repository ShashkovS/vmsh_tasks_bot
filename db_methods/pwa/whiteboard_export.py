"""Published worksheet snapshot; vmshpwa/docs/whiteboard-export.md."""

import json

from db_methods.pwa.content import _overlay_problem_titles


def published_sheets(connection):
    return connection.execute(
        "SELECT gl.public_id groupLessonId, c.public_id courseId, c.code courseCode, "
        "c.name courseName, lesson.lesson_number lessonNumber, lesson.title lessonTitle, "
        "g.public_id groupId, g.short_code groupCode, g.public_name groupName, "
        "pub.public_id publicationId, revision.public_id revisionId, "
        "revision.id revision_id, c.id course_id "
        "FROM lesson_publications pub JOIN content_revisions revision ON revision.id = pub.revision_id "
        "JOIN group_lessons gl ON gl.id = pub.group_lesson_id "
        "JOIN course_lessons lesson ON lesson.id = gl.course_lesson_id "
        "JOIN courses c ON c.id = gl.course_id "
        "JOIN groups g ON g.course_id = gl.course_id AND g.group_id = gl.group_id "
        "WHERE pub.kind = 'condition' AND pub.state = 'published' AND revision.status = 'ready' "
        "ORDER BY c.sort_order, c.id, lesson.lesson_number DESC, g.sort_order, g.id"
    ).fetchall()


def sheet_document(connection, sheet):
    row = connection.execute(
        "SELECT content_text FROM content_derivatives WHERE revision_id = ? "
        "AND kind = 'web_ast' AND invalidated_at IS NULL ORDER BY id DESC LIMIT 1",
        (sheet["revision_id"],),
    ).fetchone()
    if row is None:
        raise ValueError("Published worksheet has no web document")
    document = json.loads(row["content_text"])
    if (
        document.get("materialKind") != "condition"
        or document.get("revisionId") != sheet["revisionId"]
    ):
        raise ValueError("Invalid published condition document")
    _overlay_problem_titles(connection, document, sheet["revision_id"])
    scales = {
        r["asset_id"]: r["scale"]
        for r in connection.execute(
            "SELECT asset_id, scale FROM content_figure_scales WHERE revision_id = ?",
            (sheet["revision_id"],),
        )
    }
    return document, scales


def sheet_metadata(sheet):
    return {
        key: value
        for key, value in sheet.items()
        if key not in ("revision_id", "course_id")
    }


def document_assets(document):
    """Collect only assets actually referenced by this condition snapshot."""
    found = []

    def visit(value):
        if isinstance(value, dict):
            if (
                value.get("type") == "figure"
                and value.get("asset", {}).get("status") == "available"
            ):
                asset = value["asset"]
                found.append(asset)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    return found
