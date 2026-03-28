from datetime import datetime

from .db_abc import DB_ABC, sql
from helpers.trace import emit_trace


class DB_ZOOM_CONVERSATION(DB_ABC):
    def insert(self, *, student_id: int, teacher_id: int, lesson: int, group_id: str) -> int:
        """ Записывает в БД в отношение zoom_conversation значения zoom_conversation_id, student_id,
        teacher_id и ts, резервируя кортеж для дальнейшей записи реакции. Возвращает zoom_conversation_id.
        """
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            zoom_conversation_id = conn.execute("""
                INSERT INTO zoom_conversation ( ts,  student_id,  teacher_id,  lesson,  group_id) 
                                       VALUES (:ts, :student_id, :teacher_id, :lesson, :group_id) 
                RETURNING id;
            """, locals()).fetchone()['id']
        emit_trace(
            "zoom.conversation.started",
            zoom_conversation_id=zoom_conversation_id,
            student_id=student_id,
            teacher_id=teacher_id,
            pair_id=f"pair:{teacher_id}:{student_id}",
            lesson=lesson,
            group_id=group_id,
        )
        return zoom_conversation_id

    def update_check_time_spent_sec(self, zoom_conversation_id: int):
        """ Записывает время устной сдачи в секундах
        """
        with self.db.conn as conn:
            row_id = conn.execute("""
                UPDATE zoom_conversation 
                SET check_time_spent_sec = (julianday(CURRENT_TIMESTAMP) - julianday(ts)) * 86400.0
                WHERE id = :zoom_conversation_id;
            """, locals()).lastrowid
        emit_trace(
            "zoom.conversation.check_time_updated",
            zoom_conversation_id=zoom_conversation_id,
            row_id=row_id,
        )
        return row_id


zoom_conversation = DB_ZOOM_CONVERSATION(sql)
