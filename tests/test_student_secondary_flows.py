from __future__ import annotations

import pytest

import db_methods as db
from handlers import main_handlers, student_handlers, student_keyboards
from helpers.consts import ANS_TYPE, CALLBACK, PROB_TYPE, RES_TYPE, STATE, VERDICT
from helpers.features import FEATURES
from helpers.msg_texts import msgs
from models import Problem, State

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


async def _drain(env):
    await env["tasks"].drain()


def _callback_data(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def _button_texts(markup):
    return [
        button.text
        for row in markup.inline_keyboard
        for button in row
    ]


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


async def test_prev_problems_prev_mode_adds_lessons_button(scenario_env, monkeypatch):
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 85006)
    student.set_group_id("i27c")
    data.add_problem(
        group_id="i27c",
        lesson=2,
        prob=1,
        title="Second lesson problem",
        prob_type=PROB_TYPE.TEST,
        ans_type=ANS_TYPE.NATURAL,
        cor_ans="1",
    )
    monkeypatch.setattr(student_keyboards, "PREV_PROBLEMS_MODE", FEATURES.PREV_PROBLEMS_PREV)

    markup = student_keyboards.build_problems(2, student)

    assert str(CALLBACK.SHOW_LIST_OF_LISTS) in _callback_data(markup)


async def test_kvantlandia_button_is_present_in_problem_keyboard(scenario_env):
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 85008)
    student.set_group_id("i27c")

    markup = student_keyboards.build_problems(1, student)

    assert _button_texts(markup).count("Квантландия") == 2
    assert _callback_data(markup).count(str(CALLBACK.KVANTLANDIA)) == 2


async def test_kvantlandia_callback_sends_existing_credentials(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty1"), 85009)
    with db.sql.conn as conn:
        conn.execute(
            """
            insert into kv_logins (user_id, token, kv_login, kv_password)
            values (:user_id, :token, :kv_login, :kv_password)
            """,
            {
                "user_id": student.id,
                "token": student.token,
                "kv_login": "test<&login>",
                "kv_password": "test>&pass",
            },
        )

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(str(CALLBACK.KVANTLANDIA), chat_id=student.chat_id, message_id=9)
    )

    message = bot.sent_messages[-1]
    assert message.chat.id == student.chat_id
    assert message.kwargs["parse_mode"] == "HTML"
    assert "Для входа используйте следующие данные:" in message.text
    assert "логин: <code>test&lt;&amp;login&gt;</code>" in message.text
    assert "пароль: <code>test&gt;&amp;pass</code>" in message.text
    assert bot.answered_callbacks[-1]["id"] == "cbq-1"


async def test_kvantlandia_callback_sends_registration_instruction_without_credentials(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty2"), 85010)

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(str(CALLBACK.KVANTLANDIA), chat_id=student.chat_id, message_id=10)
    )

    message = bot.sent_messages[-1]
    assert message.chat.id == student.chat_id
    assert message.kwargs["parse_mode"] == "HTML"
    assert 'нажмите кнопку "Регистрация" и заполните форму.' in message.text
    assert "Для входа используйте следующие данные:" not in message.text
    assert bot.answered_callbacks[-1]["id"] == "cbq-1"


async def test_show_all_lessons_selection_posts_selected_lesson_keyboard(scenario_env, monkeypatch):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty1"), 85007)
    student.set_group_id("i27c")
    lesson_1_problem = Problem.get_by_key("i27c", 1, 1, "")
    assert lesson_1_problem is not None
    latest_problem = data.add_problem(
        group_id="i27c",
        lesson=2,
        prob=1,
        title="Latest lesson problem",
        prob_type=PROB_TYPE.TEST,
        ans_type=ANS_TYPE.NATURAL,
        cor_ans="1",
    )
    monkeypatch.setattr(student_keyboards, "PREV_PROBLEMS_MODE", FEATURES.PREV_PROBLEMS_SHOW_ALL)

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(str(CALLBACK.SHOW_LIST_OF_LISTS), chat_id=student.chat_id, message_id=8)
    )

    lessons_markup = bot.edited_texts[-1]["kwargs"]["reply_markup"]
    lesson_callbacks = _callback_data(lessons_markup)
    assert f"{CALLBACK.LIST_SELECTED}_1" in lesson_callbacks
    assert f"{CALLBACK.LIST_SELECTED}_2" in lesson_callbacks

    before = len(bot.sent_messages)
    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.LIST_SELECTED}_1", chat_id=student.chat_id, message_id=8)
    )

    assert len(bot.sent_messages) == before + 1
    selected_lesson_markup = bot.sent_messages[-1].kwargs["reply_markup"]
    problem_callbacks = _callback_data(selected_lesson_markup)
    assert f"{CALLBACK.PROBLEM_SELECTED}_{lesson_1_problem.id}" in problem_callbacks
    assert f"{CALLBACK.PROBLEM_SELECTED}_{latest_problem.id}" not in problem_callbacks
