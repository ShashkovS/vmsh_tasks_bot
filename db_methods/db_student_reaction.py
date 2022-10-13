import sqlite3


class DB_STUDENT_REACTION():
    conn: sqlite3.Connection

    def write_student_reaction_on_task_bad_verdict(self, tg_msg_id: int, reaction: int) -> int:
        cur = self.conn.cursor()
        cur.execute("""INSERT OR REPLACE INTO student_reaction
        SELECT problem_id, datetime(), student_id, teacher_id, chat_id, (SELECT reaction_id FROM student_reaction_enum WHERE reaction = :reaction )
        FROM written_tasks_discussions WHERE tg_msg_id = :tg_msg_id;
        """, {'tg_msg_id': tg_msg_id, 'reaction': reaction})
        self.conn.commit()
        return cur.lastrowid
