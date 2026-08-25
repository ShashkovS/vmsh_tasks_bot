"""Small rules for Staff-authored PWA-only news."""

from __future__ import annotations

import hashlib
import json
import sqlite3
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
from models.pwa.rich_document import rich_document_plain_text, validate_rich_document


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


_MARKDOWN_MARKS = (
    ("**", "bold"),
    ("__", "underline"),
    ("~~", "strike"),
    ("||", "spoiler"),
    ("`", "code"),
    ("_", "italic"),
)


def parse_telegram_markdown(value: str) -> tuple[str, list[dict[str, object]]]:
    """Parse the compact Telegram-compatible subset used by Staff news."""

    nodes: list[dict[str, object]] = []
    plain_parts: list[str] = []

    def append(text: str, mark: dict[str, str] | None = None) -> None:
        if not text:
            return
        plain_parts.append(text)
        node: dict[str, object] = {"type": "plain", "text": text}
        if mark is not None:
            node["marks"] = [mark]
        nodes.append(node)

    index = 0
    literal_start = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            append(value[literal_start:index])
            append(value[index + 1])
            index += 2
            literal_start = index
            continue
        if value[index] == "[":
            label_end = value.find("](", index + 1)
            href_end = value.find(")", label_end + 2) if label_end >= 0 else -1
            if label_end > index + 1 and href_end > label_end + 2:
                href = value[label_end + 2 : href_end]
                if href.startswith(("https://", "http://")):
                    append(value[literal_start:index])
                    append(
                        value[index + 1 : label_end],
                        {"type": "link", "href": href},
                    )
                    index = href_end + 1
                    literal_start = index
                    continue
        matched = False
        for marker, mark_type in _MARKDOWN_MARKS:
            if not value.startswith(marker, index):
                continue
            end = value.find(marker, index + len(marker))
            if end <= index + len(marker):
                continue
            append(value[literal_start:index])
            append(
                value[index + len(marker) : end],
                {"type": mark_type},
            )
            index = end + len(marker)
            literal_start = index
            matched = True
            break
        if not matched:
            index += 1
    append(value[literal_start:])
    return "".join(plain_parts), nodes


def _stored_markdown(row: dict[str, object]) -> str:
    raw = row.get("source_payload_json")
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("markdown"), str):
            return payload["markdown"]
    return str(row["text_plain"])


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
    document: object | None = None,
) -> dict[str, object]:
    """Create one Staff-authored post with Telegram-compatible inline Markdown."""

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

    if document is None:
        plain_text, content = parse_telegram_markdown(normalized_text)
        rich_document_json: str | None = None
        content_format = "legacy"
    else:
        validated_document = validate_rich_document(document)
        plain_text = rich_document_plain_text(validated_document)
        content = [{"type": "plain", "text": plain_text}]
        rich_document_json = json.dumps(
            validated_document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        content_format = "rich_markdown_v1"
    content_json = json.dumps(
        content, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    source_payload_json = json.dumps(
        {
            "schemaVersion": 2 if rich_document_json else 1,
            "publishedAt": normalized_published_at,
            "editedAt": now,
            "markdown": normalized_text,
            **({"document": json.loads(rich_document_json)} if rich_document_json else {}),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    source_hash = hashlib.sha256(
        f"{content_json}\n{source_payload_json}".encode()
    ).hexdigest()
    post_id = insert_local_post(
        connection,
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
        text_plain=plain_text,
        content_json=content_json,
        source_payload_json=source_payload_json,
        now=now,
        content_format=content_format,
        markdown_source=normalized_text if rich_document_json else None,
        rich_document_json=rich_document_json,
    )
    return {
        "post_id": post_id,
        "public_id": str(
            connection.execute(
                "SELECT public_id FROM news_posts WHERE id = ?", (post_id,)
            ).fetchone()["public_id"]
        ),
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
    document: object | None = None,
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
    if _stored_markdown(current) == normalized_text and current[
        "published_at"
    ] == normalized_published_at:
        return False

    if document is None:
        plain_text, content = parse_telegram_markdown(normalized_text)
        rich_document_json: str | None = None
        content_format = "legacy"
    else:
        validated_document = validate_rich_document(document)
        plain_text = rich_document_plain_text(validated_document)
        content = [{"type": "plain", "text": plain_text}]
        rich_document_json = json.dumps(
            validated_document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        content_format = "rich_markdown_v1"
    content_json = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    source_payload_json = json.dumps(
        {
            "schemaVersion": 2 if rich_document_json else 1,
            "publishedAt": normalized_published_at,
            "editedAt": now,
            "markdown": normalized_text,
            **({"document": json.loads(rich_document_json)} if rich_document_json else {}),
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
        text_plain=plain_text,
        content_json=content_json,
        source_payload_json=source_payload_json,
        now=now,
        content_format=content_format,
        markdown_source=normalized_text if rich_document_json else None,
        rich_document_json=rich_document_json,
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
    "parse_telegram_markdown",
    "sync_scheduled_local_news_notifications",
]
