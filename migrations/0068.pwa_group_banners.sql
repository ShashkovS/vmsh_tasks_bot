-- depends: 0067.pwa_news_mirror

create table group_banners
(
    id                       integer primary key,
    public_id text generated always as ('bn-' || id) virtual,
    group_id                 text    not null references groups (group_id),
    audience                 text    not null
        check (audience in ('student', 'family', 'both')),
    html_sanitized           text    not null,
    sanitizer_policy_version integer not null default 1,
    starts_at                text    not null,
    ends_at                  text    not null,
    priority                 integer not null default 0,
    dismissible              integer not null default 1
        check (dismissible in (0, 1)),
    status                   text    not null default 'active'
        check (status in ('active', 'cancelled')),
    created_by_user_id       integer not null references users (id),
    updated_by_user_id       integer not null references users (id),
    created_at               text    not null,
    updated_at               text    not null,
    cancelled_at             text,
    version                  integer not null default 1 check (version > 0),
    check (length(trim(public_id)) > 0),
    check (length(trim(html_sanitized)) > 0),
    check (sanitizer_policy_version = 1),
    check (ends_at > starts_at),
    check (
        (status = 'active' and cancelled_at is null)
        or (status = 'cancelled' and cancelled_at is not null)
    )
);

create index group_banners_window_idx
    on group_banners (group_id, status, starts_at, ends_at, priority desc, id);
