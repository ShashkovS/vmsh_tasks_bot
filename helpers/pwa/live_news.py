"""Live Telegram channel-post orchestration for the optional bot adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from db_methods.pwa.news import find_news_source_bindings, insert_diagnostic
from helpers.object_storage import ObjectStorage
from helpers.pwa.content.assets import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
)
from helpers.pwa.news_media import NewsFileDownloader, mirror_news_media
from helpers.pwa.telegram_news import update_from_aiogram_messages
from models.pwa.news import ingest_telegram_news


NewsInvalidator = Callable[[str], Awaitable[None]]
LiveNewsIngestor = Callable[[list[object]], Awaitable[dict[str, object]]]
_album_messages: dict[tuple[int, str], list[object]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


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
    if (
        update["media_group_id"] is not None
        and update["edited_at"] is not None
        and len(messages) == 1
    ):
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

    bindings = await factory.run_read_async(
        lambda connection: find_news_source_bindings(connection, int(update["chat_id"]))
    )
    if len(bindings) == 1:
        update = await mirror_news_media(
            update,
            download=download,
            storage=storage,
            converter=converter,
        )
    result = await factory.run_write_async(
        lambda connection: ingest_telegram_news(connection, update=update, now=now)
    )
    if result["status"] in {"created", "updated", "deleted"}:
        await invalidate("telegram-news-changed")
    return result


__all__ = [
    "LiveNewsIngestor",
    "NewsInvalidator",
    "collect_live_news_message",
    "ingest_live_news",
]
