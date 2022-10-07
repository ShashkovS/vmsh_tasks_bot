import sqlite3
from typing import List
from datetime import datetime


class DB_ZOOM_QUEUE:
    conn: sqlite3.Connection

    def add_to_queue(self, zoom_user_name: str, enter_ts: datetime, status: int = 0):
        enter_ts = enter_ts.isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            insert into zoom_queue ( zoom_user_name,  enter_ts,  status) 
            values                 (:zoom_user_name, :enter_ts, :status) 
            on conflict (zoom_user_name) do update set 
            enter_ts=min(enter_ts, excluded.enter_ts),
            status=excluded.status
        """, locals())
        self.conn.commit()
        return cur.lastrowid

    def mark_joined(self, zoom_user_name: str, status: int = 1):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE zoom_queue SET status = :status
            WHERE zoom_user_name = :zoom_user_name
        """, args)
        self.conn.commit()

    def remove_from_queue(self, zoom_user_name: str):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            DELETE from zoom_queue
            where zoom_user_name = :zoom_user_name
        """, args)
        self.conn.commit()

    def get_first_from_queue(self, show_all=False):
        cur = self.conn.cursor()
        show = 150 if show_all else 15
        cur.execute("""
            select * from zoom_queue
            order by enter_ts
            limit :show
        """, {'show': show})
        rows = cur.fetchall()
        return rows

    def get_queue_count(self):
        rows = self.conn.execute('SELECT COUNT(*) cnt FROM zoom_queue').fetchone()['cnt']
        return rows if rows is not None else 0
