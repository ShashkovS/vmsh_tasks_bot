-- depends: 0094.pwa_shared_oral_windows
-- Persist the current, replaceable evaluation projection next to the immutable
-- answer payload.  See 08-phase-4-test-submissions.md, "Full recheck".
alter table test_attempts add column evaluation_version text
    check (evaluation_version is null or length(trim(evaluation_version)) > 0);
alter table test_attempts add column feedback text;
alter table test_attempts add column checker_message text;

drop trigger test_attempts_payload_immutable;
create trigger test_attempts_payload_immutable
before update on test_attempts
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.problem_revision_id is not old.problem_revision_id
    or new.answer_payload_json is not old.answer_payload_json
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

drop trigger test_attempts_check_transition_guard;
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
) and not (
    new.evaluation_version is not old.evaluation_version
)
begin
    select raise(abort, 'invalid test attempt check transition');
end;

create index test_attempts_problem_evaluation_idx
    on test_attempts (problem_id, evaluation_version, server_received_at, id);

-- Keep the append-only automatic result audit attributable to its PWA attempt.
-- This deliberately does not classify legacy/Telegram test results.
create table test_attempt_result_events (
    attempt_id integer not null references test_attempts(id),
    result_id integer not null unique references results(id),
    created_at text not null,
    primary key (attempt_id, result_id)
);

insert into test_attempt_result_events(attempt_id, result_id, created_at)
select id, result_id, coalesce(checked_at, server_received_at)
from test_attempts
where result_id is not null;

create trigger test_attempt_result_events_update_forbidden
before update on test_attempt_result_events
begin
    select raise(abort, 'test attempt result event is immutable');
end;

create trigger test_attempt_result_events_delete_forbidden
before delete on test_attempt_result_events
begin
    select raise(abort, 'test attempt result event cannot be deleted');
end;

-- Historical automatic result rows remain an append-only audit, but current
-- read models may see only the result selected by the attempt projection.
drop view effective_results;
create view effective_results as
    select r.* from results r
    left join live_mark_cells c
      on c.student_id=r.student_id and c.problem_id=r.problem_id
    where ((c.result_id is not null and r.id=c.result_id)
       or (c.result_id is null and not exists (
           select 1 from live_mark_results m where m.result_id=r.id)))
      and (r.res_type<>1 or not exists (
           select 1 from test_attempt_result_events e
           where e.result_id=r.id)
       or exists (
           select 1 from test_attempts a
           where a.result_id=r.id));
