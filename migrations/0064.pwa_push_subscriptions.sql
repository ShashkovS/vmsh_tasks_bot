-- depends: 0063.pwa_notification_core

-- Phase 8C: browser-owned Web Push subscriptions.
create table push_subscriptions
(
    id              integer primary key,
    public_id text generated always as ('push-' || id) virtual,
    account_id      integer not null references auth_accounts (id),
    session_id      integer not null references auth_sessions (id),
    endpoint        text    not null unique,
    p256dh          text    not null,
    auth_secret     text    not null,
    expiration_time integer,
    user_agent      text,
    created_at      text    not null,
    updated_at      text    not null,
    check (length(trim(endpoint)) > 0),
    check (length(trim(p256dh)) > 0),
    check (length(trim(auth_secret)) > 0),
    check (expiration_time is null or expiration_time > 0)
);

create index push_subscriptions_account_idx
    on push_subscriptions (account_id, updated_at desc);
