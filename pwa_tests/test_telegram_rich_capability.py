from __future__ import annotations

import json

from helpers.pwa.telegram_test_binding import save_verified_binding
from helpers.pwa.telegram_test_harness import (
    RecordingBot,
    VerifiedTelegramBinding,
    run_synthetic_rich_message_lifecycle,
)
from vmshpwa.scripts import telegram_test_capability as command


def _binding() -> VerifiedTelegramBinding:
    return VerifiedTelegramBinding(
        chat_id=command.EXPECTED_TEST_CHANNEL_CHAT_ID,
        chat_title="vmsh179devbot channel",
        bot_id=179000001,
        bot_username="vmsh179devbot",
    )


def test_live_bind_accepts_only_the_owner_approved_canonical_chat_id(monkeypatch):
    monkeypatch.setenv(
        command.CHANNEL_ID_ENVIRONMENT_KEY,
        str(command.EXPECTED_TEST_CHANNEL_CHAT_ID),
    )
    assert (
        command.requested_chat_id_from_environment()
        == command.EXPECTED_TEST_CHANNEL_CHAT_ID
    )

    monkeypatch.setenv(command.CHANNEL_ID_ENVIRONMENT_KEY, "-1003913815636")
    try:
        command.requested_chat_id_from_environment()
    except command.LiveTelegramGuardError as error:
        assert "dedicated canonical signed" in str(error)
    else:
        raise AssertionError("another Telegram channel must fail closed")


def test_rich_smoke_uses_persisted_binding_and_writes_content_free_report(
    tmp_path,
    monkeypatch,
):
    binding_path = tmp_path / "binding.sqlite3"
    report_root = tmp_path / "reports"
    binding = _binding()
    save_verified_binding(binding_path, binding)

    async def fake_rich_smoke(_token, trusted_binding, run_id):
        assert trusted_binding == binding
        bot = RecordingBot(chat_id=binding.chat_id)
        return await run_synthetic_rich_message_lifecycle(
            bot,
            trusted_binding,
            run_id=run_id,
        )

    monkeypatch.setattr(command, "BINDING_DATABASE_PATH", binding_path)
    monkeypatch.setattr(command, "REPORT_ROOT", report_root)
    monkeypatch.setattr(command, "load_allowlisted_test_bot_token", lambda: "token")
    monkeypatch.setattr(command, "_execute_rich_smoke", fake_rich_smoke)
    monkeypatch.setenv(command.LIVE_ENVIRONMENT_FLAG, "1")
    monkeypatch.delenv(command.CHANNEL_ID_ENVIRONMENT_KEY, raising=False)
    monkeypatch.delenv("PROD", raising=False)

    exit_code = command.main(
        [
            "--live",
            "--run-rich-smoke",
            "--confirm",
            command.CONFIRMATION,
        ]
    )

    assert exit_code == 0
    reports = list(report_root.glob("*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["action"] == "rich-smoke"
    assert report["status"] == "passed"
    assert report["lifecycle"]["utf8_characters"] == 32_768
    serialized = json.dumps(report, ensure_ascii=False)
    assert "VMSH PWA synthetic" not in serialized
    assert "я" not in serialized
    assert "telegram_bot_token" not in serialized


def test_rich_write_action_refuses_environment_destination(monkeypatch):
    monkeypatch.setenv(command.LIVE_ENVIRONMENT_FLAG, "1")
    monkeypatch.setenv(
        command.CHANNEL_ID_ENVIRONMENT_KEY,
        str(command.EXPECTED_TEST_CHANNEL_CHAT_ID),
    )
    monkeypatch.delenv("PROD", raising=False)

    try:
        command.validate_live_opt_in(
            live=True,
            confirmation=command.CONFIRMATION,
            bind_channel=False,
            run_smoke=False,
            run_rich_smoke=True,
        )
    except command.LiveTelegramGuardError as error:
        assert "environment destination" in str(error)
    else:
        raise AssertionError("Rich write must use only the persisted binding")
