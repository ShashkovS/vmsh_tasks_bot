# -*- coding: utf-8 -*-
from __future__ import annotations

import db_methods as db
from helpers.trace import emit_trace


class Waitlist:
    @staticmethod
    def enter(student_id: int, problem_id: int):
        db.state.update_oral_problem(student_id, problem_id)
        db.user.insert_to_waitlist(student_id, problem_id)
        emit_trace(
            "queue.waitlist.entered",
            student_id=student_id,
            target_user_id=student_id,
            problem_id=problem_id,
        )

    @staticmethod
    def leave(student_id: int):
        db.state.update_oral_problem(student_id, None)
        db.waitlist.delete(student_id)
        emit_trace(
            "queue.waitlist.left",
            student_id=student_id,
            target_user_id=student_id,
        )

    @staticmethod
    def top(n: int = 10, group_ids=None) -> list:
        return db.waitlist.get_top(n, group_ids=group_ids)
