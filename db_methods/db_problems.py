import sqlite3
from typing import List


# ██████  ██████   ██████  ██████  ██      ███████ ███    ███ ███████
# ██   ██ ██   ██ ██    ██ ██   ██ ██      ██      ████  ████ ██
# ██████  ██████  ██    ██ ██████  ██      █████   ██ ████ ██ ███████
# ██      ██   ██ ██    ██ ██   ██ ██      ██      ██  ██  ██      ██
# ██      ██   ██  ██████  ██████  ███████ ███████ ██      ██ ███████

class DB_PROBLEM:
    conn: sqlite3.Connection

    def add_problem(self, data: dict) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            insert into problems ( level,  lesson,  prob,  item,  title,  prob_text,  prob_type,  ans_type,  
                                   ans_validation,  validation_error,  cor_ans,  cor_ans_checker,  wrong_ans,  congrat) 
            values               (:level, :lesson, :prob, :item, :title, :prob_text, :prob_type, :ans_type, 
                                  :ans_validation, :validation_error, :cor_ans, :cor_ans_checker, :wrong_ans, :congrat) 
            on conflict (level, lesson, prob, item) do update 
            set 
            title = excluded.title,
            prob_text = excluded.prob_text,
            prob_type = excluded.prob_type,
            ans_type = excluded.ans_type,
            ans_validation = excluded.ans_validation,
            validation_error = excluded.validation_error,
            cor_ans = excluded.cor_ans,
            cor_ans_checker = excluded.cor_ans_checker,
            wrong_ans = excluded.wrong_ans,
            congrat = excluded.congrat
        """, data)
        self.conn.commit()
        return cur.lastrowid

    def fetch_all_problems(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems")
        rows = cur.fetchall()
        return rows

    def fetch_all_problems_by_lesson(self, level: str, lesson: int) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems where level = :level and lesson = :lesson", locals())
        rows = cur.fetchall()
        return rows

    def get_problem_by_id(self, problem_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems where id = :problem_id limit 1", locals())
        row = cur.fetchone()
        return row

    def get_problem_by_text_number(self, level: str, lesson: int, prob: int, item: '') -> dict:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM problems 
            where level = :level
              and lesson = :lesson
              and prob = :prob
              and item = :item
            limit 1""", locals())
        row = cur.fetchone()
        return row

    def update_problem_type(self, level: str, lesson: int, from_prob_type: int, to_prob_type: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE problems SET prob_type = :to_prob_type
            WHERE level = :level and lesson = :lesson and prob_type = :from_prob_type
        """, args)
        self.conn.commit()

    def update_synonyms(self):
        cur = self.conn.cursor()
        cur.execute("""
            update problems
            set synonyms = (select group_concat(id, ';') from problems p2 where p2.lesson=problems.lesson and p2.title=problems.title)
            where 1=1;
        """)
        self.conn.commit()
