-- depends: 0077.pwa_course_runtime_settings

-- This rollback intentionally fails if lesson 0 data already exists: such data
-- cannot be represented by the previous schema without destructive deletion.
pragma legacy_alter_table = on;

alter table student_lesson_metrics rename to student_lesson_metrics_with_zero;

create table student_lesson_metrics
(
    run_id               integer not null references analytics_runs (id) on delete cascade,
    student_user_id      integer not null references users (id),
    lesson_number        integer not null check (lesson_number > 0),
    group_id             text    not null references groups (group_id),
    simple_strength      real    not null check (simple_strength between 0 and 10),
    complex_strength     real    not null check (complex_strength between 0 and 10),
    max_complex_strength real    not null check (max_complex_strength between 0 and 10),
    solved_items         integer not null check (solved_items >= 0),
    total_items          integer not null check (total_items >= 0),
    primary key (run_id, student_user_id, lesson_number),
    check (complex_strength <= max_complex_strength),
    check (solved_items <= total_items)
);

insert into student_lesson_metrics
    (run_id, student_user_id, lesson_number, group_id, simple_strength,
     complex_strength, max_complex_strength, solved_items, total_items)
select run_id, student_user_id, lesson_number, group_id, simple_strength,
       complex_strength, max_complex_strength, solved_items, total_items
from student_lesson_metrics_with_zero;

drop table student_lesson_metrics_with_zero;

create index student_lesson_metrics_student_run_idx
    on student_lesson_metrics (student_user_id, run_id, lesson_number);

alter table course_lessons rename to course_lessons_with_zero;

create table course_lessons
(
    id                 integer primary key,
    public_id text generated always as ('cl-' || id) virtual,
    course_id          integer not null references courses (id),
    lesson_number      integer not null check (lesson_number > 0),
    title              text check (title is null or length(trim(title)) > 0),
    created_by_user_id integer references users (id),
    updated_by_user_id integer references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    unique (course_id, lesson_number),
    unique (id, course_id)
);

insert into course_lessons
    (id, course_id, lesson_number, title, created_by_user_id,
     updated_by_user_id, created_at, updated_at, version)
select id, course_id, lesson_number, title, created_by_user_id,
       updated_by_user_id, created_at, updated_at, version
from course_lessons_with_zero;

drop table course_lessons_with_zero;

create index course_lessons_course_number_idx
    on course_lessons (course_id, lesson_number, id);

pragma legacy_alter_table = off;
