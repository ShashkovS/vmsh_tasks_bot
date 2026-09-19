-- depends: 0051.pwa_review_queue_leases

-- Phase 6C: an immutable review record and an exact, append-only evidence
-- snapshot.  Evidence rows deliberately keep each original problem/thread
-- identity: synonym grouping is a read model and may later be corrected.
-- See vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md.

create table submission_reviews
(
    id                        integer primary key,
    public_id text generated always as ('r-' || id) virtual,
    thread_id                 integer not null references submission_threads (id),
    -- Queue rows are deleted by the same transaction.  These are immutable
    -- provenance snapshots rather than foreign keys to ephemeral work items.
    queue_id                  integer not null,
    reviewer_user_id          integer not null references users (id),
    evidence_through_entry_id integer not null references submission_entries (id),
    expected_thread_version   integer not null check (expected_thread_version > 0),
    verdict                   integer not null,
    comment_entry_id          integer references submission_entries (id),
    result_id                 integer not null unique references results (id),
    review_duration_sec       integer check (review_duration_sec is null or review_duration_sec >= 0),
    source                    text    not null check (source in ('staff', 'telegram', 'ai')),
    idempotency_key           text    not null
        check (length(idempotency_key) between 1 and 200 and idempotency_key = trim(idempotency_key)),
    payload_sha256            text    not null
        check (length(payload_sha256) = 64 and payload_sha256 not glob '*[^0-9a-f]*'),
    created_at                text    not null,
    unique (reviewer_user_id, idempotency_key)
);

create index submission_reviews_thread_history_idx
    on submission_reviews (thread_id, created_at, id);

create trigger submission_reviews_scope_insert
before insert on submission_reviews
for each row
when not exists (
    select 1
    from submission_threads as thread
    join submission_entries as evidence
      on evidence.id = new.evidence_through_entry_id
     and evidence.thread_id = thread.id
     and evidence.author_kind = 'student'
    join results as result
      on result.id = new.result_id
     and result.student_id = thread.student_user_id
     and result.problem_id = thread.problem_id
     and result.res_type = 2
    left join submission_entries as comment
      on comment.id = new.comment_entry_id
    where thread.id = new.thread_id
      and (
          new.comment_entry_id is null
          or (
              comment.thread_id = thread.id
              and comment.author_user_id = new.reviewer_user_id
              and comment.author_kind in ('teacher', 'admin')
              and comment.entry_kind = 'teacher_comment'
              and comment.state = 'locked'
          )
      )
)
begin
    select raise(abort, 'submission review target is outside result/evidence scope');
end;

create trigger submission_reviews_immutable_update
before update on submission_reviews
for each row
begin
    select raise(abort, 'completed submission review is immutable');
end;

create trigger submission_reviews_delete_forbidden
before delete on submission_reviews
for each row
begin
    select raise(abort, 'completed submission review deletion is forbidden');
end;

create table submission_review_evidence_entries
(
    review_id          integer not null references submission_reviews (id),
    entry_id           integer not null references submission_entries (id),
    thread_id          integer not null references submission_threads (id),
    problem_id         integer not null references problems (id),
    entry_version      integer not null check (entry_version > 0),
    server_received_at text    not null,
    primary key (review_id, entry_id),
    foreign key (entry_id, thread_id)
        references submission_entries (id, thread_id)
);

create index submission_review_evidence_entries_entry_idx
    on submission_review_evidence_entries (entry_id, review_id);

create trigger submission_review_evidence_entries_scope_insert
before insert on submission_review_evidence_entries
for each row
when not exists (
    select 1
    from submission_reviews as review
    join submission_threads as target_thread on target_thread.id = review.thread_id
    join submission_threads as evidence_thread
      on evidence_thread.id = new.thread_id
     and evidence_thread.student_user_id = target_thread.student_user_id
     and evidence_thread.problem_id = new.problem_id
    join submission_entries as entry
      on entry.id = new.entry_id
     and entry.thread_id = evidence_thread.id
     and entry.author_kind = 'student'
     and entry.state = 'submitted'
     and entry.version = new.entry_version
     and entry.server_received_at = new.server_received_at
    where review.id = new.review_id
)
begin
    select raise(abort, 'review evidence entry is outside student/thread scope');
end;

create trigger submission_review_evidence_entries_immutable_update
before update on submission_review_evidence_entries
for each row
begin
    select raise(abort, 'review evidence entry is immutable');
end;

create trigger submission_review_evidence_entries_delete_forbidden
before delete on submission_review_evidence_entries
for each row
begin
    select raise(abort, 'review evidence entry deletion is forbidden');
end;

create table submission_review_evidence_attachments
(
    review_id     integer not null references submission_reviews (id),
    attachment_id integer not null references submission_attachments (id),
    entry_id      integer not null references submission_entries (id),
    asset_id      integer not null references media_assets (id),
    ordinal       integer not null check (ordinal >= 0),
    primary key (review_id, attachment_id),
    foreign key (review_id, entry_id)
        references submission_review_evidence_entries (review_id, entry_id),
    foreign key (attachment_id, entry_id)
        references submission_attachments (id, entry_id)
);

create index submission_review_evidence_attachments_attachment_idx
    on submission_review_evidence_attachments (attachment_id, review_id);

create index submission_review_evidence_attachments_asset_idx
    on submission_review_evidence_attachments (asset_id, review_id);

create trigger submission_review_evidence_attachments_scope_insert
before insert on submission_review_evidence_attachments
for each row
when not exists (
    select 1
    from submission_attachments as attachment
    where attachment.id = new.attachment_id
      and attachment.entry_id = new.entry_id
      and attachment.asset_id = new.asset_id
      and attachment.ordinal = new.ordinal
      and attachment.upload_status = 'stored'
)
begin
    select raise(abort, 'review evidence attachment is outside entry scope');
end;

create trigger submission_review_evidence_attachments_immutable_update
before update on submission_review_evidence_attachments
for each row
begin
    select raise(abort, 'review evidence attachment is immutable');
end;

create trigger submission_review_evidence_attachments_delete_forbidden
before delete on submission_review_evidence_attachments
for each row
begin
    select raise(abort, 'review evidence attachment deletion is forbidden');
end;

-- Reviewed evidence retains the legacy `submitted`/`stored` values so a
-- single target result can freeze material from several synonym branches.
-- These guards make that evidence just as immutable as the older one-result
-- `locked` representation, without manufacturing results for peer branches.
create trigger submission_entries_review_evidence_immutable
before update on submission_entries
for each row
when exists (
    select 1 from submission_review_evidence_entries as evidence
    where evidence.entry_id = old.id
)
begin
    select raise(abort, 'reviewed submission entry is immutable');
end;

create trigger submission_attachments_review_evidence_insert_forbidden
before insert on submission_attachments
for each row
when exists (
    select 1 from submission_review_evidence_entries as evidence
    where evidence.entry_id = new.entry_id
)
begin
    select raise(abort, 'reviewed submission attachment set is immutable');
end;

create trigger submission_attachments_review_evidence_immutable
before update on submission_attachments
for each row
when exists (
    select 1 from submission_review_evidence_attachments as evidence
    where evidence.attachment_id = old.id
)
begin
    select raise(abort, 'reviewed submission attachment is immutable');
end;

create trigger submission_attachments_review_evidence_delete_forbidden
before delete on submission_attachments
for each row
when exists (
    select 1 from submission_review_evidence_attachments as evidence
    where evidence.attachment_id = old.id
)
begin
    select raise(abort, 'reviewed submission attachment deletion is forbidden');
end;

create trigger media_assets_review_evidence_immutable
before update on media_assets
for each row
when exists (
    select 1 from submission_review_evidence_attachments as evidence
    where evidence.asset_id = old.id
)
begin
    select raise(abort, 'reviewed submission media asset is immutable');
end;

create table submission_review_events
(
    id          integer primary key,
    public_id text generated always as ('re-' || id) virtual,
    review_id   integer not null references submission_reviews (id),
    event_kind  text not null check (event_kind in ('completed')),
    payload_json text not null check (json_valid(payload_json) = 1),
    created_at  text not null
);

create trigger submission_review_events_immutable_update
before update on submission_review_events
for each row
begin
    select raise(abort, 'submission review event is immutable');
end;

create trigger submission_review_events_delete_forbidden
before delete on submission_review_events
for each row
begin
    select raise(abort, 'submission review event deletion is forbidden');
end;
