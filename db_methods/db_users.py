from typing import List

from .db_abc import DB_ABC, sql


# ██    ██ ███████ ███████ ██████  ███████
# ██    ██ ██      ██      ██   ██ ██
# ██    ██ ███████ █████   ██████  ███████
# ██    ██      ██ ██      ██   ██      ██
#  ██████  ███████ ███████ ██   ██ ███████


class DB_USER(DB_ABC):
    def add_user(self, data: dict) -> int:
        with self.db.conn as conn:
            cur = conn.execute("""
                insert into users ( chat_id,  type,  level,  name,  surname,  middlename,  token,  online,  grade,  birthday) 
                values            (:chat_id, :type, :level, :name, :surname, :middlename, :token, :online, :grade, :birthday) 
                on conflict (token) do update set 
                chat_id=coalesce(excluded.chat_id, chat_id), 
                type=excluded.type, 
                level=coalesce(level, excluded.level), 
                name=excluded.name, 
                surname=excluded.surname, 
                middlename=excluded.middlename,
                online=coalesce(online, excluded.online), 
                grade=excluded.grade, 
                birthday=excluded.birthday
            """, data)
            return cur.lastrowid

    def set_user_chat_id(self, user_id: int, chat_id: int):
        with self.db.conn as conn:
            conn.execute('begin')
            # Мы под одним телеграм-юзером хотим зайти под разными vmsh-юзерами. Нужно сбросить chat_id
            conn.execute("""
                UPDATE users
                SET chat_id = NULL
                WHERE chat_id = :chat_id
            """, locals())
            conn.execute("""
                UPDATE users
                SET chat_id = :chat_id
                WHERE id = :user_id
            """, locals())

    def set_user_level(self, user_id: int, level: str):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET level = :level
                WHERE id = :user_id
            """, locals())

    def set_user_online_mode(self, user_id: int, online: int):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET online = :online
                WHERE id = :user_id
            """, locals())

    def set_user_type(self, user_id: int, user_type: str):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET type = :user_type
                WHERE id = :user_id
            """, locals())

    def fetch_all_users_by_type(self, user_type: int = None) -> List[dict]:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where :user_type is null or type = :user_type
        ''', locals()).fetchall()

    def get_user_by_id(self, user_id: int) -> dict:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where id = :user_id limit 1
        ''', locals()).fetchone()

    def get_user_by_token(self, token: str) -> dict:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where token = :token limit 1
        ''', locals()).fetchone()

    def get_user_by_chat_id(self, chat_id: int) -> dict:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where chat_id = :chat_id limit 1
        ''', locals()).fetchone()


user = DB_USER(sql)

if __name__ == '__main__':
    pass
