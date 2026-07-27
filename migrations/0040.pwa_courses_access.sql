-- depends: 0039.pwa_auth_accounts_sessions

-- Phase 1 multi-course schema. Authoritative contract:
-- vmshpwa/docs/courses-groups-and-lessons.md.
create table courses
(
    id           integer primary key,
    public_id    text    not null unique
        check (length(trim(public_id)) > 0),
    season_id    integer not null references seasons (id),
    code         text    not null
        check (length(trim(code)) > 0),
    name         text    not null
        check (length(trim(name)) > 0),
    subject_code text    not null
        check (length(trim(subject_code)) > 0),
    status       text    not null
        check (status in ('draft', 'active', 'archived')),
    sort_order   integer not null default 0,
    accent_key   text    not null
        check (length(trim(accent_key)) > 0),
    created_at   text    not null,
    updated_at   text    not null,
    created_by   integer references users (id),
    updated_by   integer references users (id),
    version      integer not null default 1
        check (version > 0),
    unique (season_id, code)
);

create index courses_season_status_order_idx
    on courses (season_id, status, sort_order, id);

-- Transitional group ownership for Phase 1. Existing rows keep course_id NULL
-- until the controlled backfill; Phase 11 closes the remaining nullability.
alter table groups add column public_id text;
alter table groups add column course_id integer references courses (id);
alter table groups add column status text not null default 'active'
    check (status in ('draft', 'active', 'archived'));
alter table groups add column color_key text;
alter table groups add column created_at text;
alter table groups add column updated_at text;
alter table groups add column version integer not null default 1
    check (version > 0);

update groups
set public_id = 'legacy-' || lower(hex(cast(group_id as blob)))
where public_id is null;

update groups
set status = case when is_active = 1 then 'active' else 'archived' end;

create unique index groups_public_id_uq
    on groups (public_id)
    where public_id is not null;

-- This non-partial parent key is required by SQLite composite foreign keys.
create unique index groups_course_group_uq
    on groups (course_id, group_id);

create unique index groups_course_short_code_uq
    on groups (course_id, short_code)
    where course_id is not null;

create unique index groups_course_public_name_uq
    on groups (course_id, public_name)
    where course_id is not null;

create table course_enrollments
(
    id                 integer primary key,
    public_id          text    not null unique
        check (length(trim(public_id)) > 0),
    student_user_id    integer not null references users (id),
    course_id          integer not null references courses (id),
    active_group_id    text    not null,
    attendance_mode    text    not null
        check (attendance_mode in ('online', 'in_person')),
    status             text    not null
        check (status in ('active', 'paused', 'archived')),
    created_at         text    not null,
    updated_at         text    not null,
    created_by         integer references users (id),
    updated_by         integer references users (id),
    version            integer not null default 1
        check (version > 0),
    unique (student_user_id, course_id),
    unique (id, course_id),
    foreign key (course_id, active_group_id)
        references groups (course_id, group_id)
);

create index course_enrollments_course_status_idx
    on course_enrollments (course_id, status, student_user_id);

create index course_enrollments_active_group_idx
    on course_enrollments (active_group_id, status, student_user_id);

create table course_group_access
(
    enrollment_id integer not null,
    course_id      integer not null references courses (id),
    group_id       text    not null,
    valid_from     text    not null,
    valid_to       text,
    granted_by     integer references users (id),
    revoked_by     integer references users (id),
    reason         text,
    created_at     text    not null,
    updated_at     text    not null,
    version        integer not null default 1
        check (version > 0),
    primary key (enrollment_id, group_id, valid_from),
    check (valid_to is null or valid_to > valid_from),
    check (reason is null or length(trim(reason)) > 0),
    check (
        (valid_to is null and revoked_by is null)
        or valid_to is not null
    ),
    foreign key (enrollment_id, course_id)
        references course_enrollments (id, course_id),
    foreign key (course_id, group_id)
        references groups (course_id, group_id)
);

create unique index course_group_access_one_active_uq
    on course_group_access (enrollment_id, group_id)
    where valid_to is null;

create index course_group_access_group_active_idx
    on course_group_access (course_id, group_id, valid_to, enrollment_id);

create index course_group_access_enrollment_history_idx
    on course_group_access (enrollment_id, valid_from, valid_to);

create table course_enrollment_events
(
    id                       integer primary key,
    public_id                text    not null unique
        check (length(trim(public_id)) > 0),
    enrollment_id            integer not null,
    course_id                integer not null references courses (id),
    event_type               text    not null
        check (event_type in (
            'created',
            'active_group_changed',
            'attendance_mode_changed',
            'status_changed'
        )),
    previous_group_id        text,
    new_group_id             text,
    previous_attendance_mode text
        check (previous_attendance_mode in ('online', 'in_person')),
    new_attendance_mode      text
        check (new_attendance_mode in ('online', 'in_person')),
    previous_status          text
        check (previous_status in ('active', 'paused', 'archived')),
    new_status               text
        check (new_status in ('active', 'paused', 'archived')),
    actor_user_id            integer references users (id),
    source                   text    not null
        check (source in ('pwa', 'telegram', 'staff', 'import', 'system')),
    request_id               text    not null
        check (length(trim(request_id)) > 0),
    occurred_at              text    not null,
    created_at               text    not null,
    unique (enrollment_id, request_id),
    check (
        (
            event_type = 'created'
            and previous_group_id is null
            and new_group_id is not null
            and previous_attendance_mode is null
            and new_attendance_mode is not null
            and previous_status is null
            and new_status is not null
        )
        or (
            event_type = 'active_group_changed'
            and previous_group_id is not null
            and new_group_id is not null
            and previous_group_id <> new_group_id
            and previous_attendance_mode is null
            and new_attendance_mode is null
            and previous_status is null
            and new_status is null
        )
        or (
            event_type = 'attendance_mode_changed'
            and previous_group_id is null
            and new_group_id is null
            and previous_attendance_mode is not null
            and new_attendance_mode is not null
            and previous_attendance_mode <> new_attendance_mode
            and previous_status is null
            and new_status is null
        )
        or (
            event_type = 'status_changed'
            and previous_group_id is null
            and new_group_id is null
            and previous_attendance_mode is null
            and new_attendance_mode is null
            and previous_status is not null
            and new_status is not null
            and previous_status <> new_status
        )
    ),
    foreign key (enrollment_id, course_id)
        references course_enrollments (id, course_id),
    foreign key (course_id, previous_group_id)
        references groups (course_id, group_id),
    foreign key (course_id, new_group_id)
        references groups (course_id, group_id)
);

create index course_enrollment_events_timeline_idx
    on course_enrollment_events (enrollment_id, occurred_at, id);

create index course_enrollment_events_type_timeline_idx
    on course_enrollment_events (event_type, occurred_at, id);

create table staff_scopes
(
    id            integer primary key,
    staff_user_id integer not null references users (id),
    course_id     integer not null references courses (id),
    group_id      text,
    role          text    not null
        check (role in ('teacher', 'admin')),
    valid_from    text    not null,
    valid_to      text,
    granted_by    integer references users (id),
    revoked_by    integer references users (id),
    reason        text,
    created_at    text    not null,
    updated_at    text    not null,
    version       integer not null default 1
        check (version > 0),
    check (valid_to is null or valid_to > valid_from),
    check (reason is null or length(trim(reason)) > 0),
    check (
        (valid_to is null and revoked_by is null)
        or valid_to is not null
    ),
    foreign key (course_id, group_id)
        references groups (course_id, group_id)
);

create unique index staff_scopes_one_active_course_role_uq
    on staff_scopes (staff_user_id, course_id, role)
    where group_id is null and valid_to is null;

create unique index staff_scopes_one_active_group_role_uq
    on staff_scopes (staff_user_id, course_id, group_id, role)
    where group_id is not null and valid_to is null;

create index staff_scopes_lookup_idx
    on staff_scopes (staff_user_id, course_id, group_id, valid_to);
