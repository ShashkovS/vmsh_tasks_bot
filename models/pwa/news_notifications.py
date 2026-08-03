"""Create account-scoped notification events for a newly mirrored post."""

from __future__ import annotations

import json
import sqlite3
import uuid

from db_methods.pwa.news import (
    get_post,
    list_news_recipient_accounts,
    news_course_public_id,
)
from db_methods.pwa.notifications import insert_event


def create_news_notifications(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    now: str,
    deliver_after: str | None = None,
) -> int:
    post = get_post(connection, post_id)
    if post is None:
        raise ValueError("news post does not exist")
    recipients = list_news_recipient_accounts(
        connection,
        owner_course_id=(
            None if post["owner_course_id"] is None else int(post["owner_course_id"])
        ),
        owner_group_id=(
            None if post["owner_group_id"] is None else str(post["owner_group_id"])
        ),
    )
    course_public_id = news_course_public_id(
        connection,
        owner_course_id=(
            None if post["owner_course_id"] is None else int(post["owner_course_id"])
        ),
        owner_group_id=(
            None if post["owner_group_id"] is None else str(post["owner_group_id"])
        ),
    )
    created = 0
    for recipient in recipients:
        audience = str(recipient["audience"])
        if insert_event(
            connection,
            public_id=f"notification.news.{uuid.uuid4().hex}",
            account_id=int(recipient["id"]),
            category="news",
            dedupe_key=str(post["public_id"]),
            route=f"/{audience}/news/{post['public_id']}",
            payload_json=json.dumps(
                {"postId": post["public_id"], "courseId": course_public_id},
                separators=(",", ":"),
            ),
            occurred_at=deliver_after or now,
            deliver_after=deliver_after or now,
            created_at=now,
        ):
            created += 1
    return created


__all__ = ["create_news_notifications"]
