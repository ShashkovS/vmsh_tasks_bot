# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Optional, List

from helpers.consts import *
import db_methods as db
from .user import User
from .problem import Problem
from helpers.nats_brocker import vmsh_nats


class Result:
    @staticmethod
    def add(student: User, problem: Problem, teacher: Optional[User], verdict: VERDICT, answer: Optional[str], res_type: RES_TYPE, zoom_conversation_id: int = None) -> int:
        result_id = db.result.insert(student.id, problem.id, problem.level, problem.lesson, teacher and teacher.id, verdict, answer, res_type, zoom_conversation_id)
        if verdict > 0:
            asyncio.create_task(vmsh_nats.publish(NATS_GAME_STUDENT_UPDATE, student.id))
        return result_id
