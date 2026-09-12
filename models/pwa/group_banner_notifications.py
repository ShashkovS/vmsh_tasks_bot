"""Create scheduled device notifications for group announcements."""

from __future__ import annotations

import html
import json
import re
import sqlite3

from db_methods.pwa.notifications import active_group_notification_accounts, insert_event
from models.pwa.rich_document import rich_document_plain_text


_CATEGORY = "group_announcement"
_HTML_TAG = re.compile(r"<[^>]*>")
_WHITESPACE = re.compile(r"\s+")


def _plain_text(item: dict[str, object]) -> str:
    """Return a bounded trustworthy push excerpt for the stored announcement."""

    if item.get("content_format") == "rich_markdown_v1":
        try:
            document = json.loads(str(item["rich_document_json"]))
            if isinstance(document, dict):
                return rich_document_plain_text(document).strip()[:500]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    text = html.unescape(_HTML_TAG.sub(" ", str(item["html_sanitized"])))
    return _WHITESPACE.sub(" ", text).strip()[:500]


def _remove_future_events(
    connection: sqlite3.Connection, *, banner_public_id: str, now: str
) -> None:
    """Future announcement events have no delivery rows yet and are safe to replace."""

    connection.execute(
        "DELETE FROM notification_events "
        "WHERE category = ? AND dedupe_key = ? AND deliver_after > ?",
        (_CATEGORY, banner_public_id, now),
    )


def sync_group_banner_notifications(
    connection: sqlite3.Connection,
    *,
    banner: dict[str, object],
    now: str,
) -> int:
    """Schedule one in-app/Web Push event per eligible recipient.

    Before the announcement is due, edits replace the scheduled notifications.
    Once it is due, an edit changes only the banner itself: it must not re-send a
    message that a recipient may already have received.
    """

    banner_public_id = str(banner["public_id"])
    _remove_future_events(connection, banner_public_id=banner_public_id, now=now)
    if banner.get("status") != "active":
        return 0

    starts_at = str(banner["starts_at"])
    deliver_after = starts_at if starts_at > now else now
    selected_audiences = (
        {"student", "family"}
        if banner["audience"] == "both"
        else {str(banner["audience"])}
    )
    group_id = str(banner["group_id"])
    group = connection.execute(
        "SELECT course_id FROM groups WHERE group_id = ?", (group_id,)
    ).fetchone()
    if group is None:
        raise ValueError("group banner references a missing group")
    recipients = {
        int(item["account_id"]): str(item["audience"])
        for item in active_group_notification_accounts(
            connection,
            course_id=int(group["course_id"]),
            group_id=group_id,
        )
        if str(item["audience"]) in selected_audiences
    }
    payload_json = json.dumps(
        {
            "bannerId": banner_public_id,
            "courseId": banner["course_public_id"],
            "groupId": banner["group_public_id"],
            "groupName": banner["group_name"],
            "text": _plain_text(banner),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    created = 0
    for account_id, audience in recipients.items():
        if insert_event(
            connection,
            account_id=account_id,
            category=_CATEGORY,
            dedupe_key=banner_public_id,
            route=f"/{audience}/",
            payload_json=payload_json,
            occurred_at=deliver_after,
            deliver_after=deliver_after,
            created_at=now,
        ):
            created += 1
    return created


__all__ = ["sync_group_banner_notifications"]
