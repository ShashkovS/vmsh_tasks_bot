-- depends: 0069.pwa_course_notification_preferences

create table oral_windows
(
    id                 integer primary key,
    public_id          text    not null unique,
    group_lesson_id    integer not null references group_lessons (id),
    sequence_number    integer not null check (sequence_number > 0),
    opens_at           text    not null,
    closes_at          text    not null,
    join_label         text    not null,
    join_url           text    not null,
    join_code          text,
    status             text    not null check (status in ('active', 'cancelled')),
    created_by_user_id integer not null references users (id),
    updated_by_user_id integer not null references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    unique (group_lesson_id, sequence_number),
    check (opens_at < closes_at),
    check (length(trim(join_label)) > 0),
    check (length(trim(join_url)) > 0),
    check (join_code is null or length(trim(join_code)) > 0)
);

create index oral_windows_group_time_idx
    on oral_windows (group_lesson_id, opens_at, sequence_number);
