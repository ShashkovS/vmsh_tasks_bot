from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_ZOOM_CONVERSATION(DB_ABC):
    def insert(self, *, student_id: int, teacher_id: int, lesson: int, level: str) -> int:
        """ Записывает в БД в отношение zoom_conversation значения zoom_conversation_id, student_id,
        teacher_id и ts, резервируя кортеж для дальнейшей записи реакции. Возвращает zoom_conversation_id.
        """
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            return conn.execute("""
                INSERT INTO zoom_conversation ( ts,  student_id,  teacher_id,  lesson,  level) 
                                       VALUES (:ts, :student_id, :teacher_id, :lesson, :level) 
                RETURNING id;
            """, locals()).fetchone()['id']

    def update_check_time_spent_sec(self, zoom_conversation_id: int):
        """ Записывает время устной сдачи в секундах
        """
        with self.db.conn as conn:
            return conn.execute("""
                UPDATE zoom_conversation 
                SET check_time_spent_sec = (julianday(CURRENT_TIMESTAMP) - julianday(ts)) * 86400.0
                WHERE id = :zoom_conversation_id;
            """, locals()).lastrowid


zoom_conversation = DB_ZOOM_CONVERSATION(sql)
