drop index if exists surveys_by_user_type;

create table IF NOT EXISTS surveys_dg_tmp
(
    id          INTEGER primary key,
    survey_type CHAR(1)   not null,
    is_active   BOOL      not null,
    question    TEXT      not null,
    ts          timestamp not null
);

insert into surveys_dg_tmp(id, survey_type, is_active, question, ts)
select id, survey_type, is_active, question, ts
from surveys;

drop table surveys;

alter table surveys_dg_tmp
    rename to surveys;

create table IF NOT EXISTS survey_assigns
(
    id        INTEGER primary key,
    user_id   INTEGER not null references users,
    survey_id INTEGER not null references surveys,
    unique (user_id)
);
