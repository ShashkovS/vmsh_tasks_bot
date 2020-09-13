CREATE TABLE IF NOT EXISTS users
(
    id         INTEGER PRIMARY KEY,
    chat_id    INTEGER NULL UNIQUE,
    type       INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    surname    TEXT    NOT NULL,
    middlename TEXT    NULL,
    token      TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS problems
(
    id               INTEGER PRIMARY KEY,
    list             INTEGER NOT NULL,
    prob             INTEGER NOT NULL,
    item             TEXT    NOT NULL,
    title            text    NOT NULL,
    prob_text        text    not null,
    prob_type        integer not null,
    ans_type         integer null,
    ans_validation   text    null,
    validation_error text    null,
    cor_ans          text    null,
    cor_ans_checker  text    null,
    wrong_ans        text    null,
    congrat          text    null,
    UNIQUE (list, prob, item)
);

CREATE TABLE IF NOT EXISTS states
(
    user_id         INTEGER PRIMARY KEY UNIQUE,
    state           INTEGER,
    problem_id      INTEGER NULL,
    last_student_id INTEGER NULL,
    last_teacher_id INTEGER NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (last_student_id) REFERENCES users (id),
    FOREIGN KEY (last_teacher_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS results
(
    problem_id INTEGER,
    student_id INTEGER   NULL,
    teacher_id INTEGER   NULL,
    ts         timestamp NOT NULL,
    verdict    integer   NOT NULL,
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

create index if not exists results_by_student_solved on results
(student_id) where verdict > 0;

CREATE TABLE IF NOT EXISTS states_log
(
    user_id    INTEGER PRIMARY KEY,
    state      INTEGER,
    problem_id INTEGER,
    ts         timestamp NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id)
);

CREATE TABLE IF NOT EXISTS messages_log
(
    id          INTEGER PRIMARY KEY UNIQUE,
    from_bot    boolean   NOT NULL,
    tg_msg_id   INTEGER   NOT NULL,
    chat_id     INTEGER   NOT NULL,
    student_id  INTEGER   NULL,
    teacher_id  INTEGER   NULL,
    ts          timestamp NOT NULL,
    msg_text    TEXT      NULL,
    attach_path TEXT      NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);
