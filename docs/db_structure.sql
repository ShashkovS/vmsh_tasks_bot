-- GENERATED FILE. DO NOT EDIT BY HAND.
-- Authoritative source: repository yoyo migrations plus schema inventory.
-- Schema-only: contains no product row values; DDL is migration-authored.
-- Reference only: apply migrations rather than using this as a bootstrap.
-- Product schema SHA-256: ccf2343a8406d220703b3e76c98346ea009bbac71c85ce89165a47f0d8e6659a

CREATE TABLE auth_accounts
(
    id                         integer primary key,
    public_id                  text    not null unique
        check (length(trim(public_id)) > 0),
    audience                   text    not null
        check (audience in ('student', 'family', 'staff')),
    username                   text    not null
        check (length(trim(username)) > 0),
    username_normalized        text    not null
        check (length(trim(username_normalized)) > 0),
    username_algorithm_version integer
        check (username_algorithm_version > 0),
    provisioning_source        text    not null
        check (length(trim(provisioning_source)) > 0),
    display_name               text,
    credential_kind            text    not null
        check (credential_kind in ('telegram_token', 'password')),
    credential_hash            text,
    linked_user_id             integer references users (id),
    status                     text    not null
        check (status in ('active', 'blocked', 'disabled', 'archived')),
    credential_version         integer not null default 1
        check (credential_version > 0),
    last_login_at              text,
    created_at                 text    not null,
    updated_at                 text    not null,
    unique (audience, username_normalized),
    check (credential_hash is null or length(trim(credential_hash)) > 0),
    check (status <> 'active' or credential_hash is not null),
    check (audience <> 'student' or username_algorithm_version is not null),
    check (
        (audience = 'student' and credential_kind = 'telegram_token' and linked_user_id is not null)
        or (audience = 'family' and credential_kind = 'password' and linked_user_id is null)
        or (audience = 'staff' and credential_kind = 'password' and linked_user_id is not null)
    ),
    check (
        audience <> 'family'
        or (display_name is not null and length(trim(display_name)) > 0)
    )
);

CREATE TABLE auth_events
(
    id            integer primary key,
    account_id    integer references auth_accounts (id),
    session_id    integer references auth_sessions (id),
    event_type    text not null
        check (length(trim(event_type)) > 0),
    occurred_at   text not null,
    request_id    text not null
        check (length(trim(request_id)) > 0),
    ip_prefix     text,
    metadata_json text not null default '{}'
        check (json_valid(metadata_json) = 1 and json_type(metadata_json) = 'object')
);

CREATE TABLE auth_sessions
(
    id                   integer primary key,
    public_id            text    not null unique
        check (length(trim(public_id)) > 0),
    account_id           integer not null references auth_accounts (id),
    audience             text    not null
        check (audience in ('student', 'family', 'staff')),
    refresh_secret_hash  text    not null unique
        check (
            length(refresh_secret_hash) = 64
            and refresh_secret_hash not glob '*[^0-9a-f]*'
        ),
    credential_version   integer not null
        check (credential_version > 0),
    version              integer not null default 1
        check (version > 0),
    created_at           text    not null,
    updated_at           text    not null,
    last_seen_at         text    not null,
    expires_at           text    not null,
    revoked_at           text,
    revoke_reason        text,
    device_label         text,
    user_agent_family    text,
    ip_prefix            text,
    check (expires_at > created_at),
    check (last_seen_at >= created_at),
    check (revoked_at is null or revoked_at >= created_at),
    check (
        (revoked_at is null and revoke_reason is null)
        or (
            revoked_at is not null
            and revoke_reason is not null
            and length(trim(revoke_reason)) > 0
        )
    )
);

CREATE TABLE auth_throttle_buckets
(
    audience        text    not null
        check (audience in ('student', 'family', 'staff')),
    bucket_kind     text    not null
        check (bucket_kind in ('normalized_login', 'account', 'ip')),
    bucket_key_hmac text    not null
        check (
            length(bucket_key_hmac) = 64
            and bucket_key_hmac not glob '*[^0-9a-f]*'
        ),
    key_version     integer not null default 1
        check (key_version > 0),
    failure_count   integer not null default 0
        check (failure_count >= 0),
    window_started_at text  not null,
    last_failed_at  text,
    locked_until    text,
    created_at      text    not null,
    updated_at      text    not null,
    version         integer not null default 1
        check (version > 0),
    primary key (audience, bucket_kind, bucket_key_hmac, key_version),
    check (last_failed_at is null or last_failed_at >= window_started_at),
    check (locked_until is null or last_failed_at is not null)
);

CREATE TABLE course_enrollment_events
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

CREATE TABLE course_enrollments
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

CREATE TABLE course_group_access
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

CREATE TABLE courses
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

CREATE TABLE family_student_links
(
    family_account_id integer not null references auth_accounts (id),
    student_user_id   integer not null references users (id),
    relationship_label text,
    is_primary        integer not null default 0
        check (is_primary in (0, 1)),
    created_at        text    not null,
    updated_at        text    not null,
    revoked_at        text,
    primary key (family_account_id, student_user_id),
    check (relationship_label is null or length(trim(relationship_label)) > 0),
    check (revoked_at is null or revoked_at >= created_at)
);

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
, public_id text, course_id integer references courses (id), status text not null default 'active'
    check (status in ('draft', 'active', 'archived')), color_key text, created_at text, updated_at text, version integer not null default 1
    check (version > 0));

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

CREATE TABLE seasons
(
    id                 integer primary key,
    public_id          text    not null unique
        check (length(trim(public_id)) > 0),
    code               text    not null unique
        check (length(trim(code)) > 0),
    title              text    not null
        check (length(trim(title)) > 0),
    starts_on          text    not null,
    ends_on            text    not null,
    timezone           text    not null default 'Europe/Moscow'
        check (length(trim(timezone)) > 0),
    session_expires_on text    not null,
    status             text    not null
        check (status in ('draft', 'active', 'archived')),
    created_at         text    not null,
    updated_at         text    not null,
    check (starts_on <= ends_on),
    check (session_expires_on >= starts_on)
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

CREATE TABLE staff_scopes
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

CREATE INDEX auth_accounts_audience_status_idx
    on auth_accounts (audience, status);

CREATE UNIQUE INDEX auth_accounts_linked_user_audience_uq
    on auth_accounts (linked_user_id, audience)
    where linked_user_id is not null;

CREATE INDEX auth_events_account_occurred_idx
    on auth_events (account_id, occurred_at, id);

CREATE INDEX auth_events_request_idx
    on auth_events (request_id);

CREATE INDEX auth_events_session_occurred_idx
    on auth_events (session_id, occurred_at, id);

CREATE INDEX auth_events_type_occurred_idx
    on auth_events (event_type, occurred_at, id);

CREATE INDEX auth_sessions_account_revoked_expires_idx
    on auth_sessions (account_id, revoked_at, expires_at);

CREATE INDEX auth_sessions_audience_revoked_expires_idx
    on auth_sessions (audience, revoked_at, expires_at);

CREATE INDEX auth_sessions_expires_idx
    on auth_sessions (expires_at);

CREATE INDEX auth_throttle_buckets_locked_idx
    on auth_throttle_buckets (locked_until)
    where locked_until is not null;

CREATE INDEX auth_throttle_buckets_updated_idx
    on auth_throttle_buckets (updated_at);

CREATE INDEX course_enrollment_events_timeline_idx
    on course_enrollment_events (enrollment_id, occurred_at, id);

CREATE INDEX course_enrollment_events_type_timeline_idx
    on course_enrollment_events (event_type, occurred_at, id);

CREATE INDEX course_enrollments_active_group_idx
    on course_enrollments (active_group_id, status, student_user_id);

CREATE INDEX course_enrollments_course_status_idx
    on course_enrollments (course_id, status, student_user_id);

CREATE INDEX course_group_access_enrollment_history_idx
    on course_group_access (enrollment_id, valid_from, valid_to);

CREATE INDEX course_group_access_group_active_idx
    on course_group_access (course_id, group_id, valid_to, enrollment_id);

CREATE UNIQUE INDEX course_group_access_one_active_uq
    on course_group_access (enrollment_id, group_id)
    where valid_to is null;

CREATE INDEX courses_season_status_order_idx
    on courses (season_id, status, sort_order, id);

CREATE INDEX family_student_links_student_revoked_idx
    on family_student_links (student_user_id, revoked_at);

CREATE UNIQUE INDEX groups_course_group_uq
    on groups (course_id, group_id);

CREATE UNIQUE INDEX groups_course_public_name_uq
    on groups (course_id, public_name)
    where course_id is not null;

CREATE UNIQUE INDEX groups_course_short_code_uq
    on groups (course_id, short_code)
    where course_id is not null;

CREATE UNIQUE INDEX groups_public_id_uq
    on groups (public_id)
    where public_id is not null;

CREATE INDEX problems_by_synonyms
    on problems (synonyms);

CREATE INDEX results_by_student_problem
    on results (student_id, problem_id);

CREATE INDEX results_teacher_id_lesson_index
    on results (teacher_id, lesson)
    where res_type = 2;

CREATE INDEX staff_scopes_lookup_idx
    on staff_scopes (staff_user_id, course_id, group_id, valid_to);

CREATE UNIQUE INDEX staff_scopes_one_active_course_role_uq
    on staff_scopes (staff_user_id, course_id, role)
    where group_id is null and valid_to is null;

CREATE UNIQUE INDEX staff_scopes_one_active_group_role_uq
    on staff_scopes (staff_user_id, course_id, group_id, role)
    where group_id is not null and valid_to is null;

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

CREATE TRIGGER auth_accounts_audience_update
before update of audience on auth_accounts
for each row
when new.audience <> old.audience and (
    exists (
        select 1 from auth_sessions where account_id = old.id
    )
    or exists (
        select 1 from family_student_links where family_account_id = old.id
    )
)
begin
    select raise(abort, 'account audience is immutable after links or sessions exist');
end;

CREATE TRIGGER auth_sessions_audience_insert
before insert on auth_sessions
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.account_id and audience = new.audience
)
begin
    select raise(abort, 'auth session audience does not match account');
end;

CREATE TRIGGER auth_sessions_audience_update
before update of account_id, audience on auth_sessions
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.account_id and audience = new.audience
)
begin
    select raise(abort, 'auth session audience does not match account');
end;

CREATE TRIGGER family_student_links_family_account_insert
before insert on family_student_links
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.family_account_id and audience = 'family'
)
begin
    select raise(abort, 'family_student_links requires a family account');
end;

CREATE TRIGGER family_student_links_family_account_update
before update of family_account_id on family_student_links
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.family_account_id and audience = 'family'
)
begin
    select raise(abort, 'family_student_links requires a family account');
end;
