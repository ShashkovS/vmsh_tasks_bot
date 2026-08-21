-- depends: 0081.pwa_rich_markdown

-- A published condition has one current, editable task configuration. Old
-- submissions remain as artefacts, while their displayed verdict is recomputed
-- against this current configuration. See 06-phase-2-content.md, MATCH-03.
drop trigger content_problem_matches_immutable_update;
drop trigger problem_revisions_immutable_update;
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
)
begin
    select raise(abort, 'invalid test attempt check transition');
end;

create table content_review_states
(
    content_revision_id integer primary key references content_revisions (id),
    version             integer not null check (version > 0),
    updated_at          text not null,
    updated_by_user_id  integer references users (id)
);
