-- depends: 0049.pwa_submission_attachment_mutations

-- A Student prepares replacement evidence as a separate draft.  The repository
-- then swaps visibility atomically: the old submitted entry becomes deleted,
-- the new entry becomes submitted, and this append-only row preserves the
-- exact relationship.  See Phase 5 in
-- vmshpwa/dev/development-plan/09-phase-5-written-submissions.md.
create table submission_entry_replacements
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    thread_id            integer not null references submission_threads (id),
    student_user_id      integer not null references users (id),
    replaced_entry_id    integer not null unique references submission_entries (id),
    replacement_entry_id integer not null unique references submission_entries (id),
    idempotency_key      text    not null
        check (
            length(idempotency_key) between 1 and 200
            and idempotency_key = trim(idempotency_key)
        ),
    replaced_at          text    not null,
    unique (student_user_id, idempotency_key),
    check (replaced_entry_id <> replacement_entry_id)
);

create index submission_entry_replacements_thread_history_idx
    on submission_entry_replacements (thread_id, replaced_at, id);

create trigger submission_entry_replacements_scope_insert
before insert on submission_entry_replacements
for each row
when not exists (
    select 1
    from submission_threads as thread
    join submission_entries as replaced
      on replaced.id = new.replaced_entry_id
     and replaced.thread_id = thread.id
     and replaced.author_kind = 'student'
     and replaced.author_user_id = thread.student_user_id
     and replaced.state = 'deleted'
    join submission_entries as replacement
      on replacement.id = new.replacement_entry_id
     and replacement.thread_id = thread.id
     and replacement.author_kind = 'student'
     and replacement.author_user_id = thread.student_user_id
     and replacement.state = 'submitted'
    where thread.id = new.thread_id
      and thread.student_user_id = new.student_user_id
)
begin
    select raise(abort, 'submission replacement is outside mutable thread scope');
end;

create trigger submission_entry_replacements_immutable_update
before update on submission_entry_replacements
for each row
begin
    select raise(abort, 'submission replacement is immutable');
end;

create trigger submission_entry_replacements_delete_forbidden
before delete on submission_entry_replacements
for each row
begin
    select raise(abort, 'submission replacement deletion is forbidden');
end;
