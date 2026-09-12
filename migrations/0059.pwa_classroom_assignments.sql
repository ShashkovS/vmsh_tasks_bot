-- depends: 0058.pwa_classroom_layouts

-- Phase 7C: one versioned student-assignment plan per in-person event.
create table classroom_assignment_plans
(
    id                   integer primary key,
    public_id text generated always as ('cap-' || id) virtual,
    in_person_event_id   integer not null references in_person_events (id),
    layout_version_id    integer not null,
    base_plan_id         integer references classroom_assignment_plans (id),
    state                text    not null
        check (state in ('draft', 'confirmed', 'stale', 'superseded')),
    stale_reason         text,
    created_by_user_id   integer not null references users (id),
    confirmed_by_user_id integer references users (id),
    created_at           text    not null,
    updated_at           text    not null,
    confirmed_at         text,
    superseded_at        text,
    version              integer not null default 1 check (version > 0),
    unique (id, in_person_event_id),
    foreign key (layout_version_id, in_person_event_id)
        references classroom_layout_versions (id, in_person_event_id),
    check (updated_at >= created_at),
    check (
        (state in ('draft', 'stale')
            and confirmed_by_user_id is null
            and confirmed_at is null
            and superseded_at is null)
        or (state = 'confirmed'
            and confirmed_by_user_id is not null
            and confirmed_at is not null
            and superseded_at is null)
        or (state = 'superseded'
            and confirmed_by_user_id is not null
            and confirmed_at is not null
            and superseded_at is not null)
    )
);

create unique index classroom_assignment_plans_one_working_uq
    on classroom_assignment_plans (in_person_event_id)
    where state in ('draft', 'stale');

create unique index classroom_assignment_plans_one_confirmed_uq
    on classroom_assignment_plans (in_person_event_id)
    where state = 'confirmed';

create index classroom_assignment_plans_event_timeline_idx
    on classroom_assignment_plans (in_person_event_id, id);

create table classroom_assignments
(
    plan_id              integer not null references classroom_assignment_plans (id),
    course_enrollment_id integer not null references course_enrollments (id),
    group_lesson_id      integer not null references group_lessons (id),
    group_id             text    not null,
    classroom_id         integer references classrooms (id),
    status               text    not null
        check (status in ('assigned', 'reassigning')),
    source               text    not null
        check (source in (
            'previous-room', 'least-loaded', 'manual',
            'group-change', 'mode-change', 'import'
        )),
    created_at           text    not null,
    updated_at           text    not null,
    primary key (plan_id, course_enrollment_id),
    check (updated_at >= created_at),
    check (
        (status = 'assigned' and classroom_id is not null)
        or (status = 'reassigning' and classroom_id is null)
    )
);

create index classroom_assignments_enrollment_history_idx
    on classroom_assignments (course_enrollment_id, plan_id);

create index classroom_assignments_room_idx
    on classroom_assignments (plan_id, classroom_id, course_enrollment_id);

create trigger classroom_assignments_insert_working_only
before insert on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = new.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

create trigger classroom_assignments_update_working_only
before update on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

create trigger classroom_assignments_delete_working_only
before delete on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;
