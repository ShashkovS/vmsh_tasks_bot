from typing import Optional

from .db_abc import DB_ABC, sql


# TEMP_KVANTLANDIA
class DB_KV_LOGIN(DB_ABC):
    def get_by_user_id(self, user_id: int) -> Optional[dict]:
        cur = self.db.conn.execute("""
            SELECT kv_login, kv_password
            FROM kv_logins
            WHERE user_id = :user_id
        """, locals())
        return cur.fetchone()


kv_login = DB_KV_LOGIN(sql)
