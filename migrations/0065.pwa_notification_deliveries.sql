-- depends: 0064.pwa_push_subscriptions

-- Phase 8E: durable Web Push attempts; this table is the concrete outbox.
create table notification_deliveries
(
    id                     integer primary key,
    public_id text generated always as ('nd-' || id) virtual,
    event_id               integer not null references notification_events (id),
    subscription_id        integer references push_subscriptions (id) on delete set null,
    state                  text    not null
        check (state in ('pending', 'sending', 'retry', 'sent', 'failed', 'suppressed')),
    attempt_count          integer not null default 0 check (attempt_count >= 0),
    next_attempt_at        text    not null,
    claim_token            text,
    claim_until            text,
    delivered_at           text,
    last_error_code        text,
    created_at             text    not null,
    updated_at             text    not null,
    unique (event_id, subscription_id),
    check (
        (state = 'sending' and claim_token is not null and claim_until is not null)
        or (state <> 'sending' and claim_token is null and claim_until is null)
    ),
    check (
        (state = 'sent' and delivered_at is not null)
        or (state <> 'sent' and delivered_at is null)
    )
);

create index notification_deliveries_due_idx
    on notification_deliveries (state, next_attempt_at, id);
