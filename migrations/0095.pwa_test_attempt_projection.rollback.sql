-- depends: 0095.pwa_test_attempt_projection
drop view effective_results;
create view effective_results as
    select r.* from results r
    left join live_mark_cells c on c.student_id=r.student_id and c.problem_id=r.problem_id
    where (c.result_id is not null and r.id=c.result_id)
       or (c.result_id is null and not exists (
           select 1 from live_mark_results m where m.result_id=r.id));

drop trigger test_attempt_result_events_delete_forbidden;
drop trigger test_attempt_result_events_update_forbidden;
drop table test_attempt_result_events;
drop index test_attempts_problem_evaluation_idx;
drop trigger test_attempts_check_transition_guard;
drop trigger test_attempts_payload_immutable;

create trigger test_attempts_payload_immutable
before update on test_attempts
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.problem_revision_id is not old.problem_revision_id
    or new.answer_payload_json is not old.answer_payload_json
    or new.normalized_answer_json is not old.normalized_answer_json
    or new.parse_status is not old.parse_status
    or new.counts_as_attempt is not old.counts_as_attempt
    or new.client_created_at is not old.client_created_at
    or new.server_received_at is not old.server_received_at
    or new.clock_skew_seconds is not old.clock_skew_seconds
    or new.clock_suspicious is not old.clock_suspicious
    or new.idempotency_key is not old.idempotency_key
    or new.payload_sha256 is not old.payload_sha256
    or new.created_at is not old.created_at
begin
    select raise(abort, 'test attempt payload is immutable');
end;

create trigger test_attempts_check_transition_guard
before update on test_attempts
for each row
when not (
    old.check_status = 'pending_configuration'
    and new.check_status in ('pending', 'checked', 'failed')
) and not (
    old.check_status = 'pending'
    and new.check_status in ('checked', 'failed')
) and not (
    old.check_status = 'checked' and new.check_status = 'checked'
)
begin
    select raise(abort, 'invalid test attempt check transition');
end;

alter table test_attempts drop column checker_message;
alter table test_attempts drop column feedback;
alter table test_attempts drop column evaluation_version;
