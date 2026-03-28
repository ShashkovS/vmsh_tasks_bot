from __future__ import annotations

import pytest

import db_methods as db
from handlers import admin_handlers, main_handlers
from helpers.consts import CALLBACK, ONLINE_MODE, PROB_TYPE, RES_TYPE, STATE, VERDICT
from helpers.msg_texts import msgs
from models import Problem, State, User

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


async def _drain(env):
    await env["tasks"].drain()


async def test_set_sleep_state_and_reset_state_cycle(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    teacher = data.bind_chat(data.get_teacher(), 61001)
    student = data.bind_chat(data.get_user("qwerty1"), 61002)
    student.set_group_id("i27c")

    await admin_handlers.set_sleep_state_for_all_students(make_message(teacher.chat_id, text="/set_sleep_state", message_id=1))
    await _drain(scenario_env)

    assert State.get_by_user_id(student.id)["state"] == STATE.STUDENT_IS_SLEEPING

    await main_handlers.process_regular_message(make_message(student.chat_id, text="hello", message_id=2))
    assert any(msg.chat.id == student.chat_id and msg.text == msgs.student_is_sleeping_state_msg for msg in bot.sent_messages)

    await admin_handlers.set_get_task_info_for_all_students(make_message(teacher.chat_id, text="/reset_state", message_id=3))
    await _drain(scenario_env)

    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO


async def test_oral2written_and_written2oral_flip_current_lesson_problem_types(scenario_env):
    data = scenario_env["data"]
    teacher = data.bind_chat(data.get_teacher(), 62001)
    oral_problem = data.add_problem(
        group_id="i27c",
        lesson=1,
        prob=20,
        title="Overlay oral problem",
        prob_type=PROB_TYPE.ORALLY,
    )

    await admin_handlers.oral2written(make_message(teacher.chat_id, text="/oral2written i27c", message_id=10))
    changed_problem = Problem.get_by_id(oral_problem.id)
    assert changed_problem is not None
    assert changed_problem.prob_type == PROB_TYPE.WRITTEN_BEFORE_ORALLY

    await admin_handlers.oral2written(make_message(teacher.chat_id, text="/written2oral i27c", message_id=11))
    reverted_problem = Problem.get_by_id(oral_problem.id)
    assert reverted_problem is not None
    assert reverted_problem.prob_type == PROB_TYPE.ORALLY


async def test_problem_recheck_recomputes_test_verdicts(scenario_env):
    data = scenario_env["data"]
    teacher = data.bind_chat(data.get_teacher(), 63001)
    student = data.get_user("qwerty1")
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None

    db.result.insert(
        student.id,
        problem.id,
        problem.lesson,
        None,
        int(VERDICT.WRONG_ANSWER),
        "26",
        int(RES_TYPE.TEST),
        None,
        group_id=problem.group_id,
    )

    await admin_handlers.problem_recheck(
        make_message(teacher.chat_id, text="/problem_recheck i27c:1.1", message_id=20)
    )
    await _drain(scenario_env)

    rows = db.result.get_for_recheck_by_problem_id(problem.id)
    assert rows
    assert any(row["verdict"] == int(VERDICT.SOLVED) for row in rows)


async def test_broadcast_command_dispatches_to_expected_students(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    teacher = data.bind_chat(data.get_teacher(), 64001)
    student_a = data.bind_chat(data.get_user("qwerty1"), 64011)
    student_b = data.bind_chat(data.get_user("qwerty2"), 64012)
    student_c = data.bind_chat(data.get_user("qwerty3"), 64013)
    student_a.set_group_id("i27c")

    await admin_handlers.broadcast(
        make_message(
            teacher.chat_id,
            text="/broadcast\nall_i27c\nWeekly news",
            message_id=30,
        )
    )
    await _drain(scenario_env)

    delivered_texts = {(msg.chat.id, msg.text) for msg in bot.sent_messages if msg.chat.id in {student_a.chat_id, student_b.chat_id, student_c.chat_id}}
    assert (student_a.chat_id, "Weekly news") in delivered_texts
    assert (student_b.chat_id, "Weekly news") not in delivered_texts
    assert (student_c.chat_id, "Weekly news") not in delivered_texts


async def test_update_groups_can_be_invoked_with_mocked_spreadsheet_backend(scenario_env, monkeypatch):
    teacher = scenario_env["data"].bind_chat(scenario_env["data"].get_teacher(), 65001)
    calls = {"updated": 0, "registered": 0}

    monkeypatch.setattr(admin_handlers.FromGoogleSpreadsheet, "update_groups", staticmethod(lambda: []))
    monkeypatch.setattr(admin_handlers, "register_group_switch_commands", lambda: calls.__setitem__("registered", calls["registered"] + 1))

    await admin_handlers.update_groups(make_message(teacher.chat_id, text="/update_groups", message_id=40))

    assert calls["registered"] == 1
