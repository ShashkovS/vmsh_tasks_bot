"""Optional live news bridge; inactive unless the PWA adapter injects it."""

from __future__ import annotations

from aiogram import types

from helpers.bot import router
from helpers.pwa.live_news import LiveNewsIngestor, collect_live_news_message


@router.channel_post()
@router.edited_channel_post()
async def mirror_pwa_news(
    message: types.Message,
    pwa_news_ingestor: LiveNewsIngestor | None = None,
) -> None:
    if pwa_news_ingestor is not None:
        await collect_live_news_message(message, pwa_news_ingestor)


__all__ = ["mirror_pwa_news"]
