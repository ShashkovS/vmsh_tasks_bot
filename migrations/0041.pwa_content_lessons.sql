-- depends: 0040.pwa_courses_access

-- Phase 2 versioned lesson/content storage. Authoritative contracts:
-- vmshpwa/dev/development-plan/06-phase-2-content.md and
-- vmshpwa/dev/development-plan/02-data-model.md, section 2.
-- This migration is additive: legacy lessons/problems and their integer IDs
-- remain untouched until the separately rehearsed Phase-11 backfill.

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

create index course_lessons_course_number_idx
    on course_lessons (course_id, lesson_number, id);

-- course_id is an intentional ownership key: the composite foreign keys make
-- it impossible to attach a group from another course to the shared lesson.
create table group_lessons
(
    id                 integer primary key,
    public_id text generated always as ('gl-' || id) virtual,
    course_lesson_id   integer not null,
    course_id          integer not null references courses (id),
    group_id           text    not null,
    cycle_anchor_date  text    not null
        check (
            length(cycle_anchor_date) = 10
            and date(cycle_anchor_date) is not null
            and date(cycle_anchor_date) = cycle_anchor_date
        ),
    business_timezone text    not null check (length(trim(business_timezone)) > 0),
    status             text    not null default 'draft'
        check (status in ('draft', 'active', 'archived')),
    created_by_user_id integer references users (id),
    updated_by_user_id integer references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    unique (course_lesson_id, group_id),
    unique (id, course_lesson_id),
    foreign key (course_lesson_id, course_id)
        references course_lessons (id, course_id),
    foreign key (course_id, group_id)
        references groups (course_id, group_id)
);

create index group_lessons_course_group_idx
    on group_lessons (course_id, group_id, course_lesson_id, id);

-- Rules are append-versioned. Staff creates a draft and confirms it in a
-- transaction which supersedes the previous active row; already materialized
-- lesson_windows keep their timestamps and provenance unchanged.
create table course_schedule_rules
(
    id                 integer primary key,
    public_id text generated always as ('sr-' || id) virtual,
    course_id          integer not null references courses (id),
    schedule_field     text    not null
        check (schedule_field in (
            'opens_at', 'hint_scheduled_at',
            'submission_closes_at', 'solution_scheduled_at'
        )),
    rule_version       integer not null check (rule_version > 0),
    day_offset         integer not null,
    local_time         text    not null
        check (
            length(local_time) in (5, 8)
            and local_time glob '[0-2][0-9]:[0-5][0-9]*'
            and cast(substr(local_time, 1, 2) as integer) between 0 and 23
            and (
                length(local_time) = 5
                or (
                    substr(local_time, 6, 1) = ':'
                    and substr(local_time, 7, 2) glob '[0-5][0-9]'
                )
            )
        ),
    timezone           text    not null check (length(trim(timezone)) > 0),
    state              text    not null check (state in ('draft', 'active', 'superseded')),
    created_by_user_id integer references users (id),
    confirmed_by_user_id integer references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    confirmed_at       text,
    superseded_at      text,
    version            integer not null default 1 check (version > 0),
    unique (course_id, schedule_field, rule_version),
    check (
        (confirmed_by_user_id is null and confirmed_at is null)
        or (confirmed_by_user_id is not null and confirmed_at is not null)
    ),
    check ((state = 'draft') = (confirmed_at is null)),
    check ((state = 'superseded') = (superseded_at is not null))
);

create unique index course_schedule_rules_one_draft_uq
    on course_schedule_rules (course_id, schedule_field)
    where state = 'draft';

create unique index course_schedule_rules_one_active_uq
    on course_schedule_rules (course_id, schedule_field)
    where state = 'active';

create index course_schedule_rules_history_idx
    on course_schedule_rules (course_id, schedule_field, rule_version, id);

create trigger course_schedule_rules_payload_immutable
before update on course_schedule_rules
for each row
when new.public_id is not old.public_id
    or new.course_id is not old.course_id
    or new.schedule_field is not old.schedule_field
    or new.rule_version is not old.rule_version
    or new.day_offset is not old.day_offset
    or new.local_time is not old.local_time
    or new.timezone is not old.timezone
    or new.created_by_user_id is not old.created_by_user_id
    or new.created_at is not old.created_at
begin
    select raise(abort, 'course schedule rule payload is immutable');
end;

create trigger course_schedule_rules_state_transition_guard
before update on course_schedule_rules
for each row
when not (
    (
        old.state = 'draft'
        and new.state = 'active'
        and new.confirmed_by_user_id is not null
        and new.confirmed_at is not null
        and new.superseded_at is null
        and new.version = old.version + 1
    )
    or (
        old.state = 'active'
        and new.state = 'superseded'
        and new.confirmed_by_user_id is old.confirmed_by_user_id
        and new.confirmed_at is old.confirmed_at
        and new.superseded_at is not null
        and new.version = old.version + 1
    )
)
begin
    select raise(abort, 'invalid course schedule rule state transition');
end;

create trigger course_schedule_rules_delete_forbidden
before delete on course_schedule_rules
for each row
begin
    select raise(abort, 'course schedule rule deletion is forbidden');
end;

create table group_schedule_overrides
(
    id                         integer primary key,
    public_id text generated always as ('so-' || id) virtual,
    course_id                  integer not null references courses (id),
    group_id                   text    not null,
    schedule_field             text    not null
        check (schedule_field in (
            'opens_at', 'hint_scheduled_at',
            'submission_closes_at', 'solution_scheduled_at'
        )),
    override_version           integer not null check (override_version > 0),
    mode                       text    not null
        check (mode in ('inherit', 'override', 'disabled')),
    day_offset                 integer,
    local_time                 text
        check (
            local_time is null
            or (
                length(local_time) in (5, 8)
                and local_time glob '[0-2][0-9]:[0-5][0-9]*'
                and cast(substr(local_time, 1, 2) as integer) between 0 and 23
                and (
                    length(local_time) = 5
                    or (
                        substr(local_time, 6, 1) = ':'
                        and substr(local_time, 7, 2) glob '[0-5][0-9]'
                    )
                )
            )
        ),
    timezone                   text check (timezone is null or length(trim(timezone)) > 0),
    based_on_schedule_rule_id  integer not null references course_schedule_rules (id),
    state                      text    not null
        check (state in ('draft', 'active', 'superseded')),
    created_by_user_id         integer references users (id),
    confirmed_by_user_id       integer references users (id),
    created_at                 text    not null,
    updated_at                 text    not null,
    confirmed_at               text,
    superseded_at              text,
    version                    integer not null default 1 check (version > 0),
    unique (course_id, group_id, schedule_field, override_version),
    foreign key (course_id, group_id) references groups (course_id, group_id),
    check (
        (mode = 'override' and day_offset is not null and local_time is not null and timezone is not null)
        or (mode <> 'override' and day_offset is null and local_time is null and timezone is null)
    ),
    check (schedule_field <> 'submission_closes_at' or mode <> 'disabled'),
    check (
        (confirmed_by_user_id is null and confirmed_at is null)
        or (confirmed_by_user_id is not null and confirmed_at is not null)
    ),
    check ((state = 'draft') = (confirmed_at is null)),
    check ((state = 'superseded') = (superseded_at is not null))
);

create unique index group_schedule_overrides_one_draft_uq
    on group_schedule_overrides (course_id, group_id, schedule_field)
    where state = 'draft';

create unique index group_schedule_overrides_one_active_uq
    on group_schedule_overrides (course_id, group_id, schedule_field)
    where state = 'active';

create index group_schedule_overrides_history_idx
    on group_schedule_overrides
       (course_id, group_id, schedule_field, override_version, id);

create trigger group_schedule_overrides_rule_scope_insert
before insert on group_schedule_overrides
for each row
when not exists (
    select 1 from course_schedule_rules as schedule_rule
    where schedule_rule.id = new.based_on_schedule_rule_id
      and schedule_rule.course_id = new.course_id
      and schedule_rule.schedule_field = new.schedule_field
      and schedule_rule.state = 'active'
)
begin
    select raise(abort, 'group schedule override base rule is outside its scope');
end;

create trigger group_schedule_overrides_payload_immutable
before update on group_schedule_overrides
for each row
when new.public_id is not old.public_id
    or new.course_id is not old.course_id
    or new.group_id is not old.group_id
    or new.schedule_field is not old.schedule_field
    or new.override_version is not old.override_version
    or new.mode is not old.mode
    or new.day_offset is not old.day_offset
    or new.local_time is not old.local_time
    or new.timezone is not old.timezone
    or new.based_on_schedule_rule_id is not old.based_on_schedule_rule_id
    or new.created_by_user_id is not old.created_by_user_id
    or new.created_at is not old.created_at
begin
    select raise(abort, 'group schedule override payload is immutable');
end;

create trigger group_schedule_overrides_state_transition_guard
before update on group_schedule_overrides
for each row
when not (
    (
        old.state = 'draft'
        and new.state = 'active'
        and new.confirmed_by_user_id is not null
        and new.confirmed_at is not null
        and new.superseded_at is null
        and new.version = old.version + 1
    )
    or (
        old.state = 'active'
        and new.state = 'superseded'
        and new.confirmed_by_user_id is old.confirmed_by_user_id
        and new.confirmed_at is old.confirmed_at
        and new.superseded_at is not null
        and new.version = old.version + 1
    )
)
begin
    select raise(abort, 'invalid group schedule override state transition');
end;

create trigger group_schedule_overrides_rule_active_confirm
before update of state on group_schedule_overrides
for each row
when new.state = 'active' and not exists (
    select 1 from course_schedule_rules as schedule_rule
    where schedule_rule.id = new.based_on_schedule_rule_id
      and schedule_rule.course_id = new.course_id
      and schedule_rule.schedule_field = new.schedule_field
      and schedule_rule.state = 'active'
)
begin
    select raise(abort, 'group schedule override base rule is stale');
end;

create trigger group_schedule_overrides_delete_forbidden
before delete on group_schedule_overrides
for each row
begin
    select raise(abort, 'group schedule override deletion is forbidden');
end;

create table content_sources
(
    id                 integer primary key,
    public_id text generated always as ('cs-' || id) virtual,
    group_lesson_id    integer not null references group_lessons (id),
    kind               text    not null
        check (kind in ('condition', 'hint', 'solution', 'teacher_note')),
    logical_filename   text    not null
        check (length(trim(logical_filename)) > 0),
    source_encoding    text    not null
        check (source_encoding in ('utf-8', 'cp1251')),
    created_by_user_id integer references users (id),
    created_at         text    not null,
    archived_at        text,
    unique (group_lesson_id, kind, logical_filename),
    check (archived_at is null or archived_at >= created_at)
);

create index content_sources_group_kind_idx
    on content_sources (group_lesson_id, kind, archived_at, id);

create table content_revisions
(
    id                      integer primary key,
    public_id text generated always as ('cr-' || id) virtual,
    source_id               integer not null references content_sources (id),
    revision_number         integer not null check (revision_number > 0),
    source_sha256           text    not null
        check (
            length(source_sha256) = 64
            and source_sha256 not glob '*[^0-9a-f]*'
        ),
    latex_text              text    not null,
    parser_version          text    not null
        check (length(trim(parser_version)) > 0),
    status                  text    not null
        check (status in ('uploaded', 'compiling', 'ready', 'invalid', 'superseded')),
    canonical_json          text
        check (
            canonical_json is null
            or (
                json_valid(canonical_json) = 1
                and json_type(canonical_json) in ('object', 'array')
            )
        ),
    diagnostics_json        text    not null default '[]'
        check (json_valid(diagnostics_json) = 1 and json_type(diagnostics_json) = 'array'),
    provenance_json         text    not null
        check (json_valid(provenance_json) = 1 and json_type(provenance_json) = 'object'),
    created_by_user_id      integer references users (id),
    created_at              text    not null,
    supersedes_revision_id  integer references content_revisions (id),
    version                 integer not null default 1 check (version > 0),
    unique (source_id, revision_number),
    unique (source_id, source_sha256),
    check (supersedes_revision_id is null or supersedes_revision_id <> id),
    check (status <> 'ready' or canonical_json is not null)
);

create index content_revisions_source_created_idx
    on content_revisions (source_id, revision_number, created_at, id);

create trigger content_revisions_lineage_insert
before insert on content_revisions
for each row
when new.supersedes_revision_id is not null and not exists (
    select 1 from content_revisions as previous
    where previous.id = new.supersedes_revision_id
      and previous.source_id = new.source_id
      and previous.revision_number < new.revision_number
)
begin
    select raise(abort, 'content revision predecessor is outside its source lineage');
end;

-- Source identity and bytes are immutable. Compiler-state fields may advance
-- under an optimistic version while an uploaded revision is being processed;
-- ready/invalid/superseded rows are terminal.
create trigger content_revisions_source_immutable
before update on content_revisions
for each row
when new.public_id is not old.public_id
    or new.source_id is not old.source_id
    or new.revision_number is not old.revision_number
    or new.source_sha256 is not old.source_sha256
    or new.latex_text is not old.latex_text
    or new.provenance_json is not old.provenance_json
    or new.created_by_user_id is not old.created_by_user_id
    or new.created_at is not old.created_at
    or new.supersedes_revision_id is not old.supersedes_revision_id
begin
    select raise(abort, 'content revision source is immutable');
end;

create trigger content_revisions_status_transition_guard
before update on content_revisions
for each row
when not (
    (old.status = 'uploaded' and new.status in ('uploaded', 'compiling', 'invalid'))
    or (old.status = 'compiling' and new.status in ('compiling', 'ready', 'invalid'))
    or (old.status = 'ready' and new.status in ('ready', 'superseded'))
    or (old.status = 'invalid' and new.status = 'invalid')
    or (old.status = 'superseded' and new.status = 'superseded')
)
begin
    select raise(abort, 'invalid content revision status transition');
end;

create trigger content_revisions_terminal_state_immutable
before update on content_revisions
for each row
when (
    old.status in ('invalid', 'superseded')
) or (
    old.status = 'ready'
    and not (
        new.status = 'superseded'
        and new.parser_version is old.parser_version
        and new.canonical_json is old.canonical_json
        and new.diagnostics_json is old.diagnostics_json
        and new.version = old.version + 1
    )
)
begin
    select raise(abort, 'terminal content revision is immutable');
end;

create trigger content_revisions_delete_forbidden
before delete on content_revisions
for each row
begin
    select raise(abort, 'content revision deletion is forbidden');
end;

create table media_assets
(
    id                 integer primary key,
    public_id text generated always as ('ma-' || id) virtual,
    sha256             text    not null
        check (length(sha256) = 64 and sha256 not glob '*[^0-9a-f]*'),
    storage_namespace  text    not null
        check (storage_namespace in ('content', 'submission', 'news', 'annotation', 'generated')),
    object_key         text    not null unique
        check (
            length(object_key) between 1 and 1024
            and object_key = trim(object_key)
            and substr(object_key, 1, 1) <> '/'
            and substr(object_key, -1, 1) <> '/'
            and instr(object_key, char(92)) = 0
            and instr(object_key, char(9)) = 0
            and instr(object_key, char(10)) = 0
            and instr(object_key, char(13)) = 0
            and instr('/' || object_key || '/', '/./') = 0
            and instr('/' || object_key || '/', '/../') = 0
            and instr(object_key, '//') = 0
        ),
    public_url         text,
    media_type         text    not null check (length(trim(media_type)) > 0),
    byte_size          integer not null check (byte_size > 0),
    width              integer check (width is null or width between 1 and 20000),
    height             integer check (height is null or height between 1 and 20000),
    source_filename    text,
    conversion_version text    not null default 'original'
        check (length(trim(conversion_version)) > 0),
    created_by_user_id integer references users (id),
    created_at         text    not null,
    immutable_at       text,
    deleted_at         text,
    check (immutable_at is null or immutable_at >= created_at),
    check (deleted_at is null or deleted_at >= created_at)
);

create unique index media_assets_content_hash_version_uq
    on media_assets (storage_namespace, sha256, conversion_version)
    where storage_namespace in ('content', 'generated') and deleted_at is null;

create index media_assets_namespace_created_idx
    on media_assets (storage_namespace, created_at, id);

create table content_revision_assets
(
    revision_id integer not null references content_revisions (id),
    asset_id    integer not null references media_assets (id),
    logical_name text   not null check (length(trim(logical_name)) > 0),
    role        text    not null
        check (role in ('source', 'figure', 'tikz', 'pdf', 'preview')),
    ordinal     integer not null default 0 check (ordinal >= 0),
    alt_text    text,
    created_at  text    not null,
    primary key (revision_id, logical_name, role)
);

create index content_revision_assets_asset_idx
    on content_revision_assets (asset_id, revision_id);

create trigger content_revision_assets_immutable_update
before update on content_revision_assets
for each row
begin
    select raise(abort, 'content revision asset is immutable');
end;

create trigger content_revision_assets_delete_forbidden
before delete on content_revision_assets
for each row
begin
    select raise(abort, 'content revision asset deletion is forbidden');
end;

create table content_derivatives
(
    id                 integer primary key,
    revision_id        integer not null references content_revisions (id),
    kind               text    not null
        check (kind in ('web_ast', 'web_html', 'telegram_html', 'pdf', 'thumbnail')),
    renderer_version   text    not null check (length(trim(renderer_version)) > 0),
    content_text       text,
    asset_id           integer references media_assets (id),
    sha256             text    not null
        check (length(sha256) = 64 and sha256 not glob '*[^0-9a-f]*'),
    diagnostics_json   text    not null default '[]'
        check (json_valid(diagnostics_json) = 1 and json_type(diagnostics_json) = 'array'),
    provenance_json    text    not null
        check (json_valid(provenance_json) = 1 and json_type(provenance_json) = 'object'),
    created_at         text    not null,
    invalidated_at     text,
    unique (revision_id, kind, renderer_version),
    check ((content_text is null) <> (asset_id is null)),
    check (invalidated_at is null or invalidated_at >= created_at)
);

create index content_derivatives_asset_idx
    on content_derivatives (asset_id, revision_id)
    where asset_id is not null;

create trigger content_derivatives_payload_immutable
before update on content_derivatives
for each row
when new.revision_id is not old.revision_id
    or new.kind is not old.kind
    or new.renderer_version is not old.renderer_version
    or new.content_text is not old.content_text
    or new.asset_id is not old.asset_id
    or new.sha256 is not old.sha256
    or new.diagnostics_json is not old.diagnostics_json
    or new.provenance_json is not old.provenance_json
    or new.created_at is not old.created_at
begin
    select raise(abort, 'content derivative payload is immutable');
end;

create trigger content_derivatives_invalidation_once
before update on content_derivatives
for each row
when old.invalidated_at is not null
begin
    select raise(abort, 'content derivative invalidation is immutable');
end;

create trigger content_derivatives_delete_forbidden
before delete on content_derivatives
for each row
begin
    select raise(abort, 'content derivative deletion is forbidden');
end;

create trigger content_derivatives_asset_hash_insert
before insert on content_derivatives
for each row
when new.asset_id is not null and not exists (
    select 1 from media_assets as asset
    where asset.id = new.asset_id
      and asset.sha256 = new.sha256
      and asset.deleted_at is null
)
begin
    select raise(abort, 'derivative asset hash does not match media asset');
end;

create table content_problem_matches
(
    id                  integer primary key,
    content_revision_id integer not null references content_revisions (id),
    source_ordinal      integer not null check (source_ordinal >= 0),
    source_item         text    not null check (length(trim(source_item)) > 0),
    problem_id          integer references problems (id),
    decision            text    not null
        check (decision in ('auto_position', 'manual_match', 'insert_new', 'omit')),
    resolved_by_user_id integer references users (id),
    resolved_at         text,
    diagnostics_json    text    not null default '[]'
        check (json_valid(diagnostics_json) = 1 and json_type(diagnostics_json) = 'array'),
    created_at          text    not null,
    unique (content_revision_id, source_ordinal, source_item),
    check (
        (decision = 'omit' and problem_id is null)
        or (decision <> 'omit' and problem_id is not null)
    ),
    check (
        (resolved_at is null and resolved_by_user_id is null)
        or resolved_at is not null
    )
);

create index content_problem_matches_problem_idx
    on content_problem_matches (problem_id, content_revision_id)
    where problem_id is not null;

create trigger content_problem_matches_immutable_update
before update on content_problem_matches
for each row
begin
    select raise(abort, 'resolved content problem match is immutable');
end;

create trigger content_problem_matches_delete_forbidden
before delete on content_problem_matches
for each row
begin
    select raise(abort, 'content problem match deletion is forbidden');
end;

create table problem_revisions
(
    id                 integer primary key,
    problem_id         integer not null references problems (id),
    content_revision_id integer not null references content_revisions (id),
    source_ordinal     integer not null check (source_ordinal >= 0),
    source_item        text    not null check (length(trim(source_item)) > 0),
    display_number     text    not null check (length(trim(display_number)) > 0),
    title              text    not null check (length(trim(title)) > 0),
    normalized_title   text    not null check (length(trim(normalized_title)) > 0),
    problem_type       integer not null,
    answer_type        integer,
    answer_config_json text    not null
        check (json_valid(answer_config_json) = 1 and json_type(answer_config_json) = 'object'),
    attempt_policy_json text   not null
        check (json_valid(attempt_policy_json) = 1 and json_type(attempt_policy_json) = 'object'),
    config_version     integer not null check (config_version > 0),
    created_at         text    not null,
    created_by_user_id integer references users (id),
    unique (problem_id, content_revision_id),
    unique (content_revision_id, source_ordinal, source_item)
);

create index problem_revisions_title_idx
    on problem_revisions (normalized_title, content_revision_id, problem_id);

create trigger problem_revisions_match_insert
before insert on problem_revisions
for each row
when not exists (
    select 1
    from content_problem_matches as problem_match
    where problem_match.content_revision_id = new.content_revision_id
      and problem_match.source_ordinal = new.source_ordinal
      and problem_match.source_item = new.source_item
      and problem_match.problem_id = new.problem_id
      and problem_match.decision <> 'omit'
)
begin
    select raise(abort, 'problem revision requires a resolved problem match');
end;

create trigger problem_revisions_immutable_update
before update on problem_revisions
for each row
begin
    select raise(abort, 'problem revision is immutable');
end;

create trigger problem_revisions_delete_forbidden
before delete on problem_revisions
for each row
begin
    select raise(abort, 'problem revision deletion is forbidden');
end;

create table problem_synonym_groups
(
    id                 integer primary key,
    public_id text generated always as ('ps-' || id) virtual,
    course_lesson_id   integer not null references course_lessons (id),
    group_key          text    not null check (length(trim(group_key)) > 0),
    display_title      text    not null check (length(trim(display_title)) > 0),
    status             text    not null default 'active'
        check (status in ('active', 'split', 'archived')),
    created_by_user_id integer references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    unique (course_lesson_id, group_key)
);

create index problem_synonym_groups_lesson_status_idx
    on problem_synonym_groups (course_lesson_id, status, id);

-- group_lesson_id is a deliberate materialized scope key. It makes the
-- one-member-per-group-lesson invariant enforceable by SQLite while the
-- trigger below verifies it against the immutable problem revision lineage.
create table problem_synonym_members
(
    id                 integer primary key,
    synonym_group_id   integer not null references problem_synonym_groups (id),
    group_lesson_id    integer not null references group_lessons (id),
    problem_id         integer not null references problems (id),
    added_by_user_id   integer references users (id),
    added_at           text    not null,
    removed_by_user_id integer references users (id),
    removed_at         text,
    reason             text,
    membership_version integer not null check (membership_version > 0),
    unique (synonym_group_id, problem_id, membership_version),
    check (reason is null or length(trim(reason)) > 0),
    check (
        (removed_at is null and removed_by_user_id is null)
        or (removed_at is not null and removed_by_user_id is not null)
    ),
    check (removed_at is null or removed_at >= added_at)
);

create unique index problem_synonym_members_problem_active_uq
    on problem_synonym_members (problem_id)
    where removed_at is null;

create unique index problem_synonym_members_group_lesson_active_uq
    on problem_synonym_members (synonym_group_id, group_lesson_id)
    where removed_at is null;

create index problem_synonym_members_history_idx
    on problem_synonym_members (synonym_group_id, added_at, id);

create trigger problem_synonym_members_scope_insert
before insert on problem_synonym_members
for each row
when not exists (
    select 1
    from problem_synonym_groups as synonym_group
    join group_lessons as group_lesson
      on group_lesson.id = new.group_lesson_id
     and group_lesson.course_lesson_id = synonym_group.course_lesson_id
    where synonym_group.id = new.synonym_group_id
      and exists (
          select 1
          from problem_revisions as problem_revision
          join content_revisions as revision
            on revision.id = problem_revision.content_revision_id
          join content_sources as source
            on source.id = revision.source_id
          where problem_revision.problem_id = new.problem_id
            and source.group_lesson_id = new.group_lesson_id
      )
)
begin
    select raise(abort, 'synonym member is outside its course/group lesson');
end;

create trigger problem_synonym_members_identity_immutable
before update on problem_synonym_members
for each row
when new.synonym_group_id is not old.synonym_group_id
    or new.group_lesson_id is not old.group_lesson_id
    or new.problem_id is not old.problem_id
    or new.added_by_user_id is not old.added_by_user_id
    or new.added_at is not old.added_at
    or new.membership_version is not old.membership_version
begin
    select raise(abort, 'synonym member identity is immutable');
end;

create trigger problem_synonym_members_removed_immutable
before update on problem_synonym_members
for each row
when old.removed_at is not null
begin
    select raise(abort, 'removed synonym member is immutable');
end;

create trigger problem_synonym_members_delete_forbidden
before delete on problem_synonym_members
for each row
begin
    select raise(abort, 'synonym member deletion is forbidden');
end;

create table lesson_windows
(
    id                    integer primary key,
    public_id text generated always as ('lw-' || id) virtual,
    group_lesson_id       integer not null unique references group_lessons (id),
    opens_at              text,
    submission_closes_at  text    not null,
    hint_scheduled_at     text,
    solution_scheduled_at text,
    timezone              text    not null check (length(trim(timezone)) > 0),
    source                text    not null
        check (source in ('native', 'legacy_schedule', 'manual_backfill')),
    created_by_user_id    integer references users (id),
    updated_by_user_id    integer references users (id),
    created_at            text    not null,
    updated_at            text    not null,
    version               integer not null default 1 check (version > 0),
    check (opens_at is null or opens_at < submission_closes_at)
);

create index lesson_windows_close_idx
    on lesson_windows (submission_closes_at, group_lesson_id);

create table lesson_window_schedule_sources
(
    lesson_window_id           integer not null references lesson_windows (id),
    schedule_field             text    not null
        check (schedule_field in (
            'opens_at', 'hint_scheduled_at',
            'submission_closes_at', 'solution_scheduled_at'
        )),
    course_schedule_rule_id    integer not null references course_schedule_rules (id),
    course_rule_version        integer not null check (course_rule_version > 0),
    group_schedule_override_id integer references group_schedule_overrides (id),
    group_override_version     integer check (group_override_version is null or group_override_version > 0),
    resolution_mode            text    not null
        check (resolution_mode in ('inherit', 'override', 'disabled')),
    resolved_day_offset        integer,
    resolved_local_time        text
        check (
            resolved_local_time is null
            or (
                length(resolved_local_time) in (5, 8)
                and resolved_local_time glob '[0-2][0-9]:[0-5][0-9]*'
                and cast(substr(resolved_local_time, 1, 2) as integer) between 0 and 23
                and (
                    length(resolved_local_time) = 5
                    or (
                        substr(resolved_local_time, 6, 1) = ':'
                        and substr(resolved_local_time, 7, 2) glob '[0-5][0-9]'
                    )
                )
            )
        ),
    resolved_timezone          text
        check (resolved_timezone is null or length(trim(resolved_timezone)) > 0),
    created_at                 text    not null,
    primary key (lesson_window_id, schedule_field),
    check (
        (group_schedule_override_id is null and group_override_version is null)
        or (group_schedule_override_id is not null and group_override_version is not null)
    ),
    check (
        (resolution_mode = 'disabled' and resolved_day_offset is null
            and resolved_local_time is null and resolved_timezone is null)
        or (resolution_mode <> 'disabled' and resolved_day_offset is not null
            and resolved_local_time is not null and resolved_timezone is not null)
    )
);

create index lesson_window_schedule_sources_rule_idx
    on lesson_window_schedule_sources (course_schedule_rule_id, lesson_window_id);

create trigger lesson_window_schedule_sources_scope_insert
before insert on lesson_window_schedule_sources
for each row
when not exists (
    select 1
    from lesson_windows as lesson_window
    join group_lessons as group_lesson
      on group_lesson.id = lesson_window.group_lesson_id
    join course_schedule_rules as schedule_rule
      on schedule_rule.id = new.course_schedule_rule_id
     and schedule_rule.course_id = group_lesson.course_id
     and schedule_rule.schedule_field = new.schedule_field
     and schedule_rule.rule_version = new.course_rule_version
     and schedule_rule.state = 'active'
    where lesson_window.id = new.lesson_window_id
      and (
          (
              new.group_schedule_override_id is null
              and new.resolution_mode = 'inherit'
              and new.resolved_day_offset = schedule_rule.day_offset
              and new.resolved_local_time = schedule_rule.local_time
              and new.resolved_timezone = schedule_rule.timezone
          )
          or exists (
              select 1
              from group_schedule_overrides as schedule_override
              where schedule_override.id = new.group_schedule_override_id
                and schedule_override.course_id = group_lesson.course_id
                and schedule_override.group_id = group_lesson.group_id
                and schedule_override.schedule_field = new.schedule_field
                and schedule_override.override_version = new.group_override_version
                and schedule_override.state = 'active'
                and schedule_override.mode = new.resolution_mode
                and (
                    (
                        schedule_override.mode = 'inherit'
                        and new.resolved_day_offset = schedule_rule.day_offset
                        and new.resolved_local_time = schedule_rule.local_time
                        and new.resolved_timezone = schedule_rule.timezone
                    )
                    or (
                        schedule_override.mode = 'override'
                        and new.resolved_day_offset = schedule_override.day_offset
                        and new.resolved_local_time = schedule_override.local_time
                        and new.resolved_timezone = schedule_override.timezone
                    )
                    or schedule_override.mode = 'disabled'
                )
          )
      )
)
begin
    select raise(abort, 'lesson window schedule source is outside its scope');
end;

create trigger lesson_window_schedule_sources_immutable_update
before update on lesson_window_schedule_sources
for each row
begin
    select raise(abort, 'lesson window schedule source is immutable');
end;

create trigger lesson_window_schedule_sources_delete_forbidden
before delete on lesson_window_schedule_sources
for each row
begin
    select raise(abort, 'lesson window schedule source deletion is forbidden');
end;

create table lesson_publications
(
    id                        integer primary key,
    public_id text generated always as ('lp-' || id) virtual,
    group_lesson_id           integer not null references group_lessons (id),
    kind                      text    not null
        check (kind in ('condition', 'hint', 'solution')),
    revision_id               integer not null references content_revisions (id),
    state                     text    not null
        check (state in ('scheduled', 'published', 'superseded', 'hidden')),
    scheduled_at              text,
    published_at              text,
    hidden_at                 text,
    created_by_user_id        integer references users (id),
    published_by_user_id      integer references users (id),
    supersedes_publication_id integer references lesson_publications (id),
    activated_from_schedule_id integer references lesson_publications (id),
    created_at                text    not null,
    updated_at                text    not null,
    version                   integer not null default 1 check (version > 0),
    check (supersedes_publication_id is null or supersedes_publication_id <> id),
    check (activated_from_schedule_id is null or activated_from_schedule_id <> id),
    check (activated_from_schedule_id is null or state = 'published'),
    check (state <> 'scheduled' or scheduled_at is not null),
    check (state <> 'published' or published_at is not null),
    check (state <> 'hidden' or hidden_at is not null)
);

create unique index lesson_publications_one_scheduled_uq
    on lesson_publications (group_lesson_id, kind)
    where state = 'scheduled';

create unique index lesson_publications_one_published_uq
    on lesson_publications (group_lesson_id, kind)
    where state = 'published';

create index lesson_publications_timeline_idx
    on lesson_publications (group_lesson_id, kind, created_at, id);

create trigger lesson_publications_revision_scope_insert
before insert on lesson_publications
for each row
when not exists (
    select 1
    from content_revisions as revision
    join content_sources as source on source.id = revision.source_id
    where revision.id = new.revision_id
      and source.group_lesson_id = new.group_lesson_id
      and source.kind = new.kind
      and revision.status = 'ready'
)
begin
    select raise(abort, 'publication revision does not match group lesson and kind');
end;

create trigger lesson_publications_revision_scope_update
before update of group_lesson_id, kind, revision_id on lesson_publications
for each row
when not exists (
    select 1
    from content_revisions as revision
    join content_sources as source on source.id = revision.source_id
    where revision.id = new.revision_id
      and source.group_lesson_id = new.group_lesson_id
      and source.kind = new.kind
      and revision.status = 'ready'
)
begin
    select raise(abort, 'publication revision does not match group lesson and kind');
end;

create trigger lesson_publications_supersedes_scope_insert
before insert on lesson_publications
for each row
when new.supersedes_publication_id is not null and not exists (
    select 1 from lesson_publications as previous
    where previous.id = new.supersedes_publication_id
      and previous.group_lesson_id = new.group_lesson_id
      and previous.kind = new.kind
)
begin
    select raise(abort, 'superseded publication is outside group lesson or kind');
end;

create trigger lesson_publications_activation_scope_insert
before insert on lesson_publications
for each row
when new.activated_from_schedule_id is not null and not exists (
    select 1 from lesson_publications as scheduled
    where scheduled.id = new.activated_from_schedule_id
      and scheduled.group_lesson_id = new.group_lesson_id
      and scheduled.kind = new.kind
      and scheduled.revision_id = new.revision_id
      and scheduled.state = 'superseded'
      and scheduled.scheduled_at is not null
      and scheduled.scheduled_at is new.scheduled_at
      and scheduled.published_at is null
)
begin
    select raise(abort, 'activation schedule is outside group lesson or kind');
end;

create trigger lesson_publications_identity_immutable
before update on lesson_publications
for each row
when new.public_id is not old.public_id
    or new.group_lesson_id is not old.group_lesson_id
    or new.kind is not old.kind
    or new.revision_id is not old.revision_id
    or new.created_by_user_id is not old.created_by_user_id
    or new.supersedes_publication_id is not old.supersedes_publication_id
    or new.activated_from_schedule_id is not old.activated_from_schedule_id
    or new.created_at is not old.created_at
begin
    select raise(abort, 'publication identity is immutable');
end;

create trigger lesson_publications_state_transition_guard
before update on lesson_publications
for each row
when new.state is not old.state and not (
    (old.state = 'scheduled' and new.state in ('published', 'hidden', 'superseded'))
    or (old.state = 'published' and new.state in ('hidden', 'superseded'))
)
begin
    select raise(abort, 'invalid publication state transition');
end;

create trigger lesson_publications_delete_forbidden
before delete on lesson_publications
for each row
begin
    select raise(abort, 'publication deletion is forbidden');
end;

create table hint_reveals
(
    id              integer primary key,
    student_user_id integer not null references users (id),
    problem_id      integer not null references problems (id),
    publication_id  integer not null references lesson_publications (id),
    revealed_at     text    not null,
    request_id      text    not null check (length(trim(request_id)) > 0),
    unique (student_user_id, problem_id, publication_id)
);

create index hint_reveals_student_timeline_idx
    on hint_reveals (student_user_id, revealed_at, id);

create trigger hint_reveals_publication_kind_insert
before insert on hint_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    where publication.id = new.publication_id
      and publication.kind = 'hint'
      and publication.state = 'published'
      and exists (
          select 1
          from problem_revisions as problem_revision
          join content_revisions as revision
            on revision.id = problem_revision.content_revision_id
          join content_sources as source on source.id = revision.source_id
          where problem_revision.problem_id = new.problem_id
            and source.group_lesson_id = publication.group_lesson_id
      )
)
begin
    select raise(abort, 'hint reveal requires a published hint');
end;

create trigger hint_reveals_delete_forbidden
before delete on hint_reveals
for each row
begin
    select raise(abort, 'hint reveal deletion is forbidden');
end;

create trigger hint_reveals_immutable_update
before update on hint_reveals
for each row
begin
    select raise(abort, 'hint reveal is immutable');
end;

create table solution_reveals
(
    id              integer primary key,
    student_user_id integer not null references users (id),
    problem_id      integer not null references problems (id),
    publication_id  integer not null references lesson_publications (id),
    revealed_at     text    not null,
    request_id      text    not null check (length(trim(request_id)) > 0),
    unique (student_user_id, problem_id, publication_id)
);

create index solution_reveals_student_timeline_idx
    on solution_reveals (student_user_id, revealed_at, id);

create trigger solution_reveals_publication_kind_insert
before insert on solution_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    where publication.id = new.publication_id
      and publication.kind = 'solution'
      and publication.state = 'published'
      and exists (
          select 1
          from problem_revisions as problem_revision
          join content_revisions as revision
            on revision.id = problem_revision.content_revision_id
          join content_sources as source on source.id = revision.source_id
          where problem_revision.problem_id = new.problem_id
            and source.group_lesson_id = publication.group_lesson_id
      )
)
begin
    select raise(abort, 'solution reveal requires a published solution');
end;

create trigger solution_reveals_delete_forbidden
before delete on solution_reveals
for each row
begin
    select raise(abort, 'solution reveal deletion is forbidden');
end;

create trigger solution_reveals_immutable_update
before update on solution_reveals
for each row
begin
    select raise(abort, 'solution reveal is immutable');
end;
