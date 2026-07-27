-- depends: 0042.pwa_content_concurrency

-- Lesson-window rows retain a small optimistic current projection.  This
-- append-only journal preserves the exact before/after state for the two
-- independently confirmed operations required by SCHEDULE-01: ordinary
-- schedule edits and submission-cutoff changes.
create table lesson_window_changes
(
    id                integer primary key,
    public_id         text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    lesson_window_id  integer not null references lesson_windows (id),
    change_kind       text    not null
        check (change_kind in (
            'created', 'schedule_changed', 'submission_cutoff_changed'
        )),
    before_json       text
        check (before_json is null or json_valid(before_json) = 1),
    after_json        text    not null check (json_valid(after_json) = 1),
    actor_user_id     integer not null references users (id),
    request_id        text    not null check (length(trim(request_id)) > 0),
    created_at        text    not null,
    check (
        (change_kind = 'created' and before_json is null)
        or (change_kind <> 'created' and before_json is not null)
    )
);

create index lesson_window_changes_timeline_idx
    on lesson_window_changes (lesson_window_id, id);

create trigger lesson_window_changes_immutable_update
before update on lesson_window_changes
for each row
begin
    select raise(abort, 'lesson window audit is immutable');
end;

create trigger lesson_window_changes_delete_forbidden
before delete on lesson_window_changes
for each row
begin
    select raise(abort, 'lesson window audit deletion is forbidden');
end;
