"""The production Telegram adapter keeps review delivery deliberately small."""

from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

import pytest
from aiohttp import web

from apps import pwa_app
from apps.pwa_api.review_routes import PWA_REVIEW_TELEGRAM_SENDER
from helpers.config import Config
from helpers.pwa.app_keys import ENABLED_ADAPTERS, RUNTIME_CONFIG


class RecordingBot:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.photos: list[dict[str, object]] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.messages))

    async def send_photo(self, **kwargs):
        self.photos.append(kwargs)
        return SimpleNamespace(message_id=len(self.photos))


@pytest.mark.asyncio
async def test_review_sender_splits_long_text_and_sends_composites_silently(
    monkeypatch,
) -> None:
    recording_bot = RecordingBot()
    fake_bot_module = ModuleType("helpers.bot")
    fake_bot_module.bot = recording_bot
    fake_bot_module.dispatcher = SimpleNamespace(workflow_data={})
    monkeypatch.setitem(sys.modules, "helpers.bot", fake_bot_module)
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-agent",
        pwa_instance="review-telegram-test",
        config_name="review_telegram_test",
        pwa_prototype=True,
        nats_server=None,
    )
    app[ENABLED_ADAPTERS] = (SimpleNamespace(__name__="apps.tg_bot"),)

    pwa_app.configure(app)
    sender = app[PWA_REVIEW_TELEGRAM_SENDER]
    await sender(17_917_917, "я" * 7_001, (b"first-png", b"second-png"))

    assert [len(call["text"]) for call in recording_bot.messages] == [3500, 3500, 1]
    assert all(call["chat_id"] == 17_917_917 for call in recording_bot.messages)
    assert all(call["parse_mode"] is None for call in recording_bot.messages)
    assert all(call["disable_notification"] is True for call in recording_bot.messages)
    assert [call["photo"].data for call in recording_bot.photos] == [
        b"first-png",
        b"second-png",
    ]
    assert [call["photo"].filename for call in recording_bot.photos] == [
        "review-annotation-1.png",
        "review-annotation-2.png",
    ]
    assert all(call["disable_notification"] is True for call in recording_bot.photos)
