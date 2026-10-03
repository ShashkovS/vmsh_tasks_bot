-- depends: 0096.pwa_test_attempt_result_lookup

-- docs/requirements/04_admin_requirements.md: a manual Staff move is a durable
-- preference, not merely a property of one generated assignment plan.
-- Recalculation may replace plan rows, while this record survives until
-- another manual move supersedes it.
create table classroom_assignment_preferences
(
    course_enrollment_id integer primary key references course_enrollments (id),
    classroom_id         integer not null references classrooms (id),
    set_by_user_id       integer not null references users (id),
    created_at           text    not null,
    updated_at           text    not null,
    version              integer not null default 1 check (version > 0),
    check (updated_at >= created_at)
);

create index classroom_assignment_preferences_room_idx
    on classroom_assignment_preferences (classroom_id, course_enrollment_id);

-- Preserve explicit choices made before this preference table existed.  A
-- group-change assignment is also an explicit Staff room choice.
with ranked_preferences as (
    select assignment.course_enrollment_id,
           assignment.classroom_id,
           coalesce(plan.confirmed_by_user_id, plan.created_by_user_id) as actor_user_id,
           assignment.updated_at,
           row_number() over (
               partition by assignment.course_enrollment_id
               order by assignment.updated_at desc, plan.id desc
           ) as preference_rank
    from classroom_assignments assignment
    join classroom_assignment_plans plan on plan.id = assignment.plan_id
    where assignment.source in ('manual', 'group-change')
      and assignment.classroom_id is not null
)
insert into classroom_assignment_preferences
    (course_enrollment_id, classroom_id, set_by_user_id, created_at, updated_at)
select course_enrollment_id, classroom_id, actor_user_id, updated_at, updated_at
from ranked_preferences
where preference_rank = 1;
