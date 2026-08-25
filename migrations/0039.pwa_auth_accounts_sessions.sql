-- depends: 0030.initial_merged 0031.check_stat 0032.sos_questions 0033.verdicts 0034.surveys 0035.new_reation 0036.settings_and_texts_from_sheet 0037.groups 0038.kv_logins

-- Phase 1 identity/session schema. Authoritative contract:
-- vmshpwa/dev/development-plan/05-phase-1-auth.md and ADR 0003.
-- Browser contracts expose a virtual compact ID derived from the legacy
-- integer primary key. See vmshpwa/docs/compact-identifiers.md.
alter table users add column public_id text
    generated always as ('u-' || id) virtual;

create table seasons
(
    id                 integer primary key,
    public_id text generated always as ('s-' || id) virtual,
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

create table auth_accounts
(
    id                         integer primary key,
    public_id text generated always as ('a-' || id) virtual,
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

create unique index auth_accounts_linked_user_audience_uq
    on auth_accounts (linked_user_id, audience)
    where linked_user_id is not null;

create index auth_accounts_audience_status_idx
    on auth_accounts (audience, status);

create table family_student_links
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

create index family_student_links_student_revoked_idx
    on family_student_links (student_user_id, revoked_at);

create table auth_sessions
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) = 32
            and public_id not glob '*[^0-9a-f]*'
        ),
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

create index auth_sessions_account_revoked_expires_idx
    on auth_sessions (account_id, revoked_at, expires_at);

create index auth_sessions_expires_idx
    on auth_sessions (expires_at);

create index auth_sessions_audience_revoked_expires_idx
    on auth_sessions (audience, revoked_at, expires_at);

-- A mismatch against only the current digest is not proof of replay. Keep the
-- consumed HMACs until the session expires so a previously valid refresh
-- secret can be distinguished from an arbitrary invalid value without storing
-- raw secrets. Expired rows are removed by auth maintenance; deleting a
-- session also removes its bounded history.
create table auth_refresh_consumed_secrets
(
    session_id          integer not null
        references auth_sessions (id) on delete cascade,
    refresh_secret_hash text    not null
        check (
            length(refresh_secret_hash) = 64
            and refresh_secret_hash not glob '*[^0-9a-f]*'
        ),
    consumed_at         text    not null,
    expires_at          text    not null,
    primary key (session_id, refresh_secret_hash),
    check (expires_at >= consumed_at)
);

create index auth_refresh_consumed_secrets_expires_idx
    on auth_refresh_consumed_secrets (expires_at);

create table auth_events
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

create index auth_events_account_occurred_idx
    on auth_events (account_id, occurred_at, id);

create index auth_events_session_occurred_idx
    on auth_events (session_id, occurred_at, id);

create index auth_events_type_occurred_idx
    on auth_events (event_type, occurred_at, id);

create index auth_events_request_idx
    on auth_events (request_id);

-- Bucket keys are HMAC-SHA256 digests only. Normalized usernames, account IDs,
-- IPs, tokens, and passwords must never be stored in this shared-worker table.
create table auth_throttle_buckets
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

create index auth_throttle_buckets_locked_idx
    on auth_throttle_buckets (locked_until)
    where locked_until is not null;

create index auth_throttle_buckets_updated_idx
    on auth_throttle_buckets (updated_at);

create trigger family_student_links_family_account_insert
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

create trigger family_student_links_family_account_update
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

create trigger auth_sessions_audience_insert
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

create trigger auth_sessions_audience_update
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

create trigger auth_accounts_audience_update
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

-- A web credential belongs to exactly one legacy identity. Corrections create a
-- replacement account instead of silently transferring an already verified
-- credential (and possibly live sessions) to another person.
create trigger auth_accounts_linked_user_immutable
before update of linked_user_id on auth_accounts
for each row
when new.linked_user_id is not old.linked_user_id
begin
    select raise(abort, 'auth account linked user is immutable');
end;
