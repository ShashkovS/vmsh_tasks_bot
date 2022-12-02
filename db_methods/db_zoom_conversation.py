import sqlite3
from datetime import datetime

from helpers.consts import REACTION
from helpers.config import logger


class DB_ZOOM_CONVERSATION():
    conn: sqlite3.Connection

    def allocate_conversation(self, *, student_id: int, teacher_id: int, lesson: int, level: str) -> int:
        """ Записывает в БД в отношение zoom_conversation значения zoom_conversation_id, student_id,
        teacher_id и ts, резервируя кортеж для дальнейшей записи реакции. Возвращает zoom_conversation_id.
        """
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO zoom_conversation ( ts,  student_id,  teacher_id,  lesson,  level) 
                                   VALUES (:ts, :student_id, :teacher_id, :lesson, :level) 
            RETURNING id;
        """, locals())
        zoom_conversation_id = cur.fetchone()['id']
        self.conn.commit()
        return zoom_conversation_id

    def update_check_time_spent_sec(self, zoom_conversation_id: int):
        """ Записывает время устной сдачи в секундах
        """
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE zoom_conversation 
            SET check_time_spent_sec = (julianday(CURRENT_TIMESTAMP) - julianday(ts)) * 86400.0
            WHERE id = :zoom_conversation_id;
        """, locals())
        self.conn.commit()
        return cur.lastrowid
