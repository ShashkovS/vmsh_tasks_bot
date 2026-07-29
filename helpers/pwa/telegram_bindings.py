"""One-shot Bot API verification for an admin-configured destination."""

from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError


class TelegramBindingVerificationError(RuntimeError):
    def __init__(self, reason: str, *, retryable: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


def _value(value: object) -> str:
    return str(getattr(value, "value", value)).casefold()


async def verify_telegram_binding(
    *,
    token: str,
    chat_id: int,
    message_thread_id: int | None,
    purpose: str,
) -> dict[str, object]:
    if not token:
        raise TelegramBindingVerificationError("telegram_not_configured")
    bot = Bot(token)
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
    except (TelegramAPIError, OSError, TimeoutError) as error:
        raise TelegramBindingVerificationError(
            "telegram_unavailable", retryable=True
        ) from error
    finally:
        await bot.session.close()


__all__ = ["TelegramBindingVerificationError", "verify_telegram_binding"]
