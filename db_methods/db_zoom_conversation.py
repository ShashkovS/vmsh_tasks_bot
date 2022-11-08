import sqlite3
from datetime import datetime

from helpers.consts import REACTION
from helpers.config import logger


class DB_ZOOM_CONVERSATION():
    conn: sqlite3.Connection

    def allocate_conversation(self, *, student_id: int, teacher_id: int) -> int:
        """ Записывает в БД в отношение zoom_conversation значения zoom_conversation_id, student_id,
        teacher_id и ts, резервируя кортеж для дальнейшей записи реакции. Возвращает zoom_conversation_id.
        """
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO zoom_conversation (ts, student_id, teacher_id) 
            VALUES (:ts, :student_id, :teacher_id) 
            RETURNING zoom_conversation_id;
        """, locals())
        zoom_conversation_id = cur.fetchone()['zoom_conversation_id']
        self.conn.commit()
        return zoom_conversation_id

    def write_oral_reaction(self, *, reaction_type_id: int, reaction_id: int, zoom_conversation_id: int):
        """ Записывает в БД в отношение zoom_conversation в уже существующий кортеж
        с заданным значением zoom_conversation_id, значения reaction_id в поле
        student_reaction_id или teacher_reaction_id (в зависимости от reaction_type_id).
        """
        cur = self.conn.cursor()
        if reaction_type_id == REACTION.ORAL_STUDENT:
            cur.execute("""
                UPDATE zoom_conversation SET student_reaction_id = :reaction_id
                WHERE zoom_conversation_id = :zoom_conversation_id;
            """, locals())
        elif reaction_type_id == REACTION.ORAL_TEACHER:
            cur.execute("""
                UPDATE zoom_conversation SET teacher_reaction_id = :reaction_id
                WHERE zoom_conversation_id = :zoom_conversation_id;
            """, locals())
        else:
            logger.error(f'Недопустимое значение `reaction_type_id` в {__qualname__}')
        self.conn.commit()
        return cur.lastrowid
