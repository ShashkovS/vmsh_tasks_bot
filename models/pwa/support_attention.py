"""Answer visibility decisions; see vmshpwa/docs/question-attention.md."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from db_methods.pwa import support_attention as db
from db_methods.pwa.support import (
    SupportAuthorKind,
    SupportEntryRecord,
    SupportForbidden,
    SupportNotFound,
)


def attention_payload(
    *,
    last_human_author: SupportAuthorKind | None,
    unread_count: int,
    first_unread_id: str | None,
) -> dict[str, str | int | None]:
    return {
        "attentionState": (
            "unread_reply"
            if unread_count
            else "awaiting_reply"
            if last_human_author == "student"
            else "none"
        ),
        "unreadReplyCount": unread_count,
        "firstUnreadEntryId": first_unread_id,
    }


def thread_attention(
    entries: Sequence[SupportEntryRecord],
) -> dict[str, str | int | None]:
    humans = [e for e in entries if e.author_kind != "system"]
    unread = [
        e
        for e in entries
        if e.author_kind in {"teacher", "admin"} and e.read_at is None
    ]
    return attention_payload(
        last_human_author=humans[-1].author_kind if humans else None,
        unread_count=len(unread),
        first_unread_id=unread[0].entry_public_id if unread else None,
    )


def acknowledge(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    thread_public_id: str,
    entry_ids: tuple[str, ...],
    session_id: int | None,
    now: str,
) -> list[dict[str, str]]:
    thread = db.thread_owner(connection, thread_public_id)
    if thread is None:
        raise SupportNotFound("support thread was not found")
    if thread["student_user_id"] != student_user_id:
        raise SupportForbidden("support thread belongs to another Student")
    rows = db.reply_rows(connection, entry_ids)
    if len(rows) != len(entry_ids) or any(r["thread_id"] != thread["id"] for r in rows):
        raise SupportNotFound("support reply was not found")
    if any(r["author_kind"] not in {"teacher", "admin"} for r in rows):
        raise ValueError("only Staff replies can be acknowledged")
    receipts = []
    for row in rows:
        read_at = db.save_read(
            connection,
            entry_id=row["id"],
            student_user_id=student_user_id,
            now=max(now, row["server_received_at"]),
        )
        db.read_matching_notifications(
            connection,
            entry_public_id=row["public_id"],
            student_user_id=student_user_id,
            session_id=session_id,
            now=read_at,
        )
        receipts.append({"entryId": row["public_id"], "readAt": read_at})
    return receipts


def next_attention(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    now: str,
    after_thread_id: str | None = None,
) -> dict[str, object]:
    targets = db.unread_targets(connection, student_user_id=student_user_id, now=now)
    index = next(
        (i + 1 for i, t in enumerate(targets) if t["threadId"] == after_thread_id), 0
    )
    return {
        "unreadTaskCount": len(targets),
        "nextTarget": dict(targets[index % len(targets)]) if targets else None,
    }
