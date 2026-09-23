-- depends: 0099.pwa_classroom_assignment_compaction
-- Rich, independently published material positioned around a group lesson.

create table lesson_blocks
(
    id                    integer primary key,
    public_id text generated always as ('lb-' || id) virtual unique,
    group_lesson_id       integer not null references group_lessons (id),
    position              text not null check (position in ('before', 'after')),
    draft_revision_id     integer,
    published_revision_id integer,
    published_at          text,
    pending_revision_id   integer,
    pending_mode          text check (pending_mode in ('scheduled', 'with_lesson')),
    scheduled_at          text,
    version               integer not null default 1 check (version > 0),
    created_at            text not null,
    updated_at            text not null,
    created_by_user_id    integer references users (id),
    updated_by_user_id    integer references users (id),
    unique (group_lesson_id, position),
    check ((published_revision_id is null) = (published_at is null)),
    check ((pending_revision_id is null) = (pending_mode is null)),
    check ((pending_mode = 'scheduled') = (scheduled_at is not null)),
    check (pending_mode = 'scheduled' or scheduled_at is null)
);

create table lesson_block_revisions
(
    id              integer primary key,
    public_id text generated always as ('lbr-' || id) virtual unique,
    block_id        integer not null references lesson_blocks (id),
    revision_number integer not null check (revision_number > 0),
    markdown        text not null,
    document_json   text,
    created_at      text not null,
    created_by_user_id integer not null references users (id),
    unique (block_id, revision_number),
    unique (block_id, id),
    check ((length(trim(markdown)) = 0) = (document_json is null))
);

create table lesson_block_events
(
    id              integer primary key,
    public_id text generated always as ('lbe-' || id) virtual unique,
    block_id        integer not null references lesson_blocks (id),
    revision_id     integer references lesson_block_revisions (id),
    action          text not null check (action in (
        'draft_saved', 'published', 'scheduled', 'with_lesson_armed',
        'publication_cancelled', 'hidden', 'schedule_activated'
    )),
    actor_user_id   integer references users (id),
    created_at      text not null,
    block_version   integer not null check (block_version > 0),
    details_json    text not null default '{}'
);

create index lesson_blocks_due_idx on lesson_blocks (scheduled_at, id)
    where pending_mode = 'scheduled';
create index lesson_blocks_waiting_lesson_idx on lesson_blocks (group_lesson_id, id)
    where pending_mode = 'with_lesson';
create index lesson_block_revisions_block_idx on lesson_block_revisions (block_id, revision_number);
create index lesson_block_events_block_idx on lesson_block_events (block_id, id);

create trigger lesson_block_revisions_immutable
before update on lesson_block_revisions
for each row begin
    select raise(abort, 'lesson block revisions are immutable');
end;

create trigger lesson_block_revisions_delete_forbidden
before delete on lesson_block_revisions
for each row begin
    select raise(abort, 'lesson block revisions cannot be deleted');
end;

create trigger lesson_blocks_revision_scope_insert
before insert on lesson_blocks
for each row when (
    (new.draft_revision_id is not null and not exists (
        select 1 from lesson_block_revisions where id = new.draft_revision_id and block_id = new.id
    )) or (new.published_revision_id is not null and not exists (
        select 1 from lesson_block_revisions where id = new.published_revision_id and block_id = new.id
    )) or (new.pending_revision_id is not null and not exists (
        select 1 from lesson_block_revisions where id = new.pending_revision_id and block_id = new.id
    ))
) begin
    select raise(abort, 'lesson block revision is outside its block');
end;

create trigger lesson_blocks_revision_scope_update
before update of draft_revision_id, published_revision_id, pending_revision_id on lesson_blocks
for each row when (
    (new.draft_revision_id is not null and not exists (
        select 1 from lesson_block_revisions where id = new.draft_revision_id and block_id = new.id
    )) or (new.published_revision_id is not null and not exists (
        select 1 from lesson_block_revisions where id = new.published_revision_id and block_id = new.id
    )) or (new.pending_revision_id is not null and not exists (
        select 1 from lesson_block_revisions where id = new.pending_revision_id and block_id = new.id
    ))
) begin
    select raise(abort, 'lesson block revision is outside its block');
end;
