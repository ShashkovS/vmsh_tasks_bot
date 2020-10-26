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
_MAX_WRITTEN_TASKS_TO_SELECT = 8

db = None
users = None
problems = None
states = None
written_queue = None
waitlist = None

RU_TO_EN = str.maketrans('УКЕНХВАРОСМТукехарос', 'YKEHXBAPOCMTykexapoc')


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

    def add_problem(self, data: dict):
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

    def fetch_all_states(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM states")
        rows = cur.fetchall()
        return rows

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

    def add_result(self, student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int, answer: str):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO results  ( student_id,  problem_id,  level,  lesson,  teacher_id,  ts,  verdict,  answer)
            VALUES               (:student_id, :problem_id, :level, :lesson, :teacher_id, :ts, :verdict, :answer) 
        """, args)
        self.conn.commit()

    def delete_plus(self, student_id: int, problem_id: int, verdict: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            update results set verdict = :verdict
            where student_id = :student_id and problem_id = :problem_id and problem_id > 0
        """, args)
        self.conn.commit()

    def check_student_solved(self, student_id: int, level: str, lesson: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            select distinct problem_id from results
            where student_id = :student_id and level = :level and lesson = :lesson and verdict > 0
        """, args)
        rows = cur.fetchall()
        solved_ids = {row['problem_id'] for row in rows}
        return solved_ids

    def check_student_sent_written(self, student_id: int, lesson: int):
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

    def get_waitlist_top(self, top_n: int):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM waitlist
            ORDER BY entered ASC
            LIMIT :top_n
        """, args)
        return cur.fetchall()

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

    def set_user_level(self, user_id: int, level: str):
        args = locals()
        cur = self.conn.cursor()
        cur.execute("""
        UPDATE users
        SET level = :level
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

    def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int, ts: datetime = None):
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

    def get_written_tasks_to_check(self, teacher_id):
        cur = self.conn.cursor()
        now_minus_30_min = (datetime.now() - _MAX_TIME_TO_CHECK_WRITTEN_TASK).isoformat()
        cur.execute("""
            select * from written_tasks_queue 
            where cur_status = :WRITTEN_STATUS_NEW or teacher_ts < :now_minus_30_min or teacher_id = :teacher_id
            order by ts asc
            limit :_MAX_WRITTEN_TASKS_TO_SELECT
        """, {'WRITTEN_STATUS_NEW': WRITTEN_STATUS_NEW,
              '_MAX_WRITTEN_TASKS_TO_SELECT': _MAX_WRITTEN_TASKS_TO_SELECT,
              'now_minus_30_min': now_minus_30_min,
              'teacher_id': teacher_id})
        rows = cur.fetchall()
        return rows

    def get_written_tasks_count(self):
        cur = self.conn.cursor()
        cur.execute("""
            select count(*) cnt from written_tasks_queue 
        """)
        row = cur.fetchone()
        return row['cnt']

    def upd_written_task_status(self, student_id: int, problem_id: int, new_status: int, teacher_id: int = None):
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

    def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int,
                                            tg_msg_id: int):
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
    level: str
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

    def set_level(self, level: str):
        self.level = level
        db.set_user_level(self.id, level)

    def __str__(self):
        return f'{self.name} {self.middlename} {self.surname}'


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
            self.by_token[user.token.strip().translate(RU_TO_EN).lower()] = user
            self.by_id[user.id] = user

    def get_by_chat_id(self, key):
        return self.by_chat_id.get(key, None)

    def get_by_token(self, key):
        if not key:
            return None
        return self.by_token.get(key.strip().translate(RU_TO_EN).lower(), None)

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
    level: str
    lesson: int
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
        return f"Задача {self.lesson}{self.level}.{self.prob}{self.item}. {self.title}"


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
                if not row.get('lesson', None) or not row.get('prob', None):
                    continue
                problem = Problem(**row)
            elif type(row) == Problem:
                problem = row
            else:
                raise TypeError('Use dict or Problem to init Problems')
            self.all_problems.append(problem)
            self.by_key[(problem.level, problem.lesson, problem.prob, problem.item,)] = problem
            self.by_id[problem.id] = problem
            list_key = (problem.level, problem.lesson)
            if list_key not in self.by_list:
                self.by_list[list_key] = []
            self.by_list[list_key].append(problem)
        self.all_lessons = sorted(list(self.by_list.keys()))  # Осторожно, не тот смысл!
        self.last_lesson = self.all_lessons[-1][1] if self.all_lessons else -1  # Говнокод

    def get_by_id(self, key):
        return self.by_id.get(key, None)

    def get_by_key(self, level: str, lesson: int, prob: int, item: ''):
        return self.by_key.get((level, lesson, prob, item), None)

    def get_by_lesson(self, level: str, lesson: int):
        return self.by_list.get((level, lesson), [])

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
                       last_teacher_id: int = 0, oral_problem_id: int = None):
        db.update_state(user_id, state, problem_id, last_student_id, last_teacher_id, oral_problem_id)


class Waitlist:
    def enter(self, student_id: int, problem_id: int):
        db.update_oral_problem(student_id, problem_id)
        db.add_user_to_waitlist(student_id, problem_id)

    def leave(self, student_id: int):
        db.update_oral_problem(student_id, None)
        db.remove_user_from_waitlist(student_id)

    def top(self, n: int = 10) -> list:
        return db.get_waitlist_top(n)


class WrittenQueue:
    def add_to_queue(self, student_id: int, problem_id: int, ts: datetime = None):
        db.insert_into_written_task_queue(student_id, problem_id, cur_status=WRITTEN_STATUS_NEW, ts=ts)

    def take_top(self, teacher_id: int):
        return db.get_written_tasks_to_check(teacher_id)

    def mark_being_checked(self, student_id: int, problem_id: int, teacher_id: int):
        updated_rows = db.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS_BEING_CHECKED, teacher_id)
        return updated_rows > 0

    def mark_not_being_checked(self, student_id: int, problem_id: int):
        db.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS_NEW, None)

    def delete_from_queue(self, student_id: int, problem_id: int):
        db.delete_from_written_task_queue(student_id, problem_id)

    def add_to_discussions(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int, tg_msg_id: int):
        db.insert_into_written_task_discussion(student_id, problem_id, teacher_id, text, attach_path, chat_id, tg_msg_id)

    def get_discussion(self, student_id: int, problem_id: int):
        return db.fetch_written_task_discussion(student_id, problem_id)


def init_db_and_objects(db_file='prod_database.db', *, refresh=False):
    global db, users, problems, states, written_queue, waitlist
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
            teacher['level'] = None
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
    waitlist = Waitlist()
    return db, users, problems, states, written_queue, waitlist


def update_teachers(db_file='prod_database.db'):
    global users
    teachers = load_data_from_spreadsheet.load_teachers()
    for teacher in teachers:
        if not teacher.get('surname', None):
            continue
        teacher['type'] = USER_TYPE_TEACHER
        teacher['chat_id'] = None
        teacher['level'] = None
        # Создание юзеров автоматически зальёт их в базу
        User(**teacher)
    users = Users()  # TODO Это — долбанный костыль, чтобы не терять id-шники чатов. Перечитываем всё из БД
    return users


def update_problems(db_file='prod_database.db'):
    global problems
    problems = load_data_from_spreadsheet.load_problems()
    for problem in problems:
        if not problem.get('lesson', None) or not problem.get('prob', None):
            continue
        try:
            problem['prob_type'] = PROB_TYPES[problem['prob_type']]
            problem['ans_type'] = ANS_TYPES[problem['ans_type']]
        except:
            print('А-а-а-а, криво настроенные задачи!')
            continue
        Problem(**problem)
    problems = Problems()  # TODO Это — долбанный костыль, чтобы не терять id-шники чатов. Перечитываем всё из БД
    return problems


if __name__ == '__main__':
    print('Self test')

    db = DB('test.db')

    u1 = User(None, 1, 'н', 'name', 'surname', 'middle', 'tok1')
    u2 = User(124, 1, 'н', 'name2', 'surname2', 'middle', 'tok2')
    u3 = User(125, 1, 'н', 'name3', 'surname3', 'middle', 'tok3')
    u1upd = User(12312, 1, 'н', 'name1', 'surname1', 'middle', 'tok1')

    users = Users()
    print(users)
    print(users.by_token['tok2'])
    print(users.by_id[1])
    print(users.by_chat_id[12312])
    print(users.get_by_id(123))
    print(users.get_by_id(1))
    print(len(users))

    p1 = Problem('н', 1, 1, 'а', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p2 = Problem('н', 1, 1, 'б', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p3 = Problem('н', 1, 2, '', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')
    p2upd = Problem('н', 1, 1, 'б', 'Гы', 'текст_upd', 0, 0, r'\d+', 'ЧИСЛО!', '123', 'check_int', 'ЛОЖЬ!', 'Крутяк')

    problems = Problems()
    print(problems)
    print(problems.by_id[1])
    print(problems.by_key[('н', 1, 1, 'б')])
    print(problems.get_by_key('н', 1, 1, 'б'))
    print(problems.get_by_key('н', 1, 1, 'бs'))
    print(len(problems))

    waitlist = Waitlist()
    states = States()
    for i in range(1, 15):
        waitlist.enter(i, i)
        states.set_by_user_id(i, STATE_SENDING_SOLUTION, i)

    print('WL: add 14 people')
    wl = waitlist.top()
    for r in wl:
        print('wl entry = ', r)
        print('user state = ', states.get_by_user_id(r['student_id']))
        waitlist.leave(r['student_id'])
    print('States after leaving waitlist:')
    for r in wl:
        print('user state = ', states.get_by_user_id(r['student_id']))

    print('WL: new top')
    wl = waitlist.top()
    for r in wl:
        print(r)
        waitlist.leave(r['student_id'])

    db.disconnect()
    print('\n' * 10)
    print('self test 2')
    db, users, problems, states, written_queue, waitlist = init_db_and_objects('dummy2')
    for user in users.all_users:
        print(user)
    for user in problems.all_problems:
        print(user)
    db.disconnect()

    print('written queue test')
    # def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int):
    # def get_written_tasks_to_check(self):
    # def upd_written_task_status(self, id: int, new_status: int):
    # def delete_from_written_task_queue(self, id: int):
    db, users, problems, states, written_queue, waitlist = init_db_and_objects('dummy2')
    db.insert_into_written_task_queue(123, 123, 0)
    db.insert_into_written_task_queue(123, 123, 0)
    db.insert_into_written_task_queue(123, 124, 0)
    db.insert_into_written_task_queue(123, 125, 0)
    db.insert_into_written_task_queue(123, 123, 0)
    print(db.get_written_tasks_to_check(-1))
    db.upd_written_task_status(123, 125, 1)
    print(db.get_written_tasks_to_check(-1))
    print('get_written_tasks_count', db.get_written_tasks_count())
    db.delete_from_written_task_queue(123, 123)
    db.delete_from_written_task_queue(123, 124)
    db.delete_from_written_task_queue(123, 125)
    print(db.get_written_tasks_to_check(-1))

    print('written task discussion')
    # def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str):
    # def fetch_written_task_discussion(self, student_id: int, problem_id: int):
    # db.insert_into_written_task_discussion(123, 123, None, 'Привет', None)
    # db.insert_into_written_task_discussion(123, 123, None, None, '/foo/baz.txt')
    # db.insert_into_written_task_discussion(123, 123, 999, 'Ерунда', None)
    # db.insert_into_written_task_discussion(123, 123, 999, None, '/omg/img.png')
    for row in db.fetch_written_task_discussion(123, 123): print(row)

    print('written_queue')
