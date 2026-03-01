from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql
from helpers.trace import emit_trace


class DB_ZOOM_QUEUE(DB_ABC):
    def insert(self, zoom_user_name: str, enter_ts: datetime, status: int = 0):
        enter_ts = enter_ts.isoformat()
        with self.db.conn as conn:
            row_id = conn.execute("""
                insert into zoom_queue ( zoom_user_name,  enter_ts,  status) 
                values                 (:zoom_user_name, :enter_ts, :status) 
                on conflict (zoom_user_name) do update set 
                enter_ts=min(enter_ts, excluded.enter_ts),
                status=excluded.status
            """, locals()).lastrowid
        emit_trace(
            "zoom.queue.changed",
            action="upsert",
            zoom_user_name=zoom_user_name,
            status=status,
            enter_ts=enter_ts,
            row_id=row_id,
        )
        return row_id

    def mark_joined(self, zoom_user_name: str, status: int = 1):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE zoom_queue SET status = :status
                WHERE zoom_user_name = :zoom_user_name
            """, locals())
        emit_trace(
            "zoom.queue.changed",
            action="mark",
            zoom_user_name=zoom_user_name,
            status=status,
        )

    def delete(self, zoom_user_name: str):
        with self.db.conn as conn:
            conn.execute("""
                DELETE from zoom_queue
                where zoom_user_name = :zoom_user_name
            """, locals())
        emit_trace(
            "zoom.queue.changed",
            action="delete",
            zoom_user_name=zoom_user_name,
        )

    def remove_old_from_zoom_queue(self):
        with self.db.conn as conn:
            removed_rows = conn.execute("""
                DELETE from zoom_queue
                where (julianday(datetime(CURRENT_TIMESTAMP, '+3 hours')) - julianday(enter_ts)) > 0.5;
            """, locals()).rowcount
        emit_trace(
            "zoom.queue.changed",
            action="cleanup",
            removed_rows=removed_rows,
        )

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
