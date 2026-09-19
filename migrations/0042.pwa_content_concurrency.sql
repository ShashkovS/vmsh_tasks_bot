-- depends: 0041.pwa_content_lessons

-- One concrete group lesson has one active source lineage for each independently
-- published material kind.  Filename remains immutable provenance inside that
-- lineage; it is not part of active identity.  The repository's atomic
-- resolve/create+append operation relies on this database-enforced invariant.
create unique index content_sources_one_active_material_uq
    on content_sources (group_lesson_id, kind)
    where archived_at is null;

create trigger content_sources_identity_archive_guard
before update on content_sources
for each row
when not (
    new.public_id is old.public_id
    and new.group_lesson_id is old.group_lesson_id
    and new.kind is old.kind
    and new.logical_filename is old.logical_filename
    and new.source_encoding is old.source_encoding
    and new.created_by_user_id is old.created_by_user_id
    and new.created_at is old.created_at
    and old.archived_at is null
    and new.archived_at is not null
    and new.archived_at >= old.created_at
)
begin
    select raise(abort, 'content source identity/archive transition is invalid');
end;

create trigger content_sources_delete_forbidden
before delete on content_sources
for each row
begin
    select raise(abort, 'content source deletion is forbidden');
end;

alter table content_revisions add column compile_claim_token text
    check (compile_claim_token is null or length(compile_claim_token) between 16 and 128);
alter table content_revisions add column compile_claimed_at text;
alter table content_revisions add column compile_lease_expires_at text;
alter table content_revisions add column compile_attempt_count integer not null default 0
    check (compile_attempt_count >= 0);
alter table content_revisions add column compile_completed_at text;

alter table lesson_publications add column terminal_by_user_id integer references users (id);
alter table lesson_publications add column terminal_at text;
-- Historical publication timestamps can be known even when the original actor
-- is not.  Keep that uncertainty explicit instead of inventing a user ID, while
-- retaining the stricter actor requirement for every interactive/API insert.
alter table lesson_publications add column provenance_kind text not null default 'interactive'
    check (provenance_kind in ('interactive', 'legacy_backfill'));

create trigger lesson_publications_terminal_insert_guard
before insert on lesson_publications
for each row
when new.state not in ('scheduled', 'published')
    or (
        new.provenance_kind = 'interactive'
        and (
            new.created_by_user_id is null
            or (new.state = 'scheduled' and new.published_by_user_id is not null)
            or (new.state = 'published' and new.published_by_user_id is null)
        )
    )
    or (
        new.provenance_kind = 'legacy_backfill'
        and (
            new.state <> 'published'
            or new.created_by_user_id is not null
            or new.published_by_user_id is not null
            or new.supersedes_publication_id is not null
            or new.activated_from_schedule_id is not null
        )
    )
    or new.terminal_by_user_id is not null
    or new.terminal_at is not null
begin
    select raise(abort, 'publication must begin in an active non-terminal state');
end;

-- Every publication update is one terminal transition. Identity/payload times
-- are immutable, the optimistic version must advance exactly once, and the
-- responsible actor/timestamp are retained on the terminal row.
create trigger lesson_publications_terminal_audit_guard
before update on lesson_publications
for each row
when not (
    old.state in ('scheduled', 'published')
    and new.state in ('hidden', 'superseded')
    and new.state is not old.state
    and new.version = old.version + 1
    and old.terminal_by_user_id is null
    and old.terminal_at is null
    and new.public_id is old.public_id
    and new.group_lesson_id is old.group_lesson_id
    and new.kind is old.kind
    and new.revision_id is old.revision_id
    and new.scheduled_at is old.scheduled_at
    and new.published_at is old.published_at
    and (
        (new.state = 'hidden' and new.hidden_at is not null)
        or (new.state = 'superseded' and new.hidden_at is old.hidden_at)
    )
    and new.created_by_user_id is old.created_by_user_id
    and new.published_by_user_id is old.published_by_user_id
    and new.provenance_kind is old.provenance_kind
    and new.supersedes_publication_id is old.supersedes_publication_id
    and new.activated_from_schedule_id is old.activated_from_schedule_id
    and new.created_at is old.created_at
    and new.updated_at >= old.updated_at
    and new.terminal_by_user_id is not null
    and new.terminal_at is not null
    and new.terminal_at is new.updated_at
    and new.terminal_at >= old.created_at
)
begin
    select raise(abort, 'publication terminal audit/version transition is invalid');
end;
