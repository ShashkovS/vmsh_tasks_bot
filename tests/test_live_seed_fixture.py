from __future__ import annotations

import db_methods as db
from helpers.consts import PROB_TYPE, STATE, WRITTEN_STATUS
from models import Problem, State, User


def test_live_seed_loads_core_entities(live_seed_db):
    assert len(db.group.get_all()) == 3
    assert len(list(User.all_students())) == 3
    assert len(list(User.all_teachers())) == 1
    assert Problem.get_by_key("i27c", 1, 1, "") is not None
    assert db.lesson.get_last("i27c") == 1


def test_live_seed_overlay_helpers_add_entities_without_corrupting_base(live_seed_db):
    student = live_seed_db.get_user("qwerty1")
    student = live_seed_db.bind_chat(student, 50101)
    problem = live_seed_db.add_problem(
        group_id="i27c",
        lesson=1,
        prob=10,
        title="Overlay written problem",
        prob_type=PROB_TYPE.WRITTEN,
    )
    live_seed_db.add_written_submission(
        student=student,
        problem=problem,
        text="overlay solution",
        chat_id=student.chat_id,
        tg_msg_id=7001,
    )
    live_seed_db.set_state(student, STATE.SENDING_SOLUTION, problem_id=problem.id)

    queue_row = db.sql.conn.execute(
        "select * from written_tasks_queue where student_id = :student_id and problem_id = :problem_id",
        {"student_id": student.id, "problem_id": problem.id},
    ).fetchone()
    discussion_row = db.sql.conn.execute(
        "select * from written_tasks_discussions where student_id = :student_id and problem_id = :problem_id",
        {"student_id": student.id, "problem_id": problem.id},
    ).fetchone()

    assert queue_row is not None
    assert queue_row["cur_status"] == int(WRITTEN_STATUS.NEW)
    assert discussion_row is not None
    assert discussion_row["text"] == "overlay solution"
    assert State.get_by_user_id(student.id)["problem_id"] == problem.id
