-- depends: 0070.pwa_oral_windows

alter table zoom_conversation add column pwa_idempotency_key text;

create unique index zoom_conversation_pwa_idempotency_uq
    on zoom_conversation (pwa_idempotency_key)
    where pwa_idempotency_key is not null;
