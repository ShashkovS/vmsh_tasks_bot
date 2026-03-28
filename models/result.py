# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Optional, List

from helpers.consts import *
import db_methods as db
from .user import User
from .problem import Problem
from helpers.nats_brocker import vmsh_nats
from helpers.trace import emit_trace


class Result:
    @staticmethod
    def add(student: User, problem: Problem, teacher: Optional[User], verdict: VERDICT, answer: Optional[str], res_type: RES_TYPE, zoom_conversation_id: int = None) -> int:
        teacher_id = teacher and teacher.id
        result_id = db.result.insert(
            student.id,
            problem.id,
            problem.lesson,
            teacher_id,
            verdict,
            answer,
            res_type,
            zoom_conversation_id,
            group_id=problem.group_id,
        )
        pair_id = None
        if teacher_id is not None:
            pair_id = f"pair:{teacher_id}:{student.id}"
        emit_trace(
            "result.saved",
            result_id=result_id,
            student_id=student.id,
            teacher_id=teacher_id,
            user_id=student.id,
            target_user_id=student.id,
            pair_id=pair_id,
            problem_id=problem.id,
            lesson=problem.lesson,
            group_id=problem.group_id,
            verdict=int(verdict),
            res_type=int(res_type),
            zoom_conversation_id=zoom_conversation_id,
            has_answer=bool(answer),
            answer_len=len(answer) if answer else 0,
        )
        if verdict > 0:
            asyncio.create_task(vmsh_nats.publish(NATS_GAME_STUDENT_UPDATE, student.id))
        return result_id
