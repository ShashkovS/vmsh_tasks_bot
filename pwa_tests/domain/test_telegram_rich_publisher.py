from __future__ import annotations

import json
from dataclasses import replace

import pytest

from helpers.pwa.content.compiler import compile_latex
from helpers.pwa.content.model import ContentRole
from helpers.pwa.content.telegram import TelegramRichLimits
from helpers.pwa.content.telegram_publisher import (
    TelegramRichDestination,
    TelegramRichPublishError,
    TelegramRichPublisher,
    validated_compiler_telegram,
)
from helpers.pwa.telegram_rich_aiogram import (
    AiogramTelegramRichTransport,
    TelegramRichTransportFailure,
)
from helpers.pwa.telegram_test_harness import (
    RecordingBot,
    TelegramLifecycleError,
    compile_synthetic_rich_boundary,
    run_synthetic_rich_message_lifecycle,
    verify_test_channel_binding,
)


def _compiled(text: str = "Первоначальный текст"):
    return compile_latex(
        (
            r"\begin{document}\задача "
            + text
            + r" и формула $x^2=179$.\кзадача\end{document}"
        ).encode(),
        source_name="synthetic/rich-publisher.tex",
        role=ContentRole.CONDITION,
    )


@pytest.mark.asyncio
async def test_recording_bot_runs_compiler_rich_send_edit_delete_without_content_log():
    bot = RecordingBot()
    binding = await verify_test_channel_binding(bot, bot.chat_id)

    result = await run_synthetic_rich_message_lifecycle(
        bot,
        binding,
        run_id="tg-rich-hermetic-0001",
    )

    assert [operation["kind"] for operation in bot.operations] == [
        "get_me",
        "get_chat",
        "get_chat_member",
        "send_rich",
        "edit_rich",
        "delete",
    ]
    assert result.sent and result.edited and result.deleted
    assert result.cleanup_attempted
    assert result.failure_stage is None
    assert result.message_id is not None
    assert result.utf8_characters == TelegramRichLimits().max_utf8_characters
    assert result.initial_derivative_sha256 != result.edited_derivative_sha256
    assert bot.rich_messages == {}
    serialized_operations = json.dumps(bot.operations)
    assert "VMSH PWA synthetic" not in serialized_operations
    assert "я" not in serialized_operations
    assert "html_sha256" in serialized_operations


@pytest.mark.asyncio
async def test_rich_edit_failure_still_deletes_the_sent_boundary_message():
    bot = RecordingBot(fail_stage="edit_rich")
    binding = await verify_test_channel_binding(bot, bot.chat_id)

    with pytest.raises(TelegramLifecycleError) as captured:
        await run_synthetic_rich_message_lifecycle(
            bot,
            binding,
            run_id="tg-rich-edit-failure",
        )

    result = captured.value.result
    assert result.sent
    assert not result.edited
    assert result.cleanup_attempted and result.deleted
    assert result.failure_stage == "edit"
    assert bot.rich_messages == {}


def test_exact_boundary_is_compiler_owned_and_one_character_more_is_rejected():
    result = compile_synthetic_rich_boundary(
        run_id="tg-rich-boundary-0001",
        state="initial",
    )
    derivative = validated_compiler_telegram(result)

    assert derivative.metrics.utf8_characters == 32_768
    too_large = _compiled("я" * 32_768)
    assert too_large.has_errors
    with pytest.raises(TelegramRichPublishError) as captured:
        validated_compiler_telegram(too_large)
    assert captured.value.code == "telegram.compile_errors"


@pytest.mark.asyncio
async def test_publisher_rejects_tampered_or_preview_derivative_before_transport():
    bot = RecordingBot()
    publisher = TelegramRichPublisher(bot)
    destination = TelegramRichDestination(chat_id=bot.chat_id)
    compiled = _compiled()
    tampered = replace(
        compiled,
        telegram=replace(compiled.telegram, content=compiled.telegram.content + "x"),
    )

    with pytest.raises(TelegramRichPublishError) as captured:
        await publisher.send(destination, tampered)
    assert captured.value.code == "telegram.derivative_hash_mismatch"

    preview = compile_latex(
        r"\begin{document}\задача text\кзадача\end{document}".encode(),
        source_name="synthetic/full-preview.tex",
        role=ContentRole.FULL_PREVIEW,
    )
    with pytest.raises(TelegramRichPublishError) as captured:
        await publisher.send(destination, preview)
    assert captured.value.code == "telegram.preview_not_publishable"
    assert not [item for item in bot.operations if item["kind"] == "send_rich"]


@pytest.mark.asyncio
async def test_aiogram_raw_adapter_uses_bot_api_10_2_fields_without_plain_text_mode():
    class FakeBot:
        def __init__(self):
            self.calls = []
            self.method_reprs = []

        async def __call__(self, method):
            self.method_reprs.append(repr(method))
            payload = method.model_dump(exclude_none=True)
            self.calls.append((method.__api_method__, payload))
            if method.__api_method__ == "deleteMessage":
                return True
            if method.__api_method__ == "editMessageText":
                return True
            return {"message_id": 179}

    bot = FakeBot()
    publisher = TelegramRichPublisher(AiogramTelegramRichTransport(bot))
    receipt = await publisher.send(TelegramRichDestination(-100179), _compiled())
    receipt = await publisher.edit(receipt, _compiled("Исправленный текст"))
    await publisher.delete(receipt)

    assert [method for method, _payload in bot.calls] == [
        "sendRichMessage",
        "editMessageText",
        "deleteMessage",
    ]
    send = bot.calls[0][1]
    edit = bot.calls[1][1]
    assert set(send) == {"chat_id", "rich_message"}
    assert set(edit) == {"chat_id", "message_id", "rich_message"}
    assert set(send["rich_message"]) == {"html", "skip_entity_detection"}
    assert send["rich_message"]["skip_entity_detection"] is True
    assert "text" not in edit and "parse_mode" not in edit
    assert "Первоначальный текст" not in "".join(bot.method_reprs)
    assert "Исправленный текст" not in "".join(bot.method_reprs)


@pytest.mark.asyncio
async def test_aiogram_adapter_redacts_remote_exception_text():
    class FailingBot:
        async def __call__(self, _method):
            raise RuntimeError("token 123456:SECRET and full message")

    transport = AiogramTelegramRichTransport(FailingBot())

    with pytest.raises(TelegramRichTransportFailure) as captured:
        await transport.send_rich_message(
            chat_id=-100179,
            rich_message={"html": "<p>synthetic</p>"},
            message_thread_id=None,
        )

    assert "123456:SECRET" not in str(captured.value)
    assert "full message" not in str(captured.value)
