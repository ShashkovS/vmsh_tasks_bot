"""Lease/version policy for whole-entry routing; docs/serial-review-feed.md."""

import hashlib
import json
from datetime import UTC, datetime
from helpers.consts import VERDICT, VERDICTS_SOLVED

from db_methods.pwa import review_transfers as storage
from db_methods.pwa.reviews import (
    _case_rows,
    _active_pwa_claim,
    _active_legacy_claim,
    ReviewQueueForbidden,
    ReviewLeaseConflict,
    _timestamp,
)


class ReviewTransferChanged(ReviewLeaseConflict):
    """The preview, pending material or source lease no longer matches."""


def context(connection, *, entry_id, queue_id, claim_token, actor, scope, now):
    src = storage.source(connection, entry_id)
    if src is None or not scope.allows(src):
        raise ReviewQueueForbidden("entry is outside scope")
    _, rows = _case_rows(connection, queue_public_id=queue_id)
    if not any(
        r["problem_id"] == src["problem_id"]
        and r["student_id"] == src["student_user_id"]
        for r in rows
    ):
        raise ReviewQueueForbidden("entry does not belong to claimed case")
    if any(not scope.allows(r) for r in rows):
        raise ReviewQueueForbidden("case is outside scope")
    if any(
        not _active_pwa_claim(r, now=now)
        or r["claim_token"] != claim_token
        or r["teacher_id"] != actor
        for r in rows
    ):
        raise ReviewTransferChanged("source lease changed")
    if (
        src["reviewed"]
        or src["thread_status"] == "closed"
        or src["state"] != "submitted"
        or src["author_kind"] != "student"
        or src["entry_kind"] not in ("submission", "text")
    ):
        raise ReviewTransferChanged("only an unreviewed submitted entry can be routed")
    if src["was_reassigned"]:
        raise ReviewTransferChanged(
            "partially reassigned material cannot be routed as a whole"
        )
    photos = storage.attachments(connection, src["id"])
    if any(p["upload_status"] != "stored" for p in photos):
        raise ReviewTransferChanged("attachments changed")
    return src, photos, storage.targets(connection, src)


def preview(connection, *, entry_id, queue_id, claim_token, actor, scope, now=None):
    src, photos, targets = context(
        connection,
        entry_id=entry_id,
        queue_id=queue_id,
        claim_token=claim_token,
        actor=actor,
        scope=scope,
        now=now or datetime.now(UTC),
    )
    return {
        "schemaVersion": 1,
        "entryId": entry_id,
        "sourceVersion": src["thread_version"],
        "entryVersion": src["version"],
        "studentName": f"{src['name'] or ''} {src['surname'] or ''}".strip(),
        "sourceLabel": storage.label(src),
        "photoCount": len(photos),
        "targets": [
            {
                "problemId": t["public_id"],
                "label": storage.label(t),
                "threadVersion": t["thread_version"],
                "threadId": t["thread_public_id"],
            }
            for t in targets
        ],
    }


def execute(connection, *, payload, queue_id, actor, scope, notices, now=None):
    now = now or datetime.now(UTC)
    digest = hashlib.sha256(
        json.dumps({"queue": queue_id, **payload}, sort_keys=True).encode()
    ).hexdigest()
    # Check current source scope even on replay; revoked assignments stay revoked.
    src = storage.source(connection, payload["entryId"])
    if src is None or not scope.allows(src):
        raise ReviewQueueForbidden("entry is outside scope")
    replay = storage.replay(connection, actor, payload["idempotencyKey"])
    if replay:
        if replay["payload_sha256"] != digest:
            raise ReviewLeaseConflict("idempotency payload mismatch")
        return json.loads(replay["response_json"])
    src, photos, targets = context(
        connection,
        entry_id=payload["entryId"],
        queue_id=queue_id,
        claim_token=payload["claimToken"],
        actor=actor,
        scope=scope,
        now=now,
    )
    target = next(
        (t for t in targets if t["public_id"] == payload["targetProblemId"]), None
    )
    if target is None:
        raise ReviewQueueForbidden(
            "target is not an eligible same-lesson written problem"
        )
    if (
        src["thread_version"] != payload["sourceVersion"]
        or src["version"] != payload["entryVersion"]
        or target["thread_version"] != payload["targetVersion"]
        or target["thread_public_id"] != payload["targetThreadId"]
    ):
        raise ReviewTransferChanged("preview versions changed")
    queued = storage.queued_target_case(
        connection, src["student_user_id"], target["id"]
    )
    if queued:
        _, rows = _case_rows(connection, queue_public_id=queued["public_id"])
        if any(not scope.allows(r) for r in rows):
            raise ReviewQueueForbidden("target case is outside scope")
        if any(
            _active_pwa_claim(r, now=now) or _active_legacy_claim(r, now=now)
            for r in rows
        ):
            raise ReviewLeaseConflict("target is currently being reviewed")
    response = storage.commit(
        connection,
        src,
        target,
        photos,
        actor=actor,
        key=payload["idempotencyKey"],
        digest=digest,
        mode=payload["mode"],
        now=_timestamp(now),
        notices=tuple(
            text.format(source=storage.label(src), target=storage.label(target))
            for text in notices
        ),
        empty_source_status=(
            "closed"
            if src["latest_verdict"] is None
            else "accepted"
            if VERDICT(src["latest_verdict"]) in VERDICTS_SOLVED
            else "needs_work"
        ),
    )
    if payload["mode"] == "move":
        # A move advances the series. Release every surviving synonym branch,
        # including other pending entries, rather than abandoning its lease.
        storage.release_remaining(
            connection,
            actor,
            payload["claimToken"],
            _timestamp(now),
        )
    return response
