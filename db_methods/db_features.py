import sqlite3
from typing import List
from datetime import datetime


class DB_FEATURES:
    conn: sqlite3.Connection

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

    def log_signon(self, user_id: int, chat_id: int, first_name: str, last_name: str, username: str, token: str):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO signons ( ts,  user_id,  chat_id,  first_name,  last_name,  username,  token)
            VALUES              (:ts, :user_id, :chat_id, :first_name, :last_name, :username, :token) 
        """, args)
        self.conn.commit()

    def log_change(self, user_id: int, change_type: str, new_value: str):
        args = locals()
        args['ts'] = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO user_changes_log ( ts,  user_id,  change_type,  new_value)
            VALUES                       (:ts, :user_id, :change_type, :new_value) 
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
