"""Private, version-bound proposals; requirements: vmshpwa/docs/ai-review-assistant.md.

Reads never acquire a review lease. Writes touch only assistant tables; ordinary
human completion deliberately has no dependency on this module.
"""

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta

from db_methods.pwa import ai_review as db, review_sheet as sheet_db
from db_methods.pwa import student_results as archive_db
from db_methods.pwa.reviews import (
    ReviewStaffScope,
    ReviewQueueNotFound,
    ReviewQueueForbidden,
)
from helpers.pwa.permissions import (
    Capability,
    StaffScopeGrant,
    StaffScopeRole,
    build_authorization_principal,
)
from models.pwa.auth import AuthAudience
from models.pwa import review_sheet, review_conversation, student_results as archive

VERDICT_IDS = {
    "verdict_plus_minus": {11, 17},
    "verdict_plus_minus_half": {11, 14, 17},
    "verdict_plus_steps": set(range(11, 18)),
}


class AssistantError(ValueError):
    """Transport-independent, secret-free expected failure."""

    def __init__(self, code, status=422):
        self.code = code
        self.status = status
        super().__init__(code)


def timestamp(now=None):
    return (
        (now or datetime.now(UTC))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def scope_for(principal):
    if principal.audience is not AuthAudience.STAFF or not principal.has_capability(
        Capability.REVIEW_READ
    ):
        raise AssistantError("forbidden", 403)
    return ReviewStaffScope(
        global_access=principal.is_global_admin,
        course_public_ids=frozenset(
            g.course_public_id
            for g in principal.staff_scope_grants
            if g.group_public_id is None
        ),
        group_public_ids=frozenset(
            g.group_public_id
            for g in principal.staff_scope_grants
            if g.group_public_id is not None
        ),
    )


def authenticate(connection, secret, *, now=None):
    now = now or datetime.now(UTC)
    if not isinstance(secret, str) or not re.fullmatch(
        r"air_[A-Za-z0-9_-]{43}", secret
    ):
        raise AssistantError("invalid_mcp_token", 401)
    token = db.token_owner(connection, hashlib.sha256(secret.encode()).hexdigest())
    if (
        not token
        or token["revoked_at"]
        or parse_time(token["expires_at"]) <= now
        or token["account_status"] != "active"
        or token["audience"] != "staff"
        or token["credential_version"] != token["current_credential_version"]
    ):
        raise AssistantError("invalid_mcp_token", 401)
    grants = []
    for row in db.staff_grants(connection, token["linked_user_id"]):
        if parse_time(row["valid_from"]) > now or (
            row["valid_to"] and parse_time(row["valid_to"]) <= now
        ):
            continue
        if row["group_id"] is not None and row["group_public_id"] is None:
            raise AssistantError("invalid_mcp_token", 401)
        grants.append(
            StaffScopeGrant(
                row["course_public_id"],
                row["group_public_id"],
                StaffScopeRole(row["role"]),
            )
        )
    try:
        principal = build_authorization_principal(
            account_public_id=token["account_public_id"],
            session_public_id=token["public_id"],
            session_version=1,
            credential_version=token["credential_version"],
            audience=AuthAudience.STAFF,
            linked_user_id=token["linked_user_id"],
            linked_user_type=token["user_type"],
            staff_scope_grants=grants,
        )
    except ValueError as error:
        raise AssistantError("invalid_mcp_token", 401) from error
    return token, principal, scope_for(principal)


def create_token(connection, account_public_id, name, *, credential_version, now=None):
    name = text(name, 100, required=True)
    now = now or datetime.now(UTC)
    secret = "air_" + secrets.token_urlsafe(32)
    public_id = "ait-" + secrets.token_hex(16)
    try:
        token_id = db.insert_token(
            connection,
            public_id=public_id,
            account_public_id=account_public_id,
            name=name,
            secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
            now=timestamp(now),
            expires=timestamp(now + timedelta(days=90)),
            credential_version=credential_version,
        )
    except PermissionError as error:
        raise AssistantError("invalid_mcp_token", 401) from error
    row = db.token_owner(connection, hashlib.sha256(secret.encode()).hexdigest())
    db.event(
        connection,
        account_id=row["account_id"],
        token_id=token_id,
        kind="token_created",
        subject=public_id,
        now=timestamp(now),
    )
    return {"tokenId": public_id, "secret": secret, "expiresAt": row["expires_at"]}


def revoke_token(connection, account_public_id, token_id):
    row = db.revoke_token(connection, account_public_id, token_id, timestamp())
    if not row:
        raise AssistantError("token_not_found", 404)
    db.event(
        connection,
        account_id=row["account_id"],
        token_id=row["id"],
        kind="token_revoked",
        subject=token_id,
        now=timestamp(),
    )


def text(value, limit=100_000, *, required=False):
    if value is None and not required:
        return None
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (required and not value.strip())
    ):
        raise AssistantError("invalid_assistant_payload")
    return value.strip() or None


def canonical_case(connection, scope, *, case_id=None, queue_id=None):
    if queue_id:
        row = db.queue_anchor(connection, queue_id)
        if not row or row["anchor_id"] is None:
            raise AssistantError("unsupported_review", 404)
        case_id = f"st-{row['anchor_id']}"
    threads = sheet_db.case_threads(connection, case_id)
    if not threads:
        raise ReviewQueueNotFound("assistant case not found")
    if any(not scope.allows(t) for t in threads):
        raise ReviewQueueForbidden("assistant case outside scope")
    return f"st-{min(t['anchor_id'] for t in threads)}"


def problem(connection, scope, problem_id, *, revision_id=None):
    row = next(
        (p for p in db.problem_rows(connection) if p["public_id"] == problem_id), None
    )
    if row is None:
        raise ReviewQueueNotFound("problem not found")
    if not scope.allows(row):
        raise ReviewQueueForbidden("problem outside scope")
    materials = {}
    for material in db.learning_materials(connection, row["id"], revision_id):
        kind = material["kind"]
        if kind in materials:
            continue
        document = json.loads(material["content_text"])
        document["problems"] = [
            p
            for p in document.get("problems", [])
            if p.get("ordinal") == material["source_ordinal"]
        ]
        images = db.material_images(connection, material["revision_id"])
        materials[kind] = {
            "revisionId": material["revision_id"],
            "version": material["version"],
            "document": document,
            "answer": json.loads(material["answer_config_json"])
            if material["answer_config_json"]
            else None,
            "answerType": material["answer_type"],
            "images": [
                {
                    "imageId": "content:" + a["public_id"],
                    "name": a["logical_name"],
                    "mimeType": a["media_type"],
                    "sha256": a["sha256"],
                }
                for a in images
            ],
        }
    answer = db.answer_revision(connection, row["id"], revision_id)
    return {
        "problemId": row["public_id"],
        "courseId": row["course_public_id"],
        "groupId": row["group_public_id"],
        "lessonId": row["lesson_id"],
        "title": row["title"],
        "number": str(row["prob"]) + (row["item"] or ""),
        "materials": materials,
        "answer": json.loads(answer["answer_config_json"]) if answer else None,
        "answerRevisionId": answer["revision_id"] if answer else None,
        "answerConfigVersion": answer["config_version"] if answer else None,
        "missingMaterials": [
            kind for kind in ("condition", "hint", "solution") if kind not in materials
        ],
    }


def dialogue_events(connection, scope, student, problems, root):
    """Shared teaching-only export; see ai-review-assistant.md, batch history."""
    events = []
    for index, p in review_conversation.event_index(
        connection, scope, student, problems
    ):
        event = archive.event_payload(connection, index, student, p, root)
        # Only teaching dialogue, never internal reactions/contact/profile data.
        if event["internal"]:
            continue
        photos = []
        for attachment in event["attachments"]:
            aid = attachment["id"]
            annotation = attachment.get("annotation")
            image_id = (
                f"annotation:{event['reviewId']}:{aid}"
                if annotation
                else f"legacy:{aid}"
                if index["kind"] == "discussion"
                else f"attachment:{aid}"
            )
            media_version = None
            if image_id.startswith("legacy:"):
                record = archive_db.legacy_attachment(connection, student["id"], aid)
                path = (
                    archive.legacy_path(root, record["attach_path"])
                    if record and record["attach_path"]
                    else None
                )
                if path:
                    stat = path.stat()
                    media_version = [stat.st_size, stat.st_mtime_ns]
            else:
                metadata = archive_db.attachment(connection, student["id"], aid)
                media_version = metadata["sha256"] if metadata else None
            photos.append(
                {
                    "imageId": image_id,
                    "mediaVersion": media_version,
                    "annotation": annotation,
                    "available": attachment.get("available", True),
                }
            )
        events.append(
            {
                "id": event["id"],
                "at": event["at"],
                "kind": event["kind"],
                "author": event["author"],
                "authorKind": event["authorKind"],
                "source": event["source"],
                "reviewId": event["reviewId"],
                "revisionId": event["revisionId"],
                "checkStatus": event["checkStatus"],
                "text": event["text"],
                "verdict": event["verdict"],
                "problemId": p["public_id"],
                "images": photos,
            }
        )
    return events


def context(connection, scope, case_id, root):
    case_id = canonical_case(connection, scope, case_id=case_id)
    value = review_sheet.context(connection, scope, case_id)
    student, problems = review_sheet.conversation_context(connection, scope, case_id)
    events = dialogue_events(connection, scope, student, problems, root)
    material = []
    for p in problems:
        revisions = {
            e["problem_revision_id"]
            for t, e, _ in value["evidence"]
            if t["problem_id"] == p["id"]
        }
        for revision in sorted(revisions, key=lambda r: r or 0) or [None]:
            material.append(
                problem(connection, scope, p["public_id"], revision_id=revision)
            )
    detail = review_sheet.detail(connection, scope, case_id)
    result = {
        "caseId": case_id,
        "pending": bool(value["queues"]),
        "student": {
            "studentId": student["public_id"],
            "displayName": review_sheet._name(value["threads"][0]),
        },
        "workspace": detail["workspace"],
        "problems": material,
        "verdictMode": detail["workspace"].get("verdictMode", "verdict_plus_steps"),
    }
    result["allowedVerdicts"] = [
        {"id": v["id"], "symbol": v["tick"], "weight": v["val"]}
        for v in db.verdicts(connection, VERDICT_IDS[result["verdictMode"]])
    ]
    result["snapshot"] = digest(
        {
            "work": value["snapshot"],
            "events": events,
            "materials": material,
            "verdictMode": result["verdictMode"],
            "allowedVerdicts": result["allowedVerdicts"],
        }
    )
    return result, events


def require_snapshot(value, expected):
    if expected != value["snapshot"]:
        raise AssistantError("ai_context_changed", 409)


def page(rows, cursor=None, *, key="id"):
    start = 0
    if cursor:
        index = next((i for i, row in enumerate(rows) if str(row[key]) == cursor), None)
        if index is None:
            raise AssistantError("invalid_cursor")
        start = index + 1
    batch = rows[start : start + 50]
    return {
        "items": batch,
        "nextCursor": str(batch[-1][key]) if batch and start + 50 < len(rows) else None,
    }


def suggestion_payload(row, snapshot):
    return {
        "suggestionId": row["public_id"],
        "snapshot": row["snapshot"],
        "comment": row["comment"],
        "verdict": row["verdict"],
        "analysis": row["analysis"],
        "source": row["source"],
        "model": row["model"],
        "createdAt": row["created_at"],
        "isCurrent": row["snapshot"] == snapshot,
    }


def list_suggestions(
    connection, scope, root, *, case_id=None, queue_id=None, cursor=None
):
    case_id = canonical_case(connection, scope, case_id=case_id, queue_id=queue_id)
    value, _ = context(connection, scope, case_id, root)
    before = None
    if cursor:
        if not cursor.isascii() or not cursor.isdigit() or len(cursor) > 18:
            raise AssistantError("invalid_cursor")
        before = int(cursor)
    rows = db.suggestions(connection, case_id, before)
    evidence_key = "|".join(
        sorted(
            f"{b['thread']['threadId']}@{b['thread']['threadVersion']}:"
            + ",".join(
                f"{e['entryId']}@{e['entryVersion']}" for e in b["thread"]["entries"]
            )
            for b in value["workspace"]["evidenceBranches"]
            if b["thread"]
        )
    )
    return {
        "caseId": case_id,
        "snapshot": value["snapshot"],
        "pending": value["pending"],
        "evidenceKey": evidence_key,
        "items": [
            suggestion_payload(r, value["snapshot"] if value["pending"] else None)
            for r in rows[:50]
        ],
        "nextCursor": str(rows[49]["id"]) if len(rows) > 50 else None,
    }


def submit(connection, scope, token, payload, root):
    if not isinstance(payload, dict) or set(payload) - {
        "caseId",
        "snapshot",
        "idempotencyKey",
        "comment",
        "verdict",
        "analysis",
        "source",
        "model",
    }:
        raise AssistantError("invalid_assistant_payload")
    values = {
        "case_id": text(payload.get("caseId"), 128, required=True),
        "snapshot": text(payload.get("snapshot"), 64, required=True),
        "idempotency_key": text(payload.get("idempotencyKey"), 128, required=True),
        "comment": text(payload.get("comment")),
        "analysis": text(payload.get("analysis")),
        "source": text(payload.get("source"), 200, required=True),
        "model": text(payload.get("model"), 200),
        "verdict": payload.get("verdict"),
    }
    if len(values["snapshot"]) != 64 or not any(
        values[k] is not None for k in ("comment", "analysis", "verdict")
    ):
        raise AssistantError("invalid_assistant_payload")
    values["case_id"] = canonical_case(connection, scope, case_id=values["case_id"])
    payload_hash = digest(values)
    previous = db.existing_suggestion(
        connection, token["id"], values["idempotency_key"]
    )
    if previous:
        if previous["payload_hash"] != payload_hash:
            raise AssistantError("idempotency_conflict", 409)
        # Replays after completion return the original receipt without a second write.
        return {"suggestionId": previous["public_id"], "replayed": True}
    value, _ = context(connection, scope, values["case_id"], root)
    if not value["pending"]:
        raise AssistantError("review_not_pending", 409)
    require_snapshot(value, values["snapshot"])
    allowed = VERDICT_IDS[value["verdictMode"]]
    if values["verdict"] is not None and (
        type(values["verdict"]) is not int or values["verdict"] not in allowed
    ):
        raise AssistantError("invalid_suggested_verdict")
    public_id = "ais-" + secrets.token_hex(16)
    db.insert_suggestion(
        connection,
        {
            **values,
            "case_thread_id": int(values["case_id"].removeprefix("st-")),
            "public_id": public_id,
            "token_id": token["id"],
            "payload_hash": payload_hash,
            "created_at": timestamp(),
        },
    )
    db.event(
        connection,
        account_id=token["account_id"],
        token_id=token["id"],
        kind="suggestion_uploaded",
        subject=public_id,
        now=timestamp(),
    )
    return {"suggestionId": public_id, "replayed": False}


def catalog(connection, scope, tool, query):
    if tool == "list_problems":
        rows = [
            {
                "id": p["public_id"],
                "title": p["title"],
                "courseId": p["course_public_id"],
                "groupId": p["group_public_id"],
                "lessonId": p["lesson_id"],
            }
            for p in db.problem_rows(connection)
            if scope.allows(p)
        ]
    else:
        rows = []
        seen = set()
        source = (
            sheet_db.lessons(connection)
            if tool == "list_lessons" or query.get("lessonId")
            else db.course_groups(connection)
        )
        for row in source:
            if not scope.allows(row):
                continue
            item = {
                "courseId": row["course_public_id"],
                "groupId": row["group_public_id"],
                "lessonId": row.get("lesson_id"),
            }
            if not matches(item, query):
                continue
            identity = row[
                {
                    "list_courses": "course_public_id",
                    "list_groups": "group_public_id",
                    "list_lessons": "lesson_id",
                }[tool]
            ]
            if identity is None:
                continue
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "id": identity,
                    **(
                        {"courseId": item["courseId"], "name": row["group_name"]}
                        if tool == "list_groups"
                        else {"name": row["course_name"]}
                        if tool == "list_courses"
                        else {
                            **item,
                            "number": row["lesson"],
                            "groupName": row["group_name"],
                        }
                    ),
                }
            )
    return page(
        [r for r in rows if tool != "list_problems" or matches(r, query)],
        query.get("cursor"),
    )


def matches(item, query):
    return all(
        query.get(k) is None or item.get(k) == query[k]
        for k in ("courseId", "groupId", "lessonId", "problemId")
    )


def pending(connection, scope, root, query):
    rows = []
    seen = set()
    after_cursor = query.get("cursor") is None
    for row in db.pending_cases(connection):
        if not scope.allows(row):
            continue
        item = {
            "queueId": row["queue_id"],
            "problemId": row["problem_id"],
            "studentId": row["student_id"],
            "courseId": row["course_public_id"],
            "groupId": row["group_public_id"],
            "lessonId": row["lesson_id"],
            "submittedAt": row["submitted_at"],
        }
        if not matches(item, query):
            continue
        case_id = f"st-{row['anchor_id']}" if row["anchor_id"] else None
        identity = case_id or row["queue_id"]
        if identity in seen:
            continue
        seen.add(identity)
        if not after_cursor:
            if identity == query["cursor"]:
                after_cursor = True
            continue
        supported = False
        has_suggestions = False
        if case_id:
            try:
                value, _ = context(connection, scope, case_id, root)
            except ReviewQueueForbidden:
                continue
            except ReviewQueueNotFound:
                pass
            else:
                supported = value["pending"]
                has_suggestions = db.has_current_suggestion(
                    connection, case_id, value["snapshot"]
                )
        if query.get("suggestions") == "with" and not has_suggestions:
            continue
        if query.get("suggestions") == "without" and has_suggestions:
            continue
        rows.append(
            {
                **item,
                "id": identity,
                "caseId": case_id,
                "supported": supported,
                "unsupportedReason": None
                if supported
                else "legacy_or_incomplete_evidence",
                "hasCurrentSuggestions": has_suggestions,
            }
        )
        if len(rows) > 50:
            break
    if not after_cursor:
        raise AssistantError("invalid_cursor")
    return {
        "items": rows[:50],
        "nextCursor": rows[49]["id"] if len(rows) > 50 else None,
    }


def read_tool(connection, scope, root, tool, query):
    if tool.startswith("list_") and tool in {
        "list_courses",
        "list_groups",
        "list_lessons",
        "list_problems",
    }:
        return catalog(connection, scope, tool, query)
    if tool == "get_problem":
        return problem(connection, scope, query["problemId"])
    if tool == "list_pending_reviews":
        return pending(connection, scope, root, query)
    if tool == "list_ai_suggestions":
        return list_suggestions(
            connection, scope, root, case_id=query["caseId"], cursor=query.get("cursor")
        )
    from models.pwa import ai_review_exports as exports

    if tool == "list_review_comments":
        return exports.comments(connection, scope, root, query)
    if tool == "get_problem_submissions":
        return exports.submissions(connection, scope, root, query)
    if tool in {"get_previous_lesson_materials", "get_lesson_material_image"}:
        from models.pwa import ai_review_curriculum as curriculum

        if tool == "get_previous_lesson_materials":
            return curriculum.previous_materials(connection, scope, query)
        return curriculum.material_image(connection, scope, query)
    history = query["caseId"].startswith("history-")
    value, events = (
        exports.history_context(connection, scope, query["caseId"], root)
        if history
        else context(connection, scope, query["caseId"], root)
    )
    if tool == "get_review_context":
        return {**value, "dialogueCount": len(events)}
    require_snapshot(value, query["snapshot"])
    if tool == "get_review_dialogue":
        return {**page(events, query.get("cursor")), "snapshot": value["snapshot"]}
    if tool == "get_review_image":
        return image_metadata(connection, scope, value, events, query["imageId"])
    raise AssistantError("unknown_tool", 404)


def image_metadata(connection, scope, value, events, image_id):
    for p in value["problems"]:
        for material in p["materials"].values():
            if any(a["imageId"] == image_id for a in material["images"]):
                aid = image_id.removeprefix("content:")
                return {
                    "storage": next(
                        a
                        for a in db.material_images(connection, material["revisionId"])
                        if a["public_id"] == aid
                    )
                }
    for event in events:
        image = next((a for a in event["images"] if a["imageId"] == image_id), None)
        if image is None:
            continue
        if image_id.startswith("legacy:"):
            if value["caseId"].startswith("history-"):
                return {
                    "legacyPath": archive.require(
                        archive_db.legacy_attachment(
                            connection,
                            int(value["caseId"].split("-")[1]),
                            image_id.removeprefix("legacy:"),
                        )
                    )["attach_path"]
                }
            metadata = review_sheet.attachment(
                connection,
                scope,
                value["caseId"],
                image_id.removeprefix("legacy:"),
                legacy=True,
            )
            return {"legacyPath": metadata["attach_path"]}
        aid = image_id.split(":")[-1]
        # Public attachment IDs currently have no colon; resolve annotations
        # from the authorized dialogue manifest rather than arbitrary review IDs.
        if image["annotation"]:
            aid = image["annotation"]["attachmentId"]
        metadata = (
            archive.require(
                archive_db.attachment(
                    connection, int(value["caseId"].split("-")[1]), aid
                )
            )
            if value["caseId"].startswith("history-")
            else review_sheet.attachment(connection, scope, value["caseId"], aid)
        )
        return {"storage": metadata, "annotation": image["annotation"]}
    raise AssistantError("image_not_found", 404)
