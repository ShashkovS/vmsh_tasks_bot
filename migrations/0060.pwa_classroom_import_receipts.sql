-- depends: 0059.pwa_classroom_assignments

-- One receipt per one-time Excel import. The source rows stay outside SQLite;
-- this table only proves which reviewed input created the confirmed snapshots.
create table classroom_import_receipts
(
    id                    integer primary key,
    public_id             text    not null unique,
    in_person_event_id    integer not null unique references in_person_events (id),
    source_sha256         text    not null check (length(source_sha256) = 64),
    preview_sha256        text    not null check (length(preview_sha256) = 64),
    source_sheet          text    not null check (length(trim(source_sheet)) > 0),
    source_row_count      integer not null check (source_row_count >= 0),
    classroom_count       integer not null check (classroom_count >= 0),
    assignment_count      integer not null check (assignment_count >= 0),
    layout_version_id     integer not null references classroom_layout_versions (id),
    assignment_plan_id    integer not null references classroom_assignment_plans (id),
    actor_user_id         integer not null references users (id),
    applied_at            text    not null
);
