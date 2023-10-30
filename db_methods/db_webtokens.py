from typing import List

from .db_abc import DB_ABC, sql

class DB_WEBTOKEN(DB_ABC):
    def insert(self, user_id: int, webtoken: str) -> int:
        with self.db.conn as conn:
            cur = conn.execute("""
                insert into webtokens ( user_id,  webtoken) 
                values                (:user_id, :webtoken) 
                on conflict (user_id) do update set 
                webtoken=excluded.webtoken 
            """, locals())
            return cur.lastrowid

    def get_by_user_id(self, user_id: int) -> List[dict]:
        cur = self.db.conn.execute("""
            SELECT webtoken FROM webtokens 
            where user_id = :user_id
        """, locals())
        row = cur.fetchone()
        return row and row['webtoken']  # None if not found

    def get_user_id(self, webtoken: str) -> List[dict]:
        cur = self.db.conn.execute("""
            SELECT user_id FROM webtokens 
            where webtoken = :webtoken
        """, locals())
        row = cur.fetchone()
        return row and row['user_id']  # None if not found


web_token = DB_WEBTOKEN(sql)
