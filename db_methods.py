# -*- coding: utf-8 -*-
import sqlite3
import os
from datetime import datetime, timedelta
from consts import *
from typing import List
from yoyo import read_migrations
from yoyo import get_backend

_APP_PATH = os.path.dirname(os.path.realpath(__file__))
_DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_MAX_TIME_TO_CHECK_WRITTEN_TASK = timedelta(minutes=30)
_MAX_WRITTEN_TASKS_TO_SELECT = 8


class DB:
    """Класс, реализующий все взаимодействия с БД"""
    conn: sqlite3.Connection

    def __init__(self, db_file=None):
        """Инициализация и подключение к базе"""
        self.db_file = None
        if db_file is not None:
            self.setup(db_file)

    @staticmethod
    def get_db_file_full_path(db_file: str):
        return os.path.join(_APP_PATH, 'db', db_file)

    def setup(self, db_file: str):
        self.db_file = self.get_db_file_full_path(db_file)
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._run_migrations()
        self._connect_to_db()

    @staticmethod
    def _dict_factory(cursor, row: tuple) -> dict:
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _connect_to_db(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = self._dict_factory

    def _run_migrations(self):
        backend = get_backend(f'sqlite:///{self.db_file}')
        migrations = read_migrations('migrations')
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))

    def disconnect(self):
        if self.conn:
            self.conn.close()

    # ██    ██ ███████ ███████ ██████  ███████
    # ██    ██ ██      ██      ██   ██ ██
    # ██    ██ ███████ █████   ██████  ███████
    # ██    ██      ██ ██      ██   ██      ██
    #  ██████  ███████ ███████ ██   ██ ███████

    def add_user(self, data: dict) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            insert into users ( chat_id,  type,  level,  name,  surname,  middlename,  token) 
            values            (:chat_id, :type, :level, :name, :surname, :middlename, :token) 
            on conflict (token) do update set 
            chat_id=coalesce(excluded.chat_id, chat_id), 
            type=excluded.type, 
            level=coalesce(level, excluded.level), 
            name=excluded.name, 
            surname=excluded.surname, 
            middlename=excluded.middlename
        """, data)
        self.conn.commit()
        return cur.lastrowid

    def set_user_chat_id(self, user_id: int, chat_id: int):
        args = locals()
        cur = self.conn.cursor()
        try:
            cur.execute("""
                UPDATE users
                SET chat_id = :chat_id
                WHERE id = :user_id
            """, args)
        except:
            # Мы под одним телеграм-юзером хотим зайти под разными vmsh-юзерами. Нужно сбросить chat_id
            cur.execute("""
                UPDATE users
                SET chat_id = NULL
                WHERE chat_id = :chat_id
            """, args)
            cur.execute("""
                UPDATE users
                SET chat_id = :chat_id
                WHERE id = :user_id
            """, args)
        self.conn.commit()

    def set_user_level(self, user_id: int, level: str):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE users
            SET level = :level
            WHERE id = :user_id
        """, args)
        self.conn.commit()

    def fetch_all_users_by_type(self, user_type: int = None) -> List[dict]:
        cur = self.conn.cursor()
        if user_type is not None:
            sql = "SELECT * FROM users where type = :user_type"
        else:
            sql = "SELECT * FROM users"
        cur.execute(sql, locals())
        rows = cur.fetchall()
        return rows

    def get_user_by_id(self, user_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users where id = :user_id limit 1", locals())
        row = cur.fetchone()
        return row

    def get_user_by_token(self, token: str) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users where token = :token limit 1", locals())
        row = cur.fetchone()
        return row

    def get_user_by_chat_id(self, chat_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users where chat_id = :chat_id limit 1", locals())
        row = cur.fetchone()
        return row

    # ██████  ██████   ██████  ██████  ██      ███████ ███    ███ ███████
    # ██   ██ ██   ██ ██    ██ ██   ██ ██      ██      ████  ████ ██
    # ██████  ██████  ██    ██ ██████  ██      █████   ██ ████ ██ ███████
    # ██      ██   ██ ██    ██ ██   ██ ██      ██      ██  ██  ██      ██
    # ██      ██   ██  ██████  ██████  ███████ ███████ ██      ██ ███████

    def add_problem(self, data: dict) -> id:
        cur = self.conn.cursor()
        cur.execute("""
            insert into problems ( level,  lesson,  prob,  item,  title,  prob_text,  prob_type,  ans_type,  ans_validation,  validation_error,  cor_ans,  cor_ans_checker,  wrong_ans,  congrat) 
            values               (:level, :lesson, :prob, :item, :title, :prob_text, :prob_type, :ans_type, :ans_validation, :validation_error, :cor_ans, :cor_ans_checker, :wrong_ans, :congrat) 
            on conflict (level, lesson, prob, item) do update 
            set 
            title = excluded.title,
            prob_text = excluded.prob_text,
            prob_type = excluded.prob_type,
            ans_type = excluded.ans_type,
            ans_validation = excluded.ans_validation,
            validation_error = excluded.validation_error,
            cor_ans = excluded.cor_ans,
            cor_ans_checker = excluded.cor_ans_checker,
            wrong_ans = excluded.wrong_ans,
            congrat = excluded.congrat
        """, data)
        self.conn.commit()
        return cur.lastrowid

    def fetch_all_problems(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems")
        rows = cur.fetchall()
        return rows

    def fetch_all_lessons(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT distinct level, lesson FROM problems order by lesson, level")
        rows = cur.fetchall()
        return rows

    def get_last_lesson_num(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT max(lesson) as mx FROM problems")
        row = cur.fetchone()
        return row['mx']

    def fetch_all_problems_by_lesson(self, level: str, lesson: int) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems where level = :level and lesson = :lesson", locals())
        rows = cur.fetchall()
        return rows

    def get_problem_by_id(self, problem_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems where id = :problem_id limit 1", locals())
        row = cur.fetchone()
        return row

    def get_problem_by_text_number(self, level: str, lesson: int, prob: int, item: '') -> dict:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM problems 
            where level = :level
              and lesson = :lesson
              and prob = :prob
              and item = :item
            limit 1""", locals())
        row = cur.fetchone()
        return row

    # ███████ ████████  █████  ████████ ███████ ███████
    # ██         ██    ██   ██    ██    ██      ██
    # ███████    ██    ███████    ██    █████   ███████
    #      ██    ██    ██   ██    ██    ██           ██
    # ███████    ██    ██   ██    ██    ███████ ███████

    def fetch_all_states(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM states")
        rows = cur.fetchall()
        return rows

    def get_state_by_user_id(self, user_id: int) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM states WHERE user_id = :user_id limit 1", locals())
        row = cur.fetchone()
        return row

    def update_state(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                     last_teacher_id: int = 0, oral_problem_id: int = None):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO states  ( user_id,  state,  problem_id,  last_student_id,  last_teacher_id,  oral_problem_id)
            VALUES              (:user_id, :state, :problem_id, :last_student_id, :last_teacher_id, :oral_problem_id) 
            ON CONFLICT (user_id) DO UPDATE SET 
            state = :state,
            problem_id = :problem_id,
            last_student_id = :last_student_id,
            last_teacher_id = :last_teacher_id
        """, args)
        cur.execute("""
            INSERT INTO states_log  ( user_id,  state,  problem_id,  ts)
            VALUES                  (:user_id, :state, :problem_id, :ts) 
        """, args)
        self.conn.commit()

    def update_oral_problem(self, user_id: int, oral_problem_id: int = None):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE states SET oral_problem_id = :oral_problem_id
            WHERE user_id = :user_id
        """, args)
        self.conn.commit()

    # ██████  ███████ ███████ ██    ██ ██      ████████ ███████
    # ██   ██ ██      ██      ██    ██ ██         ██    ██
    # ██████  █████   ███████ ██    ██ ██         ██    ███████
    # ██   ██ ██           ██ ██    ██ ██         ██         ██
    # ██   ██ ███████ ███████  ██████  ███████    ██    ███████
    #
    def add_result(self, student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int,
                   answer: str, res_type: int = None):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO results  ( student_id,  problem_id,  level,  lesson,  teacher_id,  ts,  verdict,  answer,  res_type)
            VALUES               (:student_id, :problem_id, :level, :lesson, :teacher_id, :ts, :verdict, :answer, :res_type) 
        """, args)
        self.conn.commit()

    def check_num_answers(self, student_id: int, problem_id: int) -> tuple[int, int]:
        cur_date = datetime.now().isoformat()[:10]
        cur_hour = datetime.now().isoformat()[:13]
        cur = self.conn.cursor()
        per_day = cur.execute("""
            select count(*) cnt from results
            where student_id = :student_id and problem_id = :problem_id and substr(ts, 1, 10) = :cur_hour
        """, locals()).fetchone()['cnt']
        per_hour = cur.execute("""
            select count(*) cnt from results
            where student_id = :student_id and problem_id = :problem_id and substr(ts, 1, 13) = :cur_hour
        """, locals()).fetchone()['cnt']
        return per_day, per_hour

    def delete_plus(self, student_id: int, problem_id: int, verdict: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            update results set verdict = :verdict
            where student_id = :student_id and problem_id = :problem_id and problem_id > 0
        """, args)
        self.conn.commit()

    def check_student_solved(self, student_id: int, level: str, lesson: int) -> set:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select distinct problem_id from results
            where student_id = :student_id and level = :level and lesson = :lesson and verdict > 0
        """, args)
        rows = cur.fetchall()
        solved_ids = {row['problem_id'] for row in rows}
        return solved_ids

    # ██     ██ ██████  ██ ████████ ████████ ███████ ███    ██ ████████  █████  ███████ ██   ██  ██████  ██    ██ ███████ ██    ██ ███████
    # ██     ██ ██   ██ ██    ██       ██    ██      ████   ██    ██    ██   ██ ██      ██  ██  ██    ██ ██    ██ ██      ██    ██ ██
    # ██  █  ██ ██████  ██    ██       ██    █████   ██ ██  ██    ██    ███████ ███████ █████   ██    ██ ██    ██ █████   ██    ██ █████
    # ██ ███ ██ ██   ██ ██    ██       ██    ██      ██  ██ ██    ██    ██   ██      ██ ██  ██  ██ ▄▄ ██ ██    ██ ██      ██    ██ ██
    #  ███ ███  ██   ██ ██    ██       ██    ███████ ██   ████    ██    ██   ██ ███████ ██   ██  ██████   ██████  ███████  ██████  ███████
    #                                                                                               ▀▀

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

    def get_written_tasks_to_check(self, teacher_id) -> List[dict]:
        cur = self.conn.cursor()
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        cur.execute("""
            select * from written_tasks_queue 
            where cur_status = :WRITTEN_STATUS_NEW or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id
            order by ts
            limit :_MAX_WRITTEN_TASKS_TO_SELECT
        """, {'WRITTEN_STATUS_NEW': WRITTEN_STATUS_NEW,
              '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
              'now_minus_30_min': now_minus_30_min,
              'teacher_id': teacher_id})
        rows = cur.fetchall()
        return rows

    def get_written_tasks_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            select count(*) cnt from written_tasks_queue 
        """)
        row = cur.fetchone()
        return row['cnt']

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

    # ██     ██  █████  ██ ████████ ██      ██ ███████ ████████
    # ██     ██ ██   ██ ██    ██    ██      ██ ██         ██
    # ██  █  ██ ███████ ██    ██    ██      ██ ███████    ██
    # ██ ███ ██ ██   ██ ██    ██    ██      ██      ██    ██
    #  ███ ███  ██   ██ ██    ██    ███████ ██ ███████    ██

    def add_user_to_waitlist(self, student_id: int, problem_id: int):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO waitlist  ( student_id, entered, problem_id )
            VALUES                (:student_id, :ts,    :problem_id )
        """, args)
        self.conn.commit()

    def remove_user_from_waitlist(self, student_id: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            DELETE FROM waitlist
            WHERE  student_id = :student_id
        """, args)
        self.conn.commit()

    def get_waitlist_top(self, top_n: int) -> List[dict]:
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM waitlist
            ORDER BY entered
            LIMIT :top_n
        """, args)
        return cur.fetchall()

    # ██     ██ ██████  ████████ ████████  █████  ███████ ██   ██ ██████  ██ ███████  ██████ ██    ██ ███████ ███████ ██  ██████  ███    ██ ███████
    # ██     ██ ██   ██    ██       ██    ██   ██ ██      ██  ██  ██   ██ ██ ██      ██      ██    ██ ██      ██      ██ ██    ██ ████   ██ ██
    # ██  █  ██ ██████     ██       ██    ███████ ███████ █████   ██   ██ ██ ███████ ██      ██    ██ ███████ ███████ ██ ██    ██ ██ ██  ██ ███████
    # ██ ███ ██ ██   ██    ██       ██    ██   ██      ██ ██  ██  ██   ██ ██      ██ ██      ██    ██      ██      ██ ██ ██    ██ ██  ██ ██      ██
    #  ███ ███  ██   ██    ██       ██    ██   ██ ███████ ██   ██ ██████  ██ ███████  ██████  ██████  ███████ ███████ ██  ██████  ██   ████ ███████

    def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int,
                                            tg_msg_id: int) -> int:
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO written_tasks_discussions ( ts,  student_id,  problem_id,  teacher_id,  text,  attach_path,  chat_id,  tg_msg_id)
            VALUES                                (:ts, :student_id, :problem_id, :teacher_id, :text, :attach_path, :chat_id, :tg_msg_id)
        """, args)
        self.conn.commit()
        return cur.lastrowid

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

    # ██       ██████   ██████  ███████
    # ██      ██    ██ ██       ██
    # ██      ██    ██ ██   ███ ███████
    # ██      ██    ██ ██    ██      ██
    # ███████  ██████   ██████  ███████

    def add_message_to_log(self, from_bot: bool, tg_msg_id: int, chat_id: int,
                           student_id: int, teacher_id: int, msg_text: str, attach_path: str):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO messages_log  ( from_bot,  tg_msg_id,  chat_id,  student_id,  teacher_id,  ts,  msg_text,  attach_path)
            VALUES                    (:from_bot, :tg_msg_id, :chat_id, :student_id, :teacher_id, :ts, :msg_text, :attach_path) 
        """, args)
        self.conn.commit()

    # ███████ ███████  █████  ████████ ██    ██ ██████  ███████ ███████
    # ██      ██      ██   ██    ██    ██    ██ ██   ██ ██      ██
    # █████   █████   ███████    ██    ██    ██ ██████  █████   ███████
    # ██      ██      ██   ██    ██    ██    ██ ██   ██ ██           ██
    # ██      ███████ ██   ██    ██     ██████  ██   ██ ███████ ███████

    def calc_last_lesson_stat(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            -- Посчитать статистику решаемости по последнему занятию
            with pre as (
                select r.lesson, r.level, p.prob, p.item,
                       p.title, r.student_id,
                       case when max(r.verdict) > 0 then 1 else 0 end verdict
                from results r
                         join problems p on r.problem_id = p.id
                where p.lesson = (select max(lesson) as last_lesson from problems)
                group by 1, 2, 3, 4, 5, 6
            ),
                 res as (
            select lesson || level || '.' || prob || item as prb, title, sum(verdict) plus,
                   (select count(distinct student_id) from pre as pre2 where pre.level = pre2.level) tot
            from pre
            group by lesson, level, prob, item, title
            order by level, prob, item)
            select prb, plus||'/'||tot as frac, replace(round(plus*100.0/tot,1), '.', ',')||'%' perc, title from res
        """)
        rows = cur.fetchall()
        return rows


db = DB()
db.setup('delme.db')
