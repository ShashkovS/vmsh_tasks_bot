"""Small news-ingest rules above the direct SQLite operations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid

from db_methods.pwa.news import (
    find_news_source_bindings,
    find_telegram_post,
    get_post,
    insert_diagnostic,
    insert_media,
    insert_revision,
    insert_telegram_post,
    mark_source_deleted,
    revision_exists,
    touch_post,
)


_MEDIA_KINDS = frozenset({"image", "video", "audio", "document"})
_STORAGE_STATES = frozenset({"pending", "stored", "failed"})


class InvalidNewsUpdate(ValueError):
    pass


def _required_int(update: dict[str, object], key: str) -> int:
    value = update.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidNewsUpdate(key)
    return value


def _optional_text(update: dict[str, object], key: str) -> str | None:
    value = update.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidNewsUpdate(key)
    return value


def _content(update: dict[str, object]) -> tuple[list[dict[str, object]], str]:
    content = update.get("content")
    if not isinstance(content, list):
        raise InvalidNewsUpdate("content")
    normalized: list[dict[str, object]] = []
    plain_parts: list[str] = []
    for node in content:
        if not isinstance(node, dict):
            raise InvalidNewsUpdate("content")
        node_type = node.get("type")
        text = node.get("text")
        if not isinstance(node_type, str) or not isinstance(text, str):
            raise InvalidNewsUpdate("content")
        clean = {"type": node_type, "text": text}
        for key in ("href", "documentId", "language", "unsupportedType"):
            value = node.get(key)
            if value is not None:
                if not isinstance(value, str):
                    raise InvalidNewsUpdate("content")
                clean[key] = value
        normalized.append(clean)
        plain_parts.append(text)
    return normalized, "".join(plain_parts)


def _media(update: dict[str, object]) -> list[dict[str, object]]:
    value = update.get("media", [])
    if not isinstance(value, list):
        raise InvalidNewsUpdate("media")
    normalized: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or item.get("kind") not in _MEDIA_KINDS:
            raise InvalidNewsUpdate("media")
        state = item.get("storage_status", "pending")
        if state not in _STORAGE_STATES:
            raise InvalidNewsUpdate("media")
        normalized.append({**item, "storage_status": state})
    return normalized


def ingest_telegram_news(
    connection: sqlite3.Connection,
    *,
    update: dict[str, object],
    now: str,
) -> dict[str, object]:
    """Store one complete post/album snapshot.

    Album collection and media upload happen before this function; `media` must
    already contain the full ordered album snapshot.
    """

    chat_id = _required_int(update, "chat_id")
    message_id = _required_int(update, "message_id")
    media_group_id = _optional_text(update, "media_group_id")
    published_at = _optional_text(update, "published_at")
    edited_at = _optional_text(update, "edited_at")
    deleted = update.get("deleted", False)
    if published_at is None or not isinstance(deleted, bool):
        raise InvalidNewsUpdate("published_at" if published_at is None else "deleted")

    post = find_telegram_post(
        connection,
        chat_id=chat_id,
        message_id=message_id,
        media_group_id=media_group_id,
    )
    if deleted:
        if post is None:
            insert_diagnostic(
                connection,
                chat_id=chat_id,
                message_id=message_id,
                code="unknown_deleted_post",
                detail=None,
                now=now,
            )
            return {"status": "diagnostic", "code": "unknown_deleted_post"}
        mark_source_deleted(connection, post_id=int(post["id"]), now=now)
        return {"status": "deleted", "post_id": int(post["id"])}

    content, text_plain = _content(update)
    media = _media(update)
    payload = update.get("source_payload")
    if not isinstance(payload, dict):
        raise InvalidNewsUpdate("source_payload")
    content_json = json.dumps(
        content, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    media_hash_value = [
        {
            key: item.get(key)
            for key in (
                "kind",
                "source_message_id",
                "source_file_id",
                "storage_key",
                "public_url",
                "mime_type",
                "width",
                "height",
            )
        }
        for item in media
    ]
    source_hash = hashlib.sha256(
        json.dumps(
            {"content": content, "media": media_hash_value},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()

    if post is None:
        bindings = find_news_source_bindings(connection, chat_id)
        if len(bindings) != 1:
            code = "news_source_unmapped" if not bindings else "news_source_ambiguous"
            insert_diagnostic(
                connection,
                chat_id=chat_id,
                message_id=message_id,
                code=code,
                detail=None if not bindings else f"matches={len(bindings)}",
                now=now,
            )
            return {"status": "diagnostic", "code": code}
        binding = bindings[0]
        post_id = insert_telegram_post(
            connection,
            public_id=f"news.{uuid.uuid4().hex}",
            source_binding_public_id=str(binding["public_id"]),
            owner_course_id=(
                None
                if binding["owner_course_id"] is None
                else int(binding["owner_course_id"])
            ),
            owner_group_id=(
                None
                if binding["owner_group_id"] is None
                else str(binding["owner_group_id"])
            ),
            chat_id=chat_id,
            message_id=message_id,
            media_group_id=media_group_id,
            published_at=published_at,
            edited_at=edited_at,
            now=now,
        )
        status = "created"
    else:
        post_id = int(post["id"])
        if revision_exists(connection, post_id=post_id, source_hash=source_hash):
            return {"status": "duplicate", "post_id": post_id}
        status = "updated"

    revision_id = insert_revision(
        connection,
        post_id=post_id,
        source_hash=source_hash,
        source_edited_at=edited_at,
        text_plain=text_plain,
        content_json=content_json,
        source_payload_json=json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ),
        now=now,
    )
    insert_media(connection, revision_id=revision_id, media=media, now=now)
    if status == "updated":
        touch_post(connection, post_id=post_id, edited_at=edited_at, now=now)
    stored = get_post(connection, post_id)
    assert stored is not None
    return {
        "status": status,
        "post_id": post_id,
        "public_id": stored["public_id"],
        "revision_id": revision_id,
        "source_hash": source_hash,
    }


__all__ = ["InvalidNewsUpdate", "ingest_telegram_news"]
