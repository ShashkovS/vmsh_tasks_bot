-- depends: 0083.pwa_content_figure_scales
create table course_problem_difficulty (
    course_id integer not null references courses(id),
    logical_key text not null,
    for_weak real not null check(for_weak between 0 and 1),
    for_strong real not null check(for_strong between 0 and 1),
    primary key(course_id, logical_key)
);
create table course_student_strength (
    course_id integer not null references courses(id),
    student_user_id integer not null references users(id),
    simple real not null check(simple between 0 and 1),
    complex real not null check(complex between 0 and 1),
    primary key(course_id, student_user_id)
);
alter table student_lesson_metrics add column simple_smooth real check(simple_smooth between 0 and 10);
alter table student_lesson_metrics add column complex_smooth real check(complex_smooth between 0 and 10);
