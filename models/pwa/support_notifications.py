"""Student notification created from a committed Staff support reply."""

from __future__ import annotations

import json
import sqlite3
import uuid

from db_methods.pwa.notifications import (
    active_student_accounts,
    insert_event,
    latest_staff_support_entry,
)


def create_staff_reply_notifications(
    connection: sqlite3.Connection,
    *,
    student_account_public_ids: tuple[str, ...],
    thread_public_id: str,
) -> int:
    entry = latest_staff_support_entry(
        connection,
        thread_public_id=thread_public_id,
    )
    if entry is None:
        return 0

    occurred_at = str(entry["server_received_at"])
    entry_public_id = str(entry["public_id"])
    created = 0
    for account in active_student_accounts(
        connection,
        public_ids=tuple(dict.fromkeys(student_account_public_ids)),
    ):
        if insert_event(
            connection,
            public_id=f"notification.support.{uuid.uuid4().hex}",
            account_id=int(account["id"]),
            category="thread_updated",
            dedupe_key=entry_public_id,
            route=f"/student/questions/{thread_public_id}",
            payload_json=json.dumps(
                {"threadId": thread_public_id, "entryId": entry_public_id},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=occurred_at,
            deliver_after=occurred_at,
            created_at=occurred_at,
        ):
            created += 1
    return created


__all__ = ["create_staff_reply_notifications"]
