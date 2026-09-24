-- depends: 0061.pwa_classroom_assignment_delivery

-- One row records one explicit administrator request to retry only failed
-- Telegram recipients. Successful recipient rows are never reset.
create table classroom_assignment_delivery_retries
(
    id                     integer primary key,
    batch_id               integer not null
        references classroom_assignment_delivery_batches (id),
    requested_by_user_id   integer not null references users (id),
    idempotency_key        text    not null check (length(idempotency_key) between 1 and 128),
    expected_batch_version integer not null check (expected_batch_version > 0),
    recipient_count        integer not null check (recipient_count > 0),
    created_at             text    not null,
    unique (requested_by_user_id, idempotency_key)
);
