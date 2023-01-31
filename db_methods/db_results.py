import sqlite3
from datetime import datetime
from typing import List, Tuple, Dict


# ██████  ███████ ███████ ██    ██ ██      ████████ ███████
# ██   ██ ██      ██      ██    ██ ██         ██    ██
# ██████  █████   ███████ ██    ██ ██         ██    ███████
# ██   ██ ██           ██ ██    ██ ██         ██         ██
# ██   ██ ███████ ███████  ██████  ███████    ██    ███████

class DB_RESULT:
    conn: sqlite3.Connection

    def add_result(self, student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int,
                   answer: str, res_type: int = None, zoom_conversation_id: int = None) -> int:
        ts = datetime.now().isoformat()
        with self.conn as conn:
            cur = conn.execute("""
                INSERT INTO results  ( student_id,  problem_id,  level,  lesson,  teacher_id,  ts,  verdict,  answer,  res_type, zoom_conversation_id)
                VALUES               (:student_id, :problem_id, :level, :lesson, :teacher_id, :ts, :verdict, :answer, :res_type, :zoom_conversation_id)
                returning id
            """, locals())
            return cur.fetchone()['id']

    def check_num_answers(self, student_id: int, problem_id: int) -> Tuple[int, int]:
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

    def delete_plus(self, student_id: int, problem_id: int, res_type: int, new_verdict: int):
        with self.conn as conn:
            conn.execute("""
                update results set verdict = :new_verdict
                where 
                student_id = :student_id and problem_id = :problem_id and problem_id > 0 and verdict > 0
                and (:res_type is null or res_type = :res_type)
            """, locals())
        self.conn.commit()

    def check_student_solved(self, student_id: int, lesson: int) -> set:
        cur = self.conn.execute("""
            select distinct problem_id from results
            where student_id = :student_id and lesson = :lesson and verdict > 0
        """, locals())
        rows = cur.fetchall()
        solved_ids = {row['problem_id'] for row in rows}
        return solved_ids

    def list_student_results(self, student_id: int, lesson: int) -> List[dict]:
        return self.conn.execute("""
            select r.ts, p.level, p.lesson, p.prob, p.item, r.answer, r.verdict, r.problem_id from results r
            join problems p on r.problem_id = p.id
            where r.student_id = :student_id and r.lesson = :lesson
            order by r.ts
        """, locals()).fetchall()

    def list_all_student_results(self, student_id: int) -> List[dict]:
        return self.conn.execute("""
            select r.ts, p.level, p.lesson, p.prob, p.item, r.answer, r.verdict, r.problem_id from results r
            join problems p on r.problem_id = p.id
            where r.student_id = :student_id
            order by r.ts
        """, locals()).fetchall()

    def get_results_for_recheck_by_problem_id(self, problem_id: int) -> List[dict]:
        return self.conn.execute("""
            select r.id, r.student_id, r.answer, r.verdict from results r
            where r.problem_id = :problem_id
        """, locals()).fetchall()

    def update_verdicts(self, new_verdicts: Dict):
        with self.conn as conn:
            conn.execute("begin")
            for row in new_verdicts:
                conn.execute("""
                    update results
                    set verdict = :verdict
                    where id = :id
                """, row)

    def get_student_solved(self, student_id: int, lesson: int) -> List[dict]:
        return self.conn.execute("""
            select min(ts) ts, p.title, p.level from results r
            join problems p on r.problem_id = p.id
            where student_id = :student_id and r.lesson = :lesson and verdict > 0
            group by p.title, p.level 
            order by 1
        """, locals()).fetchall()
