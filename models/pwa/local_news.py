"""Small rules for Staff-authored PWA-only news."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime

from db_methods.pwa.local_news import (
    delete_local_news_events,
    find_local_post_for_edit,
    reschedule_local_news_events,
    update_local_post_header,
)
from db_methods.pwa.news import (
    find_local_news_owner,
    insert_local_post,
    insert_revision,
)
from models.pwa.news_notifications import create_news_notifications


class InvalidLocalNews(ValueError):
    pass


class LocalNewsOwnerNotFound(Exception):
    pass


class LocalNewsNotFound(Exception):
    pass


class LocalNewsConflict(Exception):
    pass


class LocalNewsPublicationTimeLocked(Exception):
    pass


def _published_at(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidLocalNews("published_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidLocalNews("published_at") from error
    if parsed.tzinfo is None:
        raise InvalidLocalNews("published_at")
    return (
        parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def create_local_news(
    connection: sqlite3.Connection,
    *,
    owner_type: object,
    owner_public_id: object,
    text: object,
    published_at: object,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    """Create one plain-text local post using the existing news revision model.

    Rich Markdown editing belongs to phase two; the v1 local publication is
    intentionally plain text. See development-plan Phase 8.
    """

    if owner_type not in {"course", "group"}:
        raise InvalidLocalNews("owner_type")
    if not isinstance(owner_public_id, str) or not owner_public_id:
        raise InvalidLocalNews("owner_public_id")
    if not isinstance(text, str):
        raise InvalidLocalNews("text")
    normalized_text = text.strip()
    if not normalized_text or len(normalized_text) > 32_768:
        raise InvalidLocalNews("text")
    normalized_published_at = _published_at(published_at)
    owner = find_local_news_owner(
        connection,
        owner_type=owner_type,
        owner_public_id=owner_public_id,
    )
    if owner is None:
        raise LocalNewsOwnerNotFound

    public_id = f"news.{uuid.uuid4().hex}"
    content = [{"type": "plain", "text": normalized_text}]
    content_json = json.dumps(
        content, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    source_payload_json = json.dumps(
        {
            "schemaVersion": 1,
            "publishedAt": normalized_published_at,
            "editedAt": now,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    source_hash = hashlib.sha256(
        f"{content_json}\n{source_payload_json}".encode()
    ).hexdigest()
    post_id = insert_local_post(
        connection,
        public_id=public_id,
        owner_course_id=(
            None if owner["owner_course_id"] is None else int(owner["owner_course_id"])
        ),
        owner_group_id=(
            None if owner["owner_group_id"] is None else str(owner["owner_group_id"])
        ),
        published_at=normalized_published_at,
        actor_user_id=actor_user_id,
        now=now,
    )
    revision_id = insert_revision(
        connection,
        post_id=post_id,
        source_hash=source_hash,
        source_edited_at=None,
        text_plain=normalized_text,
        content_json=content_json,
        source_payload_json=source_payload_json,
        now=now,
    )
    return {
        "post_id": post_id,
        "public_id": public_id,
        "published_at": normalized_published_at,
        "revision_id": revision_id,
    }


def edit_local_news(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    text: object,
    published_at: object | None,
    actor_user_id: int,
    now: str,
) -> bool:
    """Create a revision, allowing only text corrections after publication.

    See ``vmshpwa/docs/local-scheduled-news.md`` and
    ``test_admin_corrects_published_local_news_without_repeat_notification``.
    Published news keeps its original ordering/deadline timestamp and existing
    notification rows; only a future scheduled post may move those rows.
    """

    if not isinstance(text, str):
        raise InvalidLocalNews("text")
    normalized_text = text.strip()
    if not normalized_text or len(normalized_text) > 32_768:
        raise InvalidLocalNews("text")
    current = find_local_post_for_edit(connection, public_id=public_id)
    if current is None:
        raise LocalNewsNotFound
    if int(current["version"]) != expected_version:
        raise LocalNewsConflict
    already_published = str(current["published_at"]) <= now
    if already_published:
        if published_at is not None:
            raise LocalNewsPublicationTimeLocked
        normalized_published_at = str(current["published_at"])
    else:
        normalized_published_at = _published_at(published_at)
    if (
        current["text_plain"] == normalized_text
        and current["published_at"] == normalized_published_at
    ):
        return False

    content_json = json.dumps(
        [{"type": "plain", "text": normalized_text}],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    source_payload_json = json.dumps(
        {
            "schemaVersion": 1,
            "publishedAt": normalized_published_at,
            "editedAt": now,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    source_hash = hashlib.sha256(
        f"{content_json}\n{source_payload_json}".encode()
    ).hexdigest()
    if not update_local_post_header(
        connection,
        post_id=int(current["id"]),
        public_id=public_id,
        expected_version=expected_version,
        published_at=normalized_published_at,
        actor_user_id=actor_user_id,
        now=now,
    ):
        raise LocalNewsConflict
    insert_revision(
        connection,
        post_id=int(current["id"]),
        source_hash=source_hash,
        source_edited_at=now,
        text_plain=normalized_text,
        content_json=content_json,
        source_payload_json=source_payload_json,
        now=now,
    )
    if not already_published:
        reschedule_local_news_events(
            connection,
            public_id=public_id,
            published_at=normalized_published_at,
        )
    return True


def sync_scheduled_local_news_notifications(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    now: str,
) -> None:
    """Keep a future local post's notification events aligned with visibility."""

    current = find_local_post_for_edit(connection, public_id=public_id)
    if current is None or str(current["published_at"]) <= now:
        return
    if current["state"] == "visible":
        create_news_notifications(
            connection,
            post_id=int(current["id"]),
            now=now,
            deliver_after=str(current["published_at"]),
        )
    else:
        delete_local_news_events(connection, public_id=public_id)


__all__ = [
    "InvalidLocalNews",
    "LocalNewsConflict",
    "LocalNewsNotFound",
    "LocalNewsOwnerNotFound",
    "LocalNewsPublicationTimeLocked",
    "create_local_news",
    "edit_local_news",
    "sync_scheduled_local_news_notifications",
]
