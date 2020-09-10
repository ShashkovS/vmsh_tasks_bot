import sqlite3
import os
from dataclasses import dataclass

APP_PATH = os.path.dirname(os.path.realpath(__file__))
DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
sqlite_db_path = os.path.join(APP_PATH, 'db', 'prod_database.db')
os.makedirs(os.path.dirname(sqlite_db_path), exist_ok=True)

conn: sqlite3.Connection


def _create_base():
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
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
                text text not null,
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
        conn.commit()


def add_user(chat_id: int, type: int, name: str, surname: str, middlename: str, token: str):
    cur = conn.cursor()
    cur.execute('insert into users (chat_id, type, name, surname, middlename, token) '
                'values (?, ?, ?, ?, ?, ?) '
                'on conflict (token) do update '
                'set '
                'type=excluded.type, '
                'name=excluded.name, '
                'surname=excluded.surname, '
                'middlename=excluded.middlename'
                )
    return cur.lastrowid


def connect_to_db():
    global conn
    if not os.path.isfile(sqlite_db_path):
        _create_base()
    conn = sqlite3.connect(sqlite_db_path)


def disconnect():
    global conn
    if conn:
        conn.close()
        conn = None


@dataclass
class User:
    chat_id: int
    type: int
    name: str
    surname: str
    middlename: str
    token: str
    id: int = -1

    def __post_init__(self):
        self.id = add_user(self.chat_id, self.type, self.name, self.surname, self.middlename, self.token)


@dataclass
class Problem:
    pass


if __name__ == '__main__':
    connect_to_db()
