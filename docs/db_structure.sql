CREATE TABLE game_map_chests
(
    id         INTEGER PRIMARY KEY,
    ts         timestamp NOT NULL,
    student_id INTEGER NOT NULL,
    command_id INTEGER NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    bonus      INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    UNIQUE (student_id, command_id, x, y)
);

CREATE TABLE game_map_flags
(
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    command_id INTEGER NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    UNIQUE (student_id, command_id)
);

CREATE TABLE game_map_opened_cells
(
    id         INTEGER PRIMARY KEY,
    command_id INTEGER NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    UNIQUE (command_id, x, y)
);

CREATE TABLE game_payments
(
    id         INTEGER PRIMARY KEY,
    ts         timestamp NOT NULL,
    student_id INTEGER   NOT NULL,
    amount     INTEGER   NOT NULL,
    cell_id    INTEGER   NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (cell_id) REFERENCES game_map_opened_cells (id)
);

CREATE TABLE game_students_commands
(
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL UNIQUE,
    command_id INTEGER NOT NULL,
    group_id      text    not null,
    FOREIGN KEY (student_id) REFERENCES users (id)
);

CREATE TABLE kv (key text unique, value text);

CREATE TABLE last_keyboards
(
    user_id   INTEGER not null primary key,
    chat_id   INTEGER not null,
    tg_msg_id INTEGER not null,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE lessons
(
    id               INTEGER PRIMARY KEY,
    group_id            TEXT    NOT NULL,
    lesson           INTEGER NOT NULL,
    UNIQUE (lesson, group_id)
);

CREATE TABLE media_groups
(
    media_group_id INTEGER NOT NULL PRIMARY KEY UNIQUE,
    problem_id INTEGER NOT NULL,
    ts timestamp NOT NULL,
    FOREIGN KEY (problem_id) REFERENCES problems (id)
);

CREATE TABLE messages_log
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

CREATE TABLE problem_complexity (
synonyms TEXT NOT NULL primary key,
for_weak DOUBLE NOT NULL,
for_strong DOUBLE NOT NULL
);

CREATE TABLE problems
(
    id               INTEGER PRIMARY KEY,
    group_id            TEXT    NOT NULL,
    lesson           INTEGER NOT NULL,
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
    congrat          text    null, synonyms text default '' not null,
    UNIQUE (group_id, lesson, prob, item)
);

CREATE TABLE questions
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

CREATE TABLE reaction_enum
(
    reaction_id      INTEGER PRIMARY KEY,
    reaction         TEXT    NOT NULL,
    reaction_type_id INTEGER NOT NULL
);

CREATE TABLE reaction_type_enum
(
    reaction_type_id INTEGER PRIMARY KEY,
    reaction_type    TEXT UNIQUE NOT NULL
);

CREATE TABLE reactions
(
    id                   INTEGER PRIMARY KEY,
    ts                   TEXT,
    result_id            INT NULL,
    zoom_conversation_id INT NULL,
    reaction_id          INT NOT NULL,
    reaction_type_id     INT NOT NULL,
    FOREIGN KEY (result_id) REFERENCES results (id),
    FOREIGN KEY (zoom_conversation_id) REFERENCES zoom_conversation (zoom_conversation_id),
    FOREIGN KEY (reaction_id) REFERENCES reaction_enum (reaction_id),
    FOREIGN KEY (reaction_type_id) REFERENCES reaction_type_enum (reaction_type_id)
);

CREATE TABLE "results"
(
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    group_id      TEXT    NOT NULL,
    lesson       INTEGER NOT NULL,
    teacher_id INTEGER   NULL,
    ts         timestamp NOT NULL,
    verdict    integer   NOT NULL,
    answer     TEXT      NULL,
    res_type   integer null,
    check_time_spent_sec int null default null, zoom_conversation_id INT NULL REFERENCES zoom_conversation (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

CREATE TABLE signons
(
    ts         timestamp NOT NULL,
    user_id    INTEGER   null,
    chat_id    INTEGER   not null,
    first_name TEXT      null,
    last_name  TEXT      null,
    username   TEXT      null, token text null,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE states
(
    user_id         INTEGER PRIMARY KEY UNIQUE,
    state           INTEGER,
    problem_id      INTEGER NULL,
    last_student_id INTEGER NULL,
    last_teacher_id INTEGER NULL,
    oral_problem_id INTEGER NULL, info blob default null,  -- не NULL, если стоит в очереди сдавать эту задачу
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (last_student_id) REFERENCES users (id),
    FOREIGN KEY (last_teacher_id) REFERENCES users (id),
    FOREIGN KEY (oral_problem_id) REFERENCES users (id)
);

CREATE TABLE student_strength
(
student_id integer not null primary key,
simple_prob DOUBLE NOT NULL,
compl_prob DOUBLE NOT NULL
);

CREATE TABLE survey_assigns
(
    id        INTEGER primary key,
    user_id   INTEGER not null references users,
    survey_id INTEGER not null references surveys,
    unique (user_id)
);

CREATE TABLE survey_choices
(
    id        INTEGER primary key,
    survey_id INTEGER not null references surveys,
    text      TEXT    not null
);

CREATE TABLE survey_results
(
    id            INTEGER primary key,
    survey_id     INTEGER   not null references surveys,
    user_id       INTEGER   not null references users,
    selection_ids TEXT      not null,
    ts            timestamp not null,
    unique (survey_id, user_id)
);

CREATE TABLE surveys
(
    id          INTEGER primary key,
    survey_type CHAR(1)   not null,
    is_active   BOOL      not null,
    question    TEXT      not null,
    ts          timestamp not null
);

CREATE TABLE user_changes_log
(
    ts          timestamp not null,
    user_id     INTEGER   not null references users,
    change_type text      not null,
    new_value   text      not null
);

CREATE TABLE users
(
    id         INTEGER PRIMARY KEY,
    chat_id    INTEGER NULL UNIQUE,
    type       INTEGER NOT NULL,
    group_id      TEXT        NULL,
    name       TEXT    NOT NULL,
    surname    TEXT    NOT NULL,
    middlename TEXT    NULL,
    token      TEXT UNIQUE
, online INTEGER NULL, grade int null, birthday int null);

CREATE TABLE verdicts
(
    id   INTEGER primary key,
    tick TEXT not null,
    val  REAL not null
);

CREATE TABLE waitlist
(
    id INTEGER PRIMARY KEY UNIQUE,
    student_id INTEGER NOT NULL UNIQUE,
    entered timestamp NOT NULL,
    problem_id INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id)
);

CREATE TABLE webtokens
(
    user_id         INTEGER PRIMARY KEY UNIQUE,
    webtoken        TEXT    NOT NULL UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE written_tasks_discussions
(
    id          INTEGER PRIMARY KEY UNIQUE,
    ts          timestamp NOT NULL,
    student_id  INTEGER   NOT NULL,
    problem_id  INTEGER   NOT NULL,
    teacher_id  INTEGER   NULL,
    text        TEXT      NULL,
    attach_path TEXT      NULL,
    chat_id     INTEGER   NULL,
    tg_msg_id   INTEGER   NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id)
);

CREATE TABLE written_tasks_queue
(
    id          INTEGER PRIMARY KEY UNIQUE,
    ts          timestamp NOT NULL,
    student_id  INTEGER   NOT NULL,
    problem_id  INTEGER   NOT NULL,
    cur_status  INTEGER   NOT NULL,
    teacher_ts  TIMESTAMP null,
    teacher_id  TIMESTAMP null,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id),
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    UNIQUE (student_id, problem_id)
);

CREATE TABLE "yoyo_lock" (locked INT DEFAULT 1, ctime TIMESTAMP,pid INT NOT NULL,PRIMARY KEY (locked));

CREATE TABLE z_settings
(
    id        INTEGER primary key,
    key       text      not null unique,
    value     text      not null,
    change_ts timestamp not null
);

CREATE TABLE z_ui_messages
(
    id        INTEGER primary key,
    key       text      not null unique,
    value     text      not null,
    change_ts timestamp not null
);

CREATE TABLE zoom_conversation
(
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    student_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    group_id      TEXT NOT NULL,
    lesson     INTEGER NOT NULL,
    check_time_spent_sec INTEGER NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

CREATE TABLE zoom_events
(
    id                 INTEGER PRIMARY KEY,
    event_ts           TIMESTAMP NOT NULL,
    event              TEXT      NOT NULL,
    zoom_user_name     TEXT      NULL,
    zoom_user_id       INTEGER   NULL,
    breakout_room_uuid TEXT      NULL,
    user_id            INTEGER   NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE zoom_queue
(
    zoom_user_name TEXT NOT NULL PRIMARY KEY UNIQUE,
    enter_ts timestamp NOT NULL,
    status INTEGER NOT NULL
);

