import sqlite3
from typing import Optional


class DB_LAST_KEYBOARD:
    conn: sqlite3.Connection

    def set_last_keyboard(self, user_id: int, chat_id: int, tg_msg_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO last_keyboards ( user_id,  chat_id,  tg_msg_id)
            VALUES                     (:user_id, :chat_id, :tg_msg_id) 
            on conflict (user_id) do update set 
            chat_id = excluded.chat_id, 
            tg_msg_id = excluded.tg_msg_id
        """, locals())
        self.conn.commit()

    def get_last_keyboard(self, user_id: int) -> Optional[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            select * from last_keyboards
            where user_id = :user_id
        """, locals())
        rows = cur.fetchone()
        return rows

    def del_last_keyboard(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            delete from last_keyboards
            where user_id = :user_id
        """, locals())
        rows = cur.fetchall()
        self.conn.commit()
