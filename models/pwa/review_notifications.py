"""Notification rule applied after a written review has committed."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from db_methods.pwa.notifications import (
    active_student_accounts,
    insert_event,
    pending_review_batch,
    update_review_batch,
)


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _unique_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value if isinstance(item, str)))


def record_review_notifications(
    connection: sqlite3.Connection,
    *,
    account_public_ids: tuple[str, ...],
    review_public_id: str,
    problem_public_ids: tuple[str, ...],
    completed_at: datetime,
) -> int:
    """Append one completed review to each owner's open 30-minute batch."""

    occurred_at = _timestamp(completed_at)
    created = 0
    for account in active_student_accounts(
        connection,
        public_ids=tuple(dict.fromkeys(account_public_ids)),
    ):
        account_id = int(account["id"])
        batch = pending_review_batch(
            connection,
            account_id=account_id,
            occurred_at=occurred_at,
        )
        if batch is not None:
            payload = json.loads(str(batch["payload_json"]))
            review_ids = _unique_strings(payload.get("reviewIds"))
            if review_public_id in review_ids:
                continue
            problem_ids = _unique_strings(payload.get("problemIds"))
            review_ids.append(review_public_id)
            problem_ids.extend(
                problem_id
                for problem_id in problem_public_ids
                if problem_id not in problem_ids
            )
            update_review_batch(
                connection,
                event_id=int(batch["id"]),
                payload_json=json.dumps(
                    {
                        "count": len(review_ids),
                        "reviewIds": review_ids,
                        "problemIds": problem_ids,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                occurred_at=occurred_at,
            )
            continue

        if insert_event(
            connection,
            account_id=account_id,
            category="review_completed",
            dedupe_key=review_public_id,
            route="/student/notifications",
            payload_json=json.dumps(
                {
                    "count": 1,
                    "reviewIds": [review_public_id],
                    "problemIds": list(dict.fromkeys(problem_public_ids)),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=occurred_at,
            deliver_after=_timestamp(completed_at + timedelta(minutes=30)),
            created_at=occurred_at,
        ):
            created += 1
    return created


__all__ = ["record_review_notifications"]
