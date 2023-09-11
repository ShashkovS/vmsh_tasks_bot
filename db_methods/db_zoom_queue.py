from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_ZOOM_QUEUE(DB_ABC):
    def insert(self, zoom_user_name: str, enter_ts: datetime, status: int = 0):
        enter_ts = enter_ts.isoformat()
        with self.db.conn as conn:
            return conn.execute("""
                insert into zoom_queue ( zoom_user_name,  enter_ts,  status) 
                values                 (:zoom_user_name, :enter_ts, :status) 
                on conflict (zoom_user_name) do update set 
                enter_ts=min(enter_ts, excluded.enter_ts),
                status=excluded.status
            """, locals()).lastrowid

    def mark_joined(self, zoom_user_name: str, status: int = 1):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE zoom_queue SET status = :status
                WHERE zoom_user_name = :zoom_user_name
            """, locals())

    def delete(self, zoom_user_name: str):
        with self.db.conn as conn:
            conn.execute("""
                DELETE from zoom_queue
                where zoom_user_name = :zoom_user_name
            """, locals())

    def remove_old_from_zoom_queue(self):
        with self.db.conn as conn:
            conn.execute("""
                DELETE from zoom_queue
                where (julianday(datetime(CURRENT_TIMESTAMP, '+3 hours')) - julianday(enter_ts)) > 0.5;
            """, locals())

    def get_first_from_queue(self, show_all=False):
        show = 150 if show_all else 15
        return self.db.conn.execute("""
            select * from zoom_queue
            order by enter_ts
            limit :show
        """, {'show': show}).fetchall()

    def get_queue_count(self):
        rows = self.db.conn.execute('''
            SELECT COUNT(*) cnt FROM zoom_queue
        ''').fetchone()['cnt']
        return rows if rows is not None else 0


zoom_queue = DB_ZOOM_QUEUE(sql)
