import sqlite3


class DB_STUDENT_REACTION():
    conn: sqlite3.Connection

    def write_student_reaction_on_task_bad_verdict(self, tg_msg_id: int, reaction: int) -> int:
        """Записывает в БД в отношение student_reaction
        рекцию ученика получающего отрицательный вердикт по письменной работе.
        """
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO student_reaction
        SELECT 
            problem_id, 
            datetime(), 
            student_id, 
            teacher_id, 
            chat_id, 
            tg_msg_id,
            :reaction
        FROM written_tasks_discussions WHERE tg_msg_id = :tg_msg_id;
        """, {'tg_msg_id': tg_msg_id, 'reaction': reaction})
        self.conn.commit()
        return cur.lastrowid

    def student_reaction(self, reaction_n: int) -> str:
        """Возвращает текст реакции студента (вместе с эмоджи) в зависимости от номера реакции ученика."""
        cur = self.conn.cursor()
        cur.execute("""SELECT emoji, reaction FROM student_reaction_enum WHERE reaction_id = :reaction_n;""",
                    {'reaction_n': reaction_n})
        res = cur.fetchone()
        return ' '.join((chr(res['emoji']), res['reaction']))

    def student_ractions_number(self) -> int:
        """Возвращает число реакций ученика."""
        cur = self.conn.cursor()
        cur.execute("""SELECT count() FROM student_reaction_enum;""")
        return cur.fetchone()['count()']
