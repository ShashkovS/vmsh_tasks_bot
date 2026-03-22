from __future__ import annotations

import pytest

import db_methods as db
from handlers import main_handlers, teacher_handlers
from helpers.consts import CALLBACK, ONLINE_MODE, PROB_TYPE, RES_TYPE, STATE, VERDICT, WRITTEN_STATUS
from helpers.msg_texts import msgs
from models import Problem, State, User

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


async def _drain(env):
    await env["tasks"].drain()


async def test_teacher_can_select_specific_written_problem_and_reject_with_comment(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty1"), 84001)
    teacher = data.bind_chat(data.get_teacher(), 84002)
    written_problem = data.add_problem(
        group_id="i27c",
        lesson=1,
        prob=21,
        title="Teacher written problem",
        prob_type=PROB_TYPE.WRITTEN,
    )
    student.set_group_id("i27c")

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{written_problem.id}", chat_id=student.chat_id, message_id=1)
    )
    await main_handlers.process_regular_message(make_message(student.chat_id, text="Need detailed feedback", message_id=2))
    await _drain(scenario_env)

    await teacher_handlers.prc_SELECT_WRITTEN_TASK_TO_CHECK_callback(
        make_callback_query(str(CALLBACK.SELECT_WRITTEN_TASK_TO_CHECK), chat_id=teacher.chat_id, message_id=3),
        teacher,
    )
    assert any(msg.chat.id == teacher.chat_id for msg in bot.sent_messages)

    await teacher_handlers.prc_CHECK_ONLY_SELECTED_WRITEN_TASK_callback(
        make_callback_query(f"{CALLBACK.CHECK_ONLY_SELECTED_WRITEN_TASK}_{written_problem.id}", chat_id=teacher.chat_id, message_id=4),
        teacher,
    )
    assert teacher_handlers.get_problem_lock(teacher.id) == written_problem.id

    await teacher_handlers.prc_written_task_selected_callback(
        make_callback_query(f"{CALLBACK.WRITTEN_TASK_SELECTED}_{student.id}_{written_problem.id}", chat_id=teacher.chat_id, message_id=5),
        teacher,
    )
    queue_row = db.sql.conn.execute(
        "select * from written_tasks_queue where student_id = :student_id and problem_id = :problem_id",
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchone()
    assert queue_row["cur_status"] == int(WRITTEN_STATUS.BEING_CHECKED)
    assert State.get_by_user_id(teacher.id)["state"] == STATE.TEACHER_IS_CHECKING_TASK

    await teacher_handlers.prc_teacher_is_checking_task_state(
        make_message(teacher.chat_id, text="Please justify the last step", message_id=6),
        teacher,
    )
    await teacher_handlers.prc_written_task_bad_callback(
        make_callback_query(
            f"{CALLBACK.WRITTEN_TASK_BAD}_{student.id}_{written_problem.id}_{int(VERDICT.WRONG_ANSWER)}",
            chat_id=teacher.chat_id,
            message_id=7,
        ),
        teacher,
    )
    await _drain(scenario_env)

    result_row = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id and teacher_id = :teacher_id order by id desc limit 1",
        {"student_id": student.id, "problem_id": written_problem.id, "teacher_id": teacher.id},
    ).fetchone()
    assert result_row is not None
    assert result_row["verdict"] == int(VERDICT.WRONG_ANSWER)
    assert db.sql.conn.execute(
        "select * from written_tasks_queue where student_id = :student_id and problem_id = :problem_id",
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchall() == []
    assert any(payload["chat_id"] == student.chat_id for payload in bot.copied_messages)
    assert any(msg.chat.id == student.chat_id for msg in bot.sent_messages)


async def test_teacher_oral_round_saves_results_and_zoom_conversation(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    student = data.bind_chat(data.get_user("qwerty2"), 84101)
    teacher = data.bind_chat(data.get_teacher(), 84102)
    student.set_group_id("i27c")
    teacher.set_online_mode(ONLINE_MODE.ONLINE)
    oral_problem = data.add_problem(
        group_id="i27c",
        lesson=1,
        prob=22,
        title="Oral round problem",
        prob_type=PROB_TYPE.ORALLY,
    )
    teacher_handlers.msgs.oral_accepted_problems = teacher_handlers.msgs.t_oral_accepted_problems

    await teacher_handlers.prc_student_selected_callback(
        make_callback_query(f"{CALLBACK.STUDENT_SELECTED}_{student.id}", chat_id=teacher.chat_id, message_id=10),
        teacher,
    )
    assert State.get_by_user_id(teacher.id)["last_student_id"] == student.id

    await teacher_handlers.prc_add_or_remove_oral_plus_callback(
        make_callback_query(f"{CALLBACK.ADD_OR_REMOVE_ORAL_PLUS}_{oral_problem.id}__", chat_id=teacher.chat_id, message_id=11),
        teacher,
    )
    assert bot.edited_reply_markups

    await teacher_handlers.prc_finish_oral_round_callback(
        make_callback_query(f"{CALLBACK.FINISH_ORAL_ROUND}_{oral_problem.id}_", chat_id=teacher.chat_id, message_id=12),
        teacher,
    )
    await _drain(scenario_env)

    result_row = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id and teacher_id = :teacher_id order by id desc limit 1",
        {"student_id": student.id, "problem_id": oral_problem.id, "teacher_id": teacher.id},
    ).fetchone()
    zoom_row = db.sql.conn.execute(
        "select * from zoom_conversation where student_id = :student_id and teacher_id = :teacher_id order by id desc limit 1",
        {"student_id": student.id, "teacher_id": teacher.id},
    ).fetchone()
    assert result_row is not None
    assert result_row["verdict"] == int(VERDICT.SOLVED)
    assert result_row["res_type"] == int(RES_TYPE.ZOOM)
    assert zoom_row is not None
    assert any(msg.chat.id == student.chat_id for msg in bot.sent_messages)


async def test_teacher_service_commands_cover_find_zoom_queue_setters_and_legacy_oral_entry(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    teacher = data.bind_chat(data.get_teacher(), 84201)
    student = data.bind_chat(data.get_user("qwerty3"), 84202)
    student.set_group_id("i27c")
    oral_problem = data.add_problem(
        group_id="i27c",
        lesson=2,
        prob=5,
        title="Legacy oral entry problem",
        prob_type=PROB_TYPE.ORALLY,
    )
    data.add_test_result(
        student=student,
        problem=oral_problem,
        answer=None,
        verdict=VERDICT.WRONG_ANSWER,
        teacher=teacher,
        res_type=RES_TYPE.ZOOM,
    )
    db.zoom_queue.insert("Queued Student", enter_ts=__import__("datetime").datetime.now(), status=0)
    db.zoom_queue.insert("Inside Main Room", enter_ts=__import__("datetime").datetime.now(), status=1)

    await teacher_handlers.find_student(make_message(teacher.chat_id, text=f"/find_student {student.token}", message_id=20))
    assert any(student.token in (msg.text or "") for msg in bot.sent_messages if msg.chat.id == teacher.chat_id)

    await teacher_handlers.zoom_queue(make_message(teacher.chat_id, text="/zoom_queue", message_id=21))
    assert any("Queued Student" in (msg.text or "") for msg in bot.sent_messages if msg.chat.id == teacher.chat_id)

    await teacher_handlers.set_online(make_message(teacher.chat_id, text=f"/set_online {student.token} school", message_id=22))
    assert User.get_by_id(student.id).online == ONLINE_MODE.SCHOOL

    await teacher_handlers.set_student_group(make_message(teacher.chat_id, text=f"/set_group {student.token} i27p", message_id=23))
    assert User.get_by_id(student.id).group_id == "i27p"

    await teacher_handlers.edtplus(make_message(teacher.chat_id, text=f"/edtplus_2_{student.token}", message_id=24))
    assert State.get_by_user_id(teacher.id)["last_student_id"] == student.id


async def test_teacher_recheck_command_restarts_check_for_specific_problem(scenario_env):
    data = scenario_env["data"]
    bot = scenario_env["bot"]
    teacher = data.bind_chat(data.get_teacher(), 84301)
    student = data.bind_chat(data.get_user("qwerty1"), 84302)
    student.set_group_id("i27c")
    written_problem = data.add_problem(
        group_id="i27c",
        lesson=3,
        prob=7,
        title="Recheckable written",
        prob_type=PROB_TYPE.WRITTEN,
    )
    data.add_written_submission(
        student=student,
        problem=written_problem,
        text="Old written solution",
        chat_id=student.chat_id,
        tg_msg_id=77,
    )

    await teacher_handlers.recheck(make_message(teacher.chat_id, text=f"/recheck {student.token} i27c:3.7", message_id=30))

    assert any(msg.chat.id == teacher.chat_id and msgs.t_resend_for_checking in (msg.text or "") for msg in bot.sent_messages)
    assert State.get_by_user_id(teacher.id)["state"] == STATE.TEACHER_IS_CHECKING_TASK
