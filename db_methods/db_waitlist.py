import sqlite3
from typing import List
from datetime import datetime


# ██     ██  █████  ██ ████████ ██      ██ ███████ ████████
# ██     ██ ██   ██ ██    ██    ██      ██ ██         ██
# ██  █  ██ ███████ ██    ██    ██      ██ ███████    ██
# ██ ███ ██ ██   ██ ██    ██    ██      ██      ██    ██
#  ███ ███  ██   ██ ██    ██    ███████ ██ ███████    ██


class DB_WAITLIST:
    conn: sqlite3.Connection

    def add_user_to_waitlist(self, student_id: int, problem_id: int):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO waitlist  ( student_id, entered, problem_id )
            VALUES                (:student_id, :ts,    :problem_id )
        """, args)
        self.conn.commit()

    def remove_user_from_waitlist(self, student_id: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            DELETE FROM waitlist
            WHERE  student_id = :student_id
        """, args)
        self.conn.commit()

    def get_waitlist_top(self, top_n: int) -> List[dict]:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM waitlist
            ORDER BY entered
            LIMIT :top_n
        """, args)
        return cur.fetchall()
