from datetime import datetime
from typing import List, Dict

from .db_abc import DB_ABC, sql

"""-- Вопросы
create table IF NOT EXISTS questions
(
    id                   INTEGER primary key,
    ts                   TIMESTAMP not null,
    answered             BOOLEAN   not null default false,

    user_id              INTEGER references users,
    chat_id              INTEGER   not null,
    question_msg_id      INTEGER   not null,
    question_text        TEXT      null,

    sos_chat_id          INTEGER   not null,
    sos_header_msg_id    INTEGER   not null,
    sos_forwarded_msg_id INTEGER   not null,
    answer_text          TEXT      null,
    unique (sos_chat_id, sos_forwarded_msg_id)
);
"""


class DB_QUESTIONS(DB_ABC):
    def add(self, user_id: int, chat_id: int, question_msg_id: int, question_text: str,
            sos_chat_id: int, sos_header_msg_id: int, sos_forwarded_msg_id: int, answer_text: str = None) -> int:
        ts = datetime.now().isoformat()
        answered = False
        with self.db.conn as conn:
            cur = conn.execute("""
                INSERT INTO questions (ts, answered, user_id, chat_id, question_msg_id, question_text, sos_chat_id, 
                                       sos_header_msg_id, sos_forwarded_msg_id, answer_text)
                VALUES (:ts, :answered, :user_id, :chat_id, :question_msg_id, :question_text, :sos_chat_id, 
                        :sos_header_msg_id, :sos_forwarded_msg_id, :answer_text)
                returning id
            """, locals())
            return cur.fetchone()['id']

    def get_message_by_sos(self, sos_chat_id: int, sos_forwarded_msg_id: int) -> Dict:
        with self.db.conn as conn:
            return conn.execute("""
                SELECT * FROM questions
                WHERE sos_chat_id = :sos_chat_id AND sos_forwarded_msg_id = :sos_forwarded_msg_id
            """, locals()).fetchone()

    def mark_as_answered(self, sos_chat_id: int, sos_forwarded_msg_id: int, answer_text: str = None) -> None:
        with self.db.conn as conn:
            conn.execute("""
                UPDATE questions
                SET answered = true, answer_text = :answer_text
                WHERE sos_chat_id = :sos_chat_id AND sos_forwarded_msg_id = :sos_forwarded_msg_id
            """, locals())


# Usage example
question = DB_QUESTIONS(sql)
