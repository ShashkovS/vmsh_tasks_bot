"""Calibration and fixed-task batches; vmshpwa/docs/ai-review-assistant.md.

History cases are read-only, independent of the current human review queue.
Classify individual submitted messages, not the student's latest overall result.
"""

import re

from db_methods.pwa import ai_review_exports as db
from db_methods.pwa import ai_review as assistant_db
from db_methods.pwa import review_conversation as conversation_db
from db_methods.pwa.reviews import (
    ReviewQueueForbidden,
    ReviewQueueNotFound,
    ReviewThreadChanged,
)
from models.pwa import ai_review as ai, review_sheet


def selected_problems(connection, scope, query):
    if not query.get("problemId") and not query.get("lessonId"):
        raise ai.AssistantError("problem_or_lesson_required")
    rows = [
        p
        for p in assistant_db.problem_rows(connection)
        if (not query.get("problemId") or p["public_id"] == query["problemId"])
        and (not query.get("lessonId") or p["lesson_id"] == query["lessonId"])
    ]
    if query.get("problemId"):
        if not rows:
            raise ReviewQueueNotFound("problem not found")
        if not scope.allows(rows[0]):
            raise ReviewQueueForbidden("problem outside scope")
    return [p for p in rows if scope.allows(p)]


def history_context(connection, scope, case_id, root):
    match = re.fullmatch(r"history-([1-9][0-9]*)-([1-9][0-9]*)", case_id)
    if not match:
        raise ReviewQueueNotFound("history not found")
    student_id, problem_id = map(int, match.groups())
    p = next(
        (p for p in assistant_db.problem_rows(connection) if p["id"] == problem_id),
        None,
    )
    if p is None:
        raise ReviewQueueNotFound("problem not found")
    if not scope.allows(p):
        raise ReviewQueueForbidden("problem outside scope")
    student = next(
        (s for s in db.students(connection, problem_id) if s["id"] == student_id), None
    )
    if student is None:
        raise ReviewQueueNotFound("history not found")
    return work_context(connection, scope, student, p, root)


def work_context(connection, scope, student, p, root):
    case_id = f"history-{student['id']}-{p['id']}"
    events = ai.dialogue_events(connection, scope, student, [p], root)
    by_id = {e["id"]: e for e in events}
    submissions = []
    states = db.submission_states(connection, student["id"], p["id"])
    for row in states:
        event = by_id.get(f"entry:{row['id']}")
        if event is None:
            continue
        status = (
            "reviewed"
            if row["reviewed"]
            else "superseded"
            if row["superseded"] or row["state"] == "deleted"
            else "pending"
            if row["state"] in {"submitted", "locked"}
            else "unknown"
        )
        submissions.append(
            {
                **event,
                "entryId": row["public_id"],
                "status": status,
                "reviewIds": [
                    r["public_id"]
                    for r in db.reviews(connection, row["id"])
                    if conversation_db.review_in_scope(connection, scope, r["id"])
                ],
            }
        )
    # Legacy Telegram messages have no reliable per-message evidence link.
    # Export them without inferring a check from a later, unrelated result.
    submissions.extend(
        {**e, "entryId": None, "status": "unknown", "reviewIds": []}
        for e in events
        if e["kind"] == "discussion" and e["authorKind"] == "student"
    )
    submissions.extend(
        {
            **e,
            "entryId": None,
            "status": "reviewed" if e["verdict"] is not None else "pending",
            "reviewIds": [],
        }
        for e in events
        if e["kind"] == "test"
    )
    # Legacy auto-check answers are stored as results, not submission entries.
    submissions.extend(
        {**e, "entryId": None, "status": "reviewed", "reviewIds": []}
        for e in events
        if e["kind"] == "result" and e["text"] is not None
    )
    event_order = {e["id"]: i for i, e in enumerate(events)}
    submissions.sort(key=lambda e: event_order[e["id"]])
    revisions = db.revision_ids(connection, student["id"], p["id"])
    materials = [
        ai.problem(connection, scope, p["public_id"], revision_id=r)
        for r in sorted(revisions, key=lambda r: r or 0) or [None]
    ]
    modern = db.modern_case(connection, student["id"], p["id"])
    suggestion_case_id = None
    if modern:
        try:
            modern_id = ai.canonical_case(
                connection, scope, case_id=modern["public_id"]
            )
            value = review_sheet.context(connection, scope, modern_id)
        except ReviewQueueForbidden, ReviewQueueNotFound, ReviewThreadChanged:
            pass
        else:
            if value["queues"]:
                suggestion_case_id = modern_id
    result = {
        "caseId": case_id,
        "student": {
            "studentId": student["public_id"],
            "displayName": " ".join(
                filter(None, [student["surname"], student["name"]])
            ),
        },
        "problemId": p["public_id"],
        "lessonId": p["lesson_id"],
        "groupId": p["group_public_id"],
        "courseId": p["course_public_id"],
        "suggestionCaseId": suggestion_case_id,
        "problems": materials,
        "submissions": submissions,
    }
    result["snapshot"] = ai.digest({"work": result, "dialogue": events})
    return result, events


def export_page(items, query, size):
    """Cursor binds selection/content to avoid silent gaps during calibration."""
    snapshot = ai.digest(
        {"query": {k: v for k, v in query.items() if k != "cursor"}, "items": items}
    )
    start = 0
    if query.get("cursor"):
        version, separator, identity = query["cursor"].partition(":")
        if not separator:
            raise ai.AssistantError("invalid_cursor")
        if version != snapshot:
            raise ai.AssistantError("ai_context_changed", 409)
        index = next(
            (i for i, item in enumerate(items) if item["id"] == identity), None
        )
        if index is None:
            raise ai.AssistantError("invalid_cursor")
        start = index + 1
    batch = items[start : start + size]
    return {
        "items": batch,
        "total": len(items),
        "selectionSnapshot": snapshot,
        "nextCursor": f"{snapshot}:{batch[-1]['id']}"
        if batch and start + size < len(items)
        else None,
    }


def comments(connection, scope, root, query):
    items = {}
    for p in selected_problems(connection, scope, query):
        for student in db.students(connection, p["id"]):
            value, events = work_context(connection, scope, student, p, root)
            for event in events:
                if event["authorKind"] not in {"teacher", "admin"} or not (
                    event["text"] or event["images"]
                ):
                    continue
                if event["id"] in items:
                    items[event["id"]]["problemIds"].append(p["public_id"])
                    continue
                items[event["id"]] = {
                    **event,
                    "caseId": value["caseId"],
                    "snapshot": value["snapshot"],
                    "student": value["student"],
                    "lessonId": p["lesson_id"],
                    "problemIds": [p["public_id"]],
                }
    rows = sorted(items.values(), key=lambda e: (e["at"] or "", e["id"]))
    return export_page(rows, query, 50)


def submissions(connection, scope, root, query):
    p = selected_problems(connection, scope, query)[0]
    items = []
    counts = {status: 0 for status in ("pending", "reviewed", "superseded", "unknown")}
    for student in db.students(connection, p["id"]):
        value, events = work_context(connection, scope, student, p, root)
        for entry in value["submissions"]:
            counts[entry["status"]] += 1
        selected = [
            entry
            for entry in value["submissions"]
            if query["status"] == "all" or entry["status"] == query["status"]
        ]
        if selected:
            items.append(
                {
                    **value,
                    "id": value["caseId"],
                    "submissions": selected,
                    "dialogue": events,
                }
            )
    return {
        **export_page(items, query, query["pageSize"]),
        "submissionCounts": counts,
        "selectedSubmissionCount": sum(len(item["submissions"]) for item in items),
    }
