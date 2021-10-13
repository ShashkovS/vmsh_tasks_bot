CREATE TABLE IF NOT EXISTS last_keyboards
(
    user_id   INTEGER not null primary key,
    chat_id   INTEGER not null,
    tg_msg_id INTEGER not null,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
