import sqlite3
import os
from dataclasses import dataclass

# APP_PATH = os.path.dirname(os.path.realpath(__file__))
APP_PATH = r'X:\repos\vmsh_tasks_bot'
DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class DB:
    """Класс, реализующий все взаимодействия с БД"""
    conn: sqlite3.Connection

    def __init__(self, db_file='prod_database.db'):
        """Инициализация и подключение к базе"""
        self.db_file = os.path.join(APP_PATH, 'db', db_file)
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._connect_to_db()

    @staticmethod
    def _dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _connect_to_db(self):
        create_tables = not os.path.isfile(self.db_file)
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = self._dict_factory
        if create_tables:
            self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NULL UNIQUE,
                type INTEGER NOT NULL,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                middlename TEXT NULL,
                token TEXT UNIQUE 
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                id INTEGER PRIMARY KEY,
                list INTEGER NOT NULL,
                prob INTEGER NOT NULL,
                item TEXT NOT NULL,
                title text NOT NULL,
                prob_text text not null,
                prob_type integer not null,
                ans_type integer null,
                ans_validation text null,
                validation_error text null,
                cor_ans text null,
                cor_ans_checker text null,
                wrong_ans text null,
                congrat text null,
                UNIQUE (list, prob, item)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS states (
                user_id INTEGER PRIMARY KEY,
                state INTEGER,
                problem_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(problem_id) REFERENCES problems(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS results (
                problem_id INTEGER,
                student_id INTEGER NULL,
                teacher_id INTEGER NULL,
                ts timestamp NOT NULL,
                verdict integer NOT NULL,
                FOREIGN KEY(problem_id) REFERENCES problems(id),
                FOREIGN KEY(student_id) REFERENCES users(id),
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS states_log (
                user_id INTEGER PRIMARY KEY,
                state INTEGER,
                problem_id INTEGER,
                ts timestamp NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(problem_id) REFERENCES problems(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages_log (
                id INTEGER PRIMARY KEY UNIQUE,
                from_bot boolean NOT NULL,
                tg_msg_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                student_id INTEGER NULL,
                teacher_id INTEGER NULL,
                ts timestamp NOT NULL,
                msg_text TEXT NULL,
                attach_path TEXT NULL,
                FOREIGN KEY(student_id) REFERENCES users(id),
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
        """)
        self.conn.commit()

    def add_user(self, data: dict):
        cur = self.conn.cursor()
        cur.execute("""
            insert into users ( chat_id,  type,  name,  surname,  middlename,  token) 
            values            (:chat_id, :type, :name, :surname, :middlename, :token) 
            on conflict (token) do update set 
            chat_id=excluded.chat_id, 
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


class Users:
    def __init__(self, rows=None):
        if rows is None:
            rows = db.fetch_all_users()
        self.all_users = []
        self.by_chat_id = {}
        self.by_token = {}
        self.by_id = {}
        for row in rows:
            user = User(**row)
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

    def __repr__(self):
        return f'Users({self.all_users!r})'


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


class Problems:
    def __init__(self, rows=None):
        if rows is None:
            rows = db.fetch_all_problems()
        self.all_users = []
        self.by_key = {}
        self.by_id = {}
        for row in rows:
            problem = Problem(**row)
            self.all_users.append(problem)
            self.by_key[(problem.list, problem.prob, problem.item,)] = problem
            self.by_id[problem.id] = problem

    def get_by_id(self, key):
        return self.by_id.get(key, None)

    def get_by_key(self, list: int, prob: int, item: ''):
        return self.by_id.get((list, prob, item), None)

    def __repr__(self):
        return f'Problems({self.all_users!r})'


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

    db.disconnect()
