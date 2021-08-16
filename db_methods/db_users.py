import sqlite3
from typing import List


# ██    ██ ███████ ███████ ██████  ███████
# ██    ██ ██      ██      ██   ██ ██
# ██    ██ ███████ █████   ██████  ███████
# ██    ██      ██ ██      ██   ██      ██
#  ██████  ███████ ███████ ██   ██ ███████

class DB_USER():
    conn: sqlite3.Connection

    def add_user(self, data: dict) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            insert into users ( chat_id,  type,  level,  name,  surname,  middlename,  token) 
            values            (:chat_id, :type, :level, :name, :surname, :middlename, :token) 
            on conflict (token) do update set 
            chat_id=coalesce(excluded.chat_id, chat_id), 
            type=excluded.type, 
            level=coalesce(level, excluded.level), 
            name=excluded.name, 
            surname=excluded.surname, 
            middlename=excluded.middlename
        """, data)
        self.conn.commit()
        return cur.lastrowid

    def set_user_chat_id(self, user_id: int, chat_id: int):
        args = locals()
        cur = self.conn.cursor()
        try:
            cur.execute("""
                UPDATE users
                SET chat_id = :chat_id
                WHERE id = :user_id
            """, args)
        except sqlite3.IntegrityError:  # (UNIQUE constraint failed: users.chat_id)
            # Мы под одним телеграм-юзером хотим зайти под разными vmsh-юзерами. Нужно сбросить chat_id
            cur.execute("""
                UPDATE users
                SET chat_id = NULL
                WHERE chat_id = :chat_id
            """, args)
            cur.execute("""
                UPDATE users
                SET chat_id = :chat_id
                WHERE id = :user_id
            """, args)
        self.conn.commit()

    def set_user_level(self, user_id: int, level: str):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE users
            SET level = :level
            WHERE id = :user_id
        """, args)
        self.conn.commit()

    def fetch_all_users_by_type(self, user_type: int = None) -> List[dict]:
        cur = self.conn.cursor()
        if user_type is not None:
            sql = "SELECT * FROM users where type = :user_type"
        else:
            sql = "SELECT * FROM users"
        cur.execute(sql, locals())
        rows = cur.fetchall()
        return rows

    def get_user_by_id(self, user_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users where id = :user_id limit 1", locals())
        row = cur.fetchone()
        return row

    def get_user_by_token(self, token: str) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users where token = :token limit 1", locals())
        row = cur.fetchone()
        return row

    def get_user_by_chat_id(self, chat_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users where chat_id = :chat_id limit 1", locals())
        row = cur.fetchone()
        return row
