"""One-shot Bot API verification for an admin-configured destination."""

from __future__ import annotations

import sys
from typing import Any


# Tests can replace this factory without importing aiogram.  Production loads
# it only when an administrator explicitly verifies a Telegram destination;
# the PWA startup path must stay independent from Telegram's Pydantic models.
# See vmshpwa/docs/runtime-isolation.md.
Bot: Any | None = None


class TelegramBindingVerificationError(RuntimeError):
    def __init__(self, reason: str, *, retryable: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


def _value(value: object) -> str:
    return str(getattr(value, "value", value)).casefold()


def _bot_factory():
    global Bot
    if Bot is not None:
        return Bot

    # aiogram's recursive Telegram model graph needs more than Python 3.14's
    # default import-time recursion budget.  Legacy startup imports it near the
    # root stack; this on-demand PWA integration can be reached much deeper.
    previous_limit = sys.getrecursionlimit()
    if previous_limit < 3000:
        sys.setrecursionlimit(3000)
    try:
        from aiogram import Bot as AiogramBot
    finally:
        if previous_limit < 3000:
            sys.setrecursionlimit(previous_limit)
    Bot = AiogramBot
    return Bot


def _is_telegram_api_error(error: Exception) -> bool:
    return any(
        base.__name__ == "TelegramAPIError"
        and base.__module__.startswith("aiogram.exceptions")
        for base in type(error).__mro__
    )


async def verify_telegram_binding(
    *,
    token: str,
    chat_id: int,
    message_thread_id: int | None,
    purpose: str,
) -> dict[str, object]:
    if not token:
        raise TelegramBindingVerificationError("telegram_not_configured")
    bot = _bot_factory()(token)
    try:
        identity = await bot.get_me()
        chat = await bot.get_chat(chat_id)
        canonical_chat_id = getattr(chat, "id", None)
        if (
            isinstance(canonical_chat_id, bool)
            or not isinstance(canonical_chat_id, int)
            or canonical_chat_id != chat_id
        ):
            raise TelegramBindingVerificationError("chat_id_changed")
        chat_type = _value(getattr(chat, "type", ""))
        if chat_type not in {"channel", "supergroup"}:
            raise TelegramBindingVerificationError("unsupported_chat_type")
        if message_thread_id is not None and (
            chat_type != "supergroup" or getattr(chat, "is_forum", False) is not True
        ):
            raise TelegramBindingVerificationError("topic_not_supported")
        member = await bot.get_chat_member(chat_id, identity.id)
        status = _value(getattr(member, "status", ""))
        if status not in {"administrator", "creator"}:
            raise TelegramBindingVerificationError("bot_is_not_admin")
        if purpose == "materials_target" and chat_type == "channel" and status != "creator":
            if getattr(member, "can_post_messages", None) is not True:
                raise TelegramBindingVerificationError("bot_cannot_post")
        title = str(getattr(chat, "title", "") or "").strip()
        if not title:
            raise TelegramBindingVerificationError("chat_has_no_title")
        return {"chat_id": canonical_chat_id, "title": title[:200]}
    except TelegramBindingVerificationError:
        raise
    except (OSError, TimeoutError) as error:
        raise TelegramBindingVerificationError(
            "telegram_unavailable", retryable=True
        ) from error
    except Exception as error:
        if _is_telegram_api_error(error):
            raise TelegramBindingVerificationError(
                "telegram_unavailable", retryable=True
            ) from error
        raise
    finally:
        await bot.session.close()


__all__ = ["TelegramBindingVerificationError", "verify_telegram_binding"]
