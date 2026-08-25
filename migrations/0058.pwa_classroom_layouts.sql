-- depends: 0057.pwa_classroom_catalog

-- Phase 7B: an in-person event selects concrete group lessons. A layout is
-- versioned for that event; student assignments are added separately.
create table in_person_events
(
    id                 integer primary key,
    public_id text generated always as ('ipe-' || id) virtual,
    season_id          integer not null references seasons (id),
    name               text    not null check (length(trim(name)) > 0),
    starts_at          text    not null,
    ends_at            text    not null,
    status             text    not null default 'draft'
        check (status in ('draft', 'scheduled', 'completed', 'cancelled')),
    created_by_user_id integer not null references users (id),
    updated_by_user_id integer not null references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    check (ends_at > starts_at),
    check (updated_at >= created_at)
);

create index in_person_events_season_time_idx
    on in_person_events (season_id, starts_at, id);

create table in_person_event_group_lessons
(
    in_person_event_id integer not null references in_person_events (id),
    group_lesson_id    integer not null references group_lessons (id),
    added_by_user_id   integer not null references users (id),
    created_at         text    not null,
    primary key (in_person_event_id, group_lesson_id)
);

create index in_person_event_group_lessons_lesson_idx
    on in_person_event_group_lessons (group_lesson_id, in_person_event_id);

create table classroom_layout_versions
(
    id                   integer primary key,
    public_id text generated always as ('clv-' || id) virtual,
    in_person_event_id   integer not null references in_person_events (id),
    base_version_id      integer references classroom_layout_versions (id),
    state                text    not null
        check (state in ('draft', 'confirmed', 'superseded')),
    created_by_user_id   integer not null references users (id),
    confirmed_by_user_id integer references users (id),
    created_at           text    not null,
    updated_at           text    not null,
    confirmed_at         text,
    superseded_at        text,
    version              integer not null default 1 check (version > 0),
    unique (id, in_person_event_id),
    check (updated_at >= created_at),
    check (
        (state = 'draft' and confirmed_by_user_id is null
                         and confirmed_at is null
                         and superseded_at is null)
        or (state = 'confirmed' and confirmed_by_user_id is not null
                             and confirmed_at is not null
                             and superseded_at is null)
        or (state = 'superseded' and confirmed_by_user_id is not null
                              and confirmed_at is not null
                              and superseded_at is not null)
    )
);

create unique index classroom_layout_versions_one_draft_uq
    on classroom_layout_versions (in_person_event_id)
    where state = 'draft';

create unique index classroom_layout_versions_one_confirmed_uq
    on classroom_layout_versions (in_person_event_id)
    where state = 'confirmed';

create index classroom_layout_versions_event_timeline_idx
    on classroom_layout_versions (in_person_event_id, id);

create table classroom_layout_rooms
(
    layout_version_id       integer not null references classroom_layout_versions (id),
    classroom_id            integer not null references classrooms (id),
    group_lesson_id         integer not null references group_lessons (id),
    source_layout_version_id integer references classroom_layout_versions (id),
    created_at              text    not null,
    updated_at              text    not null,
    primary key (layout_version_id, classroom_id),
    check (updated_at >= created_at)
);

create index classroom_layout_rooms_group_idx
    on classroom_layout_rooms (layout_version_id, group_lesson_id, classroom_id);

-- Once a layout is confirmed its room mapping is historical evidence. Only a
-- draft can be edited; state changes themselves remain explicit operations.
create trigger classroom_layout_rooms_insert_draft_only
before insert on classroom_layout_rooms
for each row
when (select state from classroom_layout_versions where id = new.layout_version_id) <> 'draft'
begin
    select raise(abort, 'only a draft classroom layout can be edited');
end;

create trigger classroom_layout_rooms_update_draft_only
before update on classroom_layout_rooms
for each row
when (select state from classroom_layout_versions where id = old.layout_version_id) <> 'draft'
begin
    select raise(abort, 'only a draft classroom layout can be edited');
end;

create trigger classroom_layout_rooms_delete_draft_only
before delete on classroom_layout_rooms
for each row
when (select state from classroom_layout_versions where id = old.layout_version_id) <> 'draft'
begin
    select raise(abort, 'only a draft classroom layout can be edited');
end;
