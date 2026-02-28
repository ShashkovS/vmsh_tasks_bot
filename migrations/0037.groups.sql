create table IF NOT EXISTS groups
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

alter table users
    add column group_id text;

alter table users
    add column allowed_groups text;

alter table problems
    add column group_id text;

alter table lessons
    add column group_id text;

alter table results
    add column group_id text;

alter table zoom_conversation
    add column group_id text;

alter table game_students_commands
    add column group_id text;

insert or ignore into groups (group_id,
                              short_code,
                              broadcast_code,
                              tg_command,
                              public_name,
                              conditions_url,
                              tasks_header_template,
                              switch_message,
                              sort_order,
                              is_active,
                              is_default,
                              allow_self_switch,
                              is_system,
                              score_weight)
values
--     (
--         'testing',
--         'т',
--         'all_testing',
--         '/level_testing',
--         'Тестирование',
--         '',
--         '❓ <b>Нажимайте на задачу, чтобы сдать её</b>
-- {student.name} {student.surname}
-- уровень «{group.public_name}», режим {mode_hint}
-- <a href="{group.conditions_url}">условия</a>, <a href="https://t.me/vmsh_179_5_7_2025">канал кружка</a>',
--         'Вы переведены в тестируемых',
--         0,
--         1,
--         0,
--         0,
--         0,
--         1.0
--     ),
('novice',
 'н',
 'all_novice',
 '/level_novice',
 'Начинающие',
 'https://shashkovs.ru/vmsh/2025/n/',
 '❓ <b>Нажимайте на задачу, чтобы сдать её</b>
{student.name} {student.surname}
уровень «{group.public_name}», режим {mode_hint}
<a href="{group.conditions_url}">условия</a>, <a href="https://t.me/vmsh_179_5_7_2025">канал кружка</a>',
 'Вы переведены в группу начинающих. Успехов в занятиях! Вопросы можно задавать в группе @vmsh_179_5_7_2025_chat.',
 10,
 1,
 1,
 1,
 0,
 1.0),
('pro',
 'п',
 'all_pro',
 '/level_pro',
 'Продолжающие',
 'https://shashkovs.ru/vmsh/2025/p/',
 '❓ <b>Нажимайте на задачу, чтобы сдать её</b>
{student.name} {student.surname}
уровень «{group.public_name}», режим {mode_hint}
<a href="{group.conditions_url}">условия</a>, <a href="https://t.me/vmsh_179_5_7_2025">канал кружка</a>',
 'Вы переведены в группу продолжающих. Следите за сложностью, если не получается больше половины задач, то лучше перейти в группу «начинающих». Это будет комфортнее и полезнее!',
 20,
 1,
 0,
 1,
 0,
 1.0),
('expert',
 'э',
 'all_expert',
 '/level_expert',
 'Эксперты',
 'https://shashkovs.ru/vmsh/2025/x/',
 '❓ <b>Нажимайте на задачу, чтобы сдать её</b>
{student.name} {student.surname}
уровень «{group.public_name}», режим {mode_hint}
<a href="{group.conditions_url}">условия</a>, <a href="https://t.me/vmsh_179_5_7_2025">канал кружка</a>',
 'Вы переведены в группу экспертов. Здесь будут сложные задачи, не переборщите со сложностью :) Успехов!',
 30,
 1,
 0,
 1,
 0,
 1.0),
-- ('math_club',
--  'm',
--  'all_prep',
--  '/ss',
--  'MathClub',
--  '',
--  '❓ <b>Нажимайте на задачу, чтобы сдать её</b>
-- {student.name} {student.surname}
-- уровень «{group.public_name}», режим {mode_hint}
-- <a href="{group.conditions_url}">условия</a>, <a href="https://t.me/vmsh_179_5_7_2025">канал кружка</a>',
--  'you_are_club_student_now',
--  40,
--  1,
--  0,
--  0,
--  0,
--  1.0),
--     (
--         'gr8',
--         'В',
--         'all_gr8',
--         null,
--         '8 класс',
--         '',
--         '❓ <b>Нажимайте на задачу, чтобы сдать её</b>
-- {student.name} {student.surname}
-- уровень «{group.public_name}», режим {mode_hint}
-- <a href="{group.conditions_url}">условия</a>, <a href="https://t.me/vmsh_179_5_7_2025">канал кружка</a>',
--         'Вы переведены в группу 8 класса. Здесь будут сложные задачи, не переборщите со сложностью :) Успехов!',
--         50,
--         1,
--         0,
--         0,
--         0,
--         1.0
--     ),
('no_level',
 '@',
 'all_nolevel',
 null,
 'Без уровня',
 'https://shashkovs.ru/vmsh/2025/n/',
 '❓ <b>У вас нет доступа к задачам кружка</b>',
 '',
 100,
 0,
 0,
 0,
 1,
 1.0);

update users
set group_id = case level
                   when 'н' then 'novice'
                   when 'п' then 'pro'
                   when 'э' then 'expert'
                   when 'т' then 'testing'
                   when 'm' then 'math_club'
                   when 'В' then 'gr8'
                   when '@' then 'no_level'
                   else 'novice'
    end;

update problems
set group_id = case level
                   when 'н' then 'novice'
                   when 'п' then 'pro'
                   when 'э' then 'expert'
                   when 'т' then 'testing'
                   when 'm' then 'math_club'
                   when 'В' then 'gr8'
                   when '@' then 'no_level'
                   else 'novice'
    end;

update lessons
set group_id = case level
                   when 'н' then 'novice'
                   when 'п' then 'pro'
                   when 'э' then 'expert'
                   when 'т' then 'testing'
                   when 'm' then 'math_club'
                   when 'В' then 'gr8'
                   when '@' then 'no_level'
                   else 'novice'
    end;

update results
set group_id = case level
                   when 'н' then 'novice'
                   when 'п' then 'pro'
                   when 'э' then 'expert'
                   when 'т' then 'testing'
                   when 'm' then 'math_club'
                   when 'В' then 'gr8'
                   when '@' then 'no_level'
                   else 'novice'
    end;

update zoom_conversation
set group_id = case level
                   when 'н' then 'novice'
                   when 'п' then 'pro'
                   when 'э' then 'expert'
                   when 'т' then 'testing'
                   when 'm' then 'math_club'
                   when 'В' then 'gr8'
                   when '@' then 'no_level'
                   else 'novice'
    end;

update game_students_commands
set group_id = case level
                   when 'н' then 'novice'
                   when 'п' then 'pro'
                   when 'э' then 'expert'
                   when 'т' then 'testing'
                   when 'm' then 'math_club'
                   when 'В' then 'gr8'
                   when '@' then 'no_level'
                   else 'novice'
    end;

update users
set allowed_groups = ';novice;pro;expert;'
where type = 1;

update users
set allowed_groups = ';novice;pro;expert;'
where type is null
   or type != 1;

create index IF NOT EXISTS users_by_group_id
    on users (group_id);

create unique index IF NOT EXISTS problems_by_group_key
    on problems (group_id, lesson, prob, item);

create unique index IF NOT EXISTS lessons_by_lesson_group
    on lessons (lesson, group_id);


-- =========

create table game_students_commands_dg_tmp
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

insert into game_students_commands_dg_tmp(id, student_id, command_id, group_id)
select id, student_id, command_id, group_id
from game_students_commands;

drop table game_students_commands;

alter table game_students_commands_dg_tmp
    rename to game_students_commands;



create table lessons_dg_tmp
(
    id       INTEGER
        primary key,
    group_id text
        references groups,
    lesson   INTEGER not null,
    unique (lesson, group_id)
);

insert into lessons_dg_tmp(id, lesson, group_id)
select id, lesson, group_id
from lessons;

drop table lessons;

alter table lessons_dg_tmp
    rename to lessons;



create table problems_dg_tmp
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

insert into problems_dg_tmp(id, lesson, prob, item, title, prob_text, prob_type, ans_type, ans_validation,
                            validation_error, cor_ans, cor_ans_checker, wrong_ans, congrat, synonyms, group_id)
select id,
       lesson,
       prob,
       item,
       title,
       prob_text,
       prob_type,
       ans_type,
       ans_validation,
       validation_error,
       cor_ans,
       cor_ans_checker,
       wrong_ans,
       congrat,
       synonyms,
       group_id
from problems;

drop table problems;

alter table problems_dg_tmp
    rename to problems;

create index problems_by_synonyms
    on problems (synonyms);



create table results_dg_tmp
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

insert into results_dg_tmp(id, student_id, problem_id, lesson, teacher_id, ts, verdict, answer, res_type,
                           check_time_spent_sec, zoom_conversation_id, group_id)
select id,
       student_id,
       problem_id,
       lesson,
       teacher_id,
       ts,
       verdict,
       answer,
       res_type,
       check_time_spent_sec,
       zoom_conversation_id,
       group_id
from results;

DROP VIEW IF EXISTS reaction_view;

drop table results;

alter table results_dg_tmp
    rename to results;

create index results_by_student_problem
    on results (student_id, problem_id);

create index results_teacher_id_lesson_index
    on results (teacher_id, lesson)
    where res_type = 2;




create table users_dg_tmp
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

insert into users_dg_tmp(id, chat_id, type, name, surname, middlename, token, online, grade, birthday, group_id,
                         allowed_groups)
select id,
       chat_id,
       type,
       name,
       surname,
       middlename,
       token,
       online,
       grade,
       birthday,
       group_id,
       allowed_groups
from users;


drop view if exists temp_zoom_teacher_work;

drop table users;

alter table users_dg_tmp
    rename to users;




create table zoom_conversation_dg_tmp
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

insert into zoom_conversation_dg_tmp(id, ts, student_id, teacher_id, lesson, check_time_spent_sec, group_id)
select id, ts, student_id, teacher_id, lesson, check_time_spent_sec, group_id
from zoom_conversation;

drop table zoom_conversation;

alter table zoom_conversation_dg_tmp
    rename to zoom_conversation;


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
         LEFT JOIN users AS teach ON (teach.id = coalesce(r.teacher_id, zc.teacher_id))
;
