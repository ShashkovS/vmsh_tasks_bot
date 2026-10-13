"""Exercise Telegram /start through the isolated recording adapter."""

import pytest

from handlers import main_handlers
from helpers.consts import STATE
from helpers.features import FEATURES
from helpers.msg_texts import msgs
from models import State
from tests.telegram_harness import make_message


@pytest.mark.asyncio
async def test_start_requests_registration_without_external_telegram(
    scenario_env, monkeypatch
):
    # PWA/Telegram parallel-adapter boundary: test wiring never needs bot creds.
    monkeypatch.setattr(main_handlers, "REG_MODE", FEATURES.REG_NEEDED)
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 1230)
    message = make_message(1230, text="/start")
    await main_handlers.start(message)

    assert State.get_by_user_id(student.id)["state"] == STATE.GET_USER_INFO
    sent = scenario_env["bot"].sent_messages
    assert len(sent) == 1
    assert sent[0].chat.id == message.chat.id
    assert sent[0].text == msgs.start_if_reg_needed
