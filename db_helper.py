import sqlite3
import os

APP_PATH = os.path.dirname(os.path.realpath(__file__))
sqlite_db_path = os.path.join(APP_PATH, 'db', 'prod_database.db')
os.makedirs(os.path.dirname(sqlite_db_path), exist_ok=True)
DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _create_base():
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE,
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


def check_base():
    if not os.path.isfile(sqlite_db_path):
        _create_base()


if __name__ == '__main__':
    check_base()
