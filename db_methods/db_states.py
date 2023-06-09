from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


# ███████ ████████  █████  ████████ ███████ ███████
# ██         ██    ██   ██    ██    ██      ██
# ███████    ██    ███████    ██    █████   ███████
#      ██    ██    ██   ██    ██    ██           ██
# ███████    ██    ██   ██    ██    ███████ ███████


class DB_STATE(DB_ABC):
    def fetch_all_states(self) -> List[dict]:
        cur = self.db.conn.cursor()
        cur.execute("SELECT * FROM states")
        rows = cur.fetchall()
        return rows

    def get_state_by_user_id(self, user_id: int) -> dict:
        return self.db.conn.execute("""
            SELECT * FROM states WHERE user_id = :user_id limit 1
        """, locals()).fetchone()

    def update_state(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                     last_teacher_id: int = 0, oral_problem_id: int = None, info: bytes = None):
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            conn.execute("""
                INSERT INTO states  ( user_id,  state,  problem_id,  last_student_id,  last_teacher_id,  oral_problem_id,  info)
                VALUES              (:user_id, :state, :problem_id, :last_student_id, :last_teacher_id, :oral_problem_id, :info) 
                ON CONFLICT (user_id) DO UPDATE SET 
                state = :state,
                problem_id = :problem_id,
                last_student_id = :last_student_id,
                last_teacher_id = :last_teacher_id,
                info = :info
            """, locals())

    def update_oral_problem(self, user_id: int, oral_problem_id: int = None):
        with self.db.conn as conn:
            conn.execute("""
                UPDATE states SET oral_problem_id = :oral_problem_id
                WHERE user_id = :user_id
            """, locals())


state = DB_STATE(sql)
