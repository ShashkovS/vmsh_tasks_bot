"""Focused media-copy policy proof for Phase 8 Rich Markdown v1."""

from __future__ import annotations

import hashlib

import pytest

from helpers.pwa import rich_media
from helpers.pwa.content.assets import ConvertedAsset


class _PrivateStorage:
    def __init__(self) -> None:
        self.objects: list[tuple[str, bytes, str]] = []

    async def put(self, key: str, data: bytes, media_type: str) -> None:
        self.objects.append((key, data, media_type))

    def public_url(self, key: str) -> None:
        return None


class _PublicStorage(_PrivateStorage):
    def public_url(self, key: str) -> str:
        return f"https://cdn.example.test/{key}"


class _RasterConverter:
    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        converted = b"webp:" + payload
        return ConvertedAsset(
            source_sha256=hashlib.sha256(payload).hexdigest(),
            output_sha256=hashlib.sha256(converted).hexdigest(),
            media_type="image/webp",
            data=converted,
            width=1_200,
            height=900,
        )


@pytest.mark.asyncio
async def test_rich_media_copy_never_returns_client_hotlink_for_private_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def gif_fetch(_session, _source_url: str) -> tuple[bytes, str]:
        return b"GIF89a\x01\x00\x01\x00\x00\x00\x00", "image/gif"

    monkeypatch.setattr(rich_media, "_fetch_image", gif_fetch)
    storage = _PrivateStorage()
    document = {
        "schemaVersion": 1,
        "blocks": [{"type": "image", "mediaId": "picture", "alt": "Анимация"}],
        "media": [
            {
                "mediaId": "picture",
                "sourceUrl": "https://source.example.test/picture.gif",
                # A valid but untrusted value must never leak into a reader payload.
                "url": "https://attacker.example.test/hotlink.gif",
                "alt": "Анимация",
                "mimeType": "image/gif",
                "width": 1,
                "height": 1,
            }
        ],
    }

    finalized, manifest = await rich_media.copy_rich_document_media(
        document,
        storage=storage,
        converter=None,  # GIF bytes intentionally bypass static-image conversion.
    )

    assert finalized["media"] == [
        {
            "mediaId": "picture",
            "sourceUrl": "https://source.example.test/picture.gif",
            "alt": "Анимация",
            "mimeType": "image/gif",
            "width": 1,
            "height": 1,
        }
    ]
    assert manifest[0]["storage_status"] == "stored"
    assert storage.objects[0][2] == "image/gif"


@pytest.mark.asyncio
async def test_staff_uploaded_rich_image_is_converted_and_uses_public_s3_url() -> None:
    source = b"\x89PNG\r\n\x1a\nsource-image"
    storage = _PublicStorage()

    result = await rich_media.store_uploaded_rich_image(
        source,
        storage=storage,
        converter=_RasterConverter(),
    )

    assert result == {
        "url": f"https://cdn.example.test/{storage.objects[0][0]}",
        "mimeType": "image/webp",
        "width": 1_200,
        "height": 900,
    }
    assert storage.objects[0][0].startswith("rich-media/sha256/")
    assert storage.objects[0][1] == b"webp:" + source
    assert storage.objects[0][2] == "image/webp"


@pytest.mark.asyncio
async def test_staff_uploaded_rich_image_rejects_non_image_before_conversion() -> None:
    with pytest.raises(rich_media.RichMediaCopyError, match="PNG, JPEG or WebP"):
        await rich_media.store_uploaded_rich_image(
            b"not an image",
            storage=_PublicStorage(),
            converter=_RasterConverter(),
        )
