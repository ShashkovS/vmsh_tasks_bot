-- depends: 0062.pwa_classroom_delivery_retries

-- Phase 8A: account-scoped in-app events and notification preferences.
create table notification_preferences
(
    account_id        integer not null references auth_accounts (id),
    category          text    not null,
    in_app_enabled    integer not null check (in_app_enabled in (0, 1)),
    push_enabled      integer not null check (push_enabled in (0, 1)),
    sound_enabled     integer not null check (sound_enabled in (0, 1)),
    quiet_starts_local text   not null,
    quiet_ends_local   text   not null,
    timezone          text    not null,
    updated_at        text    not null,
    primary key (account_id, category),
    check (length(trim(category)) > 0),
    check (length(quiet_starts_local) = 5),
    check (length(quiet_ends_local) = 5),
    check (length(trim(timezone)) > 0)
);

create table notification_events
(
    id                 integer primary key,
    public_id text generated always as ('n-' || id) virtual,
    account_id         integer not null references auth_accounts (id),
    category           text    not null,
    dedupe_key         text    not null,
    route              text    not null,
    payload_json       text    not null
        check (json_valid(payload_json) = 1 and json_type(payload_json) = 'object'),
    occurred_at        text    not null,
    deliver_after      text    not null,
    read_at            text,
    read_by_session_id integer references auth_sessions (id),
    created_at         text    not null,
    unique (account_id, category, dedupe_key),
    check (length(trim(category)) > 0),
    check (length(trim(dedupe_key)) > 0),
    check (substr(route, 1, 1) = '/'),
    check (deliver_after >= occurred_at),
    check (read_at is null or read_at >= occurred_at),
    check (
        (read_at is null and read_by_session_id is null)
        or read_at is not null
    )
);

create index notification_events_account_unread_idx
    on notification_events (account_id, read_at, occurred_at desc, id desc);
