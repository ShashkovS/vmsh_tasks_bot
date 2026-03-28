from __future__ import annotations

from datetime import datetime, timedelta

import db_methods as db
from helpers.consts import PROB_TYPE, WRITTEN_STATUS


def test_written_queue_queries_counts_and_reset(live_seed_db):
    student = live_seed_db.get_user("qwerty1")
    teacher = live_seed_db.get_teacher()
    problem_a = live_seed_db.add_problem(
        group_id="i27c",
        lesson=4,
        prob=1,
        title="Written A",
        prob_type=PROB_TYPE.WRITTEN,
    )
    problem_b = live_seed_db.add_problem(
        group_id="i27c",
        lesson=4,
        prob=2,
        title="Written B",
        prob_type=PROB_TYPE.WRITTEN,
    )
    live_seed_db.add_written_submission(student=student, problem=problem_a, text="sol-a", chat_id=1, tg_msg_id=1)
    live_seed_db.add_written_submission(student=student, problem=problem_b, text="sol-b", chat_id=1, tg_msg_id=2)
    db.written_task_queue.insert(student.id, -problem_a.id, WRITTEN_STATUS.NEW)

    written_rows = db.written_task_queue.get_written_tasks_to_check(teacher.id, problem_a.synonyms, group_ids={"i27c"})
    sos_rows = db.written_task_queue.get_sos_tasks_to_check(teacher.id, group_ids={"i27c"})
    assert written_rows
    assert sos_rows
    assert db.written_task_queue.get_written_tasks_count(group_ids={"i27c"}) == 2
    assert db.written_task_queue.get_sos_tasks_count(group_ids={"i27c"}) == 1
    assert db.written_task_queue.get_written_tasks_count_by_synonyms()

    updated = db.written_task_queue.upd_written_task_status(student.id, problem_a.id, WRITTEN_STATUS.BEING_CHECKED, teacher.id)
    assert updated == 1
    reset = db.written_task_queue.reset_beeing_checked()
    assert reset >= 1
