"""Aiogram-session adapter for Bot API Rich methods not yet generated upstream.

Import this module only from an explicitly enabled Telegram adapter.  It does
not load configuration or construct a bot, and it never chooses a destination.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiogram.methods.base import TelegramMethod
from pydantic import Field


class TelegramRichTransportFailure(RuntimeError):
    """A redacted raw Bot API failure without token or message content."""


class _SendRichMessage(TelegramMethod[dict[str, Any]]):
    __returning__ = dict[str, Any]
    __api_method__ = "sendRichMessage"

    chat_id: int
    rich_message: dict[str, object] = Field(repr=False)
    message_thread_id: int | None = None


class _EditRichMessage(TelegramMethod[dict[str, Any] | bool]):
    __returning__ = dict[str, Any] | bool
    __api_method__ = "editMessageText"

    chat_id: int
    message_id: int
    rich_message: dict[str, object] = Field(repr=False)


class _DeleteMessage(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "deleteMessage"

    chat_id: int
    message_id: int


class AiogramTelegramRichTransport:
    """Use an already-constructed Bot and its bounded HTTP session."""

    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def _request(self, method: TelegramMethod[Any], *, stage: str) -> object:
        try:
            return await self.bot(method)
        except Exception as error:
            # Never interpolate Telegram's remote description: it can echo a
            # request field. The guarded command records only this stable stage.
            raise TelegramRichTransportFailure(
                f"Telegram Rich {stage} request failed"
            ) from error

    async def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: Mapping[str, object],
        message_thread_id: int | None,
    ) -> object:
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "rich_message": dict(rich_message),
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        return await self._request(_SendRichMessage(**payload), stage="send")

    async def edit_rich_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        rich_message: Mapping[str, object],
    ) -> object:
        return await self._request(
            _EditRichMessage(
                chat_id=chat_id,
                message_id=message_id,
                rich_message=dict(rich_message),
            ),
            stage="edit",
        )

    async def delete_message(self, *, chat_id: int, message_id: int) -> object:
        return await self._request(
            _DeleteMessage(chat_id=chat_id, message_id=message_id),
            stage="delete",
        )
