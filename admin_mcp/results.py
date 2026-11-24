"""Scoped task lookup and roster-based answers for the administrative MCP."""

import json

from models.pwa.ai_review import scope_for


def search_problems(c, principal, text, course, group, lesson, after):
    scope = scope_for(principal)
    term = text.strip().casefold()
    if not term or len(term) > 256:
        raise ValueError("query_length")
    items = []
    ids = []
    cached_revision = None
    texts = {}
    for row in c.execute(
        """SELECT p.id,p.public_id,p.title,p.lesson,p.prob,p.item,p.prob_text,g.short_code,pr.content_revision_id,pr.source_ordinal,pr.source_item,
        c.public_id AS course_public_id,g.public_id AS group_public_id,gl.public_id AS lesson_id
        FROM problem_catalog p JOIN groups g ON p.group_id=g.group_id JOIN courses c ON g.course_id=c.id
        LEFT JOIN course_lessons cl ON cl.course_id=c.id AND cl.lesson_number=p.lesson
        LEFT JOIN group_lessons gl ON gl.course_lesson_id=cl.id AND gl.group_id=g.group_id
        LEFT JOIN problem_revisions pr ON pr.id=(SELECT candidate.id FROM problem_revisions candidate
        JOIN content_revisions cr ON cr.id=candidate.content_revision_id JOIN content_sources cs ON cs.id=cr.source_id
        WHERE candidate.problem_id=p.id AND cs.kind='condition' AND cs.group_lesson_id=gl.id
        ORDER BY candidate.id DESC LIMIT 1)
        WHERE p.id>? AND (? IS NULL OR c.public_id=?) AND (? IS NULL OR g.public_id=?)
        AND (? IS NULL OR gl.public_id=?) ORDER BY p.id""",
        (after, course, course, group, group, lesson, lesson),
    ):
        if not scope.allows(row):
            continue
        label = f"{row['lesson']}{row['short_code']}.{row['prob']}{row['item'] or ''}"
        revision = row["content_revision_id"]
        if revision != cached_revision:
            cached_revision = revision
            derivative = c.execute(
                "SELECT content_text FROM content_derivatives WHERE revision_id=? AND kind='web_ast' AND invalidated_at IS NULL ORDER BY id DESC LIMIT 1",
                (revision,),
            ).fetchone()
            texts = {}
            if derivative:

                def fragments(node, part=None):
                    if isinstance(node, list):
                        for item in node:
                            yield from fragments(item, part)
                    elif isinstance(node, dict):
                        if node.get("type") == "subpart":
                            part = node["label"]
                        for key, value in node.items():
                            if key in {"value", "latex"} and isinstance(value, str):
                                yield part, value
                            elif isinstance(value, (list, dict)):
                                yield from fragments(value, part)

                texts = {
                    p["ordinal"]: list(fragments(p["blocks"]))
                    for p in json.loads(derivative["content_text"])["problems"]
                }
        statement = " ".join(
            value
            for part, value in texts.get(row["source_ordinal"], [])
            if part in {None, row["source_item"]}
        )
        if any(
            term in str(value or "").casefold()
            for value in (
                label,
                row["title"],
                row["prob_text"],
                row["public_id"],
                statement,
            )
        ):
            ids.append(row["id"])
            items.append(
                {
                    "id": row["public_id"],
                    "label": label,
                    "title": row["title"],
                    "courseId": row["course_public_id"],
                    "groupId": row["group_public_id"],
                    "lessonId": row["lesson_id"],
                }
            )
            if len(items) == 51:
                break
    return {"items": items[:50], "nextAfterId": ids[49] if len(items) > 50 else None}


def group_answers(c, principal, group_id, problem_ids, after, page_size):
    if (
        not 1 <= page_size <= 50
        or not 1 <= len(problem_ids) <= 30
        or len(set(problem_ids)) != len(problem_ids)
    ):
        raise ValueError("invalid_page_or_problem_count")
    group = c.execute(
        """SELECT g.group_id,g.public_id AS group_public_id,c.public_id AS course_public_id
        FROM groups g JOIN courses c ON c.id=g.course_id WHERE g.public_id=?""",
        (group_id,),
    ).fetchone()
    if not group or not scope_for(principal).allows(group):
        raise ValueError("group_unavailable")
    problems = []
    for public_id in problem_ids:
        p = c.execute(
            "SELECT id,public_id FROM problem_catalog WHERE public_id=? AND group_id=?",
            (public_id, group["group_id"]),
        ).fetchone()
        if not p:
            raise ValueError("problem_outside_group")
        problems.append(p)
    students = c.execute(
        """SELECT u.id,u.public_id,u.name,u.surname FROM course_enrollments e
        JOIN users u ON u.id=e.student_user_id WHERE e.active_group_id=? AND e.status='active'
        AND u.id>? ORDER BY u.id LIMIT ?""",
        (group["group_id"], after, page_size + 1),
    ).fetchall()
    items = []
    for student in students[:page_size]:
        answers = []
        for p in problems:
            args = (student["id"], p["id"])
            tests = [
                dict(x)
                for x in c.execute(
                    """SELECT public_id AS attemptId,server_received_at AS receivedAt,
              json_extract(answer_payload_json,'$.displayAnswer') AS answer,check_status AS status,verdict
              FROM test_attempts WHERE student_user_id=? AND problem_id=? ORDER BY id""",
                    args,
                )
            ]
            written = []
            for entry in c.execute(
                """SELECT e.id,e.public_id AS entryId,t.public_id AS caseId,e.text,
                e.server_received_at AS receivedAt,t.status AS threadStatus FROM submission_threads t
                JOIN submission_entries e ON e.thread_id=t.id WHERE t.student_user_id=? AND t.problem_id=?
                AND e.author_kind='student' AND e.state IN ('submitted','locked') ORDER BY e.id""",
                args,
            ):
                data = dict(entry)
                data["reviews"] = [
                    dict(row)
                    for row in c.execute(
                        """SELECT r.public_id AS reviewId,
                    r.verdict,r.created_at AS reviewedAt FROM submission_review_evidence_entries e
                    JOIN submission_reviews r ON r.id=e.review_id WHERE e.entry_id=? ORDER BY r.id""",
                        (data["id"],),
                    )
                ]
                data["attachments"] = [
                    a["public_id"]
                    for a in c.execute(
                        "SELECT public_id FROM submission_attachments WHERE entry_id=? AND upload_status IN ('stored','locked') ORDER BY ordinal",
                        (data.pop("id"),),
                    )
                ]
                written.append(data)
            results = [
                dict(x)
                for x in c.execute(
                    "SELECT ts,verdict,res_type AS resultType FROM results WHERE student_id=? AND problem_id=? ORDER BY id",
                    args,
                )
            ]
            answers.append(
                {
                    "problemId": p["public_id"],
                    "submitted": bool(tests or written or results),
                    "testAttempts": tests,
                    "written": written,
                    "results": results,
                    "oralResults": [
                        result for result in results if result["resultType"] in (3, 4)
                    ],
                }
            )
        items.append(
            {
                "studentId": student["public_id"],
                "name": student["name"],
                "surname": student["surname"],
                "answers": answers,
            }
        )
    return {
        "items": items,
        "nextAfterStudentId": students[page_size - 1]["id"]
        if len(students) > page_size
        else None,
    }
