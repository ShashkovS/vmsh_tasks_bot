import sqlite3
from typing import Optional


class DB_LAST_KEYBOARD:
    conn: sqlite3.Connection

    def set_last_keyboard(self, user_id: int, chat_id: int, tg_msg_id: int):
        """Сохранить «координаты» сообщения со списком задач данного студента.
        Это нужно для того, чтобы потом обновлять это сообщение:
        актуализировать сданные задачи и их статусы,
        или вообще удалить список задач в ситуации, когда появился новый"""
        with self.conn as conn:
            conn.execute("""
                INSERT INTO last_keyboards ( user_id,  chat_id,  tg_msg_id)
                VALUES                     (:user_id, :chat_id, :tg_msg_id) 
                on conflict (user_id) do update set 
                chat_id = excluded.chat_id, 
                tg_msg_id = excluded.tg_msg_id
            """, locals())

    def get_last_keyboard(self, user_id: int) -> Optional[dict]:
        """Получить «координаты» сообщения с клавиатурой-списком.
        Возвращает словарь с ключами user_id chat_id tg_msg_id"""
        return self.conn.execute("""
            select * from last_keyboards
            where user_id = :user_id
        """, locals()).fetchone()

    def del_last_keyboard(self, user_id: int):
        """Удалить «координаты» сообщения с клавой данного студента"""
        with self.conn as conn:
            cur = conn.execute("""
                delete from last_keyboards
                where user_id = :user_id
            """, locals())
            return cur.rowcount
