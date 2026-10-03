-- depends: 0086.pwa_review_history
-- Whole-entry queue routing; vmshpwa/docs/serial-review-feed.md.
CREATE TABLE submission_entry_transfers (
 id INTEGER PRIMARY KEY,
 actor_user_id INTEGER NOT NULL REFERENCES users(id),
 idempotency_key TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 mode TEXT NOT NULL CHECK(mode IN ('move', 'clone')),
 source_entry_id INTEGER NOT NULL REFERENCES submission_entries(id),
 target_entry_id INTEGER NOT NULL REFERENCES submission_entries(id),
 created_at TEXT NOT NULL,
 response_json TEXT NOT NULL,
 UNIQUE(actor_user_id, idempotency_key)
);
CREATE INDEX submission_entry_transfers_source_idx ON submission_entry_transfers(source_entry_id);
CREATE TRIGGER submission_entry_transfers_immutable BEFORE UPDATE ON submission_entry_transfers
BEGIN SELECT RAISE(ABORT, 'entry transfer is immutable'); END;
CREATE TRIGGER submission_entry_transfers_delete_forbidden BEFORE DELETE ON submission_entry_transfers
BEGIN SELECT RAISE(ABORT, 'entry transfer deletion is forbidden'); END;

-- Reopen the existing target instead of hiding its old history in a new thread.
-- Only a newly audited, still-unreviewed transfer can authorize this transition.
DROP TRIGGER submission_threads_state_transition_guard;
CREATE TRIGGER submission_threads_state_transition_guard BEFORE UPDATE OF status ON submission_threads
FOR EACH ROW WHEN new.status IS NOT old.status AND NOT (
 (old.status='open' AND new.status IN ('awaiting_review','closed')) OR
 (old.status='awaiting_review' AND new.status IN ('needs_work','accepted','closed')) OR
 (old.status IN ('needs_work','accepted') AND new.status IN ('awaiting_review','closed')) OR
 (old.status='closed' AND new.status='awaiting_review' AND EXISTS (
   SELECT 1 FROM submission_entry_transfers transfer JOIN submission_entries entry ON entry.id=transfer.target_entry_id
   WHERE entry.thread_id=old.id AND entry.state='submitted' AND transfer.created_at=new.updated_at
   AND NOT EXISTS(SELECT 1 FROM submission_review_evidence_entries evidence WHERE evidence.entry_id=entry.id)
 ))
)
BEGIN SELECT RAISE(ABORT,'invalid submission thread state transition'); END;
