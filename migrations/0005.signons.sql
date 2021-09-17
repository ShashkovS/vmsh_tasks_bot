CREATE TABLE IF NOT EXISTS signons
(
    ts         timestamp NOT NULL,
    user_id    INTEGER   null,
    chat_id    INTEGER   not null,
    first_name TEXT      null,
    last_name  TEXT      null,
    username   TEXT      null,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
