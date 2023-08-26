# -*- coding: utf-8 -*-
from __future__ import annotations

import orjson

import db_methods as db


class State:
    @staticmethod
    def get_by_user_id(user_id: int):
        state = db.state.get_by_user_id(user_id) or {'state': None}
        if state['info']:
            state['info'] = orjson.loads(state['info'])
        return state

    @staticmethod
    def set_by_user_id(user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                       last_teacher_id: int = 0, oral_problem_id: int = None, info=None):
        if info is not None:
            info = orjson.dumps(info)
        db.state.update(user_id, state, problem_id, last_student_id, last_teacher_id, oral_problem_id, info)
