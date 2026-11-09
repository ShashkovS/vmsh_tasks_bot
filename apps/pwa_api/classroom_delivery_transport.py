"""Deliver queued classroom assignments through the optional Telegram adapter."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from db_methods.pwa.classroom_delivery import (
    claim_next_telegram_recipient,
    finish_telegram_batch,
    finish_telegram_recipient,
)
from helpers.pwa.classroom_delivery import classroom_assignment_message
from models.pwa.classroom_delivery import read_classroom_delivery_batch


TelegramClassroomSender = Callable[[int, str], Awaitable[int]]


def _error_code(error: Exception) -> str:
    # Keep the PWA-only process independent from aiogram at import time.  On
    # Python 3.14 aiogram's eager Pydantic model rebuild can exceed the
    # recursion limit when it is imported late in the already-composed PWA
    # application.  The stable aiogram exception class names preserve the
    # existing classification without importing Telegram internals here.
    error_types = {
        base.__name__
        for base in type(error).__mro__
        if base.__module__.startswith("aiogram.exceptions")
    }
    if "TelegramForbiddenError" in error_types:
        return "telegram_forbidden"
    if "TelegramBadRequest" in error_types:
        return "telegram_bad_request"
    if "TelegramNetworkError" in error_types or isinstance(error, TimeoutError):
        return "telegram_temporary"
    if "TelegramAPIError" in error_types:
        return "telegram_api_error"
    return "telegram_unexpected"


async def deliver_classroom_telegram_batch(
    factory,
    *,
    batch_public_id: str,
    sender: TelegramClassroomSender,
    now: Callable[[], str],
) -> dict[str, object]:
    while True:
        recipient = await factory.run_write_async(
            lambda connection: claim_next_telegram_recipient(
                connection, batch_public_id
            )
        )
        if recipient is None:
            break
        try:
            await sender(
                int(recipient["telegram_chat_id"]),
                classroom_assignment_message(recipient),
            )
        except Exception as error:
            error_code = _error_code(error)
            await factory.run_write_async(
                lambda connection: finish_telegram_recipient(
                    connection,
                    batch_id=int(recipient["batch_id"]),
                    course_enrollment_id=int(recipient["course_enrollment_id"]),
                    state="failed",
                    error_code=error_code,
                    sent_at=None,
                )
            )
        else:
            sent_at = now()
            await factory.run_write_async(
                lambda connection: finish_telegram_recipient(
                    connection,
                    batch_id=int(recipient["batch_id"]),
                    course_enrollment_id=int(recipient["course_enrollment_id"]),
                    state="sent",
                    error_code=None,
                    sent_at=sent_at,
                )
            )

    await factory.run_write_async(
        lambda connection: finish_telegram_batch(connection, batch_public_id, now())
    )
    return await factory.run_read_async(
        lambda connection: read_classroom_delivery_batch(connection, batch_public_id)
    )


__all__ = ["TelegramClassroomSender", "deliver_classroom_telegram_batch"]
