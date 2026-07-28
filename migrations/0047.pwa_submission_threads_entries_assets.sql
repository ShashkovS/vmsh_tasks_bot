-- depends: 0046.pwa_test_attempts_idempotency

-- Phase 5A written-submission identity and evidence graph.
-- Authoritative contracts:
-- vmshpwa/dev/development-plan/09-phase-5-written-submissions.md and
-- vmshpwa/dev/development-plan/02-data-model.md, section `submission_threads`.
-- This migration is additive: legacy Telegram discussions and queue remain the
-- active compatibility path until their explicit lazy/batch backfill.

create table submission_threads
(
    id                    integer primary key,
    public_id             text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id       integer not null references users (id),
    problem_id            integer not null references problems (id),
    -- The public conditionRevisionId contract names the source/content
    -- revision. A scope trigger below proves the concrete problem has a
    -- problem_revision inside that content revision.
    condition_revision_id integer not null references content_revisions (id),
    status                 text    not null
        check (status in ('open', 'awaiting_review', 'needs_work', 'accepted', 'closed')),
    latest_result_id       integer,
    latest_entry_at        text    not null,
    created_at             text    not null,
    updated_at             text    not null,
    version                integer not null default 1 check (version > 0),
    foreign key (latest_result_id, student_user_id, problem_id)
        references results (id, student_id, problem_id),
    check (latest_entry_at >= created_at),
    check (updated_at >= created_at),
    check (status not in ('needs_work', 'accepted') or latest_result_id is not null)
);

create unique index submission_threads_id_owner_problem_uq
    on submission_threads (id, student_user_id, problem_id);

create unique index submission_threads_one_active_uq
    on submission_threads (student_user_id, problem_id)
    where status <> 'closed';

create index submission_threads_student_updated_idx
    on submission_threads (student_user_id, updated_at desc, id desc);

create index submission_threads_review_queue_idx
    on submission_threads (latest_entry_at, id)
    where status = 'awaiting_review';

create trigger submission_threads_problem_revision_scope_insert
before insert on submission_threads
for each row
when not exists (
    select 1
    from problem_revisions as problem_revision
    where problem_revision.problem_id = new.problem_id
      and problem_revision.content_revision_id = new.condition_revision_id
)
begin
    select raise(abort, 'submission thread condition revision is outside problem scope');
end;

create trigger submission_threads_result_kind_insert
before insert on submission_threads
for each row
when new.latest_result_id is not null and not exists (
    select 1
    from results as result
    where result.id = new.latest_result_id
      and result.student_id = new.student_user_id
      and result.problem_id = new.problem_id
      and result.res_type = 2
)
begin
    select raise(abort, 'submission thread latest result is not written evidence');
end;

create trigger submission_threads_result_kind_update
before update of latest_result_id on submission_threads
for each row
when new.latest_result_id is not null and not exists (
    select 1
    from results as result
    where result.id = new.latest_result_id
      and result.student_id = new.student_user_id
      and result.problem_id = new.problem_id
      and result.res_type = 2
)
begin
    select raise(abort, 'submission thread latest result is not written evidence');
end;

create trigger submission_threads_identity_immutable
before update on submission_threads
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.condition_revision_id is not old.condition_revision_id
    or new.created_at is not old.created_at
begin
    select raise(abort, 'submission thread identity is immutable');
end;

create trigger submission_threads_version_guard
before update on submission_threads
for each row
when new.version <> old.version + 1
    or new.updated_at < old.updated_at
    or new.latest_entry_at < old.latest_entry_at
begin
    select raise(abort, 'submission thread update requires next version and monotonic time');
end;

create trigger submission_threads_state_transition_guard
before update of status on submission_threads
for each row
when new.status is not old.status and not (
    (old.status = 'open' and new.status in ('awaiting_review', 'closed'))
    or (
        old.status = 'awaiting_review'
        and new.status in ('needs_work', 'accepted', 'closed')
    )
    or (
        old.status in ('needs_work', 'accepted')
        and new.status in ('awaiting_review', 'closed')
    )
)
begin
    select raise(abort, 'invalid submission thread state transition');
end;

create trigger submission_threads_delete_forbidden
before delete on submission_threads
for each row
begin
    select raise(abort, 'submission thread deletion is forbidden');
end;

create table submission_entries
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
    author_kind          text    not null
        check (author_kind in ('student', 'teacher', 'admin', 'ai', 'system')),
    author_user_id       integer references users (id),
    channel              text    not null
        check (channel in ('pwa', 'telegram', 'staff', 'system')),
    channel_group_key    text
        check (
            channel_group_key is null
            or (
                length(channel_group_key) between 1 and 200
                and channel_group_key = trim(channel_group_key)
            )
        ),
    entry_kind           text    not null
        check (entry_kind in ('text', 'submission', 'teacher_comment', 'ai_comment', 'system_event')),
    state                text    not null
        check (state in ('draft', 'uploading', 'submitted', 'deleted', 'locked')),
    text                 text    check (text is null or length(text) <= 100000),
    client_created_at    text,
    server_received_at   text    not null,
    idempotency_key      text
        check (
            idempotency_key is null
            or (
                length(idempotency_key) between 1 and 200
                and idempotency_key = trim(idempotency_key)
            )
        ),
    payload_sha256       text
        check (
            payload_sha256 is null
            or (
                length(payload_sha256) = 64
                and payload_sha256 not glob '*[^0-9a-f]*'
            )
        ),
    legacy_discussion_id integer unique references written_tasks_discussions (id),
    version              integer not null default 1 check (version > 0),
    locked_at            text,
    deleted_at           text,
    check ((idempotency_key is null) = (payload_sha256 is null)),
    check (channel_group_key is null or channel = 'telegram'),
    check (
        (author_kind in ('student', 'teacher', 'admin') and author_user_id is not null)
        or (author_kind in ('ai', 'system') and author_user_id is null)
    ),
    check (
        (author_kind = 'student' and entry_kind in ('text', 'submission'))
        or (author_kind in ('teacher', 'admin') and entry_kind = 'teacher_comment')
        or (author_kind = 'ai' and entry_kind = 'ai_comment')
        or (author_kind = 'system' and entry_kind = 'system_event')
    ),
    check (
        (state = 'locked' and locked_at is not null and deleted_at is null)
        or (state = 'deleted' and deleted_at is not null and locked_at is null)
        or (state not in ('locked', 'deleted') and locked_at is null and deleted_at is null)
    ),
    check (locked_at is null or locked_at >= server_received_at),
    check (deleted_at is null or deleted_at >= server_received_at)
);

create unique index submission_entries_id_thread_uq
    on submission_entries (id, thread_id);

create unique index submission_entries_author_idempotency_uq
    on submission_entries (author_user_id, idempotency_key)
    where idempotency_key is not null;

create index submission_entries_thread_history_idx
    on submission_entries (thread_id, server_received_at, id);

create index submission_entries_legacy_group_idx
    on submission_entries (channel_group_key, id)
    where channel = 'telegram' and channel_group_key is not null;

create trigger submission_entries_author_scope_insert
before insert on submission_entries
for each row
when new.author_kind = 'student' and not exists (
    select 1
    from submission_threads as thread
    where thread.id = new.thread_id
      and thread.student_user_id = new.author_user_id
)
begin
    select raise(abort, 'student submission entry author is outside thread scope');
end;

create trigger submission_entries_author_scope_update
before update on submission_entries
for each row
when new.author_kind = 'student' and not exists (
    select 1
    from submission_threads as thread
    where thread.id = new.thread_id
      and thread.student_user_id = new.author_user_id
)
begin
    select raise(abort, 'student submission entry author is outside thread scope');
end;

create trigger submission_entries_nonempty_insert
before insert on submission_entries
for each row
when new.state in ('submitted', 'locked')
    and coalesce(length(trim(new.text)), 0) = 0
begin
    select raise(abort, 'submitted entry requires text or stored attachment');
end;

-- On an update to submitted/locked, attachments already exist and can satisfy
-- the non-empty rule. Text-only entries remain valid.
create trigger submission_entries_nonempty_update
before update of state, text on submission_entries
for each row
when new.state in ('submitted', 'locked')
    and coalesce(length(trim(new.text)), 0) = 0
    and not exists (
        select 1
        from submission_attachments as attachment
        where attachment.entry_id = new.id
          and attachment.upload_status in ('stored', 'locked')
    )
begin
    select raise(abort, 'submitted entry requires text or stored attachment');
end;

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

create trigger submission_entries_version_guard
before update on submission_entries
for each row
when new.version <> old.version + 1
begin
    select raise(abort, 'submission entry update requires next version');
end;

create trigger submission_entries_terminal_immutable
before update on submission_entries
for each row
when old.state in ('locked', 'deleted')
begin
    select raise(abort, 'locked or deleted submission entry is immutable');
end;

create trigger submission_entries_state_transition_guard
before update of state on submission_entries
for each row
when new.state is not old.state and not (
    (old.state = 'draft' and new.state in ('uploading', 'submitted', 'deleted'))
    or (old.state = 'uploading' and new.state in ('draft', 'submitted', 'deleted'))
    or (old.state = 'submitted' and new.state in ('deleted', 'locked'))
)
begin
    select raise(abort, 'invalid submission entry state transition');
end;

create trigger submission_entries_lock_requires_attachments_locked
before update of state on submission_entries
for each row
when new.state = 'locked' and exists (
    select 1
    from submission_attachments as attachment
    where attachment.entry_id = new.id
      and attachment.upload_status <> 'locked'
)
begin
    select raise(abort, 'submission entry lock requires locked attachments');
end;

create trigger submission_entries_delete_forbidden
before delete on submission_entries
for each row
begin
    select raise(abort, 'submission entry deletion is forbidden');
end;

create table submission_attachments
(
    id                  integer primary key,
    public_id           text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    entry_id            integer not null references submission_entries (id),
    asset_id            integer not null references media_assets (id),
    -- Ordinals are deliberately sparse and non-negative. SQLite does not defer
    -- UNIQUE checks, so reorder code needs temporary high values; the separate
    -- count trigger, not the ordinal range, enforces the product limit of ten.
    ordinal             integer not null check (ordinal >= 0),
    client_filename     text check (client_filename is null or length(client_filename) <= 512),
    upload_status       text    not null
        check (upload_status in ('pending', 'stored', 'failed', 'locked')),
    created_at          text    not null,
    locked_at           text,
    locked_by_result_id integer references results (id),
    unique (entry_id, ordinal),
    check (
        (upload_status = 'locked' and locked_at is not null and locked_by_result_id is not null)
        or (upload_status <> 'locked' and locked_at is null and locked_by_result_id is null)
    ),
    check (locked_at is null or locked_at >= created_at)
);

create unique index submission_attachments_id_entry_uq
    on submission_attachments (id, entry_id);

create index submission_attachments_entry_order_idx
    on submission_attachments (entry_id, ordinal, id);

create index submission_attachments_asset_idx
    on submission_attachments (asset_id, id);

create trigger submission_attachments_max_ten_insert
before insert on submission_attachments
for each row
when (
    select count(*)
    from submission_attachments as attachment
    where attachment.entry_id = new.entry_id
) >= 10
begin
    select raise(abort, 'submission entry accepts at most ten attachments');
end;

create trigger submission_attachments_entry_mutable_insert
before insert on submission_attachments
for each row
when not exists (
    select 1
    from submission_entries as entry
    where entry.id = new.entry_id
      and entry.state in ('draft', 'uploading', 'submitted')
)
begin
    select raise(abort, 'submission attachment entry is not mutable');
end;

create trigger submission_attachments_asset_contract_insert
before insert on submission_attachments
for each row
when not exists (
    select 1
    from media_assets as asset
    where asset.id = new.asset_id
      and asset.storage_namespace = 'submission'
      and asset.media_type = 'image/webp'
      and asset.deleted_at is null
      and asset.width between 1 and 1920
      and asset.height between 1 and 1920
)
begin
    select raise(abort, 'submission attachment requires final webp asset');
end;

create trigger submission_attachments_identity_immutable
before update on submission_attachments
for each row
when new.public_id is not old.public_id
    or new.entry_id is not old.entry_id
    or new.asset_id is not old.asset_id
    or new.client_filename is not old.client_filename
    or new.created_at is not old.created_at
begin
    select raise(abort, 'submission attachment identity is immutable');
end;

create trigger submission_attachments_entry_mutable_update
before update on submission_attachments
for each row
when not exists (
    select 1
    from submission_entries as entry
    where entry.id = new.entry_id
      and entry.state in ('draft', 'uploading', 'submitted')
)
begin
    select raise(abort, 'submission attachment entry is not mutable');
end;

create trigger submission_attachments_state_transition_guard
before update of upload_status on submission_attachments
for each row
when new.upload_status is not old.upload_status and not (
    (old.upload_status = 'pending' and new.upload_status in ('stored', 'failed'))
    or (old.upload_status = 'failed' and new.upload_status in ('pending', 'stored'))
    or (old.upload_status = 'stored' and new.upload_status = 'locked')
)
begin
    select raise(abort, 'invalid submission attachment state transition');
end;

create trigger submission_attachments_lock_result_scope_update
before update of upload_status, locked_by_result_id on submission_attachments
for each row
when new.upload_status = 'locked' and not exists (
    select 1
    from submission_entries as entry
    join submission_threads as thread on thread.id = entry.thread_id
    join results as result on result.id = new.locked_by_result_id
    join media_assets as asset on asset.id = new.asset_id
    where entry.id = new.entry_id
      and result.student_id = thread.student_user_id
      and result.problem_id = thread.problem_id
      and result.res_type = 2
      and asset.immutable_at is not null
)
begin
    select raise(abort, 'submission attachment lock is outside review evidence');
end;

create trigger submission_attachments_locked_immutable
before update on submission_attachments
for each row
when old.upload_status = 'locked'
begin
    select raise(abort, 'locked submission attachment is immutable');
end;

create trigger submission_attachments_delete_guard
before delete on submission_attachments
for each row
when old.upload_status = 'locked' or exists (
    select 1
    from submission_entries as entry
    where entry.id = old.entry_id
      and entry.state = 'locked'
)
begin
    select raise(abort, 'locked submission attachment deletion is forbidden');
end;

create trigger media_assets_locked_submission_immutable
before update on media_assets
for each row
when exists (
    select 1
    from submission_attachments as attachment
    where attachment.asset_id = old.id
      and attachment.upload_status = 'locked'
)
begin
    select raise(abort, 'locked submission media asset is immutable');
end;

create table submission_material_reassignments
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id      integer not null references users (id),
    source_thread_id     integer not null,
    target_thread_id     integer not null,
    source_problem_id    integer not null references problems (id),
    target_problem_id    integer not null references problems (id),
    performed_by_user_id integer not null references users (id),
    reason               text
        check (reason is null or (length(trim(reason)) between 1 and 2000)),
    request_id           text    not null
        check (length(request_id) between 1 and 200 and request_id = trim(request_id)),
    created_at           text    not null,
    foreign key (source_thread_id, student_user_id, source_problem_id)
        references submission_threads (id, student_user_id, problem_id),
    foreign key (target_thread_id, student_user_id, target_problem_id)
        references submission_threads (id, student_user_id, problem_id),
    unique (performed_by_user_id, request_id),
    check (source_thread_id <> target_thread_id),
    check (source_problem_id <> target_problem_id)
);

create index submission_material_reassignments_student_history_idx
    on submission_material_reassignments (student_user_id, created_at, id);

create trigger submission_material_reassignments_immutable_update
before update on submission_material_reassignments
for each row
begin
    select raise(abort, 'submission material reassignment is immutable');
end;

create trigger submission_material_reassignments_delete_forbidden
before delete on submission_material_reassignments
for each row
begin
    select raise(abort, 'submission material reassignment deletion is forbidden');
end;

create table submission_material_reassignment_items
(
    reassignment_id integer not null references submission_material_reassignments (id),
    source_entry_id integer not null references submission_entries (id),
    item_kind       text    not null check (item_kind in ('entry_text', 'attachment')),
    attachment_id   integer references submission_attachments (id),
    ordinal         integer not null check (ordinal >= 0),
    primary key (reassignment_id, ordinal),
    check (
        (item_kind = 'entry_text' and attachment_id is null)
        or (item_kind = 'attachment' and attachment_id is not null)
    )
);

create index submission_material_reassignment_items_projection_idx
    on submission_material_reassignment_items
       (source_entry_id, item_kind, attachment_id, reassignment_id, ordinal);

create trigger submission_material_reassignment_items_scope_insert
before insert on submission_material_reassignment_items
for each row
when not exists (
    select 1
    from submission_material_reassignments as reassignment
    join submission_entries as entry
      on entry.id = new.source_entry_id
     and entry.thread_id = reassignment.source_thread_id
    where reassignment.id = new.reassignment_id
      and (
          (
              new.item_kind = 'entry_text'
              and new.attachment_id is null
              and coalesce(length(trim(entry.text)), 0) > 0
          )
          or (
              new.item_kind = 'attachment'
              and exists (
                  select 1
                  from submission_attachments as attachment
                  where attachment.id = new.attachment_id
                    and attachment.entry_id = entry.id
              )
          )
      )
)
begin
    select raise(abort, 'submission reassignment item is outside source scope');
end;

create trigger submission_material_reassignment_items_immutable_update
before update on submission_material_reassignment_items
for each row
begin
    select raise(abort, 'submission reassignment item is immutable');
end;

create trigger submission_material_reassignment_items_delete_forbidden
before delete on submission_material_reassignment_items
for each row
begin
    select raise(abort, 'submission reassignment item deletion is forbidden');
end;
