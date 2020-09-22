# -*- coding: utf-8 -*-
import sqlite3
import os
from dataclasses import dataclass
import load_data_from_spreadsheet
from datetime import datetime, timedelta
from consts import *

_APP_PATH = os.path.dirname(os.path.realpath(__file__))
_DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_MAX_TIME_TO_CHECK_WRITTEN_TASK = timedelta(minutes=30)
_MAX_WRITTEN_TASKS_TO_SELECT = 5

db = None
users = None
problems = None
states = None
written_queue = None


class DB:
    """Класс, реализующий все взаимодействия с БД"""
    conn: sqlite3.Connection

    def __init__(self, db_file='prod_database.db'):
        """Инициализация и подключение к базе"""
        self.db_file = os.path.join(_APP_PATH, 'db', db_file)
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._connect_to_db()

    @staticmethod
    def _dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _connect_to_db(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = self._dict_factory
        # Всегда запускаем стартовый скрипт
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        script = open(os.path.join(_APP_PATH, 'db_creation.sql')).read()
        res = c.executescript(script)
        self.conn.commit()

    def add_user(self, data: dict):
        cur = self.conn.cursor()
        cur.execute("""
            insert into users ( chat_id,  type,  name,  surname,  middlename,  token) 
            values            (:chat_id, :type, :name, :surname, :middlename, :token) 
            on conflict (token) do update set 
            chat_id=coalesce(excluded.chat_id, chat_id), 
            type=excluded.type, 
            name=excluded.name, 
            surname=excluded.surname, 
            middlename=excluded.middlename
        """, data)
        self.conn.commit()
        return cur.lastrowid

    def add_problem(self, data: dict):
        cur = self.conn.cursor()
        cur.execute("""
            insert into problems ( list,  prob,  item,  title,  prob_text,  prob_type,  ans_type,  ans_validation,  validation_error,  cor_ans,  cor_ans_checker,  wrong_ans,  congrat) 
            values               (:list, :prob, :item, :title, :prob_text, :prob_type, :ans_type, :ans_validation, :validation_error, :cor_ans, :cor_ans_checker, :wrong_ans, :congrat) 
            on conflict (list, prob, item) do update 
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

    def fetch_all_states(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM states")
        rows = cur.fetchall()
        return rows

    def update_state(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                     last_teacher_id: int = 0):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO states  ( user_id,  state,  problem_id,  last_student_id,  last_teacher_id)
            VALUES              (:user_id, :state, :problem_id, :last_student_id, :last_teacher_id) 
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

    def add_result(self, student_id: int, problem_id: int, list: int, teacher_id: int, verdict: int, answer: str):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO results  ( student_id,  problem_id,  list,  teacher_id,  ts,  verdict,  answer)
            VALUES               (:student_id, :problem_id, :list, :teacher_id, :ts, :verdict, :answer) 
        """, args)
        self.conn.commit()

    def check_student_solved(self, student_id: int, list: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select distinct problem_id from results
            where student_id = :student_id and list = :list and verdict > 0
        """, args)
        rows = cur.fetchall()
        solved_ids = {row['problem_id'] for row in rows}
        return solved_ids

    def check_student_sent_written(self, student_id: int, list: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select w.problem_id from written_tasks_queue w
            join problems p on w.problem_id = p.id
            where w.student_id = :student_id and p.list = :list
        """, args)
        rows = cur.fetchall()
        being_checked_ids = {row['problem_id'] for row in rows}
        return being_checked_ids

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

    def fetch_one_state(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("""
        SELECT * FROM states WHERE user_id = :user_id
        """, {"user_id": user_id})
        rows = cur.fetchall()
        if rows:
            return rows[0]
        else:
            return None

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

    def fetch_all_users(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        return rows

    def fetch_all_problems(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM problems")
        rows = cur.fetchall()
        return rows

    def get_all_solved(self):
        cur = self.conn.cursor()
        cur.execute("""
            select
            u.token, u.surname, u.name,
            p.list, p.prob, p.item, min(r.ts) ts
            from results r
            join users u on r.student_id = u.id
            join problems p on r.problem_id = p.id
            where r.verdict > 0
            group by 1, 2, 3, 4, 5, 6
        """)
        rows = cur.fetchall()
        return rows

    def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO written_tasks_queue  ( ts,  student_id,  problem_id,  cur_status)
            VALUES                           (:ts, :student_id, :problem_id, :cur_status)
            ON CONFLICT (student_id, problem_id) do nothing 
        """, args)
        self.conn.commit()
        return cur.lastrowid

    def get_written_tasks(self):
        cur = self.conn.cursor()
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        cur.execute("""
            select * from written_tasks_queue 
            where cur_status = :WRITTEN_STATUS_NEW or ts < :now_minus_30_min
            order by ts asc
            limit :_MAX_WRITTEN_TASKS_TO_SELECT
        """, {'WRITTEN_STATUS_NEW': WRITTEN_STATUS_NEW,
              '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
              'now_minus_30_min': now_minus_30_min})
        rows = cur.fetchall()
        return rows

    def upd_written_task_status(self, student_id: int, problem_id: int, new_status: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
        UPDATE written_tasks_queue
        SET cur_status = :new_status
        where student_id = :student_id and problem_id = :problem_id and cur_status != :new_status
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

    def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int, tg_msg_id: int):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO written_tasks_discussions ( ts,  student_id,  problem_id,  teacher_id,  text,  attach_path,  chat_id,  tg_msg_id)
            VALUES                                (:ts, :student_id, :problem_id, :teacher_id, :text, :attach_path, :chat_id, :tg_msg_id)
        """, args)
        self.conn.commit()
        return cur.lastrowid

    def fetch_written_task_discussion(self, student_id: int, problem_id: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select * from written_tasks_discussions
            where student_id = :student_id and problem_id = :problem_id
            order by ts
        """, args)
        rows = cur.fetchall()
        return rows

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None


@dataclass
class User:
    chat_id: int
    type: int
    name: str
    surname: str
    middlename: str
    token: str
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.add_user(self.__dict__)

    def set_chat_id(self, chat_id: int):
        self.chat_id = chat_id
        db.set_user_chat_id(self.id, self.chat_id)


class Users:
    def __init__(self, rows=None):
        if rows is None:
            rows = db.fetch_all_users()
        self.all_users = []
        self.by_chat_id = {}
        self.by_token = {}
        self.by_id = {}
        for row in rows:
            if type(row) == dict:
                if not row.get('surname', None):
                    continue
                user = User(**row)
            elif type(row) == User:
                user = row
            else:
                raise TypeError('Use dict or User to init Users')

            self.all_users.append(user)
            self.by_chat_id[user.chat_id] = user
            self.by_token[user.token] = user
            self.by_id[user.id] = user

    def get_by_chat_id(self, key):
        return self.by_chat_id.get(key, None)

    def get_by_token(self, key):
        return self.by_token.get(key, None)

    def get_by_id(self, key):
        return self.by_id.get(key, None)

    def set_chat_id(self, user: User, chat_id: int):
        user.set_chat_id(chat_id)
        self.by_chat_id[chat_id] = user

    def __repr__(self):
        return f'Users({self.all_users!r})'

    def __len__(self):
        return len(self.all_users)

    def __iter__(self):
        return iter(self.all_users)


@dataclass
class Problem:
    list: int
    prob: int
    item: str
    title: str
    prob_text: str
    prob_type: int
    ans_type: int
    ans_validation: str
    validation_error: str
    cor_ans: str
    cor_ans_checker: str
    wrong_ans: str
    congrat: str
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.add_problem(self.__dict__)

    def __str__(self):
        return f"Задача {self.list}.{self.prob}{self.item}. {self.title}"


class Problems:
    def __init__(self, rows=None):
        if rows is None:
            rows = db.fetch_all_problems()
        self.all_problems = []
        self.by_key = {}
        self.by_id = {}
        self.by_list = {}
        for row in rows:
            if type(row) == dict:
                if not row.get('list', None) or not row.get('prob', None):
                    continue
                problem = Problem(**row)
            elif type(row) == Problem:
                problem = row
            else:
                raise TypeError('Use dict or Problem to init Problems')
            self.all_problems.append(problem)
            self.by_key[(problem.list, problem.prob, problem.item,)] = problem
            self.by_id[problem.id] = problem
            if problem.list not in self.by_list:
                self.by_list[problem.list] = list()
            self.by_list[problem.list].append(problem)
        self.all_lessons = sorted(list(self.by_list.keys()))
        self.last_lesson = self.all_lessons[-1] if self.all_lessons else -1

    def get_by_id(self, key):
        return self.by_id.get(key, None)

    def get_by_key(self, list: int, prob: int, item: ''):
        return self.by_key.get((list, prob, item), None)

    def get_by_lesson(self, lesson: int):
        return self.by_list.get(lesson, list())

    def __repr__(self):
        return f'Problems({self.all_problems!r})'

    def __len__(self):
        return len(self.all_problems)

    def __iter__(self):
        return iter(self.all_problems)


class States:
    def get_by_user_id(self, user_id: int):
        return db.fetch_one_state(user_id)

    def set_by_user_id(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                       last_teacher_id: int = 0):
        db.update_state(user_id, state, problem_id, last_student_id, last_teacher_id)


class WrittenQueue:
    def add_to_queue(self, student_id: int, problem_id: int):
        db.insert_into_written_task_queue(student_id, problem_id, cur_status=WRITTEN_STATUS_NEW)

    def take_top(self):
        return db.get_written_tasks()

    def mark_being_checked(self, student_id: int, problem_id: int):
        updated_rows = db.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS_BEING_CHECKED)
        return updated_rows > 0

    def mark_not_being_checked(self, student_id: int, problem_id: int):
        db.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS_NEW)

    def delete_from_queue(self, student_id: int, problem_id: int):
        db.delete_from_written_task_queue(student_id, problem_id)

    def add_to_discussions(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int, tg_msg_id: int):
        db.insert_into_written_task_discussion(student_id,  problem_id,  teacher_id,  text,  attach_path, chat_id, tg_msg_id)

    def get_discussion(self, student_id: int, problem_id: int):
        return db.fetch_written_task_discussion(student_id, problem_id)


def init_db_and_objects(db_file='prod_database.db', *, refresh=False):
    global db, users, problems, states, written_queue
    db = DB(db_file)
    users = Users()
    problems = Problems()
    states = States()
    if refresh or len(users) == 0 or len(problems) == 0:
        problems, students, teachers = load_data_from_spreadsheet.load(use_pickle=not refresh)
        for student in students:
            student['type'] = USER_TYPE_STUDENT
            student['chat_id'] = None
            student['middlename'] = ''
        for teacher in teachers:
            teacher['type'] = USER_TYPE_TEACHER
            teacher['chat_id'] = None
        for problem in problems:
            try:
                problem['prob_type'] = PROB_TYPES[problem['prob_type']]
                problem['ans_type'] = ANS_TYPES[problem['ans_type']]
            except:
                print('А-а-а-а, криво настроенные задачи!')
        # Создание юзеров автоматически зальёт их в базу
        users = Users(students + teachers)
        problems = Problems(problems)
    users = Users()  # TODO Это — долбанный костыль, чтобы не терять id-шники чатов. Перечитываем всё из БД
    problems = Problems()  # TODO Это — долбанный костыль, перечитываем всё из БД
    written_queue = WrittenQueue()
    return db, users, problems, states, written_queue


if __name__ == '__main__':
    print('Self test')

    db = DB('test.db')

    u1 = User(None, 1, 'name', 'surname', 'middle', 'tok1')
    u2 = User(124, 1, 'name2', 'surname2', 'middle', 'tok2')
    u3 = User(125, 1, 'name3', 'surname3', 'middle', 'tok3')
    u1upd = User(12312, 1, 'name1', 'surname1', 'middle', 'tok1')

    users = Users()
    print(users)
    print(users.by_token['tok2'])
    print(users.by_id[1])
    print(users.by_chat_id[12312])
    print(users.get_by_id(123))
    print(users.get_by_id(1))
    print(len(users))

    p1 = Problem(1, 1, 'а', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p2 = Problem(1, 1, 'б', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p3 = Problem(1, 2, '', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p2upd = Problem(1, 1, 'б', 'Гы', 'текст_upd', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')

    problems = Problems()
    print(problems)
    print(problems.by_id[1])
    print(problems.by_key[(1, 1, 'б')])
    print(problems.get_by_key(1, 1, 'б'))
    print(problems.get_by_key(1, 1, 'бs'))
    print(len(problems))

    db.disconnect()
    print('\n' * 10)
    print('self test 2')
    db, users, problems, states, written_queue = init_db_and_objects('dummy2')
    for user in users.all_users:
        print(user)
    for user in problems.all_problems:
        print(user)
    db.disconnect()

    print('written queue test')
    # def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int):
    # def get_written_tasks(self):
    # def upd_written_task_status(self, id: int, new_status: int):
    # def delete_from_written_task_queue(self, id: int):
    db, users, problems, states, written_queue = init_db_and_objects('dummy2')
    db.insert_into_written_task_queue(123, 123, 0)
    db.insert_into_written_task_queue(123, 123, 0)
    db.insert_into_written_task_queue(123, 124, 0)
    db.insert_into_written_task_queue(123, 125, 0)
    db.insert_into_written_task_queue(123, 123, 0)
    print(db.get_written_tasks())
    db.upd_written_task_status(123, 125, 1)
    print(db.get_written_tasks())
    db.delete_from_written_task_queue(123, 123)
    db.delete_from_written_task_queue(123, 124)
    db.delete_from_written_task_queue(123, 125)
    print(db.get_written_tasks())

    print('written task discussion')
    # def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str):
    # def fetch_written_task_discussion(self, student_id: int, problem_id: int):
    # db.insert_into_written_task_discussion(123, 123, None, 'Привет', None)
    # db.insert_into_written_task_discussion(123, 123, None, None, '/foo/baz.txt')
    # db.insert_into_written_task_discussion(123, 123, 999, 'Ерунда', None)
    # db.insert_into_written_task_discussion(123, 123, 999, None, '/omg/img.png')
    for row in db.fetch_written_task_discussion(123, 123): print(row)

    print('written_queue')
