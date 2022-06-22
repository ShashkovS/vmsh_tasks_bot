import sqlite3
from typing import List
from datetime import datetime


class DB_PROBLEM_TAGS():
    conn: sqlite3.Connection

    def add_tags(self, problem_id: int, tags: str, teacher_id: int) -> int:
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            insert into problem_tags_logs ( problem_id,  tags,  ts,  teacher_id) 
            values                        (:problem_id, :tags, :ts, :teacher_id) 
        """, args)
        cur.execute("""
            insert into problem_tags ( problem_id,  tags,  ts,  teacher_id) 
            values                   (:problem_id, :tags, :ts, :teacher_id) 
            on conflict (problem_id) do update set 
            tags=excluded.tags, 
            ts=excluded.ts,
            teacher_id=excluded.teacher_id 
        """, args)
        self.conn.commit()
        return cur.lastrowid

    def get_tags_by_problem_id(self, problem_id: int) -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT tags FROM problem_tags where problem_id = :problem_id", locals())
        row = cur.fetchone()
        return row and row['tags']  # None if not found

    def get_all_tags(self):
        cur = self.conn.cursor()
        cur.execute("""
            select p.id, p.level, p.lesson, p.prob, p.item, pt.tags 
            from problems p
            left join problem_tags pt on p.id = pt.problem_id;
        """)
        rows = cur.fetchall()
        return rows
