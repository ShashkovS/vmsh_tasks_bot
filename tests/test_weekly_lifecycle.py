from __future__ import annotations

import pytest

import db_methods as db
from handlers import admin_handlers, main_handlers, student_handlers
from helpers.consts import CALLBACK, ONLINE_MODE, PROB_TYPE, RES_TYPE, STATE, VERDICT, WRITTEN_STATUS
from helpers.msg_texts import msgs
from models import Problem, State, User

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


async def _drain(env):
    await env["tasks"].drain()


async def test_monday_opening_flow(scenario_env):
    data = scenario_env["data"]
    student = data.get_user("qwerty1")
    test_problem = Problem.get_by_key("i27c", 1, 1, "")
    assert test_problem is not None
    written_problem = data.add_problem(
        group_id="i27c",
        lesson=1,
        prob=10,
        title="Monday written problem",
        prob_type=PROB_TYPE.WRITTEN,
    )

    await main_handlers.start(make_message(71001, text="/start", message_id=1))
    await main_handlers.process_regular_message(make_message(71001, text=student.token, message_id=2))
    await _drain(scenario_env)

    authed_student = User.get_by_token(student.token)
    assert authed_student is not None
    assert authed_student.chat_id == 71001

    await student_handlers.switch_group_by_command(make_message(71001, text="/i27c", message_id=3))
    await main_handlers.mode_school(make_message(71001, text="/in_school", message_id=4))
    await main_handlers.mode_online(make_message(71001, text="/online", message_id=5))

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{test_problem.id}", chat_id=71001, message_id=6)
    )
    await main_handlers.process_regular_message(make_message(71001, text="26", message_id=7))
    await _drain(scenario_env)

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{written_problem.id}", chat_id=71001, message_id=8)
    )
    await main_handlers.process_regular_message(make_message(71001, text="Monday written solution", message_id=9))
    await _drain(scenario_env)

    result_row = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id",
        {"student_id": authed_student.id, "problem_id": test_problem.id},
    ).fetchone()
    queue_row = db.sql.conn.execute(
        "select * from written_tasks_queue where student_id = :student_id and problem_id = :problem_id",
        {"student_id": authed_student.id, "problem_id": written_problem.id},
    ).fetchone()

    assert User.get_by_id(authed_student.id).group_id == "i27c"
    assert User.get_by_id(authed_student.id).online == ONLINE_MODE.ONLINE
    assert result_row is not None
    assert result_row["verdict"] == int(VERDICT.SOLVED)
    assert result_row["res_type"] == int(RES_TYPE.TEST)
    assert queue_row is not None
    assert queue_row["cur_status"] == int(WRITTEN_STATUS.NEW)


async def test_tuesday_wednesday_teacher_review_flow(scenario_env):
    data = scenario_env["data"]
    student = data.bind_chat(data.get_user("qwerty1"), 72001)
    teacher = data.bind_chat(data.get_teacher(), 72002)
    student.set_group_id("i27c")

    written_problem = data.add_problem(
        group_id="i27c",
        lesson=1,
        prob=11,
        title="Tuesday written problem",
        prob_type=PROB_TYPE.WRITTEN,
    )
    oral_problem = data.add_problem(
        group_id="i27c",
        lesson=1,
        prob=12,
        title="Tuesday oral problem",
        prob_type=PROB_TYPE.ORALLY,
    )
    test_problem = Problem.get_by_key("i27c", 1, 2, "")
    assert test_problem is not None

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{written_problem.id}", chat_id=student.chat_id, message_id=1)
    )
    await main_handlers.process_regular_message(make_message(student.chat_id, text="Need review", message_id=2))
    await _drain(scenario_env)

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{oral_problem.id}", chat_id=student.chat_id, message_id=3)
    )
    await _drain(scenario_env)

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(
            f"{CALLBACK.WRITTEN_TASK_SELECTED}_{student.id}_{written_problem.id}",
            chat_id=teacher.chat_id,
            message_id=4,
        )
    )
    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(
            f"{CALLBACK.WRITTEN_TASK_OK}_{student.id}_{written_problem.id}_{int(VERDICT.SOLVED)}",
            chat_id=teacher.chat_id,
            message_id=5,
        )
    )
    await _drain(scenario_env)

    db.result.insert(
        student.id,
        test_problem.id,
        test_problem.lesson,
        None,
        int(VERDICT.WRONG_ANSWER),
        "И90",
        int(RES_TYPE.TEST),
        None,
        group_id=test_problem.group_id,
    )
    await admin_handlers.problem_recheck(
        make_message(teacher.chat_id, text="/problem_recheck i27c:1.2", message_id=6)
    )
    await _drain(scenario_env)

    queue_left = db.sql.conn.execute(
        "select * from written_tasks_queue where student_id = :student_id and problem_id = :problem_id",
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchall()
    written_result = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id and teacher_id = :teacher_id",
        {"student_id": student.id, "problem_id": written_problem.id, "teacher_id": teacher.id},
    ).fetchone()
    rechecked_results = db.result.get_for_recheck_by_problem_id(test_problem.id)

    assert any("zoom" in (msg.text or "").lower() for msg in scenario_env["bot"].sent_messages if msg.chat.id == student.chat_id)
    assert queue_left == []
    assert written_result is not None
    assert written_result["verdict"] == int(VERDICT.SOLVED)
    assert any(row["verdict"] == int(VERDICT.SOLVED) for row in rechecked_results)


async def test_end_of_week_closing_flow(scenario_env):
    data = scenario_env["data"]
    teacher = data.bind_chat(data.get_teacher(), 73001)
    student = data.get_user("qwerty1")
    test_problem = Problem.get_by_key("i27c", 1, 1, "")
    assert test_problem is not None

    await main_handlers.start(make_message(73002, text="/start", message_id=1))
    await main_handlers.process_regular_message(make_message(73002, text=student.token, message_id=2))
    await _drain(scenario_env)

    authed_student = User.get_by_token(student.token)
    assert authed_student is not None
    await student_handlers.switch_group_by_command(make_message(authed_student.chat_id, text="/i27c", message_id=3))

    await admin_handlers.set_sleep_state_for_all_students(make_message(teacher.chat_id, text="/set_sleep_state", message_id=4))
    await _drain(scenario_env)
    assert State.get_by_user_id(authed_student.id)["state"] == STATE.STUDENT_IS_SLEEPING

    await main_handlers.process_regular_message(make_message(authed_student.chat_id, text="26", message_id=5))
    assert any(msg.chat.id == authed_student.chat_id and msg.text == msgs.student_is_sleeping_state_msg for msg in scenario_env["bot"].sent_messages)

    await admin_handlers.set_get_task_info_for_all_students(make_message(teacher.chat_id, text="/reset_state", message_id=6))
    await _drain(scenario_env)
    assert State.get_by_user_id(authed_student.id)["state"] == STATE.GET_TASK_INFO

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{test_problem.id}", chat_id=authed_student.chat_id, message_id=7)
    )
    await main_handlers.process_regular_message(make_message(authed_student.chat_id, text="26", message_id=8))
    await _drain(scenario_env)

    rows = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id",
        {"student_id": authed_student.id, "problem_id": test_problem.id},
    ).fetchall()
    assert rows
