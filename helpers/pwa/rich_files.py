"""Store Staff attachments without conversion; docs/rich-file-attachments.md."""

from __future__ import annotations

import asyncio
import hashlib

from helpers.object_storage import ObjectStorage
from models.pwa.rich_document import is_rich_link_url
from models.pwa.rich_files import (
    MAX_RICH_FILE_BYTES,
    InvalidRichFile,
    local_rich_file_url,
    rich_file_key,
    rich_file_mime_type,
    rich_file_name,
)


async def store_uploaded_rich_file(
    data: bytes, filename: str, *, storage: ObjectStorage
) -> dict[str, object]:
    if not data or len(data) > MAX_RICH_FILE_BYTES:
        raise InvalidRichFile("file is empty or exceeds 50 MiB")
    name = rich_file_name(filename)
    digest = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())
    key = rich_file_key(digest, name)
    mime_type = rich_file_mime_type(name)
    url = storage.public_url(key) or local_rich_file_url(digest, name)
    if not is_rich_link_url(url):
        raise InvalidRichFile("storage returned an invalid file URL")
    await storage.put(key, data, mime_type)
    return {"url": url, "filename": name, "mimeType": mime_type, "byteSize": len(data)}
