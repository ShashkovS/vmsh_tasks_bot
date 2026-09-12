from __future__ import annotations

import asyncio
import json
import os
import stat
from enum import Enum
from types import SimpleNamespace

import pytest

from helpers.pwa.telegram_test_harness import (
    RecordingBot,
    SYNTHETIC_TEST_CHAT_ID,
    TelegramCapabilityError,
    TelegramLifecycleError,
    VerifiedTelegramBinding,
    run_synthetic_message_lifecycle,
    verify_test_channel_binding,
)
from helpers.pwa.telegram_test_binding import (
    TelegramTestBindingError,
    load_verified_binding,
    save_verified_binding,
)
from vmshpwa.scripts import telegram_test_capability as command


@pytest.mark.asyncio
async def test_recording_bot_runs_verified_send_edit_delete_lifecycle():
    bot = RecordingBot()
    binding = await verify_test_channel_binding(bot, bot.chat_id)
    result = await run_synthetic_message_lifecycle(
        bot, binding, run_id="tg-hermetic-0001"
    )

    assert [operation["kind"] for operation in bot.operations] == [
        "get_me",
        "get_chat",
        "get_chat_member",
        "send",
        "edit",
        "delete",
    ]
    assert result.sent
    assert result.edited
    assert result.cleanup_attempted
    assert result.deleted
    assert result.failure_stage is None
    assert bot.messages == {}
    assert abs(SYNTHETIC_TEST_CHAT_ID) > 2**52


@pytest.mark.asyncio
async def test_chat_type_enum_is_normalized_by_its_value():
    class ChatType(Enum):
        CHANNEL = "channel"

    class EnumChatRecordingBot(RecordingBot):
        async def get_chat(self, chat_id: int):
            self.operations.append({"kind": "get_chat", "chat_id": chat_id})
            return SimpleNamespace(
                id=self.chat_id,
                type=ChatType.CHANNEL,
                title=self.chat_title,
            )

    bot = EnumChatRecordingBot()
    binding = await verify_test_channel_binding(bot, bot.chat_id)
    assert binding.chat_id == SYNTHETIC_TEST_CHAT_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"username": "another_bot"},
        {"chat_title": "another channel"},
        {"chat_username": "public_test_channel"},
        {"member_status": "member"},
        {"can_post_messages": False},
        {"can_edit_messages": False},
        {"can_delete_messages": False},
    ],
)
async def test_identity_destination_and_rights_fail_before_send(kwargs):
    bot = RecordingBot(**kwargs)

    with pytest.raises(TelegramCapabilityError):
        await verify_test_channel_binding(bot, bot.chat_id)

    assert not [
        operation for operation in bot.operations if operation["kind"] == "send"
    ]


@pytest.mark.asyncio
async def test_edit_failure_still_attempts_and_completes_cleanup():
    bot = RecordingBot(fail_stage="edit")
    binding = await verify_test_channel_binding(bot, bot.chat_id)

    with pytest.raises(TelegramLifecycleError) as captured:
        await run_synthetic_message_lifecycle(bot, binding, run_id="tg-edit-failure")

    result = captured.value.result
    assert result.sent
    assert not result.edited
    assert result.cleanup_attempted
    assert result.deleted
    assert result.failure_stage == "edit"
    assert bot.messages == {}
    assert [operation["kind"] for operation in bot.operations[-3:]] == [
        "send",
        "edit",
        "delete",
    ]


@pytest.mark.asyncio
async def test_delete_failure_is_visible_in_safe_lifecycle_result():
    bot = RecordingBot(fail_stage="delete")
    binding = await verify_test_channel_binding(bot, bot.chat_id)

    with pytest.raises(TelegramLifecycleError) as captured:
        await run_synthetic_message_lifecycle(bot, binding, run_id="tg-delete-failure")

    result = captured.value.result
    assert result.sent and result.edited
    assert result.cleanup_attempted
    assert not result.deleted
    assert result.failure_stage == "delete"


@pytest.mark.asyncio
async def test_cancellation_attempts_cleanup_then_propagates_cancelled_error():
    class BlockingEditBot(RecordingBot):
        def __init__(self):
            super().__init__()
            self.edit_started = asyncio.Event()
            self.release_edit = asyncio.Event()

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
            self.edit_started.set()
            await self.release_edit.wait()

    bot = BlockingEditBot()
    binding = await verify_test_channel_binding(bot, bot.chat_id)
    lifecycle = asyncio.create_task(
        run_synthetic_message_lifecycle(bot, binding, run_id="tg-cancelled")
    )
    await asyncio.wait_for(bot.edit_started.wait(), timeout=1)
    lifecycle.cancel()

    with pytest.raises(asyncio.CancelledError):
        await lifecycle
    assert [operation["kind"] for operation in bot.operations[-3:]] == [
        "send",
        "edit",
        "delete",
    ]
    assert bot.messages == {}


def test_command_refuses_without_all_three_live_gates_before_loading_credentials(
    monkeypatch,
):
    credential_read = False

    def forbidden_credential_read():
        nonlocal credential_read
        credential_read = True
        raise AssertionError("credentials must not be read")

    monkeypatch.setattr(
        command, "load_allowlisted_test_bot_token", forbidden_credential_read
    )
    assert command.main([]) == 2
    assert not credential_read


def test_command_rejects_positive_ui_fragment_instead_of_guessing_canonical_id(
    monkeypatch,
):
    monkeypatch.setenv(command.LIVE_ENVIRONMENT_FLAG, "1")
    monkeypatch.setenv(command.CHANNEL_ID_ENVIRONMENT_KEY, "1234567890")
    monkeypatch.delenv("PROD", raising=False)

    with pytest.raises(command.LiveTelegramGuardError, match="canonical signed"):
        command.validate_live_opt_in(
            live=True,
            confirmation=command.CONFIRMATION,
            bind_channel=True,
            run_smoke=False,
        )
        command.requested_chat_id_from_environment()


def test_write_enabled_smoke_refuses_environment_destination(monkeypatch):
    monkeypatch.setenv(command.LIVE_ENVIRONMENT_FLAG, "1")
    monkeypatch.setenv(command.CHANNEL_ID_ENVIRONMENT_KEY, "-1001234567890")
    monkeypatch.delenv("PROD", raising=False)

    with pytest.raises(command.LiveTelegramGuardError, match="environment destination"):
        command.validate_live_opt_in(
            live=True,
            confirmation=command.CONFIRMATION,
            bind_channel=False,
            run_smoke=True,
        )


def test_test_config_loader_returns_only_allowlisted_token(tmp_path, monkeypatch):
    token = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    config_path = tmp_path / "vmsh_bot_config_test.json"
    config_path.write_text(
        json.dumps(
            {
                "telegram_bot_token": token,
                "google_cred_json": "must-not-be-used",
                "s3_secret_key": "must-not-be-used",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(command, "TEST_CONFIG_PATH", config_path)

    assert command.load_allowlisted_test_bot_token() == token


def test_test_config_loader_opens_with_no_follow(tmp_path, monkeypatch):
    token = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    config_path = tmp_path / "vmsh_bot_config_test.json"
    config_path.write_text(json.dumps({"telegram_bot_token": token}), encoding="utf-8")
    monkeypatch.setattr(command, "TEST_CONFIG_PATH", config_path)
    original_open = command.os.open
    observed_flags = []

    def tracking_open(path, flags, *args, **kwargs):
        observed_flags.append(flags)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(command.os, "open", tracking_open)
    assert command.load_allowlisted_test_bot_token() == token
    strongest = getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0)
    if strongest:
        assert observed_flags[0] & strongest


def test_test_config_loader_rejects_symlink(tmp_path, monkeypatch):
    real_path = tmp_path / "real.json"
    real_path.write_text(
        json.dumps(
            {"telegram_bot_token": ("123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")}
        ),
        encoding="utf-8",
    )
    link_path = tmp_path / "linked.json"
    link_path.symlink_to(real_path)
    monkeypatch.setattr(command, "TEST_CONFIG_PATH", link_path)

    with pytest.raises(command.LiveTelegramGuardError, match="symlink"):
        command.load_allowlisted_test_bot_token()


def test_test_config_loader_rejects_hardlinked_credential_file(tmp_path, monkeypatch):
    real_path = tmp_path / "real.json"
    real_path.write_text(
        json.dumps(
            {"telegram_bot_token": ("123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")}
        ),
        encoding="utf-8",
    )
    hardlink_path = tmp_path / "hardlink.json"
    os.link(real_path, hardlink_path)
    monkeypatch.setattr(command, "TEST_CONFIG_PATH", hardlink_path)

    with pytest.raises(command.LiveTelegramGuardError, match="regular file"):
        command.load_allowlisted_test_bot_token()


def test_safe_report_never_contains_token_or_remote_error_text():
    report = command._safe_report(
        run_id="tg-safe-report",
        status="failed",
        error_code="capability_verification_failed",
    )
    serialized = json.dumps(report)

    assert "telegram_bot_token" not in serialized
    assert "123456789:" not in serialized
    assert set(report) == {
        "schemaVersion",
        "runId",
        "action",
        "attemptedAt",
        "syntheticOnly",
        "expectedBotUsername",
        "expectedChannelTitle",
        "status",
        "errorCode",
    }


def test_live_report_is_written_owner_only(tmp_path, monkeypatch):
    monkeypatch.setattr(command, "REPORT_ROOT", tmp_path)
    path = command._write_report(
        "tg-private-report",
        command._safe_report(run_id="tg-private-report", status="passed"),
    )

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_verified_binding_store_is_owner_only_and_immutable(tmp_path):
    path = tmp_path / "private" / "binding.sqlite3"
    binding = VerifiedTelegramBinding(
        chat_id=SYNTHETIC_TEST_CHAT_ID,
        chat_title="vmsh179devbot channel",
        bot_id=179000001,
        bot_username="vmsh179devbot",
    )

    save_verified_binding(path, binding)
    assert load_verified_binding(path) == binding
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    changed = VerifiedTelegramBinding(
        chat_id=SYNTHETIC_TEST_CHAT_ID - 1,
        chat_title=binding.chat_title,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
    )
    with pytest.raises(TelegramTestBindingError, match="different"):
        save_verified_binding(path, changed)
    assert load_verified_binding(path) == binding


def test_verified_binding_store_rejects_non_test_identity(tmp_path):
    path = tmp_path / "binding.sqlite3"
    wrong = VerifiedTelegramBinding(
        chat_id=SYNTHETIC_TEST_CHAT_ID,
        chat_title="another channel",
        bot_id=179000001,
        bot_username="vmsh179devbot",
    )

    with pytest.raises(TelegramTestBindingError, match="dedicated target"):
        save_verified_binding(path, wrong)
    assert not path.exists()


def test_verified_binding_store_rejects_symlink(tmp_path):
    real = tmp_path / "real.sqlite3"
    binding = VerifiedTelegramBinding(
        chat_id=SYNTHETIC_TEST_CHAT_ID,
        chat_title="vmsh179devbot channel",
        bot_id=179000001,
        bot_username="vmsh179devbot",
    )
    save_verified_binding(real, binding)
    link = tmp_path / "binding.sqlite3"
    link.symlink_to(real)

    with pytest.raises(TelegramTestBindingError, match="owner-only"):
        load_verified_binding(link)


def test_verified_binding_store_rejects_hardlink_and_sidecar(tmp_path):
    real = tmp_path / "real.sqlite3"
    binding = VerifiedTelegramBinding(
        chat_id=SYNTHETIC_TEST_CHAT_ID,
        chat_title="vmsh179devbot channel",
        bot_id=179000001,
        bot_username="vmsh179devbot",
    )
    save_verified_binding(real, binding)
    hardlink = tmp_path / "hardlink.sqlite3"
    os.link(real, hardlink)
    with pytest.raises(TelegramTestBindingError, match="owner-only"):
        load_verified_binding(hardlink)

    hardlink.unlink()
    (tmp_path / "real.sqlite3-wal").write_bytes(b"synthetic sidecar")
    with pytest.raises(TelegramTestBindingError, match="quiescent"):
        load_verified_binding(real)


def test_command_uses_persisted_binding_as_only_smoke_destination(
    tmp_path, monkeypatch
):
    binding_path = tmp_path / "binding.sqlite3"
    report_root = tmp_path / "reports"
    binding = VerifiedTelegramBinding(
        chat_id=command.EXPECTED_TEST_CHANNEL_CHAT_ID,
        chat_title="vmsh179devbot channel",
        bot_id=179000001,
        bot_username="vmsh179devbot",
    )
    observed = {}

    async def fake_bind(_token, chat_id):
        assert chat_id == command.EXPECTED_TEST_CHANNEL_CHAT_ID
        return binding

    async def fake_smoke(_token, trusted_binding, run_id):
        observed["binding"] = trusted_binding
        bot = RecordingBot(chat_id=trusted_binding.chat_id)
        return await run_synthetic_message_lifecycle(
            bot, trusted_binding, run_id=run_id
        )

    monkeypatch.setattr(command, "BINDING_DATABASE_PATH", binding_path)
    monkeypatch.setattr(command, "REPORT_ROOT", report_root)
    monkeypatch.setattr(command, "load_allowlisted_test_bot_token", lambda: "token")
    monkeypatch.setattr(command, "_execute_bind", fake_bind)
    monkeypatch.setattr(command, "_execute_smoke", fake_smoke)
    monkeypatch.setenv(command.LIVE_ENVIRONMENT_FLAG, "1")
    monkeypatch.setenv(
        command.CHANNEL_ID_ENVIRONMENT_KEY,
        str(command.EXPECTED_TEST_CHANNEL_CHAT_ID),
    )
    monkeypatch.delenv("PROD", raising=False)

    assert (
        command.main(["--live", "--bind-channel", "--confirm", command.CONFIRMATION])
        == 0
    )
    monkeypatch.delenv(command.CHANNEL_ID_ENVIRONMENT_KEY)
    assert (
        command.main(["--live", "--run-smoke", "--confirm", command.CONFIRMATION]) == 0
    )
    assert observed["binding"] == binding
