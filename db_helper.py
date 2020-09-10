import sqlite3
import os

APP_PATH = os.path.dirname(os.path.realpath(__file__))
sqlite_db_path = os.path.join(APP_PATH, 'db', 'prod_database.db')
DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _create_base():
    with sqlite3.connect(sqlite_db_path) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY UNIQUE ,
            user_id int UNIQUE ,
            type boolean,
            name text,
            surname text,
            middlename text,
            token text UNIQUE 
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY UNIQUE ,
            list INTEGER,
            prob INTEGER,
            item text,
            UNIQUE (list, prob, item)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS states (
            user_id INTEGER PRIMARY KEY UNIQUE ,
            state int,
            problem_id int,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY UNIQUE ,
            from_bot boolean,
            tg_msg_id int,
            chat_id int,
            student_id int,
            teacher_id int,
            ts timestamp,
            msg_text text,
            attach_path text
        )
        """)
        conn.commit()


def check_base():
    if not os.path.isfile(sqlite_db_path):
        _create_base()


if __name__ == '__main__':
    check_base()
