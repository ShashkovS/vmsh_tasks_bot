"""Private organizer dialogue policy; vmshpwa/docs/organizer-questions.md."""

import hashlib
import json
from datetime import UTC, datetime

from db_methods.pwa import organizer_questions as db
from db_methods.pwa.notifications import insert_event


class OrganizerError(Exception):
    def __init__(self, code="not_found"):
        self.code = code


def identity(c, principal):
    account = db.account(c, principal.account_public_id)
    if account is None or account["status"] != "active":
        raise OrganizerError("forbidden")
    if account["audience"] == "staff" and not principal.is_global_admin:
        raise OrganizerError("forbidden")
    return account


def authorized(c, principal, question_id):
    a = identity(c, principal)
    q = db.question(c, question_id)
    if q is None or (a["audience"] != "staff" and q["owner_account_id"] != a["id"]):
        raise OrganizerError()
    return a, q


def summary(q):
    return dict(
        threadId=q["public_id"],
        title=(q["first_text"] or "Фотография")[:100],
        owner=dict(
            accountId=q["owner_public_id"],
            name=q["owner_name"],
            audience=q["owner_audience"],
        ),
        child=None
        if q["child_public_id"] is None
        else dict(studentId=q["child_public_id"], name=q["child_name"]),
        state="awaiting_staff"
        if q["latest_author"] == q["owner_account_id"]
        else "answered",
        latestText=q["latest_text"],
        latestAt=q["latest_at"],
        latestEntryId=q["latest_entry_id"],
    )


def listing(c, p, state, cursor):
    a = identity(c, p)
    owner_id = None if a["audience"] == "staff" else a["id"]
    items = db.listing(c, owner_id, state, cursor)
    return dict(
        items=[summary(q) for q in items[:50]],
        nextCursor=str(items[49]["latest_entry_id"]) if len(items) > 50 else None,
        unreadCount=db.counts(c, owner_id),
    )


def photo_view(photo, audience):
    return dict(
        photoId=photo["public_id"],
        url=f"/{audience}/api/v1/organizer-questions/photos/{photo['public_id']}",
        width=photo["width"],
        height=photo["height"],
    )


def thread(c, p, public_id, after=0):
    a, q = authorized(c, p, public_id)
    entries = db.entries(c, q["id"], after)
    return dict(
        thread=summary(q),
        entries=[
            dict(
                entryId=e["public_id"],
                sequence=e["id"],
                text=e["text"],
                author=dict(name=e["author_name"], audience=e["audience"]),
                createdAt=e["created_at"],
                photos=[
                    photo_view(photo, a["audience"]) for photo in db.photos(c, e["id"])
                ],
            )
            for e in entries[:50]
        ],
        nextCursor=str(entries[49]["id"]) if len(entries) > 50 else None,
    )


def validate(payload):
    required = {"text", "photoIds", "idempotencyKey", "childId"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise OrganizerError("validation_error")
    text, photos, key, child = (
        payload[k] for k in ("text", "photoIds", "idempotencyKey", "childId")
    )
    if (
        not isinstance(text, str)
        or len(text) > 100000
        or not isinstance(photos, list)
        or len(photos) > 10
        or any(not isinstance(x, str) for x in photos)
        or len(set(photos)) != len(photos)
    ):
        raise OrganizerError("validation_error")
    if (
        not isinstance(key, str)
        or not 1 <= len(key) <= 200
        or not key.strip()
        or (child is not None and not isinstance(child, str))
        or not (text.strip() or photos)
    ):
        raise OrganizerError("validation_error")


def send(c, p, public_id, payload):
    validate(payload)
    a = identity(c, p)
    q = authorized(c, p, public_id)[1] if public_id else None
    if q is None and a["audience"] == "staff":
        raise OrganizerError("forbidden")
    digest = hashlib.sha256(
        json.dumps([public_id, payload], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    previous = db.replay(c, a["id"], payload["idempotencyKey"])
    if previous:
        if previous["payload_sha256"] != digest:
            raise OrganizerError("idempotency_conflict")
        return previous["question_public_id"]
    child_id = a["linked_user_id"] if a["audience"] == "student" else None
    if payload["childId"] is not None:
        if q is not None or a["audience"] != "family":
            raise OrganizerError("validation_error")
        child = db.child(c, a["id"], payload["childId"])
        if child is None:
            raise OrganizerError("forbidden")
        child_id = child["id"]
    photos = [db.photo(c, photo_id) for photo_id in payload["photoIds"]]
    if any(
        photo is None
        or photo["uploader_account_id"] != a["id"]
        or photo["entry_id"] is not None
        for photo in photos
    ):
        raise OrganizerError("forbidden")
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    qid = q["id"] if q else db.create_question(c, a["id"], child_id, now)
    eid = db.insert_entry(
        c,
        qid,
        a["id"],
        payload["text"].strip(),
        now,
        payload["idempotencyKey"],
        digest,
        [photo["id"] for photo in photos],
    )
    public_id = f"oq-{qid}"
    if a["audience"] == "staff":
        insert_event(
            c,
            account_id=q["owner_account_id"],
            category="thread_updated",
            dedupe_key=f"organizer-{eid}",
            route=f"/{q['owner_audience']}/organizers/{public_id}",
            payload_json=json.dumps(dict(threadId=public_id, entryId=f"oqe-{eid}")),
            occurred_at=now,
            deliver_after=now,
            created_at=now,
        )
    return public_id


def read(c, p, public_id, sequence, session_id):
    a, q = authorized(c, p, public_id)
    if (
        a["audience"] == "staff"
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 0 <= sequence <= q["latest_entry_id"]
    ):
        raise OrganizerError("validation_error")
    db.mark_read(
        c,
        q["id"],
        sequence,
        a["id"],
        session_id,
        datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )


def photo_access(c, p, public_id):
    a = identity(c, p)
    photo = db.photo(c, public_id)
    if photo is None:
        raise OrganizerError()
    if photo["entry_id"] is None:
        if photo["uploader_account_id"] != a["id"]:
            raise OrganizerError()
    else:
        authorized(c, p, photo["question_public_id"])
    return photo
