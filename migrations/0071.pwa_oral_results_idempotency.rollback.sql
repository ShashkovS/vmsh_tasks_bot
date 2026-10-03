drop index if exists zoom_conversation_pwa_idempotency_uq;
alter table zoom_conversation drop column pwa_idempotency_key;
