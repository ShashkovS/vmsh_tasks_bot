-- depends: 0056.pwa_support_threads

-- Phase 7A: a small global catalog of classroom names. Layouts and student
-- assignments arrive in later migrations and reference these stable rows.
create table classrooms
(
    id                 integer primary key,
    public_id text generated always as ('room-' || id) virtual,
    name               text    not null
        check (name = trim(name) and length(name) between 1 and 200),
    normalized_name    text    not null unique
        check (length(normalized_name) between 1 and 200),
    status             text    not null default 'active'
        check (status in ('active', 'archived')),
    created_by_user_id integer not null references users (id),
    updated_by_user_id integer not null references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    check (updated_at >= created_at)
);

create index classrooms_status_name_idx
    on classrooms (status, normalized_name, id);

create trigger classrooms_delete_forbidden
before delete on classrooms
for each row
begin
    select raise(abort, 'classroom deletion is forbidden');
end;

-- Renames and visibility changes are rare, so an explicit append-only row is
-- clearer than a generic audit framework. The current projection stays small.
create table classroom_events
(
    id                     integer primary key,
    public_id text generated always as ('ce-' || id) virtual,
    classroom_id           integer not null references classrooms (id),
    action                 text    not null
        check (action in ('created', 'renamed', 'archived', 'restored')),
    before_name            text,
    before_normalized_name text,
    before_status          text check (
        before_status is null or before_status in ('active', 'archived')
    ),
    after_name             text    not null,
    after_normalized_name  text    not null,
    after_status           text    not null
        check (after_status in ('active', 'archived')),
    version_after          integer not null check (version_after > 0),
    actor_user_id          integer not null references users (id),
    request_id             text    not null check (length(trim(request_id)) > 0),
    created_at             text    not null,
    check (
        (action = 'created' and before_name is null
                            and before_normalized_name is null
                            and before_status is null)
        or (action <> 'created' and before_name is not null
                               and before_normalized_name is not null
                               and before_status is not null)
    )
);

create index classroom_events_timeline_idx
    on classroom_events (classroom_id, id);

create trigger classroom_events_immutable_update
before update on classroom_events
for each row
begin
    select raise(abort, 'classroom event is immutable');
end;

create trigger classroom_events_delete_forbidden
before delete on classroom_events
for each row
begin
    select raise(abort, 'classroom event deletion is forbidden');
end;
