-- depends: 0106.pwa_figure_presentation
-- vmshpwa/docs/problem-release.md: independent, group-owned PWA visibility.
alter table group_lessons add column problem_release_version integer not null default 1
    check (problem_release_version > 0);

create table lesson_problem_release (
    group_lesson_id integer not null references group_lessons(id),
    problem_id integer not null references problems(id),
    is_open integer not null check (is_open in (0, 1)),
    primary key (group_lesson_id, problem_id)
);

create table lesson_problem_release_events (
    id integer primary key,
    group_lesson_id integer not null references group_lessons(id),
    condition_revision_id integer not null references content_revisions(id),
    version integer not null,
    before_json text not null check (json_valid(before_json)),
    after_json text not null check (json_valid(after_json)),
    actor_user_id integer not null references users(id),
    request_id text not null,
    ts text not null
);

create trigger lesson_problem_release_events_no_update
before update on lesson_problem_release_events begin
    select raise(abort, 'problem release audit is immutable');
end;
create trigger lesson_problem_release_events_no_delete
before delete on lesson_problem_release_events begin
    select raise(abort, 'problem release audit is immutable');
end;
