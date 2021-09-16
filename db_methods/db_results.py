import sqlite3
from datetime import datetime


# ██████  ███████ ███████ ██    ██ ██      ████████ ███████
# ██   ██ ██      ██      ██    ██ ██         ██    ██
# ██████  █████   ███████ ██    ██ ██         ██    ███████
# ██   ██ ██           ██ ██    ██ ██         ██         ██
# ██   ██ ███████ ███████  ██████  ███████    ██    ███████

class DB_RESULT:
    conn: sqlite3.Connection

    def add_result(self, student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int,
                   answer: str, res_type: int = None):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO results  ( student_id,  problem_id,  level,  lesson,  teacher_id,  ts,  verdict,  answer,  res_type)
            VALUES               (:student_id, :problem_id, :level, :lesson, :teacher_id, :ts, :verdict, :answer, :res_type) 
        """, args)
        self.conn.commit()

    def check_num_answers(self, student_id: int, problem_id: int) -> tuple[int, int]:
        cur_date = datetime.now().isoformat()[:10]
        cur_hour = datetime.now().isoformat()[:13]
        cur = self.conn.cursor()
        per_day = cur.execute("""
            select count(*) cnt from results
            where student_id = :student_id and problem_id = :problem_id and substr(ts, 1, 10) = :cur_hour
        """, locals()).fetchone()['cnt']
        per_hour = cur.execute("""
            select count(*) cnt from results
            where student_id = :student_id and problem_id = :problem_id and substr(ts, 1, 13) = :cur_hour
        """, locals()).fetchone()['cnt']
        return per_day, per_hour

    def delete_plus(self, student_id: int, problem_id: int, verdict: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            update results set verdict = :verdict
            where student_id = :student_id and problem_id = :problem_id and problem_id > 0 and verdict > 0
        """, args)
        self.conn.commit()

    def check_student_solved(self, student_id: int, level: str, lesson: int) -> set:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select distinct problem_id from results
            where student_id = :student_id and level = :level and lesson = :lesson and verdict > 0
        """, args)
        rows = cur.fetchall()
        solved_ids = {row['problem_id'] for row in rows}
        return solved_ids

    def list_student_results(self, student_id: int, lesson: int) -> list[dict]:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select r.ts, p.level, p.lesson, p.prob, p.item, r.answer, r.verdict from results r
            join problems p on r.problem_id = p.id
            where r.student_id = :student_id and r.lesson = :lesson
            order by r.ts
        """, args)
        rows = cur.fetchall()
        return rows
