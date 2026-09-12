-- depends: 0072.pwa_course_analytics

create table achievement_definitions
(
    id           integer primary key,
    code         text    not null unique,
    rule_version integer not null check (rule_version > 0),
    is_active    integer not null default 1 check (is_active in (0, 1)),
    created_at   text    not null,
    updated_at   text    not null
);

insert into achievement_definitions
    (code, rule_version, is_active, created_at, updated_at)
values
    ('first_submission', 1, 1, '2026-07-29T00:00:00Z', '2026-07-29T00:00:00Z'),
    ('first_accepted', 1, 1, '2026-07-29T00:00:00Z', '2026-07-29T00:00:00Z'),
    ('first_written_submission', 1, 1, '2026-07-29T00:00:00Z', '2026-07-29T00:00:00Z');

create table user_achievements
(
    id            integer primary key,
    definition_id integer not null references achievement_definitions (id),
    user_id       integer not null references users (id),
    course_id     integer not null references courses (id),
    earned_at     text    not null,
    evidence_json text    not null default '{}'
        check (json_valid(evidence_json) = 1 and json_type(evidence_json) = 'object'),
    notified_at   text,
    unique (definition_id, user_id, course_id)
);

create index user_achievements_user_course_idx
    on user_achievements (user_id, course_id, earned_at, id);
