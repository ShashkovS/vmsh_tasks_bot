# -*- coding: utf-8 -*-
from __future__ import annotations

import orjson

import db_methods as db
from helpers.trace import emit_trace


class State:
    @staticmethod
    def get_by_user_id(user_id: int):
        state = db.state.get_by_user_id(user_id) or {'state': None, 'problem_id': None, 'info': None}
        if state['info']:
            state['info'] = orjson.loads(state['info'])
        return state

    @staticmethod
    def set_by_user_id(user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                       last_teacher_id: int = 0, oral_problem_id: int = None, info=None):
        prev_state_row = db.state.get_by_user_id(user_id) or {}
        prev_state = prev_state_row.get('state')
        prev_problem_id = prev_state_row.get('problem_id')
        prev_oral_problem_id = prev_state_row.get('oral_problem_id')
        if info is not None:
            info = orjson.dumps(info)
        db.state.update(user_id, state, problem_id, last_student_id, last_teacher_id, oral_problem_id, info)
        emit_trace(
            "state.transition",
            user_id=user_id,
            state_from=prev_state,
            state_to=state,
            problem_id=problem_id,
            prev_problem_id=prev_problem_id,
            oral_problem_id=oral_problem_id,
            prev_oral_problem_id=prev_oral_problem_id,
            last_student_id=last_student_id,
            last_teacher_id=last_teacher_id,
            info_len=len(info) if info else 0,
        )
