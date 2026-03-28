from __future__ import annotations

import pytest

import db_methods as db
from handlers import main_handlers, student_handlers
from helpers.consts import ANS_TYPE, CALLBACK, PROB_TYPE, RES_TYPE, STATE, VERDICT
from helpers.features import FEATURES
from helpers.msg_texts import msgs
from models import Problem, State

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


async def _drain(env):
    await env["tasks"].drain()


async def test_student_results_command_prints_saved_results(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty1"), 85001)
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None
    data.add_test_result(student=student, problem=problem, answer="26", verdict=VERDICT.SOLVED)

    await student_handlers.students_my_results(make_message(student.chat_id, text="/results", message_id=1))

    assert any(msg.chat.id == student.chat_id and "01c.01" in (msg.text or "") for msg in bot.sent_messages)


async def test_select_one_answer_callback_saves_result_and_returns_to_problem_list(scenario_env):
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 85002)
    problem = data.add_problem(
        group_id="i27c",
        lesson=2,
        prob=9,
        title="Select-one test",
        prob_type=PROB_TYPE.TEST,
        ans_type=ANS_TYPE.SELECT_ONE,
        ans_validation="A;B;C",
        cor_ans="B",
        wrong_ans="Wrong choice",
        congrat="Correct choice",
    )
    student.set_group_id("i27c")

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{problem.id}", chat_id=student.chat_id, message_id=2)
    )
    assert State.get_by_user_id(student.id)["state"] == STATE.SENDING_TEST_ANSWER

    await student_handlers.prc_one_of_test_answer_selected_callback(
        make_callback_query(f"{CALLBACK.ONE_OF_TEST_ANSWER_SELECTED}_{problem.id}_B", chat_id=student.chat_id, message_id=3),
        student,
    )
    await _drain(scenario_env)

    row = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id order by id desc limit 1",
        {"student_id": student.id, "problem_id": problem.id},
    ).fetchone()
    assert row is not None
    assert row["verdict"] == int(VERDICT.SOLVED)
    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO


async def test_cancel_submission_callback_resets_student_state(scenario_env):
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 85003)
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None
    data.set_state(student, STATE.SENDING_SOLUTION, problem_id=problem.id)

    await student_handlers.prc_cancel_task_submission_callback(
        make_callback_query(str(CALLBACK.CANCEL_TASK_SUBMISSION), chat_id=student.chat_id, message_id=4),
        student,
    )
    await _drain(scenario_env)

    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO


async def test_validation_error_rate_limit_and_sleeping_paths(scenario_env, monkeypatch):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty1"), 85004)
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None

    await student_handlers.check_answer_and_react(student.chat_id, problem, student, "not-a-number")
    assert any(problem.validation_error in (msg.text or "") for msg in bot.sent_messages)

    monkeypatch.setattr(student_handlers, "RATE_LIMIT_MODE", FEATURES.RATE_LIMIT_3_AND_6)
    monkeypatch.setattr(student_handlers, "check_test_ans_rate_limit", lambda student_id, problem_id: "slow down")
    verdict, message, _ = student_handlers.check_test_problem_answer(problem, student, "26")
    assert verdict == student_handlers.ANS_CHECK_VERDICT.RATE_LIMIT
    assert message == "slow down"

    await student_handlers.prc_student_is_sleeping_state(make_message(student.chat_id, text="hello", message_id=5), student)
    assert any(msg.chat.id == student.chat_id and msg.text == msgs.student_is_sleeping_state_msg for msg in bot.sent_messages)

    before = len(bot.sent_messages)
    await student_handlers.prc_student_is_in_conference_state(make_message(student.chat_id, text="hello", message_id=6), student)
    assert len(bot.sent_messages) == before


async def test_sos_entrypoint_for_known_user_shows_question_actions(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty2"), 85005)

    await student_handlers.sos(make_message(student.chat_id, text="/sos", message_id=7))

    assert any(msg.chat.id == student.chat_id and msgs.sos_what_is_your_question in (msg.text or "") for msg in bot.sent_messages)
