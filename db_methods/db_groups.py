from typing import List, Optional

from .db_abc import DB_ABC, sql


class DB_GROUP(DB_ABC):
    def insert(self, data: dict) -> str:
        fields = [
            'group_id',
            'short_code',
            'broadcast_code',
            'tg_command',
            'public_name',
            'conditions_url',
            'tasks_header_template',
            'switch_message',
            'sort_order',
            'is_active',
            'is_default',
            'allow_self_switch',
            'is_system',
            'score_weight',
        ]
        payload = {field: data.get(field) for field in fields}
        with self.db.conn as conn:
            conn.execute("""
                insert into groups (
                    group_id,
                    short_code,
                    broadcast_code,
                    tg_command,
                    public_name,
                    conditions_url,
                    tasks_header_template,
                    switch_message,
                    sort_order,
                    is_active,
                    is_default,
                    allow_self_switch,
                    is_system,
                    score_weight
                )
                values (
                    :group_id,
                    :short_code,
                    :broadcast_code,
                    :tg_command,
                    :public_name,
                    :conditions_url,
                    :tasks_header_template,
                    :switch_message,
                    :sort_order,
                    :is_active,
                    :is_default,
                    :allow_self_switch,
                    :is_system,
                    :score_weight
                )
                on conflict (group_id) do update set
                    short_code = excluded.short_code,
                    broadcast_code = excluded.broadcast_code,
                    tg_command = excluded.tg_command,
                    public_name = excluded.public_name,
                    conditions_url = excluded.conditions_url,
                    tasks_header_template = excluded.tasks_header_template,
                    switch_message = excluded.switch_message,
                    sort_order = excluded.sort_order,
                    is_active = excluded.is_active,
                    is_default = excluded.is_default,
                    allow_self_switch = excluded.allow_self_switch,
                    is_system = excluded.is_system,
                    score_weight = excluded.score_weight
            """, payload)
        return payload['group_id']

    def get_all(self) -> List[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            order by sort_order, group_id
        """).fetchall()

    def get_active(self, include_system: bool = False) -> List[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            where is_active = 1
              and (:include_system = 1 or is_system = 0)
            order by sort_order, group_id
        """, {'include_system': int(include_system)}).fetchall()

    def get_by_id(self, group_id: str) -> Optional[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            where group_id = :group_id
            limit 1
        """, locals()).fetchone()

    def get_by_short_code(self, short_code: str) -> List[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            where short_code = :short_code
            order by sort_order, group_id
        """, locals()).fetchall()

    def get_by_broadcast_code(self, broadcast_code: str) -> Optional[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            where broadcast_code = :broadcast_code
            limit 1
        """, locals()).fetchone()

    def get_by_command(self, tg_command: str) -> Optional[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            where tg_command = :tg_command
            limit 1
        """, locals()).fetchone()

    def get_default(self) -> Optional[dict]:
        return self.db.conn.execute("""
            select *
            from groups
            where is_default = 1
            order by sort_order, group_id
            limit 1
        """).fetchone()


group = DB_GROUP(sql)
