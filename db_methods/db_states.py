import sqlite3
from typing import List
from datetime import datetime


# ███████ ████████  █████  ████████ ███████ ███████
# ██         ██    ██   ██    ██    ██      ██
# ███████    ██    ███████    ██    █████   ███████
#      ██    ██    ██   ██    ██    ██           ██
# ███████    ██    ██   ██    ██    ███████ ███████


class DB_STATE:
    conn: sqlite3.Connection

    def fetch_all_states(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM states")
        rows = cur.fetchall()
        return rows

    def get_state_by_user_id(self, user_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM states WHERE user_id = :user_id limit 1", locals())
        row = cur.fetchone()
        return row

    def update_state(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                     last_teacher_id: int = 0, oral_problem_id: int = None):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO states  ( user_id,  state,  problem_id,  last_student_id,  last_teacher_id,  oral_problem_id)
            VALUES              (:user_id, :state, :problem_id, :last_student_id, :last_teacher_id, :oral_problem_id) 
            ON CONFLICT (user_id) DO UPDATE SET 
            state = :state,
            problem_id = :problem_id,
            last_student_id = :last_student_id,
            last_teacher_id = :last_teacher_id
        """, args)
        self.conn.commit()

    def update_oral_problem(self, user_id: int, oral_problem_id: int = None):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE states SET oral_problem_id = :oral_problem_id
            WHERE user_id = :user_id
        """, args)
        self.conn.commit()
