import sqlite3
from datetime import datetime

class DB_STUDENT_REACTION():
    conn: sqlite3.Connection

    def write_student_reaction_on_task_bad_verdict(self, result_id: int, reaction_id: int) -> int:
        """Записывает в БД в отношение student_reaction
        реакцию ученика получающего отрицательный вердикт по письменной работе.
        """
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT into student_reaction ( ts,  result_id,  reaction_id)
                          VALUES         (:ts, :result_id, :reaction_id)
        """, locals())
        self.conn.commit()
        return cur.lastrowid

    def student_reactions(self) -> list:
        """Возвращает все реакции студента (вместе с эмоджи) в виде списка."""
        cur = self.conn.cursor()
        cur.execute("""SELECT reaction_id, reaction FROM student_reaction_enum ORDER BY reaction_id;""")
        reactions = cur.fetchall()
        return reactions

    def get_student_reaction_by_id(self, reaction_id: int) -> str:
        """Возвращает текст реакции студента (вместе с эмоджи) в зависимости от номера реакции ученика."""
        cur = self.conn.cursor()
        cur.execute("""SELECT reaction FROM student_reaction_enum WHERE reaction_id = :reaction_id;""",
                    {'reaction_id': reaction_id})
        res = cur.fetchone()
        return res['reaction']
