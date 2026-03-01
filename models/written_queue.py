# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Optional

from helpers.consts import *
import db_methods as db
from helpers.trace import emit_trace


class WrittenQueue:
    @staticmethod
    def add_to_queue(student_id: int, problem_id: int, ts: datetime = None):
        db.written_task_queue.insert(student_id, problem_id, cur_status=WRITTEN_STATUS.NEW, ts=ts)
        emit_trace(
            "queue.written.enqueued",
            student_id=student_id,
            target_user_id=student_id,
            problem_id=problem_id,
            status=int(WRITTEN_STATUS.NEW),
        )

    @staticmethod
    def take_top_synonyms(teacher_id: int, synonyms: str, group_ids=None):
        return db.written_task_queue.get_written_tasks_to_check(teacher_id, synonyms, group_ids=group_ids)

    @staticmethod
    def take_sos_top(teacher_id: int, group_ids=None):
        return db.written_task_queue.get_sos_tasks_to_check(teacher_id, group_ids=group_ids)

    @staticmethod
    def mark_being_checked(student_id: int, problem_id: int, teacher_id: int):
        updated_rows = db.written_task_queue.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS.BEING_CHECKED, teacher_id)
        emit_trace(
            "queue.written.status_changed",
            student_id=student_id,
            teacher_id=teacher_id,
            target_user_id=student_id,
            pair_id=f"pair:{teacher_id}:{student_id}",
            problem_id=problem_id,
            status=int(WRITTEN_STATUS.BEING_CHECKED),
            updated=updated_rows > 0,
        )
        return updated_rows > 0

    @staticmethod
    def mark_not_being_checked(student_id: int, problem_id: int):
        db.written_task_queue.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS.NEW, None)
        emit_trace(
            "queue.written.status_changed",
            student_id=student_id,
            target_user_id=student_id,
            problem_id=problem_id,
            status=int(WRITTEN_STATUS.NEW),
            updated=True,
        )

    @staticmethod
    def delete_from_queue(student_id: int, problem_id: int):
        db.written_task_queue.delete(student_id, problem_id)
        emit_trace(
            "queue.written.dequeued",
            student_id=student_id,
            target_user_id=student_id,
            problem_id=problem_id,
        )

    @staticmethod
    def add_to_discussions(student_id: int, problem_id: int, teacher_id: Optional[int], text: str, attach_path: Optional[str], chat_id: int,
                           tg_msg_id: int) -> int:
        wtd_id = db.written_task_discussion.insert(student_id, problem_id, teacher_id, text, attach_path, chat_id, tg_msg_id)
        emit_trace(
            "queue.written.discussion_added",
            discussion_id=wtd_id,
            student_id=student_id,
            teacher_id=teacher_id,
            target_user_id=student_id,
            pair_id=(f"pair:{teacher_id}:{student_id}" if teacher_id else None),
            problem_id=problem_id,
            chat_id=chat_id,
            tg_message_id=tg_msg_id,
            has_text=bool(text),
            text_len=len(text) if text else 0,
            has_attach=bool(attach_path),
        )
        return wtd_id

    @staticmethod
    def get_discussion(student_id: int, problem_id: int):
        return db.written_task_discussion.get(student_id, problem_id)
