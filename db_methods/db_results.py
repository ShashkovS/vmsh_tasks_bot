from datetime import datetime
from typing import List, Tuple, Dict

from .db_abc import DB_ABC, sql


# ██████  ███████ ███████ ██    ██ ██      ████████ ███████
# ██   ██ ██      ██      ██    ██ ██         ██    ██
# ██████  █████   ███████ ██    ██ ██         ██    ███████
# ██   ██ ██           ██ ██    ██ ██         ██         ██
# ██   ██ ███████ ███████  ██████  ███████    ██    ███████


class DB_RESULT(DB_ABC):
    """
    The DB_RESULT class is a subclass of the DB_ABC abstract class. It provides methods to interact with the "results" table in the database.

    Methods:
    - insert(student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int,
             answer: str, res_type: int = None, zoom_conversation_id: int = None) -> int:
        Inserts a new record into the "results" table with the given parameters and returns the ID of the new record.

    - check_num_answers(student_id: int, problem_id: int) -> Tuple[int, int]:
        Returns the number of answers for a given student and problem, both per day and per hour.

    - delete_plus(student_id: int, problem_id: int, res_type: int, new_verdict: int):
        Updates the verdict of certain records in the "results" table based on the given parameters.

    - check_student_solved(student_id: int, lesson: int) -> set:
        Returns a set of problem IDs for which a given student has a solved verdict in a specific lesson.

    - list_student_results(student_id: int, lesson: int) -> List[dict]:
        Returns a list of dictionaries representing the results of a given student in a specific lesson. Each dictionary contains the timestamp, level, lesson, problem, item, answer, verdict, and problem ID.

    - list_all_student_results(student_id: int) -> List[dict]:
        Returns a list of dictionaries representing all the results of a given student. Each dictionary contains the timestamp, level, lesson, problem, item, answer, verdict, and problem ID.

    - get_for_recheck_by_problem_id(problem_id: int) -> List[dict]:
        Returns a list of dictionaries representing the results that need to be rechecked for a given problem ID. Each dictionary contains the ID, student ID, answer, and verdict.

    - update_verdicts(new_verdicts: Dict):
        Updates the verdicts of multiple records in the "results" table based on a dictionary mapping IDs to verdicts.

    - get_student_solved(student_id: int, lesson: int) -> List[dict]:
        Returns a list of dictionaries representing the problems that a given student has solved in a specific lesson. Each dictionary contains the minimum timestamp, problem title, and problem level.

    Note: This class assumes the existence of a "results" table in the database, and the database connection is represented by a "db" object with a "conn" attribute.
    """
    def insert(self, student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int,
                   answer: str, res_type: int = None, zoom_conversation_id: int = None) -> int:
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            cur = conn.execute("""
                INSERT INTO results  ( student_id,  problem_id,  level,  lesson,  teacher_id,  ts,  verdict,  answer,  res_type, zoom_conversation_id)
                VALUES               (:student_id, :problem_id, :level, :lesson, :teacher_id, :ts, :verdict, :answer, :res_type, :zoom_conversation_id)
                returning id
            """, locals())
            return cur.fetchone()['id']

    def check_num_answers(self, student_id: int, problem_id: int) -> Tuple[int, int]:
        cur_date = datetime.now().isoformat()[:10]
        cur_hour = datetime.now().isoformat()[:13]
        cur = self.db.conn.cursor()
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
        with self.db.conn as conn:
            conn.execute("""
                update results set verdict = :new_verdict
                where 
                student_id = :student_id and problem_id = :problem_id and problem_id > 0 and verdict > 0
                and (:res_type is null or res_type = :res_type)
            """, locals())
        self.db.conn.commit()

    def check_student_solved(self, student_id: int, lesson: int) -> set:
        cur = self.db.conn.execute("""
            select distinct problem_id from results
            where student_id = :student_id and lesson = :lesson and verdict > 0
        """, locals())
        rows = cur.fetchall()
        solved_ids = {row['problem_id'] for row in rows}
        return solved_ids

    def list_student_results(self, student_id: int, lesson: int) -> List[dict]:
        return self.db.conn.execute("""
            select r.ts, p.level, p.lesson, p.prob, p.item, r.answer, r.verdict, r.problem_id from results r
            join problems p on r.problem_id = p.id
            where r.student_id = :student_id and r.lesson = :lesson
            order by r.ts
        """, locals()).fetchall()

    def list_all_student_results(self, student_id: int) -> List[dict]:
        return self.db.conn.execute("""
            select r.ts, p.level, p.lesson, p.prob, p.item, r.answer, r.verdict, r.problem_id from results r
            join problems p on r.problem_id = p.id
            where r.student_id = :student_id
            order by r.ts
        """, locals()).fetchall()

    def get_for_recheck_by_problem_id(self, problem_id: int) -> List[dict]:
        return self.db.conn.execute("""
            select r.id, r.student_id, r.answer, r.verdict from results r
            where r.problem_id = :problem_id
        """, locals()).fetchall()

    def update_verdicts(self, new_verdicts: Dict):
        with self.db.conn as conn:
            conn.execute("begin")
            for row in new_verdicts:
                conn.execute("""
                    update results
                    set verdict = :verdict
                    where id = :id
                """, row)

    def get_student_solved(self, student_id: int, lesson: int) -> List[dict]:
        return self.db.conn.execute("""
            select min(ts) ts, p.title, p.level from results r
            join problems p on r.problem_id = p.id
            where student_id = :student_id and r.lesson = :lesson and verdict > 0
            group by p.title, p.level 
            order by 1
        """, locals()).fetchall()


result = DB_RESULT(sql)
