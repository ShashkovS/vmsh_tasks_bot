"""Scoped history read model; see vmshpwa/docs/review-history.md."""

import json

from db_methods.pwa.content import _overlay_problem_titles
from datetime import UTC, datetime
from db_methods.pwa.review_corrections import find_source_review, active_review_owner
from models.pwa.course_runtime_settings import DEFAULT_COURSE_RUNTIME_SETTINGS


BASE = """
FROM submission_reviews r
JOIN submission_threads t ON t.id = r.thread_id
JOIN users s ON s.id = t.student_user_id
JOIN users u ON u.id = r.reviewer_user_id
JOIN problems p ON p.id = t.problem_id
JOIN groups g ON g.group_id = p.group_id
JOIN courses c ON c.id = g.course_id
LEFT JOIN submission_entries comment ON comment.id = r.comment_entry_id
"""


def scope_clause(scope, reviewer_id, is_admin):
    clauses, values = [], []
    if not is_admin:
        clauses.append("r.reviewer_user_id = ?")
        values.append(reviewer_id)
    if not scope.global_access:
        courses, groups = (
            sorted(scope.course_public_ids),
            sorted(scope.group_public_ids),
        )
        clauses.append(
            "(c.public_id IN ("
            + ",".join("?" for _ in courses)
            + ") OR g.public_id IN ("
            + ",".join("?" for _ in groups)
            + "))"
        )
        values.extend(courses + groups)
        clauses.append(
            "NOT EXISTS (SELECT 1 FROM submission_review_evidence_entries evidence "
            "JOIN problems ep ON ep.id = evidence.problem_id "
            "LEFT JOIN groups eg ON eg.group_id = ep.group_id "
            "LEFT JOIN courses ec ON ec.id = eg.course_id "
            "WHERE evidence.review_id = r.id AND NOT (coalesce(ec.public_id, '') IN ("
            + ",".join("?" for _ in courses)
            + ") OR coalesce(eg.public_id, '') IN ("
            + ",".join("?" for _ in groups)
            + ")))"
        )
        values.extend(courses + groups)
    return " AND ".join(clauses) or "1", values


def history_rows(
    connection,
    scope,
    reviewer_id,
    is_admin,
    *,
    course=None,
    lesson=None,
    teacher=None,
    student=None,
    problem=None,
    comment=None,
    before=None,
    review=None,
):
    clause, values = scope_clause(scope, reviewer_id, is_admin)
    for column, value in [
        ("c.public_id", course),
        ("p.lesson", lesson),
        ("u.public_id", teacher),
        ("s.public_id", student),
        ("p.public_id", problem),
        ("r.public_id", review),
    ]:
        if value is not None:
            clause += f" AND {column} = ?"
            values.append(value)
    # SQLite lower() is ASCII-only. A literal casefold matcher handles Russian
    # without regex/LIKE wildcard semantics, bounded by course and lesson.
    if comment:
        connection.create_function(
            "review_contains",
            2,
            lambda text, part: part.casefold() in (text or "").casefold(),
        )
        clause += " AND review_contains(comment.text, ?)"
        values.append(comment)
    if before is not None:
        clause += " AND (r.created_at, r.id) < (SELECT created_at, id FROM submission_reviews WHERE public_id = ?)"
        values.append(before)
    return connection.execute(
        """
SELECT r.id, r.public_id AS review_id, r.verdict, r.created_at, r.thread_id,
 t.version AS thread_version, s.public_id AS student_id, s.name, s.surname,
 s.type AS student_type, u.public_id AS teacher_id, u.name AS teacher_name,
 u.surname AS teacher_surname, p.public_id AS problem_id, p.lesson, p.prob, p.item,
 p.title, g.public_id AS group_id, g.public_name AS group_name, g.short_code,
 c.public_id AS course_id, c.name AS course_name, comment.text AS comment,
 (SELECT newer.public_id FROM submission_reviews newer WHERE newer.thread_id = r.thread_id
  ORDER BY newer.created_at DESC, newer.id DESC LIMIT 1) AS latest_review_id
"""
        + BASE
        + " WHERE "
        + clause
        + " ORDER BY r.created_at DESC, r.id DESC LIMIT 51",
        values,
    ).fetchall()


def summary(row):
    return {
        "reviewId": row["review_id"],
        "verdict": row["verdict"],
        "completedAt": row["created_at"],
        "studentId": row["student_id"],
        "studentName": f"{row['name'] or ''} {row['surname'] or ''}".strip(),
        "isTestStudent": bool(row["student_type"] & 512),
        "teacherId": row["teacher_id"],
        "teacherName": f"{row['teacher_name'] or ''} {row['teacher_surname'] or ''}".strip(),
        "problemId": row["problem_id"],
        "problemNumber": f"{row['lesson']}{row['short_code']}.{row['prob']}{row['item'] or ''}",
        "problemTitle": row["title"] or "Задача",
        "groupName": row["group_name"] or row["short_code"],
        "comment": (row["comment"] or "")[:300],
        "isLatestReview": row["review_id"] == row["latest_review_id"],
    }


def history_options(connection, scope, reviewer_id, is_admin, course=None, lesson=None):
    clause, values = scope_clause(scope, reviewer_id, is_admin)
    rows = connection.execute(
        "SELECT DISTINCT c.public_id AS course_id, c.name AS course_name, p.lesson "
        + BASE
        + " WHERE "
        + clause
        + " ORDER BY p.lesson DESC, c.id",
        values,
    ).fetchall()
    courses = {
        r["course_id"]: {"id": r["course_id"], "name": r["course_name"]} for r in rows
    }
    selected_course = course if course is not None else next(iter(courses), None)
    lessons = sorted(
        {r["lesson"] for r in rows if r["course_id"] == selected_course}, reverse=True
    )
    selected_lesson = lesson if lesson is not None else next(iter(lessons), None)
    clause += " AND c.public_id = ? AND p.lesson = ?"
    values += [selected_course, selected_lesson]
    people = connection.execute(
        "SELECT DISTINCT s.public_id AS student_id, s.name, s.surname, u.public_id AS teacher_id, "
        "u.name AS teacher_name, u.surname AS teacher_surname, p.public_id AS problem_id, p.prob, p.item, p.title "
        + BASE
        + " WHERE "
        + clause,
        values,
    ).fetchall()
    students, teachers, problems = {}, {}, {}
    for r in people:
        students[r["student_id"]] = {
            "studentId": r["student_id"],
            "name": f"{r['name'] or ''} {r['surname'] or ''}".strip(),
        }
        teachers[r["teacher_id"]] = {
            "id": r["teacher_id"],
            "name": f"{r['teacher_name'] or ''} {r['teacher_surname'] or ''}".strip(),
        }
        problems[r["problem_id"]] = {
            "id": r["problem_id"],
            "name": f"{r['prob']}{r['item'] or ''}. {r['title'] or ''}",
        }
    return {
        "courses": list(courses.values()),
        "courseId": selected_course,
        "lessons": lessons,
        "lesson": selected_lesson,
        "students": list(students.values()),
        "teachers": list(teachers.values()),
        "problems": list(problems.values()),
        "canChooseTeacher": is_admin,
    }


def history_detail(connection, scope, reviewer_id, is_admin, review_id):
    rows = history_rows(connection, scope, reviewer_id, is_admin, review=review_id)
    if not rows:
        return None
    row = rows[0]
    holder = active_review_owner(
        connection, find_source_review(connection, review_id), datetime.now(UTC)
    )
    blocked_by = (
        holder["display_name"]
        if holder is not None and holder["teacher_id"] != reviewer_id
        else None
    )
    material = connection.execute(
        "SELECT content.id content_revision_id, derivative.content_text, revision.source_ordinal FROM problem_revisions revision "
        "JOIN content_revisions content ON content.id = revision.content_revision_id "
        "JOIN content_sources source ON source.id = content.source_id AND source.kind = 'condition' "
        "JOIN content_derivatives derivative ON derivative.revision_id = content.id "
        "AND derivative.kind = 'web_ast' AND derivative.invalidated_at IS NULL "
        "WHERE revision.problem_id = (SELECT id FROM problems WHERE public_id = ?) "
        "ORDER BY (revision.id IN (SELECT entry.problem_revision_id FROM submission_review_evidence_entries evidence "
        "JOIN submission_entries entry ON entry.id = evidence.entry_id WHERE evidence.review_id = ?)) DESC, "
        "revision.id DESC, derivative.id DESC LIMIT 1",
        (row["problem_id"], row["id"]),
    ).fetchone()
    document = None
    if material is not None:
        document = json.loads(material["content_text"])
        _overlay_problem_titles(connection, document, material["content_revision_id"])
        document["problems"] = [
            p
            for p in document["problems"]
            if p["ordinal"] == material["source_ordinal"]
        ]
        document["introduction"] = []
    statement = connection.execute(
        "SELECT prob_text FROM problems WHERE public_id = ?", (row["problem_id"],)
    ).fetchone()["prob_text"]
    settings = connection.execute(
        "SELECT values_json FROM course_runtime_settings WHERE course_id = (SELECT id FROM courses WHERE public_id = ?)",
        (row["course_id"],),
    ).fetchone()
    mode = (
        DEFAULT_COURSE_RUNTIME_SETTINGS["verdictMode"]
        if settings is None
        else json.loads(settings["values_json"])["verdictMode"]
    )
    entries = []
    for entry in connection.execute(
        "SELECT e.id, e.public_id, e.text, evidence.entry_version FROM submission_review_evidence_entries evidence "
        "JOIN submission_entries e ON e.id = evidence.entry_id WHERE evidence.review_id = ? "
        "ORDER BY evidence.server_received_at, e.id",
        (row["id"],),
    ).fetchall():
        attachments = connection.execute(
            "SELECT a.public_id AS attachment_id, evidence.ordinal, annotation.schema_version, annotation.rotation, annotation.marks_json "
            "FROM submission_review_evidence_attachments evidence JOIN submission_attachments a ON a.id = evidence.attachment_id "
            "LEFT JOIN submission_review_annotations annotation ON annotation.review_id = evidence.review_id AND annotation.attachment_id = a.id "
            "WHERE evidence.review_id = ? AND evidence.entry_id = ? ORDER BY evidence.ordinal",
            (row["id"], entry["id"]),
        ).fetchall()
        entries.append(
            {
                "entryId": entry["public_id"],
                "text": entry["text"],
                "attachments": [
                    {
                        "attachmentId": a["attachment_id"],
                        "ordinal": a["ordinal"],
                        "annotation": None
                        if a["marks_json"] is None
                        else {
                            "attachmentId": a["attachment_id"],
                            "schemaVersion": a["schema_version"],
                            "rotation": a["rotation"],
                            "marks": json.loads(a["marks_json"]),
                        },
                    }
                    for a in attachments
                ],
            }
        )
    # After authorization of the selected review, show all later verdict authors
    # in this same thread, including another teacher's superseding assessment.
    timeline = connection.execute(
        "SELECT r.public_id AS review_id, r.verdict, r.created_at, u.name, u.surname, comment.text AS comment "
        "FROM submission_reviews r JOIN users u ON u.id = r.reviewer_user_id "
        "LEFT JOIN submission_entries comment ON comment.id = r.comment_entry_id "
        "WHERE r.thread_id = ? ORDER BY r.created_at DESC, r.id DESC",
        (row["thread_id"],),
    ).fetchall()
    return {
        "review": summary(row),
        "verdictMode": mode,
        "statement": statement,
        "document": document,
        "blockedBy": blocked_by,
        "comment": row["comment"] or "",
        "threadVersion": row["thread_version"],
        "latestReviewId": row["latest_review_id"],
        "entries": entries,
        "timeline": [
            {
                "reviewId": r["review_id"],
                "verdict": r["verdict"],
                "completedAt": r["created_at"],
                "teacherName": f"{r['name'] or ''} {r['surname'] or ''}".strip(),
                "comment": r["comment"] or "",
            }
            for r in timeline
        ],
    }
