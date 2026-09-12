"""Hermetic Telegram contract and guarded synthetic capability lifecycle.

This module never constructs an aiogram ``Bot`` and never loads credentials.
Unit/E2E inject ``RecordingBot``; the strictly opt-in command in
``vmshpwa/scripts/telegram_test_capability.py`` is the only Phase-0 live caller.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Protocol

from helpers.pwa.content.compiler import compile_latex
from helpers.pwa.content.model import CompileResult, ContentRole
from helpers.pwa.content.telegram import TelegramRichLimits
from helpers.pwa.content.telegram_publisher import (
    TelegramRichDestination,
    TelegramRichPublisher,
    TelegramRichReceipt,
    TelegramRichTransport,
    validated_compiler_telegram,
)

EXPECTED_TEST_BOT_USERNAME = "vmsh179devbot"
EXPECTED_TEST_CHANNEL_TITLE = "vmsh179devbot channel"
# Outside Telegram's documented 52-significant-bit identifier range, while still
# fitting signed 64-bit. It cannot be mistaken for the real private test channel.
SYNTHETIC_TEST_CHAT_ID = -(2**60) + 179
_RUN_MARKER = re.compile(r"^[a-z0-9][a-z0-9-]{5,63}$")


class TelegramCapabilityError(RuntimeError):
    """A test identity, destination or required channel capability was wrong."""


class TelegramLifecycleError(RuntimeError):
    """A synthetic send/edit/delete lifecycle did not cleanly complete."""

    def __init__(
        self,
        result: "TelegramLifecycleResult | TelegramRichLifecycleResult",
    ):
        super().__init__(
            "Synthetic Telegram lifecycle failed; inspect safe result flags"
        )
        self.result = result


class TelegramBotContract(Protocol):
    async def get_me(self): ...

    async def get_chat(self, chat_id: int): ...

    async def get_chat_member(self, chat_id: int, user_id: int): ...

    async def send_message(self, chat_id: int, text: str, **kwargs): ...

    async def edit_message_text(
        self, text: str, *, chat_id: int, message_id: int, **kwargs
    ): ...

    async def delete_message(self, chat_id: int, message_id: int, **kwargs): ...


@dataclass(frozen=True, slots=True)
class VerifiedTelegramBinding:
    """Canonical destination produced only after identity/capability probes."""

    chat_id: int
    chat_title: str
    bot_id: int
    bot_username: str


@dataclass(frozen=True, slots=True)
class TelegramLifecycleResult:
    run_id: str
    binding: VerifiedTelegramBinding
    message_id: int | None
    sent: bool
    edited: bool
    cleanup_attempted: bool
    deleted: bool
    failure_stage: str | None


@dataclass(frozen=True, slots=True)
class TelegramRichLifecycleResult:
    """Safe Rich lifecycle evidence: identifiers, hashes and flags only."""

    run_id: str
    binding: VerifiedTelegramBinding
    message_id: int | None
    initial_derivative_sha256: str
    edited_derivative_sha256: str
    utf8_characters: int
    sent: bool
    edited: bool
    cleanup_attempted: bool
    deleted: bool
    failure_stage: str | None


def _enum_value(value: Any) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value).casefold()


async def verify_test_channel_binding(
    bot: TelegramBotContract,
    requested_chat_id: int,
) -> VerifiedTelegramBinding:
    """Resolve and verify the one allowlisted private channel before any send."""

    identity = await bot.get_me()
    username = str(getattr(identity, "username", "") or "").removeprefix("@")
    if not getattr(identity, "is_bot", False) or username.casefold() != (
        EXPECTED_TEST_BOT_USERNAME.casefold()
    ):
        raise TelegramCapabilityError("Unexpected Telegram test bot identity")

    chat = await bot.get_chat(requested_chat_id)
    canonical_chat_id = getattr(chat, "id", None)
    if not isinstance(canonical_chat_id, int) or isinstance(canonical_chat_id, bool):
        raise TelegramCapabilityError(
            "Telegram did not return a canonical integer chat ID"
        )
    if canonical_chat_id != requested_chat_id:
        raise TelegramCapabilityError(
            "Requested and canonical Telegram chat IDs differ"
        )
    if _enum_value(getattr(chat, "type", "")) != "channel":
        raise TelegramCapabilityError(
            "Allowlisted Telegram destination is not a channel"
        )
    title = str(getattr(chat, "title", "") or "")
    if title != EXPECTED_TEST_CHANNEL_TITLE:
        raise TelegramCapabilityError("Unexpected Telegram test channel title")
    if getattr(chat, "username", None) is not None:
        raise TelegramCapabilityError("Telegram test channel must remain private")

    bot_id = getattr(identity, "id", None)
    if not isinstance(bot_id, int) or isinstance(bot_id, bool):
        raise TelegramCapabilityError("Telegram did not return a canonical bot ID")
    member = await bot.get_chat_member(canonical_chat_id, bot_id)
    status = _enum_value(getattr(member, "status", ""))
    if status not in {"administrator", "creator"}:
        raise TelegramCapabilityError("Test bot is not an administrator in the channel")
    if status != "creator":
        required_rights = (
            "can_post_messages",
            "can_edit_messages",
            "can_delete_messages",
        )
        missing = [
            right
            for right in required_rights
            if getattr(member, right, None) is not True
        ]
        if missing:
            raise TelegramCapabilityError(
                "Test bot lacks required send/edit/delete channel capabilities"
            )

    return VerifiedTelegramBinding(
        chat_id=canonical_chat_id,
        chat_title=title,
        bot_id=bot_id,
        bot_username=username,
    )


async def run_synthetic_message_lifecycle(
    bot: TelegramBotContract,
    binding: VerifiedTelegramBinding,
    *,
    run_id: str,
) -> TelegramLifecycleResult:
    """Send, edit and always attempt deletion of one fixed synthetic message."""

    if not _RUN_MARKER.fullmatch(run_id):
        raise ValueError("run_id must be a 6-64 character lowercase synthetic marker")

    message_id: int | None = None
    sent = False
    edited = False
    cleanup_attempted = False
    deleted = False
    failure_stage: str | None = None
    primary_error: Exception | None = None
    cleanup_error: Exception | None = None
    cancellation: asyncio.CancelledError | None = None
    original_text = (
        "VMSH PWA synthetic integration probe\n"
        f"run: {run_id}\n"
        "No student or production data."
    )
    edited_text = f"{original_text}\nstate: edited"

    try:
        message = await bot.send_message(
            binding.chat_id,
            original_text,
            parse_mode=None,
            disable_notification=True,
        )
        raw_message_id = getattr(message, "message_id", None)
        if not isinstance(raw_message_id, int) or isinstance(raw_message_id, bool):
            raise TelegramCapabilityError(
                "Telegram send returned no integer message ID"
            )
        message_id = raw_message_id
        sent = True
        await bot.edit_message_text(
            edited_text,
            chat_id=binding.chat_id,
            message_id=message_id,
            parse_mode=None,
        )
        edited = True
    except asyncio.CancelledError as error:
        cancellation = error
        failure_stage = "edit" if sent else "send"
    except Exception as error:
        primary_error = error
        failure_stage = "edit" if sent else "send"
    finally:
        if message_id is not None:
            cleanup_attempted = True
            try:
                deleted = bool(await bot.delete_message(binding.chat_id, message_id))
                if not deleted:
                    raise TelegramCapabilityError("Telegram delete returned false")
            except asyncio.CancelledError as error:
                cancellation = error
                if failure_stage is None:
                    failure_stage = "delete"
            except Exception as error:
                cleanup_error = error
                if failure_stage is None:
                    failure_stage = "delete"

    result = TelegramLifecycleResult(
        run_id=run_id,
        binding=binding,
        message_id=message_id,
        sent=sent,
        edited=edited,
        cleanup_attempted=cleanup_attempted,
        deleted=deleted,
        failure_stage=failure_stage,
    )
    if cancellation is not None:
        if cleanup_error is not None:
            cancellation.add_note("Synthetic Telegram cleanup also failed")
        raise cancellation
    if primary_error is not None or cleanup_error is not None:
        cause = primary_error if primary_error is not None else cleanup_error
        raise TelegramLifecycleError(result) from cause
    return result


def compile_synthetic_rich_boundary(
    *,
    run_id: str,
    state: str,
) -> CompileResult:
    """Build compiler-owned Rich HTML at the exact 10.2 character boundary."""

    if not _RUN_MARKER.fullmatch(run_id):
        raise ValueError("run_id must be a 6-64 character lowercase synthetic marker")
    if state not in {"initial", "edited"}:
        raise ValueError("state must be initial or edited")

    def compile_with_fill(fill_count: int) -> CompileResult:
        source = (
            r"\begin{document}"
            r"\задача "
            r"\textbf{VMSH PWA synthetic Rich Message}. "
            f"Run {run_id}; state {state}. "
            r"Formula $x^2+y^2=179$."
            r"\begin{enumerate}"
            r"\item First synthetic item."
            r"\item Second synthetic item."
            r"\end{enumerate}"
            r"\begin{tabular}{|c|c|}"
            r"\hline $x$ & $y$ \\"
            r"\hline 1 & 179 \\"
            r"\hline\end{tabular}" + ("я" * fill_count) + r"\кзадача\end{document}"
        ).encode("utf-8")
        return compile_latex(
            source,
            source_name=f"synthetic/rich-boundary-{state}.tex",
            role=ContentRole.CONDITION,
        )

    seed = compile_with_fill(1)
    seed_derivative = validated_compiler_telegram(seed)
    maximum = TelegramRichLimits().max_utf8_characters
    fill_count = 1 + maximum - seed_derivative.metrics.utf8_characters
    if fill_count < 1:
        raise RuntimeError("Synthetic Rich boundary template exceeds Bot API limits")
    result = compile_with_fill(fill_count)
    derivative = validated_compiler_telegram(result)
    if derivative.metrics.utf8_characters != maximum:
        raise RuntimeError("Synthetic Rich fixture did not reach the exact boundary")
    return result


async def run_synthetic_rich_message_lifecycle(
    transport: TelegramRichTransport,
    binding: VerifiedTelegramBinding,
    *,
    run_id: str,
) -> TelegramRichLifecycleResult:
    """Send/edit/delete exactly one compiler-produced boundary Rich Message."""

    initial = compile_synthetic_rich_boundary(run_id=run_id, state="initial")
    edited_result = compile_synthetic_rich_boundary(run_id=run_id, state="edited")
    initial_derivative = validated_compiler_telegram(initial)
    edited_derivative = validated_compiler_telegram(edited_result)
    publisher = TelegramRichPublisher(transport)
    destination = TelegramRichDestination(chat_id=binding.chat_id)

    receipt: TelegramRichReceipt | None = None
    sent = False
    edited = False
    cleanup_attempted = False
    deleted = False
    failure_stage: str | None = None
    primary_error: Exception | None = None
    cleanup_error: Exception | None = None
    cancellation: asyncio.CancelledError | None = None

    try:
        receipt = await publisher.send(destination, initial)
        sent = True
        receipt = await publisher.edit(receipt, edited_result)
        edited = True
    except asyncio.CancelledError as error:
        cancellation = error
        failure_stage = "edit" if sent else "send"
    except Exception as error:
        primary_error = error
        failure_stage = "edit" if sent else "send"
    finally:
        if receipt is not None:
            cleanup_attempted = True
            try:
                await publisher.delete(receipt)
                deleted = True
            except asyncio.CancelledError as error:
                cancellation = error
                if failure_stage is None:
                    failure_stage = "delete"
            except Exception as error:
                cleanup_error = error
                if failure_stage is None:
                    failure_stage = "delete"

    result = TelegramRichLifecycleResult(
        run_id=run_id,
        binding=binding,
        message_id=receipt.message_id if receipt is not None else None,
        initial_derivative_sha256=initial_derivative.sha256,
        edited_derivative_sha256=edited_derivative.sha256,
        utf8_characters=initial_derivative.metrics.utf8_characters,
        sent=sent,
        edited=edited,
        cleanup_attempted=cleanup_attempted,
        deleted=deleted,
        failure_stage=failure_stage,
    )
    if cancellation is not None:
        if cleanup_error is not None:
            cancellation.add_note("Synthetic Telegram Rich cleanup also failed")
        raise cancellation
    if primary_error is not None or cleanup_error is not None:
        cause = primary_error if primary_error is not None else cleanup_error
        raise TelegramLifecycleError(result) from cause
    return result


class RecordingBot:
    """Network-free bot implementing probe plus send/edit/delete behavior."""

    def __init__(
        self,
        *,
        chat_id: int = SYNTHETIC_TEST_CHAT_ID,
        username: str = EXPECTED_TEST_BOT_USERNAME,
        chat_title: str = EXPECTED_TEST_CHANNEL_TITLE,
        chat_username: str | None = None,
        member_status: str = "administrator",
        can_post_messages: bool = True,
        can_edit_messages: bool = True,
        can_delete_messages: bool = True,
        fail_stage: str | None = None,
    ):
        self.bot_id = 179000001
        self.chat_id = chat_id
        self.username = username
        self.chat_title = chat_title
        self.chat_username = chat_username
        self.member_status = member_status
        self.can_post_messages = can_post_messages
        self.can_edit_messages = can_edit_messages
        self.can_delete_messages = can_delete_messages
        self.fail_stage = fail_stage
        self.operations: list[dict[str, Any]] = []
        self.messages: dict[int, str] = {}
        self.rich_messages: dict[int, str] = {}
        self._next_message_id = 1000

    async def get_me(self):
        self.operations.append({"kind": "get_me"})
        return SimpleNamespace(id=self.bot_id, is_bot=True, username=self.username)

    async def get_chat(self, chat_id: int):
        self.operations.append({"kind": "get_chat", "chat_id": chat_id})
        if chat_id != self.chat_id:
            raise LookupError("Unknown synthetic chat")
        return SimpleNamespace(
            id=self.chat_id,
            type="channel",
            title=self.chat_title,
            username=self.chat_username,
        )

    async def get_chat_member(self, chat_id: int, user_id: int):
        self.operations.append(
            {"kind": "get_chat_member", "chat_id": chat_id, "user_id": user_id}
        )
        return SimpleNamespace(
            status=self.member_status,
            can_post_messages=self.can_post_messages,
            can_edit_messages=self.can_edit_messages,
            can_delete_messages=self.can_delete_messages,
        )

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.operations.append(
            {"kind": "send", "chat_id": chat_id, "text": text, "kwargs": kwargs}
        )
        if self.fail_stage == "send":
            raise RuntimeError("synthetic send failure")
        self._next_message_id += 1
        self.messages[self._next_message_id] = text
        return SimpleNamespace(message_id=self._next_message_id)

    async def edit_message_text(
        self, text: str, *, chat_id: int, message_id: int, **kwargs
    ):
        self.operations.append(
            {
                "kind": "edit",
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "kwargs": kwargs,
            }
        )
        if self.fail_stage == "edit":
            raise RuntimeError("synthetic edit failure")
        if chat_id != self.chat_id or message_id not in self.messages:
            raise LookupError("Unknown synthetic message")
        self.messages[message_id] = text
        return True

    async def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message,
        message_thread_id: int | None,
    ):
        html = rich_message.get("html")
        if not isinstance(html, str):
            raise TypeError("Synthetic Rich transport requires HTML")
        html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
        self.operations.append(
            {
                "kind": "send_rich",
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "html_sha256": html_sha256,
            }
        )
        if self.fail_stage in {"send", "send_rich"}:
            raise RuntimeError("synthetic Rich send failure")
        if chat_id != self.chat_id:
            raise LookupError("Unknown synthetic Rich chat")
        self._next_message_id += 1
        self.rich_messages[self._next_message_id] = html_sha256
        return SimpleNamespace(message_id=self._next_message_id)

    async def edit_rich_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        rich_message,
    ):
        html = rich_message.get("html")
        if not isinstance(html, str):
            raise TypeError("Synthetic Rich transport requires HTML")
        html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
        self.operations.append(
            {
                "kind": "edit_rich",
                "chat_id": chat_id,
                "message_id": message_id,
                "html_sha256": html_sha256,
            }
        )
        if self.fail_stage in {"edit", "edit_rich"}:
            raise RuntimeError("synthetic Rich edit failure")
        if chat_id != self.chat_id or message_id not in self.rich_messages:
            raise LookupError("Unknown synthetic Rich message")
        self.rich_messages[message_id] = html_sha256
        return SimpleNamespace(message_id=message_id)

    async def delete_message(self, chat_id: int, message_id: int, **kwargs):
        self.operations.append(
            {
                "kind": "delete",
                "chat_id": chat_id,
                "message_id": message_id,
                "kwargs": kwargs,
            }
        )
        if self.fail_stage == "delete":
            raise RuntimeError("synthetic delete failure")
        if chat_id != self.chat_id or (
            message_id not in self.messages and message_id not in self.rich_messages
        ):
            raise LookupError("Unknown synthetic message")
        self.messages.pop(message_id, None)
        self.rich_messages.pop(message_id, None)
        return True
