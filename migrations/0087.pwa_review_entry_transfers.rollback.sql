DROP TRIGGER submission_threads_state_transition_guard;
CREATE TRIGGER submission_threads_state_transition_guard BEFORE UPDATE OF status ON submission_threads
FOR EACH ROW WHEN new.status IS NOT old.status AND NOT (
 (old.status='open' AND new.status IN ('awaiting_review','closed')) OR
 (old.status='awaiting_review' AND new.status IN ('needs_work','accepted','closed')) OR
 (old.status IN ('needs_work','accepted') AND new.status IN ('awaiting_review','closed'))
)
BEGIN SELECT RAISE(ABORT,'invalid submission thread state transition'); END;
DROP TRIGGER submission_entry_transfers_immutable;
DROP TRIGGER submission_entry_transfers_delete_forbidden;
DROP TABLE submission_entry_transfers;
