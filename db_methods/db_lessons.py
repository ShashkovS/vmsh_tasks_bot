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
        self.conn.commit()

    def fetch_all_lessons(self, level: str = None) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute('''
            SELECT level, lesson 
            FROM lessons 
            where :level is null or :level = level
            order by lesson, level
            ''', locals())
        rows = cur.fetchall()
        return rows

    def get_last_lesson_num(self, level: str = None) -> int:
        cur = self.conn.cursor()
        cur.execute('''SELECT max(lesson) as mx 
                       FROM lessons
                       where :level is null or :level = level
                       ''', locals())
        row = cur.fetchone()
        return row['mx']
