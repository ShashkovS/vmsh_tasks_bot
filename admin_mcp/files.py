"""Bounded, single-hop transfers of ChatGPT native file parameters."""

import os
from typing import NotRequired, TypedDict
from urllib.parse import urlsplit

import aiohttp


class ChatFile(TypedDict):
    file_id: str
    download_url: str
    file_name: NotRequired[str]
    mime_type: NotRequired[str]


async def download(file: ChatFile, maximum: int) -> bytes:
    url = urlsplit(file["download_url"])
    configured = {
        h.strip().lower()
        for h in os.getenv("VMSH_ADMIN_MCP_FILE_HOSTS", "").split(",")
        if h.strip()
    }
    if (
        url.scheme != "https"
        or url.port not in (None, 443)
        or url.username is not None
        or url.password is not None
        or not (
            (url.hostname or "").endswith(".oaiusercontent.com")
            or url.hostname in configured
        )
    ):
        raise ValueError("unsupported_chatgpt_file_origin")
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=90), cookie_jar=aiohttp.DummyCookieJar()
        ) as session:
            async with session.get(
                file["download_url"], allow_redirects=False
            ) as response:
                if response.status != 200:
                    raise ValueError("file_expired_or_unavailable")
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > maximum:
                        raise ValueError("file_too_large")
                return bytes(data)
    except aiohttp.ClientError, TimeoutError:
        raise ValueError("file_unavailable") from None
