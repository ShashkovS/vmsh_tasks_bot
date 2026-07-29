-- depends: 0066.pwa_telegram_bindings

-- Phase 8G: immutable Telegram/local news revisions and current PWA visibility.
create table news_posts
(
    id                       integer primary key,
    public_id                text    not null unique,
    source_type              text    not null check (source_type in ('telegram', 'local')),
    source_binding_public_id text,
    owner_course_id          integer references courses (id),
    owner_group_id           text references groups (group_id),
    source_chat_id           integer,
    source_message_id        integer,
    source_media_group_id    text,
    published_at             text    not null,
    last_source_edited_at    text,
    source_deleted_at        text,
    created_at               text    not null,
    updated_at               text    not null,
    version                  integer not null default 1 check (version > 0),
    check (
        (source_type = 'telegram'
            and source_binding_public_id is not null
            and source_chat_id is not null
            and source_message_id is not null)
        or
        (source_type = 'local'
            and source_binding_public_id is null
            and source_chat_id is null
            and source_message_id is null
            and source_media_group_id is null)
    ),
    check (
        (owner_course_id is not null and owner_group_id is null)
        or (owner_course_id is null and owner_group_id is not null)
    )
);

create unique index news_posts_telegram_message_uq
    on news_posts (source_chat_id, source_message_id)
    where source_type = 'telegram' and source_media_group_id is null;

create unique index news_posts_telegram_album_uq
    on news_posts (source_chat_id, source_media_group_id)
    where source_type = 'telegram' and source_media_group_id is not null;

create index news_posts_course_feed_idx
    on news_posts (owner_course_id, published_at desc, id desc);

create index news_posts_group_feed_idx
    on news_posts (owner_group_id, published_at desc, id desc);

create table news_revisions
(
    id                  integer primary key,
    post_id             integer not null references news_posts (id) on delete cascade,
    revision_number     integer not null check (revision_number > 0),
    source_hash         text    not null check (length(source_hash) = 64),
    source_edited_at    text,
    text_plain          text    not null,
    content_json        text    not null,
    source_payload_json text    not null,
    created_at          text    not null,
    unique (post_id, revision_number),
    unique (post_id, source_hash)
);

create index news_revisions_latest_idx
    on news_revisions (post_id, revision_number desc);

create table news_media
(
    id                integer primary key,
    revision_id       integer not null references news_revisions (id) on delete cascade,
    ordinal           integer not null check (ordinal >= 0),
    media_kind        text    not null check (media_kind in ('image', 'video', 'audio', 'document')),
    source_message_id integer,
    source_file_id    text,
    storage_key       text,
    public_url        text,
    mime_type         text,
    width             integer check (width is null or width > 0),
    height            integer check (height is null or height > 0),
    storage_status    text    not null check (storage_status in ('pending', 'stored', 'failed')),
    created_at        text    not null,
    updated_at        text    not null,
    unique (revision_id, ordinal)
);

create table news_visibility
(
    post_id            integer primary key references news_posts (id) on delete cascade,
    state              text    not null check (state in ('visible', 'manual_hidden', 'source_deleted')),
    moderation_reason  text,
    updated_by_user_id integer references users (id),
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0)
);

create index news_visibility_state_idx on news_visibility (state, post_id);

create table news_ingest_diagnostics
(
    id                integer primary key,
    source_chat_id    integer,
    source_message_id integer,
    code              text not null,
    detail            text,
    created_at        text not null
);

create index news_ingest_diagnostics_created_idx
    on news_ingest_diagnostics (created_at desc, id desc);
