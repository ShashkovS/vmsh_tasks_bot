-- depends: 0073.pwa_course_achievements

create table problem_import_receipts
(
    id                     integer primary key,
    public_id              text    not null unique,
    course_id              integer not null references courses (id),
    source_filename        text    not null check (length(trim(source_filename)) > 0),
    source_sha256          text    not null check (length(source_sha256) = 64),
    preview_sha256         text    not null check (length(preview_sha256) = 64),
    state                  text    not null check (state in ('applied', 'rolled_back')),
    summary_json           text    not null
        check (json_valid(summary_json) = 1 and json_type(summary_json) = 'object'),
    changes_json           text    not null
        check (json_valid(changes_json) = 1 and json_type(changes_json) = 'array'),
    applied_by_user_id     integer not null references users (id),
    applied_at             text    not null,
    rolled_back_by_user_id integer references users (id),
    rolled_back_at         text,
    version                integer not null default 1 check (version > 0),
    unique (course_id, source_sha256, preview_sha256),
    check (
        (state = 'applied' and rolled_back_by_user_id is null and rolled_back_at is null)
        or (state = 'rolled_back' and rolled_back_by_user_id is not null and rolled_back_at is not null)
    )
);

create index problem_import_receipts_course_idx
    on problem_import_receipts (course_id, applied_at desc, id desc);
