-- GENERATED FILE. DO NOT EDIT BY HAND.
-- Authoritative source: repository yoyo migrations plus schema inventory.
-- Schema-only: contains no product row values; DDL is migration-authored.
-- Reference only: apply migrations rather than using this as a bootstrap.
-- Product schema SHA-256: 5ba3e4323ba8b0808516bb3986a0460e3d2f0a87d33d351bc9c4161c93d5b594

CREATE TABLE game_map_chests
(
    id         INTEGER primary key,
    ts         timestamp not null,
    student_id INTEGER   not null references users,
    command_id INTEGER   not null,
    x          INTEGER   not null,
    y          INTEGER   not null,
    bonus      INTEGER   not null,
    unique (student_id, command_id, x, y)
);

CREATE TABLE game_map_flags
(
    id         INTEGER primary key,
    student_id INTEGER not null references users,
    command_id INTEGER not null,
    x          INTEGER not null,
    y          INTEGER not null,
    unique (student_id, command_id)
);

CREATE TABLE game_map_opened_cells
(
    id         INTEGER primary key,
    command_id INTEGER not null,
    x          INTEGER not null,
    y          INTEGER not null,
    unique (command_id, x, y)
);

CREATE TABLE game_payments
(
    id         INTEGER primary key,
    ts         timestamp not null,
    student_id INTEGER   not null references users,
    amount     INTEGER   not null,
    cell_id    INTEGER   not null references game_map_opened_cells
);

CREATE TABLE "game_students_commands"
(
    id         INTEGER
        primary key,
    student_id INTEGER not null
        unique
        references users,
    command_id INTEGER not null,
    group_id   text
        references groups
);

CREATE TABLE groups
(
    group_id              text primary key,
    short_code            text    not null,
    broadcast_code        text unique,
    tg_command            text unique,
    public_name           text    not null,
    conditions_url        text,
    tasks_header_template text,
    switch_message        text,
    sort_order            integer,
    is_active             integer not null default 1,
    is_default            integer not null default 0,
    allow_self_switch     integer not null default 0,
    is_system             integer not null default 0,
    score_weight          real    not null default 1.0
);

CREATE TABLE kv
(
    key   text unique,
    value text
);

CREATE TABLE kv_logins
(
    id          integer not null            primary key,
    user_id     integer not null
        constraint kv_logins_pk_2
            unique
        constraint kv_logins_users_id_fk
            references users,
    token       text    not null,
    kv_login    text,
    kv_password text
);

CREATE TABLE last_keyboards
(
    user_id   INTEGER not null primary key references users,
    chat_id   INTEGER not null,
    tg_msg_id INTEGER not null
);

CREATE TABLE "lessons"
(
    id       INTEGER
        primary key,
    group_id text
        references groups,
    lesson   INTEGER not null,
    unique (lesson, group_id)
);

CREATE TABLE media_groups
(
    media_group_id INTEGER   not null primary key unique,
    problem_id     INTEGER   not null references problems,
    ts             timestamp not null
);

CREATE TABLE messages_log
(
    id          INTEGER primary key unique,
    from_bot    boolean   not null,
    tg_msg_id   INTEGER   not null,
    chat_id     INTEGER   not null,
    student_id  INTEGER references users,
    teacher_id  INTEGER references users,
    ts          timestamp not null,
    msg_text    TEXT,
    attach_path TEXT
);

CREATE TABLE problem_complexity
(
    synonyms   TEXT   not null primary key,
    for_weak   DOUBLE not null,
    for_strong DOUBLE not null
);

CREATE TABLE "problems"
(
    id               INTEGER
        primary key,
    group_id         text
        references groups,
    lesson           INTEGER         not null,
    prob             INTEGER         not null,
    item             TEXT            not null,
    title            text            not null,
    prob_text        text            not null,
    prob_type        integer         not null,
    ans_type         integer,
    ans_validation   text,
    validation_error text,
    cor_ans          text,
    cor_ans_checker  text,
    wrong_ans        text,
    congrat          text,
    synonyms         text default '' not null,
    unique (group_id, lesson, prob, item)
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
    reaction_id      INTEGER primary key,
    reaction         TEXT    not null,
    reaction_type_id INTEGER not null references reaction_type_enum
);

CREATE TABLE reaction_type_enum
(
    reaction_type_id INTEGER primary key,
    reaction_type    TEXT not null unique
);

CREATE TABLE reactions
(
    id                   INTEGER primary key,
    ts                   TEXT,
    result_id            INT references results,
    zoom_conversation_id INT references zoom_conversation,
    reaction_id          INT not null references reaction_enum,
    reaction_type_id     INT not null references reaction_type_enum
);

CREATE TABLE "results"
(
    id                   INTEGER
        primary key,
    student_id           INTEGER   not null
        references users,
    problem_id           INTEGER   not null
        references problems,
    group_id             text
        references groups,
    lesson               INTEGER   not null,
    teacher_id           INTEGER
        references users,
    ts                   timestamp not null,
    verdict              integer   not null,
    answer               TEXT,
    res_type             integer,
    check_time_spent_sec int default null,
    zoom_conversation_id INT
        references zoom_conversation
);

CREATE TABLE signons
(
    ts         timestamp not null,
    user_id    INTEGER references users,
    chat_id    INTEGER   not null,
    first_name TEXT,
    last_name  TEXT,
    username   TEXT,
    token      text
);

CREATE TABLE states
(
    user_id         INTEGER primary key unique references users,
    state           INTEGER,
    problem_id      INTEGER references problems,
    last_student_id INTEGER references users,
    last_teacher_id INTEGER references users,
    oral_problem_id INTEGER references users,
    info            blob default null
);

CREATE TABLE student_strength
(
    student_id  integer not null primary key,
    simple_prob DOUBLE  not null,
    compl_prob  DOUBLE  not null
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

CREATE TABLE "users"
(
    id             INTEGER
        primary key,
    chat_id        INTEGER
        unique,
    type           INTEGER not null,
    group_id       text
        references groups,
    name           TEXT    not null,
    surname        TEXT    not null,
    middlename     TEXT,
    token          TEXT
        unique,
    online         INTEGER,
    grade          int,
    birthday       int,
    allowed_groups text
);

CREATE TABLE verdicts
(
    id   INTEGER primary key,
    tick TEXT not null,
    val  REAL not null
);

CREATE TABLE waitlist
(
    id         INTEGER primary key unique,
    student_id INTEGER   not null unique references users,
    entered    timestamp not null,
    problem_id INTEGER   not null references problems
);

CREATE TABLE webtokens
(
    user_id  INTEGER primary key unique references users,
    webtoken TEXT not null unique
);

CREATE TABLE written_tasks_discussions
(
    id          INTEGER primary key unique,
    ts          timestamp not null,
    student_id  INTEGER   not null references users,
    problem_id  INTEGER   not null references problems,
    teacher_id  INTEGER references users,
    text        TEXT,
    attach_path TEXT,
    chat_id     INTEGER,
    tg_msg_id   INTEGER
);

CREATE TABLE written_tasks_queue
(
    id         INTEGER primary key unique,
    ts         timestamp not null,
    student_id INTEGER   not null references users,
    problem_id INTEGER   not null references problems,
    cur_status INTEGER   not null,
    teacher_ts TIMESTAMP,
    teacher_id TIMESTAMP references users,
    unique (student_id, problem_id)
);

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

CREATE TABLE "zoom_conversation"
(
    id                   INTEGER
        primary key,
    ts                   TEXT    not null,
    student_id           INTEGER not null
        references users,
    teacher_id           INTEGER not null
        references users,
    group_id             text
        references groups,
    lesson               INTEGER not null,
    check_time_spent_sec INTEGER
);

CREATE TABLE zoom_events
(
    id                 INTEGER primary key,
    event_ts           TIMESTAMP not null,
    event              TEXT      not null,
    zoom_user_name     TEXT,
    zoom_user_id       INTEGER,
    breakout_room_uuid TEXT,
    user_id            INTEGER references users
);

CREATE TABLE zoom_queue
(
    zoom_user_name TEXT      not null primary key unique,
    enter_ts       timestamp not null,
    status         INTEGER   not null
);

CREATE INDEX problems_by_synonyms
    on problems (synonyms);

CREATE INDEX results_by_student_problem
    on results (student_id, problem_id);

CREATE INDEX results_teacher_id_lesson_index
    on results (teacher_id, lesson)
    where res_type = 2;

CREATE INDEX waitlist_by_student
    on waitlist (student_id);

CREATE INDEX written_tasks_discussions_by_task
    on written_tasks_discussions (student_id, problem_id, ts);

CREATE INDEX written_tasks_queue_by_tst
    on written_tasks_queue (ts desc);

CREATE INDEX zoom_queue_by_ts
    on zoom_queue (enter_ts);

CREATE VIEW reaction_enum_view AS
SELECT *
FROM reaction_enum
         JOIN reaction_type_enum USING (reaction_type_id);

CREATE VIEW reaction_view AS
SELECT rct.ts,
       reaction_type,
       problem_id,
       result_id,
       stud.name || ' ' || stud.surname || ' ' || stud.middlename    AS student_name,
       reaction_enum.reaction,
       teach.name || ' ' || teach.surname || ' ' || teach.middlename AS teacher_name,
       coalesce(r.lesson, zc.lesson)                                 as lesson,
       coalesce(r.group_id, zc.group_id)                             as group_id,
       verdict,
       coalesce(r.check_time_spent_sec, zc.check_time_spent_sec)     as check_time_spent_sec
FROM reactions rct
         JOIN reaction_enum USING (reaction_id)
         JOIN reaction_type_enum USING (reaction_type_id)
         LEFT JOIN results r ON rct.result_id = r.id
         LEFT JOIN zoom_conversation zc on rct.zoom_conversation_id = zc.id
         LEFT JOIN users AS stud ON (stud.id = coalesce(r.student_id, zc.student_id))
         LEFT JOIN users AS teach ON (teach.id = coalesce(r.teacher_id, zc.teacher_id));
