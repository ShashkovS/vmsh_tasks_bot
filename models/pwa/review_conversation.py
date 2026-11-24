"""Scoped full conversation; authoritative flow: vmshpwa/docs/review-history.md."""

from db_methods.pwa import review_conversation as db
from db_methods.pwa import student_results as archive_db
from models.pwa import student_results as archive

# Reuse the archive's deduplication and submitted-material rules without its
# admin-only reactions/audit feed. Correction evidence remains independent.
CONVERSATION_KINDS = frozenset(
    {"entry", "discussion", "review", "test", "result", "reassignment"}
)


def authorized_context(c, scope, actor, is_admin, review_id):
    review, problems = archive.require(db.context(c, scope, actor, is_admin, review_id))
    student = archive.require(archive_db.student(c, review["student_id"]))
    return student, problems


def event_index(c, scope, student, problems):
    indexed = {}
    for problem in problems:
        for event in archive_db.event_index(c, student["id"], problem["id"]):
            kind = event["kind"]
            if kind not in CONVERSATION_KINDS:
                continue
            if kind == "review" and not db.review_in_scope(c, scope, event["id"]):
                continue
            if kind == "reassignment" and not all(
                scope.allows(row) for row in db.reassignment_scopes(c, event["id"])
            ):
                continue
            indexed.setdefault((kind, event["id"]), (event, problem))
    return sorted(
        indexed.values(),
        key=lambda item: (
            item[0]["sort_ts"] if item[0]["sort_ts"] is not None else float("-inf"),
            item[0]["ts"],
            item[0]["kind"],
            item[0]["id"],
        ),
    )


def history(c, scope, actor, is_admin, review_id, root, cursor=None):
    student, problems = authorized_context(c, scope, actor, is_admin, review_id)
    events = event_index(c, scope, student, problems)
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
            raise archive.ArchiveNotFound()
        start = found + 1
    batch = events[start : start + 50]
    payloads = []
    for event, problem in batch:
        payload = archive.event_payload(
            c,
            event,
            student,
            problem,
            root,
            media_base=f"/staff/api/v1/review/history/{review_id}",
        )
        payload["problemNumber"] = (
            f"{problem['lesson']}{problem['short_code']}.{problem['prob']}{problem['item'] or ''}"
        )
        payloads.append(payload)
    return {
        "events": payloads,
        "nextCursor": f"{batch[-1][0]['kind']}:{batch[-1][0]['id']}"
        if batch and start + 50 < len(events)
        else None,
        "total": len(events),
    }


def attachment(c, scope, actor, is_admin, review_id, attachment_id, *, legacy=False):
    student, problems = authorized_context(c, scope, actor, is_admin, review_id)
    for event, _ in event_index(c, scope, student, problems):
        kind, event_id = event["kind"], event["id"]
        if legacy:
            if kind == "discussion" and event_id == attachment_id:
                return archive.require(
                    archive_db.legacy_attachment(c, student["id"], attachment_id)
                )
            continue
        attachments = (
            archive_db.attachments(c, event_id)
            if kind == "entry"
            else archive_db.annotations(c, event_id)
            if kind == "review"
            else archive_db.reassigned_materials(c, event_id)
            if kind == "reassignment"
            else []
        )
        if any(
            a.get("public_id", a.get("attachment_id")) == attachment_id
            for a in attachments
        ):
            return archive.require(
                archive_db.attachment(c, student["id"], attachment_id)
            )
    raise archive.ArchiveNotFound()
