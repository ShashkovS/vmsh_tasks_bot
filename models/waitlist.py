# -*- coding: utf-8 -*-
from __future__ import annotations

import db_methods as db


class Waitlist:
    @staticmethod
    def enter(student_id: int, problem_id: int):
        db.state.update_oral_problem(student_id, problem_id)
        db.user.insert_to_waitlist(student_id, problem_id)

    @staticmethod
    def leave(student_id: int):
        db.state.update_oral_problem(student_id, None)
        db.waitlist.delete(student_id)

    @staticmethod
    def top(n: int = 10) -> list:
        return db.waitlist.get_top(n)
