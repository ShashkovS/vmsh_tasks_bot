from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


# ██     ██  █████  ██ ████████ ██      ██ ███████ ████████
# ██     ██ ██   ██ ██    ██    ██      ██ ██         ██
# ██  █  ██ ███████ ██    ██    ██      ██ ███████    ██
# ██ ███ ██ ██   ██ ██    ██    ██      ██      ██    ██
#  ███ ███  ██   ██ ██    ██    ███████ ██ ███████    ██


class DB_WAITLIST(DB_ABC):
    def insert_to_waitlist(self, student_id: int, problem_id: int):
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            conn.execute("""
                INSERT INTO waitlist  ( student_id, entered, problem_id )
                VALUES                (:student_id, :ts,    :problem_id )
            """, locals())

    def delete(self, student_id: int):
        with self.db.conn as conn:
            conn.execute("""
                DELETE FROM waitlist
                WHERE  student_id = :student_id
            """, locals())

    def get_top(self, top_n: int) -> List[dict]:
        return self.db.conn.execute("""
            SELECT * FROM waitlist
            ORDER BY entered
            LIMIT :top_n
        """, locals()).fetchall()


waitlist = DB_WAITLIST(sql)
