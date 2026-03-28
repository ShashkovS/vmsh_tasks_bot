from typing import List
from datetime import datetime, timedelta
from helpers.consts import WRITTEN_STATUS

from .db_abc import DB_ABC, sql

_MAX_TIME_TO_CHECK_WRITTEN_TASK = timedelta(minutes=30)
_MAX_WRITTEN_TASKS_TO_SELECT = 8


# ██     ██ ██████  ██ ████████ ████████ ███████ ███    ██ ████████  █████  ███████ ██   ██  ██████  ██    ██ ███████ ██    ██ ███████
# ██     ██ ██   ██ ██    ██       ██    ██      ████   ██    ██    ██   ██ ██      ██  ██  ██    ██ ██    ██ ██      ██    ██ ██
# ██  █  ██ ██████  ██    ██       ██    █████   ██ ██  ██    ██    ███████ ███████ █████   ██    ██ ██    ██ █████   ██    ██ █████
# ██ ███ ██ ██   ██ ██    ██       ██    ██      ██  ██ ██    ██    ██   ██      ██ ██  ██  ██ ▄▄ ██ ██    ██ ██      ██    ██ ██
#  ███ ███  ██   ██ ██    ██       ██    ███████ ██   ████    ██    ██   ██ ███████ ██   ██  ██████   ██████  ███████  ██████  ███████
#                                                                                               ▀▀


class DB_WRITTENTASKQUEUE(DB_ABC):
    @staticmethod
    def _group_filter(group_ids, *, alias: str = 'p'):
        if not group_ids:
            return '', {}
        group_ids = list(group_ids)
        placeholders = []
        params = {}
        for idx, group_id in enumerate(group_ids):
            key = f'group_id_{idx}'
            placeholders.append(f':{key}')
            params[key] = group_id
        clause = f' and {alias}.group_id in ({", ".join(placeholders)})'
        return clause, params

    def check_student_sent_written(self, student_id: int, lesson: int, group_id: str = None) -> set:
        cur = self.db.conn.execute("""
            select w.problem_id from written_tasks_queue w
            join problems p on w.problem_id = p.id
            where w.student_id = :student_id and p.lesson = :lesson
              and (:group_id is null or p.group_id = :group_id)
        """, locals())
        rows = cur.fetchall()
        being_checked_ids = {row['problem_id'] for row in rows}
        return being_checked_ids

    def insert(self, student_id: int, problem_id: int, cur_status: int, ts: datetime = None) -> int:
        ts = ts or datetime.now().isoformat()
        with self.db.conn as conn:
            return conn.execute("""
                INSERT INTO written_tasks_queue  ( ts,  student_id,  problem_id,  cur_status)
                VALUES                           (:ts, :student_id, :problem_id, :cur_status)
                ON CONFLICT (student_id, problem_id) do nothing 
            """, locals()).lastrowid

    def get_written_tasks_to_check(self, teacher_id, synonyms: str, group_ids=None) -> List[dict]:
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        group_clause, params = self._group_filter(group_ids)
        # order = 'prob, item' if order_by_problem_num else 'ts'
        query = f"""
                select * from written_tasks_queue
                where (cur_status = :WRITTEN_STATUS_NEW or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id)
                      and problem_id in (select id from problems p where synonyms = :synonyms{group_clause})
                order by ts
                limit :_MAX_WRITTEN_TASKS_TO_SELECT
            """
        params.update({
            'WRITTEN_STATUS_NEW': WRITTEN_STATUS.NEW,
            '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
            'now_minus_30_min': now_minus_30_min,
            'teacher_id': teacher_id,
            'synonyms': synonyms,
        })
        return self.db.conn.execute(
            query,
            params
        ).fetchall()

    def get_sos_tasks_to_check(self, teacher_id, group_ids=None) -> List[dict]:
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        group_clause, params = self._group_filter(group_ids)
        # order = 'prob, item' if order_by_problem_num else 'ts'
        # TODO Удалить этот кусок треша!
        query = f"""
                select wq.* from written_tasks_queue wq
                join problems p on p.id = abs(wq.problem_id)
                where 
                (cur_status = :WRITTEN_STATUS_NEW or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id)
                and problem_id < 0  -- < 0 - это SOS
                {group_clause}
                order by ts -- p.prob, p.id
                limit :_MAX_WRITTEN_TASKS_TO_SELECT
            """
        params.update({
            'WRITTEN_STATUS_NEW': WRITTEN_STATUS.NEW,
            '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
            'now_minus_30_min': now_minus_30_min,
            'teacher_id': teacher_id,
        })
        return self.db.conn.execute(query, params).fetchall()

    def get_written_tasks_count(self, group_ids=None) -> int:
        group_clause, params = self._group_filter(group_ids)
        query = f"""
            select count(*) cnt
            from written_tasks_queue wq
            join problems p on wq.problem_id = p.id
            where wq.problem_id > 0 {group_clause}
        """
        return self.db.conn.execute(query, params).fetchone()['cnt']

    def get_sos_tasks_count(self, group_ids=None) -> int:
        group_clause, params = self._group_filter(group_ids)
        query = f"""
            select count(*) cnt
            from written_tasks_queue wq
            join problems p on p.id = abs(wq.problem_id)
            where wq.problem_id < 0 {group_clause}
        """
        return self.db.conn.execute(query, params).fetchone()['cnt']

    def get_written_tasks_count_by_id(self) -> List[dict]:
        return self.db.conn.execute("""
            select problem_id, count(*) cnt 
            from written_tasks_queue 
            group by problem_id
        """).fetchall()

    def get_written_tasks_count_by_synonyms(self, group_ids=None) -> List[dict]:
        group_clause, params = self._group_filter(group_ids)
        query = f"""
            select 
                synonyms, count(*) cnt,
                round(JULIANDAY(datetime()) - JULIANDAY(min(ts)), 1) days_waits
            from written_tasks_queue wq
            join problems p on wq.problem_id = p.id
            where wq.problem_id > 0 {group_clause}
            group by synonyms
            order by min(ts);
        """
        return self.db.conn.execute(query, params).fetchall()

    def upd_written_task_status(self, student_id: int, problem_id: int, new_status: int, teacher_id: int = None) -> int:
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        teacher_ts = datetime.now().isoformat() if new_status > 0 else None
        with self.db.conn as conn:
            return conn.execute("""
                UPDATE written_tasks_queue
                SET cur_status = :new_status,
                    teacher_ts = :teacher_ts,
                    teacher_id = :teacher_id
                where student_id = :student_id and problem_id = :problem_id and 
                (cur_status != :new_status or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id)
            """, locals()).rowcount

    def delete(self, student_id: int, problem_id: int):
        with self.db.conn as conn:
            conn.execute("""
            DELETE from written_tasks_queue
            where student_id = :student_id and problem_id = :problem_id
            """, locals())

    def reset_beeing_checked(self) -> int:
        new_status = WRITTEN_STATUS.NEW
        with self.db.conn as conn:
            return conn.execute("""
                UPDATE written_tasks_queue
                SET cur_status = :new_status
            """, locals()).rowcount


written_task_queue = DB_WRITTENTASKQUEUE(sql)
