"""Notification events created by an actual lesson-material publication."""

from __future__ import annotations

import json
import sqlite3

from db_methods.pwa.notifications import (
    active_group_notification_accounts,
    insert_event,
    published_content_event_source,
)


_CATEGORY_BY_KIND = {
    "condition": "lesson_published",
    "hint": "hint_published",
    "solution": "solution_published",
}


def create_content_publication_notifications(
    connection: sqlite3.Connection,
    *,
    group_lesson_id: int,
    course_id: int,
    group_id: str,
    kind: str,
) -> int:
    """Create one account event for the current active-group publication."""

    category = _CATEGORY_BY_KIND.get(kind)
    if category is None:
        raise ValueError("unsupported content notification kind")
    source = published_content_event_source(
        connection,
        group_lesson_id=group_lesson_id,
        kind=kind,
    )
    if source is None:
        return 0

    recipients: dict[int, tuple[str, list[str]]] = {}
    for row in active_group_notification_accounts(
        connection,
        course_id=course_id,
        group_id=group_id,
    ):
        account_id = int(row["account_id"])
        recipient = recipients.get(account_id)
        if recipient is None:
            recipient = (str(row["audience"]), [])
            recipients[account_id] = recipient
        student_id = str(row["student_public_id"])
        if student_id not in recipient[1]:
            recipient[1].append(student_id)

    created = 0
    for account_id, (audience, student_ids) in recipients.items():
        route = (
            "/student/tasks"
            f"?course={source['course_public_id']}"
            f"&group={source['group_public_id']}"
            f"&lesson={source['lesson_number']}"
            if audience == "student"
            else f"/family/children/{student_ids[0]}"
        )
        payload = {
            "publicationId": source["publication_public_id"],
            "courseId": source["course_public_id"],
            "groupId": source["group_public_id"],
            "groupLessonId": source["group_lesson_public_id"],
            "lessonNumber": source["lesson_number"],
            "kind": kind,
            "studentIds": student_ids,
        }
        occurred_at = str(source["published_at"])
        if insert_event(
            connection,
            account_id=account_id,
            category=category,
            dedupe_key=str(source["publication_public_id"]),
            route=route,
            payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            occurred_at=occurred_at,
            deliver_after=occurred_at,
            created_at=occurred_at,
        ):
            created += 1
    return created


__all__ = ["create_content_publication_notifications"]
