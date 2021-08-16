import sqlite3
from typing import List


# ██      ███████ ███████ ███████  ██████  ███    ██ ███████
# ██      ██      ██      ██      ██    ██ ████   ██ ██
# ██      █████   ███████ ███████ ██    ██ ██ ██  ██ ███████
# ██      ██           ██      ██ ██    ██ ██  ██ ██      ██
# ███████ ███████ ███████ ███████  ██████  ██   ████ ███████

class DB_LESSON:
    conn: sqlite3.Connection

    def update_lessons(self):
        cur = self.conn.cursor()
        cur.execute("""
            insert into lessons (lesson, level)
            select distinct p.lesson, p.level
            from problems p
            where (p.lesson, p.level) not in (select l.lesson, l.level from lessons l)
        """)

    def fetch_all_lessons(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT level, lesson FROM lessons order by lesson, level")
        rows = cur.fetchall()
        return rows

    def get_last_lesson_num(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT max(lesson) as mx FROM lessons")
        row = cur.fetchone()
        return row['mx']
