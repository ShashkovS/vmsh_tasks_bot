import sqlite3
from typing import List
from datetime import datetime


class DB_ZOOM_QUEUE:
    conn: sqlite3.Connection

    def add_to_queue(self, zoom_user_name: str, enter_ts: datetime, status: int = 0):
        enter_ts = enter_ts.isoformat()
        with self.conn as conn:
            return conn.execute("""
                insert into zoom_queue ( zoom_user_name,  enter_ts,  status) 
                values                 (:zoom_user_name, :enter_ts, :status) 
                on conflict (zoom_user_name) do update set 
                enter_ts=min(enter_ts, excluded.enter_ts),
                status=excluded.status
            """, locals()).lastrowid

    def mark_joined(self, zoom_user_name: str, status: int = 1):
        with self.conn as conn:
            conn.execute("""
                UPDATE zoom_queue SET status = :status
                WHERE zoom_user_name = :zoom_user_name
            """, locals())

    def remove_from_queue(self, zoom_user_name: str):
        with self.conn as conn:
            conn.execute("""
                DELETE from zoom_queue
                where zoom_user_name = :zoom_user_name
            """, locals())

    def remove_old_from_zoom_queue(self):
        with self.conn as conn:
            conn.execute("""
                DELETE from zoom_queue
                where (julianday(CURRENT_TIMESTAMP) - julianday(enter_ts)) > 0.5;
            """, locals())

    def get_first_from_queue(self, show_all=False):
        show = 150 if show_all else 15
        return self.conn.execute("""
            select * from zoom_queue
            order by enter_ts
            limit :show
        """, {'show': show}).fetchall()

    def get_queue_count(self):
        rows = self.conn.execute('''
            SELECT COUNT(*) cnt FROM zoom_queue
        ''').fetchone()['cnt']
        return rows if rows is not None else 0
