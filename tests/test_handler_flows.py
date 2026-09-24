from __future__ import annotations

import asyncio
import os
from copy import deepcopy

import pytest

import db_methods as db
from handlers import main_handlers, student_handlers, teacher_handlers, student_keyboards
from helpers.consts import CALLBACK, ONLINE_MODE, RES_TYPE, STATE, VERDICT, WRITTEN_STATUS
from helpers.features import FEATURES
from models import Group, Problem, State, User

from .initial_test_data import test_problems, test_students, test_teachers
from .telegram_harness import RecordingBot, make_callback_query, make_message


async def _fast_sleep(_seconds=0):
    return None


async def _noop(*args, **kwargs):
    return None

def _get_worker_id():
    return os.environ.get('PYTEST_XDIST_WORKER', 'gw0')


@pytest.fixture()
def isolated_db(tmp_path):
    db.sql.disconnect()
    db_file = tmp_path / f"handler_flows_{_get_worker_id()}.db"
    db.sql.setup(str(db_file))

    students = deepcopy(test_students)
    teachers = deepcopy(test_teachers)
    problems = deepcopy(test_problems)

    for row in students + teachers:
        row["id"] = db.user.insert(row)
    for row in problems:
        row["id"] = db.problem.insert(row)

    yield {"students": students, "teachers": teachers, "problems": problems}

    db.sql.disconnect()


@pytest.fixture()
def fake_bot(monkeypatch):
    bot = RecordingBot()

    for module in (main_handlers, student_handlers, teacher_handlers):
        monkeypatch.setattr(module, "bot", bot)

    monkeypatch.setattr(main_handlers.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(student_handlers, "sleep_and_send_problems_keyboard", _noop)
    monkeypatch.setattr(student_handlers, "refresh_last_student_keyboard", _noop)
    monkeypatch.setattr(teacher_handlers, "prc_teacher_select_action", _noop)
    monkeypatch.setattr(teacher_handlers, "sleep_and_send_problems_keyboard", _noop)

    monkeypatch.setattr(student_handlers, "SAVE_SOL_MODE", FEATURES.SAVE_SOL_IN_TG_ONLY)
    monkeypatch.setattr(student_handlers, "RESULT_MODE", FEATURES.RESULT_IMMEDIATELY)
    monkeypatch.setattr(student_handlers, "RATE_LIMIT_MODE", FEATURES.RATE_LIMIT_NONE)
    monkeypatch.setattr(teacher_handlers, "RESULT_MODE", FEATURES.RESULT_IMMEDIATELY)
    monkeypatch.setattr(student_keyboards, "RESULT_MODE", FEATURES.RESULT_IMMEDIATELY)
    monkeypatch.setattr(student_keyboards, "GAME_MODE", FEATURES.GAME_HIDDEN)
    monkeypatch.setattr(student_keyboards, "PREV_PROBLEMS_MODE", FEATURES.PREV_PROBLEMS_HIDDEN)

    return bot


async def _flush_tasks():
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_student_auth_selects_test_problem_and_submits_correct_answer(isolated_db, fake_bot):
    chat_id = 99001
    student_token = isolated_db["students"][0]["token"]
    test_problem = Problem.get_by_key("н", 4, 4, "")
    assert test_problem is not None

    await main_handlers.start(make_message(chat_id, text="/start", message_id=10))
    await main_handlers.process_regular_message(make_message(chat_id, text=student_token, message_id=11))
    await _flush_tasks()

    authed_student = User.get_by_token(student_token)
    assert authed_student.chat_id == chat_id
    assert State.get_by_user_id(authed_student.id)["state"] == STATE.GET_TASK_INFO

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{test_problem.id}", chat_id=chat_id, message_id=12)
    )
    assert State.get_by_user_id(authed_student.id)["state"] == STATE.SENDING_TEST_ANSWER
    assert State.get_by_user_id(authed_student.id)["problem_id"] == test_problem.id

    await main_handlers.process_regular_message(make_message(chat_id, text="50", message_id=13))
    await _flush_tasks()

    rows = db.sql.conn.execute(
        """
        select * from results
        where student_id = :student_id and problem_id = :problem_id
        order by id
        """,
        {"student_id": authed_student.id, "problem_id": test_problem.id},
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["verdict"] == int(VERDICT.SOLVED)
    assert rows[0]["res_type"] == int(RES_TYPE.TEST)
    assert rows[0]["answer"] == "50"
    assert State.get_by_user_id(authed_student.id)["state"] == STATE.GET_TASK_INFO
    assert any("верно" in (msg.text or "").lower() for msg in fake_bot.sent_messages)


@pytest.mark.asyncio
async def test_broken_test_checker_does_not_create_false_wrong_result(isolated_db, fake_bot):
    student = User.get_by_id(isolated_db["students"][0]["id"])
    problem = Problem(
        group_id="н",
        lesson=4,
        prob=16,
        item="",
        title="Задача с временно сломанной проверкой",
        prob_text="",
        prob_type=1,
        ans_type=99,
        ans_validation="",
        validation_error="Введите строку",
        cor_ans="",
        cor_ans_checker="def check(answer):\n    return missing_name(answer)",
        wrong_ans="Нет",
        congrat="Да",
    )

    await student_handlers.check_answer_and_react(student.chat_id, problem, student, "179")
    await _flush_tasks()

    rows = db.sql.conn.execute(
        "select * from results where student_id = :student_id and problem_id = :problem_id",
        {"student_id": student.id, "problem_id": problem.id},
    ).fetchall()
    student_messages = [
        message.text for message in fake_bot.sent_messages if message.chat.id == student.chat_id
    ]
    assert rows == []
    assert "Ответ принят и ожидает настройки проверки." in student_messages
    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO


@pytest.mark.asyncio
async def test_student_written_submission_creates_discussion_and_queue(isolated_db, fake_bot):
    student = User.get_by_id(isolated_db["students"][4]["id"])
    written_problem = Problem.get_by_key("н", 4, 11, "")
    assert written_problem is not None

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{written_problem.id}", chat_id=student.chat_id, message_id=21)
    )
    state = State.get_by_user_id(student.id)
    assert state["state"] == STATE.SENDING_SOLUTION
    assert state["problem_id"] == written_problem.id

    await main_handlers.process_regular_message(
        make_message(student.chat_id, text="Моё письменное решение", message_id=22)
    )
    await _flush_tasks()

    queue_rows = db.sql.conn.execute(
        """
        select * from written_tasks_queue
        where student_id = :student_id and problem_id = :problem_id
        """,
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchall()
    discussion_rows = db.sql.conn.execute(
        """
        select * from written_tasks_discussions
        where student_id = :student_id and problem_id = :problem_id
        order by id
        """,
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchall()

    assert len(queue_rows) == 1
    assert queue_rows[0]["cur_status"] == int(WRITTEN_STATUS.NEW)
    assert len(discussion_rows) == 1
    assert discussion_rows[0]["text"] == "Моё письменное решение"
    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO
    assert any("принят" in (msg.text or "").lower() for msg in fake_bot.sent_messages)


@pytest.mark.asyncio
async def test_teacher_written_review_flow_locks_queue_and_saves_verdict(isolated_db, fake_bot):
    student = User.get_by_id(isolated_db["students"][4]["id"])
    teacher = User.get_by_token(isolated_db["teachers"][0]["token"])
    teacher.set_chat_id(88001)
    written_problem = Problem.get_by_key("н", 4, 11, "")
    assert written_problem is not None

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{written_problem.id}", chat_id=student.chat_id, message_id=31)
    )
    await main_handlers.process_regular_message(
        make_message(student.chat_id, text="Решение для проверки", message_id=32)
    )
    await _flush_tasks()

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(
            f"{CALLBACK.WRITTEN_TASK_SELECTED}_{student.id}_{written_problem.id}",
            chat_id=teacher.chat_id,
            message_id=33,
        )
    )
    await _flush_tasks()

    queue_row = db.sql.conn.execute(
        """
        select * from written_tasks_queue
        where student_id = :student_id and problem_id = :problem_id
        """,
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchone()
    teacher_state = State.get_by_user_id(teacher.id)
    assert queue_row["cur_status"] == int(WRITTEN_STATUS.BEING_CHECKED)
    assert queue_row["teacher_id"] == teacher.id
    assert teacher_state["state"] == STATE.TEACHER_IS_CHECKING_TASK
    assert teacher_state["last_student_id"] == student.id

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(
            f"{CALLBACK.WRITTEN_TASK_OK}_{student.id}_{written_problem.id}_{int(VERDICT.SOLVED)}",
            chat_id=teacher.chat_id,
            message_id=34,
        )
    )
    await _flush_tasks()

    results = db.sql.conn.execute(
        """
        select * from results
        where student_id = :student_id and problem_id = :problem_id and teacher_id = :teacher_id
        order by id
        """,
        {"student_id": student.id, "problem_id": written_problem.id, "teacher_id": teacher.id},
    ).fetchall()
    queue_left = db.sql.conn.execute(
        """
        select * from written_tasks_queue
        where student_id = :student_id and problem_id = :problem_id
        """,
        {"student_id": student.id, "problem_id": written_problem.id},
    ).fetchall()

    assert len(results) == 1
    assert results[0]["verdict"] == int(VERDICT.SOLVED)
    assert results[0]["res_type"] == int(RES_TYPE.WRITTEN)
    assert queue_left == []
    assert State.get_by_user_id(teacher.id)["state"] == STATE.TEACHER_SELECT_ACTION


@pytest.mark.asyncio
async def test_oral_problem_selection_shows_zoom_instruction_and_resets_state(isolated_db, fake_bot):
    student = User.get_by_id(isolated_db["students"][4]["id"])
    oral_problem = Problem(
        group_id="н",
        lesson=4,
        prob=15,
        item="",
        title="Устная задача для теста",
        prob_text="",
        prob_type=3,
        ans_type="",
        ans_validation="",
        validation_error="",
        cor_ans="",
        cor_ans_checker="",
        wrong_ans="",
        congrat="",
    )

    await main_handlers.inline_kb_answer_callback_handler(
        make_callback_query(f"{CALLBACK.PROBLEM_SELECTED}_{oral_problem.id}", chat_id=student.chat_id, message_id=41)
    )
    await _flush_tasks()

    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO
    assert any("zoom" in (msg.text or "").lower() for msg in fake_bot.sent_messages)


@pytest.mark.asyncio
async def test_student_group_switch_command_updates_group_when_access_allowed(isolated_db, fake_bot):
    student = User.get_by_id(isolated_db["students"][1]["id"])
    expert_group = Group.get_by_id("э")
    assert expert_group is not None
    assert expert_group.tg_command

    await student_handlers.switch_group_by_command(
        make_message(student.chat_id, text=expert_group.tg_command, message_id=42)
    )
    await _flush_tasks()

    assert User.get_by_id(student.id).group_id == "э"
    assert State.get_by_user_id(student.id)["state"] == STATE.GET_TASK_INFO


@pytest.mark.asyncio
async def test_mode_switch_commands_change_student_online_mode(isolated_db, fake_bot):
    student = User.get_by_id(isolated_db["students"][4]["id"])

    await main_handlers.mode_school(make_message(student.chat_id, text="/in_school", message_id=51))
    assert User.get_by_id(student.id).online == ONLINE_MODE.SCHOOL

    await main_handlers.mode_online(make_message(student.chat_id, text="/online", message_id=52))
    assert User.get_by_id(student.id).online == ONLINE_MODE.ONLINE
