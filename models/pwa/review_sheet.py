"""Optimistic, lease-free written review; vmshpwa/docs/review-sheet.md."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from db_methods.pwa import review_sheet as db, review_corrections as corrections
from db_methods.pwa import review_series, student_results as archive_db
from db_methods.pwa.reviews import (
    CompleteReviewReceipt,
    ReviewAnnotationReceipt,
    ReviewInternalReactionState,
    ReviewQueueNotFound,
    ReviewQueueForbidden,
    ReviewCompletionInvalid,
    ReviewIdempotencyConflict,
    ReviewThreadChanged,
    _timestamp,
    REVIEW_INTERNAL_REACTION_EDIT_WINDOW,
)
from helpers.consts import USER_TYPE, VERDICT, VERDICTS_SOLVED
from models.pwa import review_conversation, student_results as archive
from models.pwa.course_runtime_settings import DEFAULT_COURSE_RUNTIME_SETTINGS

LESSON_LIMIT = 300


def _digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _name(row):
    return " ".join(filter(None, (row["name"], row["surname"]))) or str(
        row.get("student_public_id") or ""
    )


def _label(row):
    return f"{row['lesson']}{row['short_code']}.{row['prob']}{row['item'] or ''} · {row['title'] or ''}"


def context(connection, scope, case_id, *, allow_empty=False, include_snapshot=True):
    threads = db.case_threads(connection, case_id)
    if not threads:
        raise ReviewQueueNotFound("sheet case was not found")
    if any(not scope.allows(t) for t in threads):
        raise ReviewQueueForbidden("sheet case is outside current scope")
    queue_rows = db.queues(connection, threads)
    source = db.latest_review(connection, threads)
    if source and any(
        not scope.allows(row)
        for row in corrections.evidence_scopes(connection, source["id"])
    ):
        raise ReviewQueueForbidden("review evidence is outside current scope")
    evidence = []
    if queue_rows:
        for queue in queue_rows:
            thread = next(
                (
                    t
                    for t in reversed(threads)
                    if t["problem_id"] == queue["problem_id"]
                    and t["status"] != "closed"
                ),
                None,
            )
            entries = db.entries(connection, thread["id"]) if thread else []
            if not entries or thread["status"] != "awaiting_review":
                raise ReviewQueueNotFound(
                    "case has no complete modern pending evidence"
                )
            for entry in entries:
                photos = db.attachments(connection, entry["id"])
                if any(a["upload_status"] != "stored" for a in photos):
                    raise ReviewThreadChanged("pending attachments are not ready")
                evidence.append((thread, entry, photos))
    elif source:
        for thread in threads:
            for entry in db.entries(connection, thread["id"], review_id=source["id"]):
                evidence.append(
                    (
                        thread,
                        entry,
                        db.attachments(connection, entry["id"], review_id=source["id"]),
                    )
                )
    if not evidence and not allow_empty:
        raise ReviewQueueNotFound("case has no modern review evidence")
    # The collection needs evidence eligibility, not the detail/CAS snapshot.
    # followups-20261018.md: keep CAS reads unchanged for detail and mutations.
    result = db.latest_result(connection, threads) if include_snapshot else None
    snapshot = _digest(
        {
            "threads": [
                (
                    t["public_id"],
                    t["version"],
                    t["status"],
                    t["latest_result_id"],
                    t["problem_id"],
                    t["logical_key"],
                )
                for t in threads
            ],
            # Claim/heartbeat changes are deliberately absent: they do not change evidence.
            "queue": [(q["id"], q["problem_id"]) for q in queue_rows],
            "review": source["public_id"] if source else None,
            "result": result["id"] if result else None,
            "evidence": [
                (
                    e["public_id"],
                    e["version"],
                    [
                        (
                            a["public_id"],
                            a["ordinal"],
                            a["asset_id"],
                            a["upload_status"],
                        )
                        for a in photos
                    ],
                )
                for _, e, photos in evidence
            ],
        }
    ) if include_snapshot else None
    return dict(
        threads=threads,
        queues=queue_rows,
        source=source,
        evidence=evidence,
        snapshot=snapshot,
    )


def directory(connection, scope):
    return {
        "schemaVersion": 1,
        "lessons": [
            {
                "lessonId": row["lesson_id"],
                "label": f"{row['course_name']} · {row['lesson']}{row['short_code']} · {row['group_name']}",
            }
            for row in db.lessons(connection)
            if scope.allows(row)
        ],
    }


def collection(connection, scope, *, lesson_id, problem_id=None, mode="pending"):
    if lesson_id is None and problem_id:
        found = db.problem_lesson(connection, problem_id)
        lesson_id = found["public_id"] if found else None
    selected = db.lesson(connection, lesson_id)
    if selected is None:
        raise ReviewQueueNotFound("lesson not found")
    if not scope.allows(selected):
        raise ReviewQueueForbidden("lesson is outside scope")
    problems = db.problems(connection, selected)
    chosen = (
        next((p for p in problems if p["public_id"] == problem_id), None)
        if problem_id
        else None
    )
    if problem_id and chosen is None:
        raise ReviewQueueNotFound("problem is outside selected lesson")
    by_number = {}
    for p in problems:
        by_number.setdefault(p["prob"], []).append(p)
    candidates = {}
    for t in db.lesson_threads(connection, selected, pending_only=mode == "pending"):
        case_id = f"st-{t['anchor_id']}"
        # Assign a synonym case once, at its earliest selected task/part.
        candidates.setdefault(case_id, t)
    cases = []
    for case_id, row in candidates.items():
        try:
            value = context(connection, scope, case_id, include_snapshot=False)
        except ReviewQueueNotFound, ReviewQueueForbidden:
            continue
        if mode == "pending" and not value["queues"]:
            continue
        oldest = min(e["server_received_at"] for _, e, _ in value["evidence"])
        cases.append(
            {
                "caseId": case_id,
                "problemId": row["problem_public_id"],
                "number": row["prob"],
                "item": row["item"] or "",
                "studentName": _name(row),
                "submittedAt": oldest,
                "pending": bool(value["queues"]),
            }
        )
    cases.sort(
        key=lambda item: (
            item["number"],
            item["item"],
            item["submittedAt"],
            item["studentName"],
            item["caseId"],
        )
    )
    total = len(cases)
    allowed = chosen is not None or total <= LESSON_LIMIT
    selected_cases = [
        c for c in cases if chosen is None or c["number"] == chosen["prob"]
    ]
    tasks = []
    condition_documents = {}
    for number, parts in by_number.items():
        if chosen is not None and number != chosen["prob"]:
            continue
        tasks.append(
            {
                "problemId": parts[0]["public_id"],
                "label": _label({**parts[0], "item": ""}),
                "count": sum(c["number"] == number for c in cases),
                "parts": [
                    {
                        "problemId": p["public_id"],
                        "label": _label(p),
                        "condition": review_series.condition(
                            connection, scope, p["public_id"],
                            documents=condition_documents,
                        )["document"],
                        "statement": p.get("prob_text") or "",
                    }
                    for p in parts
                ]
                if allowed
                else [],
                "cases": [c for c in selected_cases if c["number"] == number]
                if allowed
                else [],
            }
        )
    return {
        "schemaVersion": 1,
        "lessonId": lesson_id,
        "total": total,
        "limit": LESSON_LIMIT,
        "canOpenLesson": total <= LESSON_LIMIT,
        "tasks": tasks,
    }


def detail(connection, scope, case_id):
    value = context(connection, scope, case_id, allow_empty=True)
    threads, evidence, source = value["threads"], value["evidence"], value["source"]
    branches, evidence_branches = [], []
    seen = set()
    for thread in [row[0] for row in evidence] or [threads[-1]]:
        if thread["id"] in seen:
            continue
        seen.add(thread["id"])
        entries = []
        for t, e, photos in evidence:
            if t["id"] != thread["id"]:
                continue
            entries.append(
                {
                    "entryId": e["public_id"],
                    "entryVersion": e["version"],
                    "entryKind": e["entry_kind"],
                    "text": e["text"],
                    "submittedAt": e["server_received_at"],
                    "attachments": [
                        {"attachmentId": a["public_id"], "ordinal": a["ordinal"]}
                        for a in photos
                    ],
                }
            )
        branches.append(
            {
                "queueId": thread["public_id"],
                "problemId": thread["problem_public_id"],
                "problemNumber": _label(thread).split(" · ")[0],
                "problemTitle": thread["title"],
                "courseId": thread["course_public_id"],
                "courseName": thread["course_name"],
                "groupId": thread["group_public_id"],
                "groupName": thread["group_name"],
                "groupShortCode": thread["short_code"],
                "groupColorKey": thread["color_key"],
                "submittedAt": entries[0]["submittedAt"]
                if entries
                else thread["created_at"],
                "leaseVersion": 0,
            }
        )
        evidence_branches.append(
            {
                "queueId": thread["public_id"],
                "thread": {
                    "threadId": thread["public_id"],
                    "threadVersion": thread["version"],
                    "entries": entries,
                    "timelineEntries": [
                        {**e, "authorKind": "student"} for e in entries
                    ],
                },
            }
        )
    mode = (
        corrections.read_verdict_mode(connection, threads[0]["course_public_id"])
        or DEFAULT_COURSE_RUNTIME_SETTINGS["verdictMode"]
    )
    annotations = (
        []
        if value["queues"] or source is None
        else [
            {
                "schemaVersion": n["schema_version"],
                "attachmentId": n["attachment_public_id"],
                "rotation": n["rotation"],
                "marks": json.loads(n["marks_json"]),
            }
            for n in db.annotations(connection, source["id"])
        ]
    )
    return {
        "schemaVersion": 1,
        "caseId": case_id,
        "snapshot": value["snapshot"],
        "pending": bool(value["queues"]),
        "canReview": bool(evidence),
        "workspace": {
            "logicalCaseId": case_id,
            "student": {
                "studentId": threads[0]["student_public_id"],
                "displayName": _name(threads[0]),
            },
            "branches": branches,
            "evidenceBranches": evidence_branches,
            "verdictMode": mode,
        },
        "annotations": annotations,
        "currentReview": None
        if source is None
        else {
            "reviewId": source["public_id"],
            "verdict": source["verdict"],
            "comment": source["comment"] or "",
            "teacherName": " ".join(
                filter(None, (source["teacher_name"], source["teacher_surname"]))
            ),
            "completedAt": source["created_at"],
        },
    }


def conversation_context(connection, scope, case_id):
    value = context(connection, scope, case_id, allow_empty=True)
    student = archive.require(
        archive_db.student(connection, value["threads"][0]["student_public_id"])
    )
    problems = {
        t["problem_id"]: {
            **t,
            "id": t["problem_id"],
            "public_id": t["problem_public_id"],
        }
        for t in value["threads"]
    }
    return student, list(problems.values())


def conversation(connection, scope, case_id, root, cursor=None):
    student, problems = conversation_context(connection, scope, case_id)
    events = review_conversation.event_index(connection, scope, student, problems)
    start = 0
    if cursor:
        found = next(
            (
                i
                for i, (e, _) in enumerate(events)
                if f"{e['kind']}:{e['id']}" == cursor
            ),
            None,
        )
        if found is None:
            raise ReviewQueueNotFound("conversation cursor not found")
        start = found + 1
    batch = events[start : start + 50]
    payloads = []
    for event, problem in batch:
        payload = archive.event_payload(
            connection,
            event,
            student,
            problem,
            root,
            media_base=f"/staff/api/v1/review/sheet/{case_id}",
        )
        # review-sheet.md: join editable evidence into the one conversation view.
        payload["entryId"] = (
            archive_db.event_record(connection, "entry", event["id"])["public_id"]
            if event["kind"] == "entry"
            else None
        )
        payload["problemNumber"] = _label(problem).split(" · ")[0]
        payloads.append(payload)
    return {
        "schemaVersion": 1,
        "events": payloads,
        "total": len(events),
        "nextCursor": f"{batch[-1][0]['kind']}:{batch[-1][0]['id']}"
        if batch and start + 50 < len(events)
        else None,
    }


def attachment(connection, scope, case_id, attachment_id, *, legacy=False):
    student, problems = conversation_context(connection, scope, case_id)
    for event, _ in review_conversation.event_index(
        connection, scope, student, problems
    ):
        kind, event_id = event["kind"], event["id"]
        if legacy:
            if kind == "discussion" and event_id == attachment_id:
                return archive.require(
                    archive_db.legacy_attachment(
                        connection, student["id"], attachment_id
                    )
                )
            continue
        photos = (
            archive_db.attachments(connection, event_id)
            if kind == "entry"
            else archive_db.annotations(connection, event_id)
            if kind == "review"
            else archive_db.reassigned_materials(connection, event_id)
            if kind == "reassignment"
            else []
        )
        if any(
            a.get("public_id", a.get("attachment_id")) == attachment_id for a in photos
        ):
            return archive.require(
                archive_db.attachment(connection, student["id"], attachment_id)
            )
    raise ReviewQueueNotFound("attachment is outside conversation")


def complete(connection, *, scope, actor, case_id, payload, annotations, now=None):
    """One transaction: authorize, replay, CAS, then append result/evidence/audit."""
    value = context(connection, scope, case_id)
    digest = _digest({"caseId": case_id, **payload})
    replay = db.replay(connection, actor, payload["idempotencyKey"])
    if replay:
        if replay["payload_sha256"] != digest:
            raise ReviewIdempotencyConflict("sheet idempotency payload changed")
        if any(
            not scope.allows(row)
            for row in corrections.evidence_scopes(connection, replay["id"])
        ):
            raise ReviewQueueForbidden("replay evidence is outside scope")
        return _receipt(connection, replay, value["threads"], replayed=True)
    if payload["snapshot"] != value["snapshot"]:
        raise ReviewThreadChanged("sheet result or evidence changed")
    threads, evidence, old = value["threads"], value["evidence"], value["source"]
    mode = (
        corrections.read_verdict_mode(connection, threads[0]["course_public_id"])
        or DEFAULT_COURSE_RUNTIME_SETTINGS["verdictMode"]
    )
    allowed = {
        "verdict_plus_minus": {11, 17},
        "verdict_plus_minus_half": {11, 14, 17},
        "verdict_plus_steps": set(range(11, 18)),
    }[mode]
    verdict = payload["verdict"]
    comment = (payload["comment"] or "").strip() or None
    if verdict not in allowed or (
        verdict < 16 and not comment and not payload["confirmWithoutComment"]
    ):
        raise ReviewCompletionInvalid("invalid verdict or missing comment confirmation")
    reaction = payload["internalReactionId"]
    if reaction is not None and not db.reaction_exists(connection, reaction):
        raise ReviewCompletionInvalid("unsupported internal reaction")
    teacher = db.reviewer(connection, actor)
    if teacher is None:
        raise ReviewQueueForbidden("reviewer no longer exists")
    current = now or datetime.now(UTC)
    current = max(
        current,
        max(
            datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00"))
            for t in threads
        )
        + timedelta(microseconds=1),
    )
    timestamp = _timestamp(current)
    if value["queues"]:
        target, last, _ = max(
            evidence, key=lambda row: (row[1]["server_received_at"], row[1]["id"])
        )
        source = {
            "thread_id": target["id"],
            "thread_version": target["version"],
            "queue_id": value["queues"][0]["id"],
            "evidence_through_entry_id": last["id"],
        }
    else:
        target = next(t for t in threads if t["id"] == old["thread_id"])
        source = {**old, "thread_version": target["version"]}
    result_id = corrections.insert_result(
        connection,
        student_user_id=target["student_user_id"],
        problem_id=target["problem_id"],
        group_id=target["group_id"],
        lesson=target["lesson"],
        reviewer_user_id=actor,
        verdict=verdict,
        created_at=timestamp,
    )
    comment_id = (
        corrections.insert_comment(
            connection,
            thread_id=target["id"],
            author_kind="admin"
            if teacher["type"] & int(USER_TYPE.ADMIN)
            else "teacher",
            author_user_id=actor,
            text=comment,
            created_at=timestamp,
        )
        if comment
        else None
    )
    review_id, public_id = corrections.insert_review(
        connection,
        source=source,
        reviewer_user_id=actor,
        verdict=verdict,
        comment_entry_id=comment_id,
        result_id=result_id,
        idempotency_key=payload["idempotencyKey"],
        payload_sha256=digest,
        created_at=timestamp,
    )
    if value["queues"]:
        db.store_evidence(connection, review_id, evidence)
    else:
        corrections.copy_evidence(
            connection, source_review_id=old["id"], review_id=review_id
        )
    try:
        corrections.store_annotations(connection, review_id, annotations, timestamp)
    except ValueError as error:
        raise ReviewCompletionInvalid(str(error)) from error
    if reaction is not None:
        db.store_reaction(
            connection,
            review_id,
            actor,
            reaction,
            timestamp,
            _timestamp(current + REVIEW_INTERNAL_REACTION_EDIT_WINDOW),
        )
    status = "accepted" if VERDICT(verdict) in VERDICTS_SOLVED else "needs_work"
    if value["queues"]:
        db.finish_pending(
            connection,
            list({t["id"]: t for t, _, _ in evidence}.values()),
            value["queues"],
            target,
            result_id,
            status,
            comment_id is not None,
            timestamp,
        )
    else:
        corrections.update_thread_result(
            connection,
            thread_id=target["id"],
            result_id=result_id,
            current_status=target["status"],
            status=status,
            comment_created=comment_id is not None,
            created_at=timestamp,
        )
    corrections.insert_event(
        connection,
        review_id=review_id,
        payload_json=json.dumps(
            {
                "mode": "sheet",
                "caseId": case_id,
                "reviewPublicId": public_id,
                "studentUserId": target["student_user_id"],
                "targetProblemId": target["problem_id"],
                "evidenceEntryIds": [entry["public_id"] for _, entry, _ in evidence],
                "annotationIds": [
                    n["public_id"] for n in db.annotations(connection, review_id)
                ],
                "internalReactionId": reaction,
                "supersedesReviewPublicId": old["public_id"] if old else None,
                "correctsReviewPublicId": old["public_id"]
                if old and not value["queues"]
                else None,
            }
        ),
        created_at=timestamp,
    )
    stored = db.replay(connection, actor, payload["idempotencyKey"])
    return _receipt(connection, stored, threads, replayed=False)


def _receipt(connection, stored, threads, *, replayed):
    evidence = db.review_receipt_rows(connection, stored["id"])
    owners, families = corrections.recipient_account_public_ids(
        connection, threads[0]["student_user_id"]
    )
    reaction = db.review_reaction(connection, stored["id"])
    return CompleteReviewReceipt(
        review_public_id=stored["public_id"],
        target_thread_public_id=stored["thread_public_id"],
        target_problem_public_id=stored["problem_public_id"],
        target_thread_status="accepted"
        if VERDICT(stored["verdict"]) in VERDICTS_SOLVED
        else "needs_work",
        verdict=stored["verdict"],
        comment_entry_public_id=stored["comment_public_id"],
        evidence_entry_public_ids=tuple(e["public_id"] for e in evidence),
        evidence_problem_public_ids=tuple(
            dict.fromkeys(e["problem_public_id"] for e in evidence)
        ),
        owner_account_public_ids=owners,
        family_account_public_ids=families,
        annotations=tuple(
            ReviewAnnotationReceipt(
                annotation_public_id=n["public_id"],
                attachment_public_id=n["attachment_public_id"],
                schema_version=n["schema_version"],
                rotation=n["rotation"],
                mark_count=len(json.loads(n["marks_json"])),
            )
            for n in db.annotations(connection, stored["id"])
        ),
        internal_reaction=None
        if reaction is None
        else ReviewInternalReactionState(
            review_public_id=stored["public_id"],
            reaction_id=reaction["reaction_id"],
            version=reaction["version"],
            editable_until=datetime.fromisoformat(
                reaction["editable_until"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                reaction["updated_at"].replace("Z", "+00:00")
            ),
        ),
        completed_at=datetime.fromisoformat(
            stored["created_at"].replace("Z", "+00:00")
        ),
        replayed=replayed,
    )
