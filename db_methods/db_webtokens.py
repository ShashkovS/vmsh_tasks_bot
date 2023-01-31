import sqlite3
from typing import List


class DB_WEBTOKEN():
    conn: sqlite3.Connection

    def add_webtoken(self, user_id: int, webtoken: str) -> int:
        with self.conn as conn:
            cur = conn.execute("""
                insert into webtokens ( user_id,  webtoken) 
                values                (:user_id, :webtoken) 
                on conflict (user_id) do update set 
                webtoken=excluded.webtoken 
            """, locals())
            return cur.lastrowid

    def get_webtoken_by_user_id(self, user_id: int) -> List[dict]:
        cur = self.conn.execute("""
            SELECT webtoken FROM webtokens 
            where user_id = :user_id
        """, locals())
        row = cur.fetchone()
        return row and row['webtoken']  # None if not found

    def get_user_id_by_webtoken(self, webtoken: str) -> List[dict]:
        cur = self.conn.execute("""
            SELECT user_id FROM webtokens 
            where webtoken = :webtoken
        """, locals())
        row = cur.fetchone()
        return row and row['user_id']  # None if not found
