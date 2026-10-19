"""Copy normalized Telegram news media into the configured PWA storage."""

from __future__ import annotations

import hashlib
import mimetypes
from collections.abc import Awaitable, Callable

from helpers.object_storage import ObjectStorage, content_addressed_key
from helpers.pwa.content.assets import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
)


MAX_NEWS_SOURCE_BYTES = 25 * 1024 * 1024
MAX_NEWS_MEDIA_ITEMS = 50
NewsFileDownloader = Callable[[str], Awaitable[bytes]]


def _extension(mime_type: str) -> str:
    known = {
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "application/pdf": "pdf",
        "video/mp4": "mp4",
        "video/webm": "webm",
    }
    guessed = known.get(mime_type) or mimetypes.guess_extension(mime_type)
    return (guessed or ".bin").removeprefix(".").casefold()


async def mirror_news_media(
    update: dict[str, object],
    *,
    download: NewsFileDownloader,
    storage: ObjectStorage,
    converter: ContentAssetConverter | ConfiguredContentAssetConverter,
) -> dict[str, object]:
    """Return a complete snapshot whose pending media is stored and public.

    Objects use their final byte hash as identity. A retry after an interrupted
    album therefore overwrites/reuses the same harmless objects and preserves
    the source order supplied by Telegram.
    """

    raw_media = update.get("media", [])
    if not isinstance(raw_media, list) or len(raw_media) > MAX_NEWS_MEDIA_ITEMS:
        raise ValueError("news media manifest is invalid")

    mirrored: list[dict[str, object]] = []
    for raw_item in raw_media:
        if not isinstance(raw_item, dict):
            raise ValueError("news media item is invalid")
        item = dict(raw_item)
        if item.get("storage_status") == "stored":
            mirrored.append(item)
            continue

        source_file_id = item.get("source_file_id")
        kind = item.get("kind")
        mime_type = item.get("mime_type")
        if (
            not isinstance(source_file_id, str)
            or not source_file_id
            or kind not in {"image", "video", "audio", "document"}
            or not isinstance(mime_type, str)
            or "/" not in mime_type
        ):
            raise ValueError("pending news media is incomplete")

        source = await download(source_file_id)
        if not isinstance(source, bytes) or not source:
            raise ValueError("downloaded news media is empty")
        if len(source) > MAX_NEWS_SOURCE_BYTES:
            raise ValueError("downloaded news media is too large")

        if kind == "image":
            converted = await converter.raster_to_webp(source)
            if (
                converted.source_sha256 != hashlib.sha256(source).hexdigest()
                or converted.media_type != "image/webp"
                or hashlib.sha256(converted.data).hexdigest() != converted.output_sha256
                or not 1 <= converted.width <= 1920
                or not 1 <= converted.height <= 1920
            ):
                raise ValueError("news image converter returned invalid output")
            data = converted.data
            content_type = "image/webp"
            extension = "webp"
            item["width"] = converted.width
            item["height"] = converted.height
        else:
            data = source
            content_type = mime_type
            extension = _extension(mime_type)

        key = content_addressed_key("news", data, extension)
        await storage.put(key, data, content_type)
        item.update(
            {
                "storage_key": key,
                "public_url": storage.public_url(key),
                "mime_type": content_type,
                "storage_status": "stored",
            }
        )
        mirrored.append(item)

    return {**update, "media": mirrored}


__all__ = [
    "MAX_NEWS_MEDIA_ITEMS",
    "MAX_NEWS_SOURCE_BYTES",
    "NewsFileDownloader",
    "mirror_news_media",
]
