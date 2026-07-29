-- depends: 0065.pwa_notification_deliveries

-- Phase 8F: course/group destinations. Bot credentials stay in runtime config.
create table telegram_bindings
(
    id                  integer primary key,
    public_id           text    not null unique,
    owner_type          text    not null check (owner_type in ('course', 'group')),
    owner_course_id     integer references courses (id),
    owner_group_id      text references groups (group_id),
    purpose             text    not null
        check (purpose in ('news_source', 'materials_target')),
    chat_id             integer not null check (chat_id <> 0),
    message_thread_id   integer check (message_thread_id is null or message_thread_id > 0),
    title_cached        text check (
        title_cached is null
        or (title_cached = trim(title_cached) and length(title_cached) between 1 and 200)
    ),
    status              text    not null check (status in ('draft', 'verified', 'disabled')),
    verified_at         text,
    created_by_user_id  integer not null references users (id),
    updated_by_user_id  integer not null references users (id),
    created_at          text    not null,
    updated_at          text    not null,
    version             integer not null default 1 check (version > 0),
    check (
        (owner_type = 'course' and owner_course_id is not null and owner_group_id is null)
        or (owner_type = 'group' and owner_course_id is null and owner_group_id is not null)
    ),
    check (
        (status = 'verified' and verified_at is not null)
        or status <> 'verified'
    )
);

create unique index telegram_bindings_owner_destination_uq
    on telegram_bindings (
        owner_type,
        ifnull(owner_course_id, -1),
        ifnull(owner_group_id, ''),
        purpose,
        chat_id,
        ifnull(message_thread_id, -1)
    );

create index telegram_bindings_course_idx
    on telegram_bindings (owner_course_id, purpose, status, id);

create index telegram_bindings_group_idx
    on telegram_bindings (owner_group_id, purpose, status, id);
