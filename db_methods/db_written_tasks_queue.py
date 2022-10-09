import sqlite3
from typing import List
from datetime import datetime, timedelta
from helpers.consts import WRITTEN_STATUS

_MAX_TIME_TO_CHECK_WRITTEN_TASK = timedelta(minutes=30)
_MAX_WRITTEN_TASKS_TO_SELECT = 8


# ██     ██ ██████  ██ ████████ ████████ ███████ ███    ██ ████████  █████  ███████ ██   ██  ██████  ██    ██ ███████ ██    ██ ███████
# ██     ██ ██   ██ ██    ██       ██    ██      ████   ██    ██    ██   ██ ██      ██  ██  ██    ██ ██    ██ ██      ██    ██ ██
# ██  █  ██ ██████  ██    ██       ██    █████   ██ ██  ██    ██    ███████ ███████ █████   ██    ██ ██    ██ █████   ██    ██ █████
# ██ ███ ██ ██   ██ ██    ██       ██    ██      ██  ██ ██    ██    ██   ██      ██ ██  ██  ██ ▄▄ ██ ██    ██ ██      ██    ██ ██
#  ███ ███  ██   ██ ██    ██       ██    ███████ ██   ████    ██    ██   ██ ███████ ██   ██  ██████   ██████  ███████  ██████  ███████
#                                                                                               ▀▀


class DB_WRITTENTASKQUEUE:
    conn: sqlite3.Connection

    def check_student_sent_written(self, student_id: int, lesson: int) -> set:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select w.problem_id from written_tasks_queue w
            join problems p on w.problem_id = p.id
            where w.student_id = :student_id and p.lesson = :lesson
        """, args)
        rows = cur.fetchall()
        being_checked_ids = {row['problem_id'] for row in rows}
        return being_checked_ids

    def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int, ts: datetime = None) -> int:
        args = locals()
        args['ts'] = args['ts'] or datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO written_tasks_queue  ( ts,  student_id,  problem_id,  cur_status)
            VALUES                           (:ts, :student_id, :problem_id, :cur_status)
            ON CONFLICT (student_id, problem_id) do nothing 
        """, args)
        self.conn.commit()
        return cur.lastrowid

    def get_written_tasks_to_check(self, teacher_id, synonyms: set) -> List[dict]:
        cur = self.conn.cursor()
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        # order = 'prob, item' if order_by_problem_num else 'ts'
        rows = []
        for problem_id in synonyms:
            cur.execute("""
                select * from written_tasks_queue
                where (cur_status = :WRITTEN_STATUS_NEW or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id)
                      and problem_id = :problem_id
                order by ts
                limit :_MAX_WRITTEN_TASKS_TO_SELECT
            """, {'WRITTEN_STATUS_NEW': WRITTEN_STATUS.NEW,
                  '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
                  'now_minus_30_min': now_minus_30_min,
                  'teacher_id': teacher_id,
                  'problem_id': problem_id})
            rows.extend(cur.fetchall())
        return rows

    def get_sos_tasks_to_check(self, teacher_id) -> List[dict]:
        cur = self.conn.cursor()
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        # order = 'prob, item' if order_by_problem_num else 'ts'
        # TODO Удалить этот кусок треша!
        cur.execute("""
            select wq.* from written_tasks_queue wq
            -- join problems p on wq.problem_id = p.id
            where 
            (cur_status = :WRITTEN_STATUS_NEW or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id)
            and problem_id < 0  -- < 0 - это SOS
            order by ts -- p.prob, p.id
            limit :_MAX_WRITTEN_TASKS_TO_SELECT
        """, {'WRITTEN_STATUS_NEW': WRITTEN_STATUS.NEW,
              '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
              'now_minus_30_min': now_minus_30_min,
              'teacher_id': teacher_id})
        rows = cur.fetchall()
        return rows

    def get_written_tasks_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            select count(*) cnt from written_tasks_queue where problem_id > 0 -- >0 - значит решение
        """)
        row = cur.fetchone()
        return row['cnt']

    def get_sos_tasks_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("""
               select count(*) cnt from written_tasks_queue where problem_id < 0 -- >0 - значит решение
           """)
        row = cur.fetchone()
        return row['cnt']

    def get_written_tasks_count_by_id(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            select problem_id, count(*) cnt from written_tasks_queue group by problem_id
        """)
        rows = cur.fetchall()
        return rows

    def get_written_tasks_count_by_synonyms(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            select synonyms, count(*) cnt from written_tasks_queue wq 
            join problems p on wq.problem_id = p.id
            group by synonyms
            order by synonyms
        """)
        rows = cur.fetchall()
        return rows

    def upd_written_task_status(self, student_id: int, problem_id: int, new_status: int, teacher_id: int = None) -> int:
        args = locals()
        args['now_minus_30_min'] = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        args['teacher_ts'] = datetime.now().isoformat() if new_status > 0 else None
        cur = self.conn.cursor()
        cur.execute("""
        UPDATE written_tasks_queue
        SET cur_status = :new_status,
            teacher_ts = :teacher_ts,
            teacher_id = :teacher_id
        where student_id = :student_id and problem_id = :problem_id and 
        (cur_status != :new_status or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id)
        """, args)
        self.conn.commit()
        return cur.rowcount

    def delete_from_written_task_queue(self, student_id: int, problem_id: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
        DELETE from written_tasks_queue
        where student_id = :student_id and problem_id = :problem_id
        """, args)
        self.conn.commit()
