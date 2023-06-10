from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


# ██     ██ ██████  ████████ ████████  █████  ███████ ██   ██ ██████  ██ ███████  ██████ ██    ██ ███████ ███████ ██  ██████  ███    ██ ███████
# ██     ██ ██   ██    ██       ██    ██   ██ ██      ██  ██  ██   ██ ██ ██      ██      ██    ██ ██      ██      ██ ██    ██ ████   ██ ██
# ██  █  ██ ██████     ██       ██    ███████ ███████ █████   ██   ██ ██ ███████ ██      ██    ██ ███████ ███████ ██ ██    ██ ██ ██  ██ ███████
# ██ ███ ██ ██   ██    ██       ██    ██   ██      ██ ██  ██  ██   ██ ██      ██ ██      ██    ██      ██      ██ ██ ██    ██ ██  ██ ██      ██
#  ███ ███  ██   ██    ██       ██    ██   ██ ███████ ██   ██ ██████  ██ ███████  ██████  ██████  ███████ ███████ ██  ██████  ██   ████ ███████


class DB_WRITTEN_TASK_DISCUSSION(DB_ABC):
    def insert(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int,
                                            tg_msg_id: int) -> int:
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            return conn.execute("""
                INSERT INTO written_tasks_discussions ( ts,  student_id,  problem_id,  teacher_id,  text,  attach_path,  chat_id,  tg_msg_id)
                VALUES                                (:ts, :student_id, :problem_id, :teacher_id, :text, :attach_path, :chat_id, :tg_msg_id)
                returning id
            """, locals()).fetchone()['id']

    def get(self, student_id: int, problem_id: int) -> List[dict]:
        return self.db.conn.execute("""
            select * from written_tasks_discussions
            where student_id = :student_id and problem_id = :problem_id
            order by ts
        """, locals()).fetchall()

    def delete(self, wtd_ids_to_remove: List[int]):
        assert all(type(id) == int for id in wtd_ids_to_remove)
        with self.db.conn as conn:
            conn.execute(f'''
                delete from written_tasks_discussions
                where id in ({",".join(map(str, wtd_ids_to_remove))})
            ''')


written_task_discussion = DB_WRITTEN_TASK_DISCUSSION(sql)
