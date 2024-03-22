-- Вопросы
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
