-- depends: 0071.pwa_oral_results_idempotency

create table analytics_runs
(
    id                      integer primary key,
    public_id               text    not null unique,
    course_id               integer not null references courses (id),
    algorithm               text    not null,
    algorithm_version       text    not null,
    input_through_result_id integer not null check (input_through_result_id >= 0),
    state                   text    not null check (state in ('running', 'completed', 'failed')),
    started_at              text    not null,
    completed_at            text,
    diagnostics_json        text    not null default '[]'
        check (json_valid(diagnostics_json) = 1 and json_type(diagnostics_json) = 'array'),
    check (
        (state = 'running' and completed_at is null)
        or (state in ('completed', 'failed') and completed_at is not null)
    )
);

create index analytics_runs_course_latest_idx
    on analytics_runs (course_id, state, completed_at desc, id desc);

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

create index student_lesson_metrics_student_run_idx
    on student_lesson_metrics (student_user_id, run_id, lesson_number);
