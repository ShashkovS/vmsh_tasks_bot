import sqlite3
from datetime import datetime


class DB_TEACHER_REACTION():
    conn: sqlite3.Connection

    def write_teacher_reaction_on_solution(self, result_id: int, reaction_id: int) -> int:
        """Записывает в БД в отношение teacher_reaction
        реакцию учителя на решение, присланное учеником.
        """
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT into teacher_reaction ( ts,  result_id,  reaction_id)
                          VALUES         (:ts, :result_id, :reaction_id)
        """, locals())
        self.conn.commit()
        return cur.lastrowid

    def teacher_reactions(self) -> list:
        """Возвращает все реакции учителя (вместе с эмоджи) в виде списка."""
        cur = self.conn.cursor()
        cur.execute("""SELECT reaction_id, reaction FROM teacher_reaction_enum ORDER BY reaction_id;""")
        reactions = cur.fetchall()
        return reactions

    def get_teacher_reaction_by_id(self, reaction_id: int) -> str:
        """Возвращает текст реакции учителя (вместе с эмоджи) в зависимости от номера реакции учителя."""
        cur = self.conn.cursor()
        cur.execute("""SELECT reaction FROM teacher_reaction_enum WHERE reaction_id = :reaction_id;""",
                    {'reaction_id': reaction_id})
        res = cur.fetchone()
        return res['reaction']
