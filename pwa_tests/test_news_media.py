from __future__ import annotations

import hashlib

import pytest

from helpers.object_storage import LocalObjectStorage
from helpers.pwa.content.assets import ConvertedAsset
from helpers.pwa.news_media import MAX_NEWS_SOURCE_BYTES, mirror_news_media


class Converter:
    async def raster_to_webp(self, source: bytes) -> ConvertedAsset:
        result = b"webp:" + source
        return ConvertedAsset(
            source_sha256=hashlib.sha256(source).hexdigest(),
            output_sha256=hashlib.sha256(result).hexdigest(),
            media_type="image/webp",
            data=result,
            width=1200,
            height=900,
        )


def _update() -> dict[str, object]:
    return {
        "chat_id": -100179,
        "message_id": 41,
        "media": [
            {
                "kind": "image",
                "source_message_id": 41,
                "source_file_id": "telegram-photo",
                "mime_type": "image/jpeg",
                "storage_status": "pending",
            },
            {
                "kind": "document",
                "source_message_id": 42,
                "source_file_id": "telegram-pdf",
                "mime_type": "application/pdf",
                "storage_status": "pending",
            },
        ],
    }


@pytest.mark.asyncio
async def test_mirror_news_media_converts_images_and_preserves_order(tmp_path):
    storage = LocalObjectStorage(tmp_path / "media")
    sources = {"telegram-photo": b"jpeg", "telegram-pdf": b"pdf"}

    async def download(file_id: str) -> bytes:
        return sources[file_id]

    result = await mirror_news_media(
        _update(), download=download, storage=storage, converter=Converter()
    )
    media = result["media"]
    assert [item["source_message_id"] for item in media] == [41, 42]
    assert media[0]["mime_type"] == "image/webp"
    assert media[0]["width"] == 1200
    assert media[1]["mime_type"] == "application/pdf"
    assert media[0]["storage_key"].endswith(".webp")
    assert media[1]["storage_key"].endswith(".pdf")
    assert await storage.get(media[0]["storage_key"]) == b"webp:jpeg"
    assert await storage.get(media[1]["storage_key"]) == b"pdf"
    assert not any(
        path.name.endswith(".jpg") for path in (tmp_path / "media").rglob("*")
    )


@pytest.mark.asyncio
async def test_mirror_news_media_keeps_already_stored_item_without_download(tmp_path):
    storage = LocalObjectStorage(tmp_path / "media")
    update = _update()
    stored = {
        **update["media"][0],
        "storage_key": "news/sha256/aa/bb/already.webp",
        "public_url": "https://cdn.example.test/already.webp",
        "storage_status": "stored",
    }
    update["media"] = [stored]

    async def unexpected_download(_file_id: str) -> bytes:
        raise AssertionError("stored media must not be downloaded")

    result = await mirror_news_media(
        update, download=unexpected_download, storage=storage, converter=Converter()
    )
    assert result["media"] == [stored]


@pytest.mark.asyncio
async def test_mirror_news_media_rejects_oversized_file_before_storage(tmp_path):
    storage = LocalObjectStorage(tmp_path / "media")
    update = _update()
    update["media"] = [update["media"][1]]

    async def download(_file_id: str) -> bytes:
        return b"x" * (MAX_NEWS_SOURCE_BYTES + 1)

    with pytest.raises(ValueError, match="too large"):
        await mirror_news_media(
            update, download=download, storage=storage, converter=Converter()
        )
    assert list((tmp_path / "media").rglob("*.pdf")) == []
