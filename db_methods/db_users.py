from typing import List

from .db_abc import DB_ABC, sql


# ██    ██ ███████ ███████ ██████  ███████
# ██    ██ ██      ██      ██   ██ ██
# ██    ██ ███████ █████   ██████  ███████
# ██    ██      ██ ██      ██   ██      ██
#  ██████  ███████ ███████ ██   ██ ███████


class DB_USER(DB_ABC):
    def insert(self, data: dict) -> int:
        payload = dict(data)
        payload.setdefault('group_id', None)
        payload.setdefault('allowed_groups', None)
        with self.db.conn as conn:
            cur = conn.execute("""
                insert into users (
                    chat_id,
                    type,
                    name,
                    surname,
                    middlename,
                    token,
                    online,
                    grade,
                    birthday,
                    group_id,
                    allowed_groups
                )
                values (
                    :chat_id,
                    :type,
                    :name,
                    :surname,
                    :middlename,
                    :token,
                    :online,
                    :grade,
                    :birthday,
                    :group_id,
                    :allowed_groups
                )
                on conflict (token) do update set 
                chat_id=coalesce(excluded.chat_id, chat_id), 
                type=excluded.type, 
                name=excluded.name, 
                surname=excluded.surname, 
                middlename=excluded.middlename,
                online=coalesce(online, excluded.online), 
                grade=excluded.grade, 
                birthday=excluded.birthday,
                group_id=coalesce(excluded.group_id, group_id),
                allowed_groups=coalesce(excluded.allowed_groups, allowed_groups)
                returning id
            """, payload)
            return cur.fetchone()['id']

    def set_chat_id(self, user_id: int, chat_id: int):
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

    def set_group_id(self, user_id: int, group_id: str):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET group_id = :group_id
                WHERE id = :user_id
            """, locals())

    def set_allowed_groups(self, user_id: int, allowed_groups: str):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET allowed_groups = :allowed_groups
                WHERE id = :user_id
            """, locals())

    def get_allowed_groups(self, user_id: int) -> str:
        row = self.db.conn.execute("""
            SELECT allowed_groups
            FROM users
            WHERE id = :user_id
        """, locals()).fetchone()
        return row['allowed_groups'] if row else None

    def set_online_mode(self, user_id: int, online: int):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET online = :online
                WHERE id = :user_id
            """, locals())

    def set_type(self, user_id: int, user_type: str):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE users
                SET type = :user_type
                WHERE id = :user_id
            """, locals())

    def get_all_by_type(self, user_type: int = None) -> List[dict]:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where :user_type is null or type = :user_type
        ''', locals()).fetchall()

    def get_by_id(self, user_id: int) -> dict:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where id = :user_id limit 1
        ''', locals()).fetchone()

    def get_by_token(self, token: str) -> dict:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where token = :token limit 1
        ''', locals()).fetchone()

    def get_by_chat_id(self, chat_id: int) -> dict:
        return self.db.conn.execute('''
            SELECT * FROM users 
            where chat_id = :chat_id limit 1
        ''', locals()).fetchone()


user = DB_USER(sql)

if __name__ == '__main__':
    pass
