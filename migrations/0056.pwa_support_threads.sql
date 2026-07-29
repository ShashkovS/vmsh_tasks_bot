-- depends: 0055.pwa_submission_review_student_reactions

-- Phase 6P: private Student/Staff question threads. New PWA questions no
-- longer depend on magic negative problem IDs. Telegram ``questions`` rows
-- remain a legacy adapter until the separately tested dual-write increment.
-- Authoritative contracts:
-- vmshpwa/dev/development-plan/02-data-model.md, `support_threads` and
-- vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md, Questions/SOS.
create table support_threads
(
    id                integer primary key,
    public_id         text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id   integer not null references users (id),
    problem_id        integer references problems (id),
    group_lesson_id   integer references group_lessons (id),
    kind              text    not null
        check (kind in ('problem_question', 'sos', 'general')),
    latest_entry_at   text    not null,
    created_at        text    not null,
    updated_at        text    not null,
    version           integer not null default 1 check (version > 0),
    check (latest_entry_at >= created_at),
    check (updated_at >= created_at),
    check (
        (kind = 'problem_question' and problem_id is not null and group_lesson_id is not null)
        or (kind = 'general' and problem_id is null and group_lesson_id is not null)
        or (kind = 'sos' and problem_id is null)
    )
);

create unique index support_threads_problem_question_uq
    on support_threads (student_user_id, group_lesson_id, problem_id)
    where kind = 'problem_question';

create unique index support_threads_general_question_uq
    on support_threads (student_user_id, group_lesson_id)
    where kind = 'general';

create index support_threads_student_timeline_idx
    on support_threads (student_user_id, latest_entry_at desc, id desc);

create index support_threads_staff_timeline_idx
    on support_threads (group_lesson_id, latest_entry_at desc, id desc);

create trigger support_threads_problem_scope_insert
before insert on support_threads
for each row
when new.kind = 'problem_question' and not exists (
    select 1
    from problem_revisions as problem_revision
    join content_revisions as revision
      on revision.id = problem_revision.content_revision_id
    join content_sources as source on source.id = revision.source_id
    where problem_revision.problem_id = new.problem_id
      and source.group_lesson_id = new.group_lesson_id
)
begin
    select raise(abort, 'support problem is outside group lesson scope');
end;

create trigger support_threads_identity_immutable
before update on support_threads
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.group_lesson_id is not old.group_lesson_id
    or new.kind is not old.kind
    or new.created_at is not old.created_at
begin
    select raise(abort, 'support thread identity is immutable');
end;

create trigger support_threads_version_guard
before update on support_threads
for each row
when new.version <> old.version + 1
    or new.updated_at < old.updated_at
    or new.latest_entry_at < old.latest_entry_at
begin
    select raise(abort, 'support thread update requires next version and monotonic time');
end;

create trigger support_threads_delete_forbidden
before delete on support_threads
for each row
begin
    select raise(abort, 'support thread deletion is forbidden');
end;

create table support_entries
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    thread_id          integer not null references support_threads (id),
    author_kind        text    not null
        check (author_kind in ('student', 'teacher', 'admin', 'system')),
    author_user_id     integer references users (id),
    text               text check (text is null or length(text) <= 100000),
    asset_id           integer references media_assets (id),
    channel            text    not null
        check (channel in ('pwa', 'telegram', 'staff', 'system')),
    client_created_at  text,
    server_received_at text    not null,
    idempotency_key    text
        check (
            idempotency_key is null
            or (
                length(idempotency_key) between 1 and 200
                and idempotency_key = trim(idempotency_key)
            )
        ),
    payload_sha256     text
        check (
            payload_sha256 is null
            or (
                length(payload_sha256) = 64
                and payload_sha256 not glob '*[^0-9a-f]*'
            )
        ),
    legacy_question_id integer references questions (id),
    legacy_problem_id  integer,
    created_at         text    not null,
    check ((idempotency_key is null) = (payload_sha256 is null)),
    check (text is not null or asset_id is not null),
    check (text is null or length(trim(text)) > 0),
    check (
        (author_kind in ('student', 'teacher', 'admin') and author_user_id is not null)
        or (author_kind = 'system' and author_user_id is null)
    ),
    check (
        (author_kind = 'student' and channel in ('pwa', 'telegram'))
        or (author_kind in ('teacher', 'admin') and channel in ('staff', 'telegram'))
        or (author_kind = 'system' and channel = 'system')
    ),
    check (server_received_at >= created_at)
);

create unique index support_entries_author_idempotency_uq
    on support_entries (author_user_id, idempotency_key)
    where idempotency_key is not null;

create index support_entries_thread_timeline_idx
    on support_entries (thread_id, server_received_at, id);

create index support_entries_legacy_question_idx
    on support_entries (legacy_question_id, id)
    where legacy_question_id is not null;

create trigger support_entries_author_scope_insert
before insert on support_entries
for each row
when (
    new.author_kind = 'student'
    and not exists (
        select 1 from support_threads as thread
        where thread.id = new.thread_id
          and thread.student_user_id = new.author_user_id
    )
) or (
    new.author_kind in ('teacher', 'admin')
    and exists (
        select 1 from support_threads as thread
        where thread.id = new.thread_id
          and thread.student_user_id = new.author_user_id
    )
)
begin
    select raise(abort, 'support entry author is outside thread scope');
end;

create trigger support_entries_asset_scope_insert
before insert on support_entries
for each row
when new.asset_id is not null and not exists (
    select 1 from media_assets as asset
    where asset.id = new.asset_id
      and asset.storage_namespace = 'submission'
      and asset.deleted_at is null
)
begin
    select raise(abort, 'support entry asset is unavailable');
end;

create trigger support_entries_identity_immutable
before update on support_entries
for each row
begin
    select raise(abort, 'support entry is immutable');
end;

create trigger support_entries_delete_forbidden
before delete on support_entries
for each row
begin
    select raise(abort, 'support entry deletion is forbidden');
end;
