"""Focused checks for the one-shot Telegram binding probe."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from helpers.pwa import telegram_bindings


class Session:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBot:
    def __init__(self, _token: str, *, can_post: bool = True) -> None:
        self.session = Session()
        self.can_post = can_post

    async def get_me(self):
        return SimpleNamespace(id=179)

    async def get_chat(self, chat_id):
        return SimpleNamespace(id=chat_id, type="channel", title="Канал ВМШ")

    async def get_chat_member(self, _chat_id, _user_id):
        return SimpleNamespace(status="administrator", can_post_messages=self.can_post)


async def test_verifier_returns_only_canonical_identity_and_closes_bot(monkeypatch):
    bot = FakeBot("ignored")
    monkeypatch.setattr(telegram_bindings, "Bot", lambda _token: bot)

    result = await telegram_bindings.verify_telegram_binding(
        token="synthetic-token",
        chat_id=-100179000001,
        message_thread_id=None,
        purpose="materials_target",
    )

    assert result == {"chat_id": -100179000001, "title": "Канал ВМШ"}
    assert bot.session.closed


async def test_verifier_rejects_missing_post_right_and_still_closes(monkeypatch):
    bot = FakeBot("ignored", can_post=False)
    monkeypatch.setattr(telegram_bindings, "Bot", lambda _token: bot)

    with pytest.raises(
        telegram_bindings.TelegramBindingVerificationError,
        match="bot_cannot_post",
    ):
        await telegram_bindings.verify_telegram_binding(
            token="synthetic-token",
            chat_id=-100179000001,
            message_thread_id=None,
            purpose="materials_target",
        )
    assert bot.session.closed
