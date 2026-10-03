-- depends: 0047.pwa_submission_threads_entries_assets

drop trigger submission_entries_identity_immutable;
drop trigger submission_entries_problem_revision_scope_update;
drop trigger submission_entries_problem_revision_scope_insert;

alter table submission_entries drop column problem_revision_id;

create trigger submission_entries_identity_immutable
before update on submission_entries
for each row
when new.public_id is not old.public_id
    or new.thread_id is not old.thread_id
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
