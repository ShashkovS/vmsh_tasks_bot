import sqlite3
from datetime import datetime


class DB_ZOOM_CONVERSATION():
    conn: sqlite3.Connection

    def allocate_conversation(self) -> int:
        """ Записывает в БД в отношение zoom_conversation значения zoom_conversation_id и ts,
        бронируя кортеж для дальнейшей записи реакции. Возвращает zoom_conversation_id.
        """
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO zoom_conversation (ts) VALUES (:ts) RETURNING zoom_conversation_id;
        """, {'ts': ts})
        zoom_conversation_id = cur.fetchone()['zoom_conversation_id']
        self.conn.commit()
        return zoom_conversation_id
