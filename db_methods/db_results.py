from datetime import datetime
from typing import List, Tuple, Dict

from .db_abc import DB_ABC, sql


# ██████  ███████ ███████ ██    ██ ██      ████████ ███████
# ██   ██ ██      ██      ██    ██ ██         ██    ██
# ██████  █████   ███████ ██    ██ ██         ██    ███████
# ██   ██ ██           ██ ██    ██ ██         ██         ██
# ██   ██ ███████ ███████  ██████  ███████    ██    ███████


class DB_RESULT(DB_ABC):

    def insert(self, student_id: int, problem_id: int, lesson: int, teacher_id: int, verdict: int,
               answer: str, res_type: int = None, zoom_conversation_id: int = None, group_id: str = None) -> int:
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            cur = conn.execute("""
                INSERT INTO results  ( student_id,  problem_id,  lesson,  teacher_id,  ts,  verdict,  answer,
                                       res_type, zoom_conversation_id, group_id)
                VALUES               (:student_id, :problem_id, :lesson, :teacher_id, :ts, :verdict, :answer,
                                      :res_type, :zoom_conversation_id,
                                      coalesce(:group_id, (select group_id from problems where id = :problem_id)))
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

    def check_student_solved(self, student_id: int, lesson: int, group_id: str = None) -> Dict[int, int]:
        cur = self.db.conn.execute("""
            select problem_id, max(verdict) verdict 
            from results r 
            join verdicts v on r.verdict = v.id    
            where student_id = :student_id and lesson = :lesson and v.val > 0
              and (:group_id is null or group_id = :group_id)
            group by problem_id
        """, locals())
        rows = cur.fetchall()
        return {row['problem_id']: row['verdict'] for row in rows}

    def check_student_tried(self, student_id: int, lesson: int, group_id: str = None) -> set:
        cur = self.db.conn.execute("""
            select distinct problem_id from results
            where student_id = :student_id and lesson = :lesson
              and (:group_id is null or group_id = :group_id)
        """, locals())
        rows = cur.fetchall()
        tried_ids = {row['problem_id'] for row in rows}
        return tried_ids

    def list_student_results(self, student_id: int, lesson: int, group_id: str = None) -> List[dict]:
        return self.db.conn.execute("""
            select r.ts, p.group_id, coalesce(g.short_code, p.group_id) as group_code,
                   p.lesson, p.prob, p.item, r.answer, r.verdict, r.problem_id
            from results r
            join problems p on r.problem_id = p.id
            left join groups g on g.group_id = p.group_id
            where r.student_id = :student_id and r.lesson = :lesson
              and (:group_id is null or r.group_id = :group_id)
            order by r.ts
        """, locals()).fetchall()

    def list_all_student_results(self, student_id: int, group_id: str = None) -> List[dict]:
        return self.db.conn.execute("""
            select r.ts, p.group_id, coalesce(g.short_code, p.group_id) as group_code,
                   p.lesson, p.prob, p.item, r.answer, r.verdict, r.problem_id
            from results r
            join problems p on r.problem_id = p.id
            left join groups g on g.group_id = p.group_id
            where r.student_id = :student_id
              and (:group_id is null or r.group_id = :group_id)
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

    def get_student_solved(self, student_id: int, lesson: int, group_id: str = None) -> List[dict]:
        return self.db.conn.execute("""
            select min(ts) ts, p.title, p.group_id, coalesce(g.short_code, p.group_id) as group_code
            from results r
            join problems p on r.problem_id = p.id
            left join groups g on g.group_id = p.group_id
            join verdicts v on r.verdict = v.id
            where student_id = :student_id and r.lesson = :lesson and v.val >= 0.8
              and (:group_id is null or r.group_id = :group_id)
            group by p.title, p.group_id 
            order by 1
        """, locals()).fetchall()

    def check_stat(self, lesson: int, teacher_id: int) -> Tuple[int, int]:
        stat = self.db.conn.execute('''
            select sum(v.val >= 0.8) plus, sum(v.val < 0.8) minus from results r
            join verdicts v on r.verdict = v.id
            where lesson = :lesson and teacher_id = :teacher_id and res_type = 2;
        ''', {'lesson': lesson, 'teacher_id': teacher_id}).fetchone()
        if stat:
            plus, minus = stat['plus'], stat['minus']
        else:
            plus, minus = 0, 0
        return plus, minus


result = DB_RESULT(sql)
