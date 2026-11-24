"""Live Telegram channel-post orchestration for the optional bot adapter."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from db_methods.pwa.news import (
    find_news_source_bindings,
    find_telegram_post,
    get_post,
    insert_diagnostic,
    list_media,
)
from helpers.object_storage import ObjectStorage
from helpers.pwa.content.assets import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
)
from helpers.pwa.news_media import NewsFileDownloader, mirror_news_media
from helpers.pwa.telegram_news import update_from_aiogram_messages
from models.pwa.news import ingest_telegram_news
from models.pwa.news_notifications import create_news_notifications


NewsInvalidator = Callable[[str], Awaitable[None]]
LiveNewsIngestor = Callable[[list[object]], Awaitable[dict[str, object]]]
_album_messages: dict[tuple[int, str], list[object]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _stored_media(item: dict[str, object]) -> dict[str, object]:
    return {
        "kind": item["media_kind"],
        "source_message_id": item["source_message_id"],
        "source_file_id": item["source_file_id"],
        "storage_key": item["storage_key"],
        "public_url": item["public_url"],
        "mime_type": item["mime_type"],
        "width": item["width"],
        "height": item["height"],
        "storage_status": item["storage_status"],
    }


def _merge_edited_album(
    update: dict[str, object],
    post: dict[str, object],
    media: list[dict[str, object]],
) -> dict[str, object]:
    incoming_message_id = int(update["message_id"])
    incoming_media = update["media"]
    merged_media = [_stored_media(item) for item in media]
    if incoming_media:
        replacement = incoming_media[0]
        for index, item in enumerate(merged_media):
            if item["source_message_id"] == incoming_message_id:
                merged_media[index] = replacement
                break
        else:
            merged_media.append(replacement)
        merged_media.sort(key=lambda item: int(item["source_message_id"]))

    existing_content = json.loads(str(post["content_json"]))
    existing_payload = json.loads(str(post["source_payload_json"]))
    messages = {
        int(item["message_id"]): item
        for item in existing_payload.get("messages", [])
        if isinstance(item, dict) and isinstance(item.get("message_id"), int)
    }
    for item in update["source_payload"].get("messages", []):
        if isinstance(item, dict) and isinstance(item.get("message_id"), int):
            messages[int(item["message_id"])] = item
    return {
        **update,
        "message_id": int(post["source_message_id"]),
        "published_at": str(post["published_at"]),
        "content": update["content"] or existing_content,
        "media": merged_media,
        "source_payload": {"messages": [messages[key] for key in sorted(messages)]},
    }


async def collect_live_news_message(
    message: object,
    ingest: LiveNewsIngestor,
    *,
    album_wait_seconds: float = 1.0,
) -> dict[str, object] | None:
    media_group_id = getattr(message, "media_group_id", None)
    if media_group_id is None:
        return await ingest([message])
    chat_id = int(message.chat.id)
    key = (chat_id, str(media_group_id))
    _album_messages.setdefault(key, []).append(message)
    await asyncio.sleep(album_wait_seconds)
    complete = _album_messages.pop(key, None)
    if complete is None:
        return None
    complete.sort(key=lambda item: int(item.message_id))
    return await ingest(complete)


async def ingest_live_news(
    messages: list[object],
    *,
    factory,
    storage: ObjectStorage,
    converter: ContentAssetConverter | ConfiguredContentAssetConverter,
    download: NewsFileDownloader,
    invalidate: NewsInvalidator,
) -> dict[str, object]:
    """Persist one complete live post/album and announce actual changes."""

    update = update_from_aiogram_messages(messages)
    now = _now()
    partial_album_edit = (
        update["media_group_id"] is not None
        and update["edited_at"] is not None
        and len(messages) == 1
    )

    def read_context(connection):
        bindings = find_news_source_bindings(connection, int(update["chat_id"]))
        existing = find_telegram_post(
            connection,
            chat_id=int(update["chat_id"]),
            message_id=int(update["message_id"]),
            media_group_id=(
                None
                if update["media_group_id"] is None
                else str(update["media_group_id"])
            ),
        )
        if existing is None:
            return bindings, None, []
        post = get_post(connection, int(existing["id"]))
        assert post is not None
        return bindings, post, list_media(connection, int(post["revision_id"]))

    bindings, existing_post, existing_media = await factory.run_read_async(read_context)
    if partial_album_edit and existing_post is None:
        await factory.run_write_async(
            lambda connection: insert_diagnostic(
                connection,
                chat_id=int(update["chat_id"]),
                message_id=int(update["message_id"]),
                code="incomplete_edited_album",
                detail=None,
                now=now,
            )
        )
        return {"status": "diagnostic", "code": "incomplete_edited_album"}
    if partial_album_edit:
        update = _merge_edited_album(update, existing_post, existing_media)

    if existing_post is not None or len(bindings) == 1:
        update = await mirror_news_media(
            update,
            download=download,
            storage=storage,
            converter=converter,
        )

    def write(connection):
        result = ingest_telegram_news(connection, update=update, now=now)
        if result["status"] == "created":
            result["notification_count"] = create_news_notifications(
                connection, post_id=int(result["post_id"]), now=now
            )
        return result

    result = await factory.run_write_async(write)
    if result["status"] in {"created", "updated", "deleted"}:
        await invalidate("telegram-news-changed")
    return result


__all__ = [
    "LiveNewsIngestor",
    "NewsInvalidator",
    "collect_live_news_message",
    "ingest_live_news",
]
