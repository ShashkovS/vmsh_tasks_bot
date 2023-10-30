# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Optional

from helpers.consts import *
import db_methods as db


class WrittenQueue:
    @staticmethod
    def add_to_queue(student_id: int, problem_id: int, ts: datetime = None):
        db.written_task_queue.insert(student_id, problem_id, cur_status=WRITTEN_STATUS.NEW, ts=ts)

    @staticmethod
    def take_top_synonyms(teacher_id: int, synonyms: str):
        return db.written_task_queue.get_written_tasks_to_check(teacher_id, synonyms)

    @staticmethod
    def take_sos_top(teacher_id: int):
        return db.written_task_queue.get_sos_tasks_to_check(teacher_id)

    @staticmethod
    def mark_being_checked(student_id: int, problem_id: int, teacher_id: int):
        updated_rows = db.written_task_queue.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS.BEING_CHECKED, teacher_id)
        return updated_rows > 0

    @staticmethod
    def mark_not_being_checked(student_id: int, problem_id: int):
        db.written_task_queue.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS.NEW, None)

    @staticmethod
    def delete_from_queue(student_id: int, problem_id: int):
        db.written_task_queue.delete(student_id, problem_id)

    @staticmethod
    def add_to_discussions(student_id: int, problem_id: int, teacher_id: Optional[int], text: str, attach_path: Optional[str], chat_id: int,
                           tg_msg_id: int) -> int:
        wtd_id = db.written_task_discussion.insert(student_id, problem_id, teacher_id, text, attach_path, chat_id, tg_msg_id)
        return wtd_id

    @staticmethod
    def get_discussion(student_id: int, problem_id: int):
        return db.written_task_discussion.get(student_id, problem_id)
