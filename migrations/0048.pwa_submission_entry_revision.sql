-- depends: 0047.pwa_submission_threads_entries_assets

-- A written thread survives condition edits, but each student entry must keep
-- the exact problem revision that was visible when that material was created.
-- See Phase 5 in vmshpwa/dev/development-plan/09-phase-5-written-submissions.md.
alter table submission_entries
    add column problem_revision_id integer references problem_revisions (id);

drop trigger submission_entries_identity_immutable;

create trigger submission_entries_problem_revision_scope_insert
before insert on submission_entries
for each row
when (
    new.author_kind = 'student'
    and new.problem_revision_id is null
) or (
    new.problem_revision_id is not null
    and not exists (
        select 1
        from submission_threads as thread
        join problem_revisions as problem_revision
          on problem_revision.id = new.problem_revision_id
         and problem_revision.problem_id = thread.problem_id
        where thread.id = new.thread_id
    )
)
begin
    select raise(abort, 'submission entry problem revision is outside thread scope');
end;

create trigger submission_entries_problem_revision_scope_update
before update on submission_entries
for each row
when (
    new.author_kind = 'student'
    and new.problem_revision_id is null
) or (
    new.problem_revision_id is not null
    and not exists (
        select 1
        from submission_threads as thread
        join problem_revisions as problem_revision
          on problem_revision.id = new.problem_revision_id
         and problem_revision.problem_id = thread.problem_id
        where thread.id = new.thread_id
    )
)
begin
    select raise(abort, 'submission entry problem revision is outside thread scope');
end;

create trigger submission_entries_identity_immutable
before update on submission_entries
for each row
when new.public_id is not old.public_id
    or new.thread_id is not old.thread_id
    or new.problem_revision_id is not old.problem_revision_id
    or new.author_kind is not old.author_kind
    or new.author_user_id is not old.author_user_id
    or new.channel is not old.channel
    or new.channel_group_key is not old.channel_group_key
    or new.entry_kind is not old.entry_kind
    or new.client_created_at is not old.client_created_at
    or new.server_received_at is not old.server_received_at
    or new.idempotency_key is not old.idempotency_key
    or new.legacy_discussion_id is not old.legacy_discussion_id
begin
    select raise(abort, 'submission entry identity is immutable');
end;
