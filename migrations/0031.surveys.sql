create table IF NOT EXISTS surveys
(
    id            INTEGER primary key,
    survey_type   CHAR(1)   not null,
    for_user_type int       not null,
    is_active     BOOL      not null,
    question      TEXT      not null,
    ts            timestamp not null
);
create index if not exists surveys_by_user_type
on surveys (for_user_type, id) where is_active;

create table IF NOT EXISTS survey_choices
(
    id        INTEGER primary key,
    survey_id INTEGER not null references surveys,
    text      TEXT    not null
);

create table IF NOT EXISTS survey_results
(
    id            INTEGER primary key,
    survey_id     INTEGER   not null references surveys,
    user_id       INTEGER   not null references users,
    selection_ids TEXT      not null,
    ts            timestamp not null,
    unique (survey_id, user_id)
);
