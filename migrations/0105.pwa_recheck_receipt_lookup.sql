-- depends: 0103.course_in_person_classes
-- vmshpwa/docs/sqlite-admission-performance.md: indexed receipt lookup in _stored_attempts.
CREATE INDEX idempotency_records_completed_receipt_lookup_idx
    ON idempotency_records (account_id, operation, idempotency_key, payload_sha256, id DESC)
    WHERE state = 'completed';
