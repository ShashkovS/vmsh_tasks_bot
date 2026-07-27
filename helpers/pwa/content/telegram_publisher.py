"""Transport-neutral publisher for compiler-produced Telegram Rich HTML.

This is the narrow side-effect boundary required by Phase 2.  It deliberately
does not know about aiogram, credentials, bindings, retries, or a default chat.
Callers must supply one explicit destination and a transport implementation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from .model import CompileResult, ContentRole
from .renderers import TELEGRAM_RENDERER_VERSION
from .telegram import (
    TELEGRAM_BOT_API_DIALECT,
    TelegramRichLimits,
    TelegramRichMetrics,
    validate_telegram_rich_html,
)


class TelegramRichPublishError(RuntimeError):
    """A stable publication failure that never includes message content."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


class TelegramRichTransport(Protocol):
    async def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: Mapping[str, object],
        message_thread_id: int | None,
    ) -> object: ...

    async def edit_rich_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        rich_message: Mapping[str, object],
    ) -> object: ...

    async def delete_message(self, *, chat_id: int, message_id: int) -> object: ...


@dataclass(frozen=True, slots=True)
class TelegramRichDestination:
    chat_id: int
    message_thread_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.chat_id, int) or isinstance(self.chat_id, bool):
            raise TypeError("chat_id must be an explicit integer destination")
        if not -(2**63) <= self.chat_id < 2**63 or self.chat_id == 0:
            raise ValueError("chat_id is outside the signed Bot API range")
        if self.message_thread_id is not None and (
            not isinstance(self.message_thread_id, int)
            or isinstance(self.message_thread_id, bool)
            or self.message_thread_id <= 0
        ):
            raise ValueError("message_thread_id must be a positive integer")


@dataclass(frozen=True, slots=True)
class ValidatedTelegramRichDerivative:
    html: str
    sha256: str
    metrics: TelegramRichMetrics
    dialect: str
    renderer_version: str


@dataclass(frozen=True, slots=True)
class TelegramRichReceipt:
    chat_id: int
    message_id: int
    derivative_sha256: str
    metrics: TelegramRichMetrics


def validated_compiler_telegram(
    result: CompileResult,
) -> ValidatedTelegramRichDerivative:
    """Revalidate the exact compiler derivative immediately before transport."""

    if not isinstance(result, CompileResult):
        raise TypeError("result must be a CompileResult")
    if result.role is ContentRole.FULL_PREVIEW:
        raise TelegramRichPublishError(
            "telegram.preview_not_publishable",
            "A full preview cannot be sent as one audience material",
        )
    if result.has_errors:
        raise TelegramRichPublishError(
            "telegram.compile_errors",
            "The content revision has blocking compiler diagnostics",
        )
    derivative = result.telegram
    if (
        derivative.kind != "telegram_html"
        or derivative.renderer_version != TELEGRAM_RENDERER_VERSION
        or not derivative.content
    ):
        raise TelegramRichPublishError(
            "telegram.derivative_untrusted",
            "The Telegram derivative does not match the active compiler renderer",
        )
    actual_sha256 = hashlib.sha256(derivative.content.encode("utf-8")).hexdigest()
    if actual_sha256 != derivative.sha256:
        raise TelegramRichPublishError(
            "telegram.derivative_hash_mismatch",
            "The Telegram derivative changed after compilation",
        )
    normalized, metrics = validate_telegram_rich_html(
        derivative.content,
        # Publication always uses the fixed Bot API 10.2 boundary. Callers
        # cannot relax it with custom limits.
        limits=TelegramRichLimits(),
    )
    if normalized != derivative.content:
        raise TelegramRichPublishError(
            "telegram.derivative_not_canonical",
            "The Telegram derivative is not in canonical Rich HTML form",
        )
    return ValidatedTelegramRichDerivative(
        html=normalized,
        sha256=actual_sha256,
        metrics=metrics,
        dialect=TELEGRAM_BOT_API_DIALECT,
        renderer_version=TELEGRAM_RENDERER_VERSION,
    )


def _message_id(response: Any) -> int:
    raw_message_id = (
        response.get("message_id")
        if isinstance(response, Mapping)
        else getattr(response, "message_id", None)
    )
    if (
        not isinstance(raw_message_id, int)
        or isinstance(raw_message_id, bool)
        or raw_message_id <= 0
    ):
        raise TelegramRichPublishError(
            "telegram.response_invalid",
            "Telegram returned no positive integer message ID",
        )
    return raw_message_id


def _input_rich_message(
    derivative: ValidatedTelegramRichDerivative,
) -> Mapping[str, object]:
    # MappingProxyType prevents a transport from accidentally mutating the
    # validated request shared with audit/provenance code.
    return MappingProxyType(
        {
            "html": derivative.html,
            "skip_entity_detection": True,
        }
    )


class TelegramRichPublisher:
    def __init__(self, transport: TelegramRichTransport) -> None:
        self.transport = transport

    async def send(
        self,
        destination: TelegramRichDestination,
        result: CompileResult,
    ) -> TelegramRichReceipt:
        derivative = validated_compiler_telegram(result)
        try:
            response = await self.transport.send_rich_message(
                chat_id=destination.chat_id,
                rich_message=_input_rich_message(derivative),
                message_thread_id=destination.message_thread_id,
            )
        except TelegramRichPublishError:
            raise
        except Exception as error:
            raise TelegramRichPublishError(
                "telegram.send_failed",
                "Telegram Rich send failed",
            ) from error
        return TelegramRichReceipt(
            chat_id=destination.chat_id,
            message_id=_message_id(response),
            derivative_sha256=derivative.sha256,
            metrics=derivative.metrics,
        )

    async def edit(
        self,
        receipt: TelegramRichReceipt,
        result: CompileResult,
    ) -> TelegramRichReceipt:
        derivative = validated_compiler_telegram(result)
        try:
            response = await self.transport.edit_rich_message(
                chat_id=receipt.chat_id,
                message_id=receipt.message_id,
                rich_message=_input_rich_message(derivative),
            )
        except TelegramRichPublishError:
            raise
        except Exception as error:
            raise TelegramRichPublishError(
                "telegram.edit_failed",
                "Telegram Rich edit failed",
            ) from error
        if response is False:
            raise TelegramRichPublishError(
                "telegram.edit_rejected",
                "Telegram rejected the Rich edit",
            )
        if isinstance(response, Mapping) or hasattr(response, "message_id"):
            response_message_id = _message_id(response)
            if response_message_id != receipt.message_id:
                raise TelegramRichPublishError(
                    "telegram.edit_response_mismatch",
                    "Telegram returned a different message after Rich edit",
                )
        return TelegramRichReceipt(
            chat_id=receipt.chat_id,
            message_id=receipt.message_id,
            derivative_sha256=derivative.sha256,
            metrics=derivative.metrics,
        )

    async def delete(self, receipt: TelegramRichReceipt) -> None:
        try:
            deleted = await self.transport.delete_message(
                chat_id=receipt.chat_id,
                message_id=receipt.message_id,
            )
        except Exception as error:
            raise TelegramRichPublishError(
                "telegram.delete_failed",
                "Telegram Rich cleanup failed",
            ) from error
        if deleted is not True:
            raise TelegramRichPublishError(
                "telegram.delete_rejected",
                "Telegram rejected the Rich cleanup",
            )
