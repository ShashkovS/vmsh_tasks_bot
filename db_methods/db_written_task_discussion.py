import sqlite3
from typing import List
from datetime import datetime


# ██     ██ ██████  ████████ ████████  █████  ███████ ██   ██ ██████  ██ ███████  ██████ ██    ██ ███████ ███████ ██  ██████  ███    ██ ███████
# ██     ██ ██   ██    ██       ██    ██   ██ ██      ██  ██  ██   ██ ██ ██      ██      ██    ██ ██      ██      ██ ██    ██ ████   ██ ██
# ██  █  ██ ██████     ██       ██    ███████ ███████ █████   ██   ██ ██ ███████ ██      ██    ██ ███████ ███████ ██ ██    ██ ██ ██  ██ ███████
# ██ ███ ██ ██   ██    ██       ██    ██   ██      ██ ██  ██  ██   ██ ██      ██ ██      ██    ██      ██      ██ ██ ██    ██ ██  ██ ██      ██
#  ███ ███  ██   ██    ██       ██    ██   ██ ███████ ██   ██ ██████  ██ ███████  ██████  ██████  ███████ ███████ ██  ██████  ██   ████ ███████


class DB_WRITTEN_TASK_DISCUSSION:
    conn: sqlite3.Connection

    def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int,
                                            tg_msg_id: int) -> int:
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        wtd_id = cur.execute("""
            INSERT INTO written_tasks_discussions ( ts,  student_id,  problem_id,  teacher_id,  text,  attach_path,  chat_id,  tg_msg_id)
            VALUES                                (:ts, :student_id, :problem_id, :teacher_id, :text, :attach_path, :chat_id, :tg_msg_id)
            returning id
        """, args).fetchone()['id']
        self.conn.commit()
        return wtd_id

    def fetch_written_task_discussion(self, student_id: int, problem_id: int) -> List[dict]:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select * from written_tasks_discussions
            where student_id = :student_id and problem_id = :problem_id
            order by ts
        """, args)
        rows = cur.fetchall()
        return rows

    def remove_written_task_discussion_by_ids(self, wtd_ids_to_remove: List[int]):
        assert all(type(id) == int for id in wtd_ids_to_remove)
        cur = self.conn.cursor()
        cur.execute(f'''
            delete from written_tasks_discussions
            where id in ({",".join(map(str, wtd_ids_to_remove))})
        ''')
        self.conn.commit()
