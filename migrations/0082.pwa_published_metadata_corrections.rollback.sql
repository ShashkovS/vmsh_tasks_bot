-- depends: 0082.pwa_published_metadata_corrections

drop table content_review_states;

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
)
begin
    select raise(abort, 'invalid test attempt check transition');
end;

create trigger problem_revisions_immutable_update
before update on problem_revisions
for each row
begin
    select raise(abort, 'problem revision is immutable');
end;

create trigger content_problem_matches_immutable_update
before update on content_problem_matches
for each row
begin
    select raise(abort, 'resolved content problem match is immutable');
end;
