from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from helpers.pwa.live_news import collect_live_news_message


def _message(message_id: int):
    return SimpleNamespace(
        message_id=message_id,
        media_group_id="album-41",
        chat=SimpleNamespace(id=-100179),
    )


@pytest.mark.asyncio
async def test_album_messages_are_ingested_once_in_source_order():
    calls: list[list[int]] = []

    async def ingest(messages: list[object]) -> dict[str, object]:
        calls.append([message.message_id for message in messages])
        return {"status": "created"}

    await asyncio.gather(
        collect_live_news_message(_message(42), ingest, album_wait_seconds=0),
        collect_live_news_message(_message(41), ingest, album_wait_seconds=0),
    )
    assert calls == [[41, 42]]
