"""Server-side external image copy for RichDocument v1.

The media policy belongs to the Phase-8 Rich Markdown decision: authoring URLs
are never hotlinked into reader payloads. Each redirect receives a fresh DNS
SSRF check and the custom resolver connects only to the checked addresses.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from urllib.parse import urljoin

import aiohttp
from aiohttp.abc import AbstractResolver

from helpers.object_storage import ObjectStorage, content_addressed_key
from helpers.pwa.content.assets import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
)
from models.pwa.rich_document import InvalidRichDocument, is_rich_https_url


MAX_RICH_MEDIA_ITEMS = 10
MAX_RICH_MEDIA_BYTES = 10 * 1024 * 1024
MAX_RICH_MEDIA_TOTAL_BYTES = 25 * 1024 * 1024
MAX_RICH_MEDIA_SIDE = 1_920
_ALLOWED_STATIC = frozenset({"image/jpeg", "image/png", "image/webp"})


class RichMediaCopyError(InvalidRichDocument):
    pass


def _static_image_payload(data: bytes) -> bool:
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


async def store_uploaded_rich_image(
    data: bytes,
    *,
    storage: ObjectStorage,
    converter: ContentAssetConverter | ConfiguredContentAssetConverter,
) -> dict[str, object]:
    """Convert one Staff-uploaded image and return its safe public Markdown URL."""

    if not data or len(data) > MAX_RICH_MEDIA_BYTES:
        raise RichMediaCopyError("image file is empty or exceeds 10 MiB")
    if not _static_image_payload(data):
        raise RichMediaCopyError("upload must be a PNG, JPEG or WebP image")
    converted = await converter.raster_to_webp(data)
    if (
        converted.source_sha256 != hashlib.sha256(data).hexdigest()
        or converted.media_type != "image/webp"
        or not 1 <= converted.width <= MAX_RICH_MEDIA_SIDE
        or not 1 <= converted.height <= MAX_RICH_MEDIA_SIDE
    ):
        raise RichMediaCopyError("image conversion returned invalid output")
    key = content_addressed_key("rich-media", converted.data, "webp")
    await storage.put(key, converted.data, "image/webp")
    public_url = storage.public_url(key)
    if public_url is None or not is_rich_https_url(public_url):
        raise RichMediaCopyError("public HTTPS URL for uploaded image is unavailable")
    return {
        "url": public_url,
        "mimeType": "image/webp",
        "width": converted.width,
        "height": converted.height,
    }


class _SafeResolver(AbstractResolver):
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC) -> list[dict[str, object]]:
        try:
            values = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM, family=family
            )
        except socket.gaierror as error:
            raise RichMediaCopyError("media URL DNS resolution failed") from error
        result: list[dict[str, object]] = []
        for item in values:
            address = str(item[4][0])
            parsed = ipaddress.ip_address(address)
            if not parsed.is_global:
                raise RichMediaCopyError("media URL resolves to a non-public address")
            result.append(
                {
                    "hostname": host,
                    "host": address,
                    "port": port,
                    "family": item[0],
                    "proto": 0,
                    "flags": 0,
                }
            )
        if not result:
            raise RichMediaCopyError("media URL has no usable DNS address")
        return result

    async def close(self) -> None:
        return None


def _gif_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise RichMediaCopyError("media payload is not a GIF")
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    if not 1 <= width <= MAX_RICH_MEDIA_SIDE or not 1 <= height <= MAX_RICH_MEDIA_SIDE:
        raise RichMediaCopyError("GIF dimensions exceed 1920×1920")
    return width, height


async def _fetch_image(session: aiohttp.ClientSession, source_url: str) -> tuple[bytes, str]:
    current = source_url
    for _ in range(5):
        if not is_rich_https_url(current):
            raise RichMediaCopyError("media URL must be credential-free HTTPS")
        try:
            async with session.get(current, allow_redirects=False, headers={"Accept": "image/gif,image/webp,image/png,image/jpeg"}) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise RichMediaCopyError("media redirect has no location")
                    current = urljoin(current, location)
                    continue
                if response.status != 200:
                    raise RichMediaCopyError("media URL did not return an image")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
                declared = response.content_length
                if declared is not None and declared > MAX_RICH_MEDIA_BYTES:
                    raise RichMediaCopyError("media file exceeds 10 MiB")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    total += len(chunk)
                    if total > MAX_RICH_MEDIA_BYTES:
                        raise RichMediaCopyError("media file exceeds 10 MiB")
                    chunks.append(chunk)
                if not chunks:
                    raise RichMediaCopyError("media file is empty")
                return b"".join(chunks), content_type
        except aiohttp.ClientError as error:
            raise RichMediaCopyError("media download failed") from error
    raise RichMediaCopyError("media URL redirects too many times")


async def copy_rich_document_media(
    document: dict[str, object],
    *,
    storage: ObjectStorage,
    converter: ContentAssetConverter | ConfiguredContentAssetConverter,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Copy manifest media before the caller opens its database transaction."""

    raw_media = document.get("media")
    if not isinstance(raw_media, list) or len(raw_media) > MAX_RICH_MEDIA_ITEMS:
        raise RichMediaCopyError("rich media manifest is invalid")
    total = 0
    finalized_media: list[dict[str, object]] = []
    manifest: list[dict[str, object]] = []
    resolver = _SafeResolver()
    connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False, limit=4)
    timeout = aiohttp.ClientTimeout(total=30, connect=8, sock_read=15)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for raw_item in raw_media:
                if not isinstance(raw_item, dict):
                    raise RichMediaCopyError("rich media item is invalid")
                source_url = raw_item.get("sourceUrl")
                if not is_rich_https_url(source_url):
                    raise RichMediaCopyError("media URL must be credential-free HTTPS")
                data, content_type = await _fetch_image(session, str(source_url))
                total += len(data)
                if total > MAX_RICH_MEDIA_TOTAL_BYTES:
                    raise RichMediaCopyError("rich media exceeds 25 MiB in total")
                if content_type == "image/gif":
                    width, height = _gif_dimensions(data)
                    output = data
                    mime_type = "image/gif"
                    extension = "gif"
                elif content_type in _ALLOWED_STATIC:
                    converted = await converter.raster_to_webp(data)
                    if (
                        converted.source_sha256 != hashlib.sha256(data).hexdigest()
                        or converted.media_type != "image/webp"
                        or not 1 <= converted.width <= MAX_RICH_MEDIA_SIDE
                        or not 1 <= converted.height <= MAX_RICH_MEDIA_SIDE
                    ):
                        raise RichMediaCopyError("image conversion returned invalid output")
                    output = converted.data
                    mime_type = "image/webp"
                    extension = "webp"
                    width, height = converted.width, converted.height
                else:
                    raise RichMediaCopyError("media MIME type is not an allowed image")
                key = content_addressed_key("rich-media", output, extension)
                await storage.put(key, output, mime_type)
                public_url = storage.public_url(key)
                # ``url`` is server output only. Dropping any client-provided
                # value ensures a local/private storage adapter cannot turn an
                # authored HTTPS URL into a direct reader-side hotlink.
                item = {
                    "mediaId": raw_item["mediaId"],
                    "sourceUrl": source_url,
                    "alt": raw_item["alt"],
                    "mimeType": mime_type,
                    "width": width,
                    "height": height,
                }
                if public_url is not None:
                    item["url"] = public_url
                finalized_media.append(item)
                manifest.append(
                    {
                        "kind": "image",
                        "media_id": item["mediaId"],
                        "source_url": source_url,
                        "storage_key": key,
                        "public_url": public_url,
                        "mime_type": mime_type,
                        "width": width,
                        "height": height,
                        "storage_status": "stored",
                    }
                )
    finally:
        await resolver.close()
    return {**document, "media": finalized_media}, manifest


__all__ = [
    "MAX_RICH_MEDIA_ITEMS",
    "MAX_RICH_MEDIA_BYTES",
    "MAX_RICH_MEDIA_TOTAL_BYTES",
    "RichMediaCopyError",
    "copy_rich_document_media",
    "store_uploaded_rich_image",
]
