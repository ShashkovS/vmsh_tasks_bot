-- Для key-value storage
create table IF NOT EXISTS kv
(
    key   text unique,
    value text
);

------------------------------------------
-- Студенты, учителя и т.п., и их активность
------------------------------------------

-- Пользователи: студенты, учителя, админы
create table IF NOT EXISTS users
(
    id         INTEGER primary key,
    chat_id    INTEGER unique,
    type       INTEGER not null,
    level      TEXT,
    name       TEXT    not null,
    surname    TEXT    not null,
    middlename TEXT,
    token      TEXT unique,
    online     INTEGER,
    grade      int,
    birthday   int
);

-- Силы студентов
create table IF NOT EXISTS student_strength
(
    student_id  integer not null primary key,
    simple_prob DOUBLE  not null,
    compl_prob  DOUBLE  not null
);


-- Факты логина и доп.атрибуты
create table IF NOT EXISTS signons
(
    ts         timestamp not null,
    user_id    INTEGER references users,
    chat_id    INTEGER   not null,
    first_name TEXT,
    last_name  TEXT,
    username   TEXT,
    token      text
);

-- Изменения уровня, режима и т.п.
create table IF NOT EXISTS user_changes_log
(
    ts          timestamp not null,
    user_id     INTEGER   not null references users,
    change_type text      not null,
    new_value   text      not null
);

-- Состояния пользователей
create table IF NOT EXISTS states
(
    user_id         INTEGER primary key unique references users,
    state           INTEGER,
    problem_id      INTEGER references problems,
    last_student_id INTEGER references users,
    last_teacher_id INTEGER references users,
    oral_problem_id INTEGER references users,
    info            blob default null
);

-- Последние списковые клавиатуры
create table IF NOT EXISTS last_keyboards
(
    user_id   INTEGER not null primary key references users,
    chat_id   INTEGER not null,
    tg_msg_id INTEGER not null
);


-- Лог отправленных сообщений
create table IF NOT EXISTS messages_log
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


------------------------------------------
-- Задачи, результаты проверки, письменная переписка
------------------------------------------

-- Задачи
create table IF NOT EXISTS problems
(
    id               INTEGER primary key,
    level            TEXT            not null,
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
    unique (level, lesson, prob, item)
);
create index IF NOT EXISTS problems_by_synonyms
    on problems (synonyms);

-- Сложности задач
create table IF NOT EXISTS problem_complexity
(
    synonyms   TEXT   not null primary key,
    for_weak   DOUBLE not null,
    for_strong DOUBLE not null
);

-- Уроки
create table IF NOT EXISTS lessons
(
    id     INTEGER primary key,
    level  TEXT    not null,
    lesson INTEGER not null,
    unique (lesson, level)
);


-- «Сеансы» устной сдачи
create table IF NOT EXISTS zoom_conversation
(
    id                   INTEGER primary key,
    ts                   TEXT    not null,
    student_id           INTEGER not null references users,
    teacher_id           INTEGER not null references users,
    level                TEXT    not null,
    lesson               INTEGER not null,
    check_time_spent_sec INTEGER
);

-- Результаты проверки
create table IF NOT EXISTS results
(
    id                   INTEGER primary key,
    student_id           INTEGER   not null references users,
    problem_id           INTEGER   not null references problems,
    level                TEXT      not null,
    lesson               INTEGER   not null,
    teacher_id           INTEGER references users,
    ts                   timestamp not null,
    verdict              integer   not null,
    answer               TEXT,
    res_type             integer,
    check_time_spent_sec int default null,
    zoom_conversation_id INT references zoom_conversation
);

create index IF NOT EXISTS results_by_student_problem
    on results (student_id, problem_id);

create index IF NOT EXISTS results_by_student_solved
    on results (student_id, level, lesson)
    where verdict > 0;


-- Переписка по письменным задачам
create table IF NOT EXISTS written_tasks_discussions
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
create index IF NOT EXISTS written_tasks_discussions_by_task
    on written_tasks_discussions (student_id, problem_id, ts);

-- Очередь письменных задач на проверку
create table IF NOT EXISTS written_tasks_queue
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
create index IF NOT EXISTS written_tasks_queue_by_tst
    on written_tasks_queue (ts desc);

-- Привязка медиа-групп к задачам для обработки сообщений-галерей
create table IF NOT EXISTS media_groups
(
    media_group_id INTEGER   not null primary key unique,
    problem_id     INTEGER   not null references problems,
    ts             timestamp not null
);


------------------------------------------
-- Реакции
------------------------------------------

-- Типы реакций ()
create table IF NOT EXISTS reaction_type_enum
(
    reaction_type_id INTEGER primary key,
    reaction_type    TEXT not null unique
);
delete
from reaction_type_enum
where 1 = 1;
INSERT INTO reaction_type_enum
VALUES (0, 'Письменно, ученик'),
       (100, 'Письменно, учитель'),
       (200, 'Устно, ученик'),
       (300, 'Устно, учитель');

-- Сами возможные реакции
create table IF NOT EXISTS reaction_enum
(
    reaction_id      INTEGER primary key,
    reaction         TEXT    not null,
    reaction_type_id INTEGER not null references reaction_type_enum
);
delete
from reaction_enum
where 1 = 1;
INSERT INTO reaction_enum
    -- реакция ученика на письменную сдачу
VALUES (0, '👌 Ок. Всё ясно.', 0),
       (1, '😕 Непонятно, что не так...', 0),
       (2, '🙋 Не могу согласиться с проверкой!', 0),

       -- реакция учителя на письменную сдачу
       (100, '🔥 Суперское решение.', 100),
       (101, '😕 Жуткая муть.', 100),
       (102, '😠 Решение, вероятно, списано.', 100),

       -- реакция ученика на устную сдачу
       (200, '👌 С устным приёмом всё ОК.', 200),
       (201, '😀 Сдавать понравилось!', 200),
       (202, '📡 Связь прервалась.', 200),
       (203, '😰 Сдавать не понравилось...', 200),
       (204, '⌛ Это старые плюсики поставили...', 200),

       -- реакция учителя на устную сдачу
       (300, '👍 Внятно, уверенно.', 300),
       (301, '👎 Мутно, много ошибок.', 300),
       (302, '😠 Решение, вероятно, несамостоятельно.', 300),
       (303, '📡 Технические проблемы.', 300)
;

DROP VIEW IF EXISTS reaction_enum_view;
CREATE VIEW reaction_enum_view AS
SELECT *
FROM reaction_enum
         JOIN reaction_type_enum USING (reaction_type_id);

-- Реакции на проверку (и студентов, и учителей)
create table IF NOT EXISTS reactions
(
    id                   INTEGER primary key,
    ts                   TEXT,
    result_id            INT references results,
    zoom_conversation_id INT references zoom_conversation,
    reaction_id          INT not null references reaction_enum,
    reaction_type_id     INT not null references reaction_type_enum
);

DROP VIEW IF EXISTS reaction_view;
CREATE VIEW reaction_view AS
SELECT rct.ts,
       reaction_type,
       problem_id,
       result_id,
       stud.name || ' ' || stud.surname || ' ' || stud.middlename    AS student_name,
       reaction_enum.reaction,
       teach.name || ' ' || teach.surname || ' ' || teach.middlename AS teacher_name,
       coalesce(r.lesson, zc.lesson)                                 as lesson,
       coalesce(r.level, zc.level)                                   as level,
       verdict,
       coalesce(r.check_time_spent_sec, zc.check_time_spent_sec)     as check_time_spent_sec
FROM reactions rct
         JOIN reaction_enum USING (reaction_id)
         JOIN reaction_type_enum USING (reaction_type_id)
         LEFT JOIN results r ON rct.result_id = r.id
         LEFT JOIN zoom_conversation zc on rct.zoom_conversation_id = zc.id
         LEFT JOIN users AS stud ON (stud.id = coalesce(r.student_id, zc.student_id))
         LEFT JOIN users AS teach ON (teach.id = coalesce(r.teacher_id, zc.teacher_id))
;


------------------------------------------
-- Для веб-приложений
------------------------------------------

create table IF NOT EXISTS webtokens
(
    user_id  INTEGER primary key unique references users,
    webtoken TEXT not null unique
);



------------------------------------------
-- Игра
------------------------------------------

-- Команда данного студента
create table IF NOT EXISTS game_students_commands
(
    id         INTEGER primary key,
    student_id INTEGER not null unique references users,
    command_id INTEGER not null,
    level      text    not null
);

-- Открытые клетки
create table IF NOT EXISTS game_map_opened_cells
(
    id         INTEGER primary key,
    command_id INTEGER not null,
    x          INTEGER not null,
    y          INTEGER not null,
    unique (command_id, x, y)
);

-- Открытые сундуки
create table IF NOT EXISTS game_map_chests
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

-- Установленные флаги
create table IF NOT EXISTS game_map_flags
(
    id         INTEGER primary key,
    student_id INTEGER not null references users,
    command_id INTEGER not null,
    x          INTEGER not null,
    y          INTEGER not null,
    unique (student_id, command_id)
);

-- Внутриигровые траты
create table IF NOT EXISTS game_payments
(
    id         INTEGER primary key,
    ts         timestamp not null,
    student_id INTEGER   not null references users,
    amount     INTEGER   not null,
    cell_id    INTEGER   not null references game_map_opened_cells
);



------------------------------------------
-- Интеграция с zoom'ом
------------------------------------------

create table IF NOT EXISTS zoom_events
(
    id                 INTEGER primary key,
    event_ts           TIMESTAMP not null,
    event              TEXT      not null,
    zoom_user_name     TEXT,
    zoom_user_id       INTEGER,
    breakout_room_uuid TEXT,
    user_id            INTEGER references users
);

create table IF NOT EXISTS zoom_queue
(
    zoom_user_name TEXT      not null primary key unique,
    enter_ts       timestamp not null,
    status         INTEGER   not null
);

create index IF NOT EXISTS zoom_queue_by_ts
    on zoom_queue (enter_ts);

create table IF NOT EXISTS waitlist
(
    id         INTEGER primary key unique,
    student_id INTEGER   not null unique references users,
    entered    timestamp not null,
    problem_id INTEGER   not null references problems
);

create index IF NOT EXISTS waitlist_by_student
    on waitlist (student_id);
