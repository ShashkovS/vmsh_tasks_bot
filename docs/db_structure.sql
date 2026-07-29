-- GENERATED FILE. DO NOT EDIT BY HAND.
-- Authoritative source: repository yoyo migrations plus schema inventory.
-- Schema-only: contains no product row values; DDL is migration-authored.
-- Reference only: apply migrations rather than using this as a bootstrap.
-- Product schema SHA-256: 4c977a5d76db476101a4d8fe5f9416188efb9940adfb13b3e787c12f9b473714

CREATE TABLE auth_accounts
(
    id                         integer primary key,
    public_id                  text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    audience                   text    not null
        check (audience in ('student', 'family', 'staff')),
    username                   text    not null
        check (length(trim(username)) > 0),
    username_normalized        text    not null
        check (length(trim(username_normalized)) > 0),
    username_algorithm_version integer
        check (username_algorithm_version > 0),
    provisioning_source        text    not null
        check (length(trim(provisioning_source)) > 0),
    display_name               text,
    credential_kind            text    not null
        check (credential_kind in ('telegram_token', 'password')),
    credential_hash            text,
    linked_user_id             integer references users (id),
    status                     text    not null
        check (status in ('active', 'blocked', 'disabled', 'archived')),
    credential_version         integer not null default 1
        check (credential_version > 0),
    last_login_at              text,
    created_at                 text    not null,
    updated_at                 text    not null,
    unique (audience, username_normalized),
    check (credential_hash is null or length(trim(credential_hash)) > 0),
    check (status <> 'active' or credential_hash is not null),
    check (audience <> 'student' or username_algorithm_version is not null),
    check (
        (audience = 'student' and credential_kind = 'telegram_token' and linked_user_id is not null)
        or (audience = 'family' and credential_kind = 'password' and linked_user_id is null)
        or (audience = 'staff' and credential_kind = 'password' and linked_user_id is not null)
    ),
    check (
        audience <> 'family'
        or (display_name is not null and length(trim(display_name)) > 0)
    )
);

CREATE TABLE auth_events
(
    id            integer primary key,
    account_id    integer references auth_accounts (id),
    session_id    integer references auth_sessions (id),
    event_type    text not null
        check (length(trim(event_type)) > 0),
    occurred_at   text not null,
    request_id    text not null
        check (length(trim(request_id)) > 0),
    ip_prefix     text,
    metadata_json text not null default '{}'
        check (json_valid(metadata_json) = 1 and json_type(metadata_json) = 'object')
);

CREATE TABLE auth_refresh_consumed_secrets
(
    session_id          integer not null
        references auth_sessions (id) on delete cascade,
    refresh_secret_hash text    not null
        check (
            length(refresh_secret_hash) = 64
            and refresh_secret_hash not glob '*[^0-9a-f]*'
        ),
    consumed_at         text    not null,
    expires_at          text    not null,
    primary key (session_id, refresh_secret_hash),
    check (expires_at >= consumed_at)
);

CREATE TABLE auth_sessions
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) = 32
            and public_id not glob '*[^0-9a-f]*'
        ),
    account_id           integer not null references auth_accounts (id),
    audience             text    not null
        check (audience in ('student', 'family', 'staff')),
    refresh_secret_hash  text    not null unique
        check (
            length(refresh_secret_hash) = 64
            and refresh_secret_hash not glob '*[^0-9a-f]*'
        ),
    credential_version   integer not null
        check (credential_version > 0),
    version              integer not null default 1
        check (version > 0),
    created_at           text    not null,
    updated_at           text    not null,
    last_seen_at         text    not null,
    expires_at           text    not null,
    revoked_at           text,
    revoke_reason        text,
    device_label         text,
    user_agent_family    text,
    ip_prefix            text,
    check (expires_at > created_at),
    check (last_seen_at >= created_at),
    check (revoked_at is null or revoked_at >= created_at),
    check (
        (revoked_at is null and revoke_reason is null)
        or (
            revoked_at is not null
            and revoke_reason is not null
            and length(trim(revoke_reason)) > 0
        )
    )
);

CREATE TABLE auth_throttle_buckets
(
    audience        text    not null
        check (audience in ('student', 'family', 'staff')),
    bucket_kind     text    not null
        check (bucket_kind in ('normalized_login', 'account', 'ip')),
    bucket_key_hmac text    not null
        check (
            length(bucket_key_hmac) = 64
            and bucket_key_hmac not glob '*[^0-9a-f]*'
        ),
    key_version     integer not null default 1
        check (key_version > 0),
    failure_count   integer not null default 0
        check (failure_count >= 0),
    window_started_at text  not null,
    last_failed_at  text,
    locked_until    text,
    created_at      text    not null,
    updated_at      text    not null,
    version         integer not null default 1
        check (version > 0),
    primary key (audience, bucket_kind, bucket_key_hmac, key_version),
    check (last_failed_at is null or last_failed_at >= window_started_at),
    check (locked_until is null or last_failed_at is not null)
);

CREATE TABLE classroom_assignment_delivery_batches
(
    id                           integer primary key,
    public_id                    text    not null unique,
    assignment_plan_id           integer not null references classroom_assignment_plans (id),
    assignment_plan_version      integer not null check (assignment_plan_version > 0),
    requested_by_user_id         integer not null references users (id),
    pwa_selected                 integer not null check (pwa_selected in (0, 1)),
    telegram_selected            integer not null check (telegram_selected in (0, 1)),
    recipient_snapshot_hash      text    not null check (length(recipient_snapshot_hash) = 64),
    recipient_count              integer not null check (recipient_count >= 0),
    changed_since_previous_count integer not null check (changed_since_previous_count >= 0),
    state                        text    not null
        check (state in ('queued', 'completed', 'completed_with_errors')),
    idempotency_key              text    not null check (length(idempotency_key) between 1 and 128),
    created_at                   text    not null,
    completed_at                 text,
    version                      integer not null default 1 check (version > 0),
    unique (requested_by_user_id, idempotency_key),
    check (pwa_selected = 1 or telegram_selected = 1),
    check (changed_since_previous_count <= recipient_count)
);

CREATE TABLE classroom_assignment_delivery_recipients
(
    batch_id                    integer not null
        references classroom_assignment_delivery_batches (id),
    student_user_id             integer not null references users (id),
    course_enrollment_id        integer not null references course_enrollments (id),
    group_lesson_id             integer not null references group_lessons (id),
    classroom_id                integer not null references classrooms (id),
    student_public_id           text    not null,
    student_display_name        text    not null,
    event_public_id             text    not null,
    event_name                  text    not null,
    course_public_id            text    not null,
    course_name                 text    not null,
    group_public_id             text    not null,
    group_name                  text    not null,
    classroom_public_id         text    not null,
    classroom_name              text    not null,
    student_account_id          integer references auth_accounts (id),
    telegram_chat_id            integer,
    pwa_state                   text    not null
        check (pwa_state in ('not_requested', 'sent', 'suppressed', 'failed')),
    pwa_error_code              text,
    pwa_sent_at                 text,
    telegram_state              text    not null
        check (telegram_state in ('not_requested', 'queued', 'sent', 'suppressed', 'failed')),
    telegram_error_code         text,
    telegram_sent_at            text,
    primary key (batch_id, course_enrollment_id),
    check (
        (pwa_state = 'sent' and pwa_sent_at is not null and pwa_error_code is null)
        or (pwa_state <> 'sent' and pwa_sent_at is null)
    ),
    check (
        (telegram_state = 'sent' and telegram_sent_at is not null
                                  and telegram_error_code is null)
        or (telegram_state <> 'sent' and telegram_sent_at is null)
    )
);

CREATE TABLE classroom_assignment_delivery_retries
(
    id                     integer primary key,
    batch_id               integer not null
        references classroom_assignment_delivery_batches (id),
    requested_by_user_id   integer not null references users (id),
    idempotency_key        text    not null check (length(idempotency_key) between 1 and 128),
    expected_batch_version integer not null check (expected_batch_version > 0),
    recipient_count        integer not null check (recipient_count > 0),
    created_at             text    not null,
    unique (requested_by_user_id, idempotency_key)
);

CREATE TABLE classroom_assignment_plans
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE classroom_assignments
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

CREATE TABLE classroom_events
(
    id                     integer primary key,
    public_id              text    not null unique,
    classroom_id           integer not null references classrooms (id),
    action                 text    not null
        check (action in ('created', 'renamed', 'archived', 'restored')),
    before_name            text,
    before_normalized_name text,
    before_status          text check (
        before_status is null or before_status in ('active', 'archived')
    ),
    after_name             text    not null,
    after_normalized_name  text    not null,
    after_status           text    not null
        check (after_status in ('active', 'archived')),
    version_after          integer not null check (version_after > 0),
    actor_user_id          integer not null references users (id),
    request_id             text    not null check (length(trim(request_id)) > 0),
    created_at             text    not null,
    check (
        (action = 'created' and before_name is null
                            and before_normalized_name is null
                            and before_status is null)
        or (action <> 'created' and before_name is not null
                               and before_normalized_name is not null
                               and before_status is not null)
    )
);

CREATE TABLE classroom_import_receipts
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

CREATE TABLE classroom_layout_rooms
(
    layout_version_id       integer not null references classroom_layout_versions (id),
    classroom_id            integer not null references classrooms (id),
    group_lesson_id         integer not null references group_lessons (id),
    source_layout_version_id integer references classroom_layout_versions (id),
    created_at              text    not null,
    updated_at              text    not null,
    primary key (layout_version_id, classroom_id),
    check (updated_at >= created_at)
);

CREATE TABLE classroom_layout_versions
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    in_person_event_id   integer not null references in_person_events (id),
    base_version_id      integer references classroom_layout_versions (id),
    state                text    not null
        check (state in ('draft', 'confirmed', 'superseded')),
    created_by_user_id   integer not null references users (id),
    confirmed_by_user_id integer references users (id),
    created_at           text    not null,
    updated_at           text    not null,
    confirmed_at         text,
    superseded_at        text,
    version              integer not null default 1 check (version > 0),
    unique (id, in_person_event_id),
    check (updated_at >= created_at),
    check (
        (state = 'draft' and confirmed_by_user_id is null
                         and confirmed_at is null
                         and superseded_at is null)
        or (state = 'confirmed' and confirmed_by_user_id is not null
                             and confirmed_at is not null
                             and superseded_at is null)
        or (state = 'superseded' and confirmed_by_user_id is not null
                              and confirmed_at is not null
                              and superseded_at is not null)
    )
);

CREATE TABLE classrooms
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    name               text    not null
        check (name = trim(name) and length(name) between 1 and 200),
    normalized_name    text    not null unique
        check (length(normalized_name) between 1 and 200),
    status             text    not null default 'active'
        check (status in ('active', 'archived')),
    created_by_user_id integer not null references users (id),
    updated_by_user_id integer not null references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    check (updated_at >= created_at)
);

CREATE TABLE content_derivatives
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

CREATE TABLE content_problem_matches
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

CREATE TABLE content_revision_assets
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

CREATE TABLE content_revisions
(
    id                      integer primary key,
    public_id               text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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
    version                 integer not null default 1 check (version > 0), compile_claim_token text
    check (compile_claim_token is null or length(compile_claim_token) between 16 and 128), compile_claimed_at text, compile_lease_expires_at text, compile_attempt_count integer not null default 0
    check (compile_attempt_count >= 0), compile_completed_at text,
    unique (source_id, revision_number),
    unique (source_id, source_sha256),
    check (supersedes_revision_id is null or supersedes_revision_id <> id),
    check (status <> 'ready' or canonical_json is not null)
);

CREATE TABLE content_sources
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE course_enrollment_events
(
    id                       integer primary key,
    public_id                text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    enrollment_id            integer not null,
    course_id                integer not null references courses (id),
    event_type               text    not null
        check (event_type in (
            'created',
            'active_group_changed',
            'attendance_mode_changed',
            'status_changed'
        )),
    previous_group_id        text,
    new_group_id             text,
    previous_attendance_mode text
        check (previous_attendance_mode in ('online', 'in_person')),
    new_attendance_mode      text
        check (new_attendance_mode in ('online', 'in_person')),
    previous_status          text
        check (previous_status in ('active', 'paused', 'archived')),
    new_status               text
        check (new_status in ('active', 'paused', 'archived')),
    actor_user_id            integer references users (id),
    source                   text    not null
        check (source in ('pwa', 'telegram', 'staff', 'import', 'system')),
    request_id               text    not null
        check (length(trim(request_id)) > 0),
    occurred_at              text    not null,
    created_at               text    not null,
    unique (enrollment_id, request_id),
    check (
        (
            event_type = 'created'
            and previous_group_id is null
            and new_group_id is not null
            and previous_attendance_mode is null
            and new_attendance_mode is not null
            and previous_status is null
            and new_status is not null
        )
        or (
            event_type = 'active_group_changed'
            and previous_group_id is not null
            and new_group_id is not null
            and previous_group_id <> new_group_id
            and previous_attendance_mode is null
            and new_attendance_mode is null
            and previous_status is null
            and new_status is null
        )
        or (
            event_type = 'attendance_mode_changed'
            and previous_group_id is null
            and new_group_id is null
            and previous_attendance_mode is not null
            and new_attendance_mode is not null
            and previous_attendance_mode <> new_attendance_mode
            and previous_status is null
            and new_status is null
        )
        or (
            event_type = 'status_changed'
            and previous_group_id is null
            and new_group_id is null
            and previous_attendance_mode is null
            and new_attendance_mode is null
            and previous_status is not null
            and new_status is not null
            and previous_status <> new_status
        )
    ),
    foreign key (enrollment_id, course_id)
        references course_enrollments (id, course_id),
    foreign key (course_id, previous_group_id)
        references groups (course_id, group_id),
    foreign key (course_id, new_group_id)
        references groups (course_id, group_id)
);

CREATE TABLE course_enrollments
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id    integer not null references users (id),
    course_id          integer not null references courses (id),
    active_group_id    text    not null,
    attendance_mode    text    not null
        check (attendance_mode in ('online', 'in_person')),
    status             text    not null
        check (status in ('active', 'paused', 'archived')),
    created_at         text    not null,
    updated_at         text    not null,
    created_by         integer references users (id),
    updated_by         integer references users (id),
    version            integer not null default 1
        check (version > 0),
    unique (student_user_id, course_id),
    unique (id, course_id),
    foreign key (course_id, active_group_id)
        references groups (course_id, group_id)
);

CREATE TABLE course_group_access
(
    enrollment_id integer not null,
    course_id      integer not null references courses (id),
    group_id       text    not null,
    valid_from     text    not null,
    valid_to       text,
    granted_by     integer references users (id),
    revoked_by     integer references users (id),
    reason         text,
    created_at     text    not null,
    updated_at     text    not null,
    version        integer not null default 1
        check (version > 0),
    primary key (enrollment_id, group_id, valid_from),
    check (valid_to is null or valid_to > valid_from),
    check (reason is null or length(trim(reason)) > 0),
    check (
        (valid_to is null and revoked_by is null)
        or valid_to is not null
    ),
    foreign key (enrollment_id, course_id)
        references course_enrollments (id, course_id),
    foreign key (course_id, group_id)
        references groups (course_id, group_id)
);

CREATE TABLE course_lessons
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE course_schedule_rules
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE courses
(
    id           integer primary key,
    public_id    text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    season_id    integer not null references seasons (id),
    code         text    not null
        check (length(trim(code)) > 0),
    name         text    not null
        check (length(trim(name)) > 0),
    subject_code text    not null
        check (length(trim(subject_code)) > 0),
    status       text    not null
        check (status in ('draft', 'active', 'archived')),
    sort_order   integer not null default 0,
    accent_key   text    not null
        check (length(trim(accent_key)) > 0),
    created_at   text    not null,
    updated_at   text    not null,
    created_by   integer references users (id),
    updated_by   integer references users (id),
    version      integer not null default 1
        check (version > 0),
    unique (season_id, code)
);

CREATE TABLE family_student_links
(
    family_account_id integer not null references auth_accounts (id),
    student_user_id   integer not null references users (id),
    relationship_label text,
    is_primary        integer not null default 0
        check (is_primary in (0, 1)),
    created_at        text    not null,
    updated_at        text    not null,
    revoked_at        text,
    primary key (family_account_id, student_user_id),
    check (relationship_label is null or length(trim(relationship_label)) > 0),
    check (revoked_at is null or revoked_at >= created_at)
);

CREATE TABLE game_map_chests
(
    id         INTEGER primary key,
    ts         timestamp not null,
    student_id INTEGER   not null references users,
    command_id INTEGER   not null,
    x          INTEGER   not null,
    y          INTEGER   not null,
    bonus      INTEGER   not null,
    unique (student_id, command_id, x, y)
);

CREATE TABLE game_map_flags
(
    id         INTEGER primary key,
    student_id INTEGER not null references users,
    command_id INTEGER not null,
    x          INTEGER not null,
    y          INTEGER not null,
    unique (student_id, command_id)
);

CREATE TABLE game_map_opened_cells
(
    id         INTEGER primary key,
    command_id INTEGER not null,
    x          INTEGER not null,
    y          INTEGER not null,
    unique (command_id, x, y)
);

CREATE TABLE game_payments
(
    id         INTEGER primary key,
    ts         timestamp not null,
    student_id INTEGER   not null references users,
    amount     INTEGER   not null,
    cell_id    INTEGER   not null references game_map_opened_cells
);

CREATE TABLE "game_students_commands"
(
    id         INTEGER
        primary key,
    student_id INTEGER not null
        unique
        references users,
    command_id INTEGER not null,
    group_id   text
        references groups
);

CREATE TABLE group_lessons
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE group_schedule_overrides
(
    id                         integer primary key,
    public_id                  text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE groups
(
    group_id              text primary key,
    short_code            text    not null,
    broadcast_code        text unique,
    tg_command            text unique,
    public_name           text    not null,
    conditions_url        text,
    tasks_header_template text,
    switch_message        text,
    sort_order            integer,
    is_active             integer not null default 1,
    is_default            integer not null default 0,
    allow_self_switch     integer not null default 0,
    is_system             integer not null default 0,
    score_weight          real    not null default 1.0
, public_id text
    check (
        public_id is null
        or (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        )
    ), course_id integer references courses (id), status text not null default 'active'
    check (status in ('draft', 'active', 'archived')), color_key text, created_at text, updated_at text, version integer not null default 1
    check (version > 0));

CREATE TABLE hint_reveals
(
    id              integer primary key,
    student_user_id integer not null references users (id),
    problem_id      integer not null references problems (id),
    publication_id  integer not null references lesson_publications (id),
    revealed_at     text    not null,
    request_id      text    not null check (length(trim(request_id)) > 0),
    unique (student_user_id, problem_id, publication_id)
);

CREATE TABLE idempotency_records
(
    id              integer primary key,
    audience        text    not null
        check (audience in ('student', 'family', 'staff')),
    account_id      integer not null references auth_accounts (id),
    operation       text    not null
        check (length(operation) between 1 and 200 and operation = trim(operation)),
    idempotency_key text    not null
        check (
            length(idempotency_key) between 1 and 200
            and idempotency_key = trim(idempotency_key)
        ),
    payload_sha256  text    not null
        check (
            length(payload_sha256) = 64
            and payload_sha256 not glob '*[^0-9a-f]*'
        ),
    state           text    not null
        check (state in ('processing', 'completed', 'failed')),
    http_status     integer
        check (http_status is null or http_status between 100 and 599),
    response_json   text
        check (
            response_json is null
            or (json_valid(response_json) = 1 and json_type(response_json) = 'object')
        ),
    created_at      text    not null,
    completed_at    text,
    expires_at      text,
    unique (audience, account_id, operation, idempotency_key),
    check (expires_at is null or expires_at > created_at),
    check (
        (
            state = 'processing'
            and http_status is null
            and response_json is null
            and completed_at is null
        )
        or (
            state in ('completed', 'failed')
            and http_status is not null
            and response_json is not null
            and completed_at is not null
            and completed_at >= created_at
        )
    )
);

CREATE TABLE in_person_event_group_lessons
(
    in_person_event_id integer not null references in_person_events (id),
    group_lesson_id    integer not null references group_lessons (id),
    added_by_user_id   integer not null references users (id),
    created_at         text    not null,
    primary key (in_person_event_id, group_lesson_id)
);

CREATE TABLE in_person_events
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    season_id          integer not null references seasons (id),
    name               text    not null check (length(trim(name)) > 0),
    starts_at          text    not null,
    ends_at            text    not null,
    status             text    not null default 'draft'
        check (status in ('draft', 'scheduled', 'completed', 'cancelled')),
    created_by_user_id integer not null references users (id),
    updated_by_user_id integer not null references users (id),
    created_at         text    not null,
    updated_at         text    not null,
    version            integer not null default 1 check (version > 0),
    check (ends_at > starts_at),
    check (updated_at >= created_at)
);

CREATE TABLE kv
(
    key   text unique,
    value text
);

CREATE TABLE kv_logins
(
    id          integer not null            primary key,
    user_id     integer not null
        constraint kv_logins_pk_2
            unique
        constraint kv_logins_users_id_fk
            references users,
    token       text    not null,
    kv_login    text,
    kv_password text
);

CREATE TABLE last_keyboards
(
    user_id   INTEGER not null primary key references users,
    chat_id   INTEGER not null,
    tg_msg_id INTEGER not null
);

CREATE TABLE lesson_publications
(
    id                        integer primary key,
    public_id                 text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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
    version                   integer not null default 1 check (version > 0), terminal_by_user_id integer references users (id), terminal_at text, provenance_kind text not null default 'interactive'
    check (provenance_kind in ('interactive', 'legacy_backfill')),
    check (supersedes_publication_id is null or supersedes_publication_id <> id),
    check (activated_from_schedule_id is null or activated_from_schedule_id <> id),
    check (activated_from_schedule_id is null or state = 'published'),
    check (state <> 'scheduled' or scheduled_at is not null),
    check (state <> 'published' or published_at is not null),
    check (state <> 'hidden' or hidden_at is not null)
);

CREATE TABLE lesson_window_changes
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

CREATE TABLE lesson_window_schedule_sources
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

CREATE TABLE lesson_windows
(
    id                    integer primary key,
    public_id             text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE "lessons"
(
    id       INTEGER
        primary key,
    group_id text
        references groups,
    lesson   INTEGER not null,
    unique (lesson, group_id)
);

CREATE TABLE media_assets
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE media_groups
(
    media_group_id INTEGER   not null primary key unique,
    problem_id     INTEGER   not null references problems,
    ts             timestamp not null
);

CREATE TABLE messages_log
(
    id          INTEGER primary key unique,
    from_bot    boolean   not null,
    tg_msg_id   INTEGER   not null,
    chat_id     INTEGER   not null,
    student_id  INTEGER references users,
    teacher_id  INTEGER references users,
    ts          timestamp not null,
    msg_text    TEXT,
    attach_path TEXT
);

CREATE TABLE notification_deliveries
(
    id                     integer primary key,
    public_id              text    not null unique,
    event_id               integer not null references notification_events (id),
    subscription_public_id text    not null,
    state                  text    not null
        check (state in ('pending', 'sending', 'retry', 'sent', 'failed', 'suppressed')),
    attempt_count          integer not null default 0 check (attempt_count >= 0),
    next_attempt_at        text    not null,
    claim_token            text,
    claim_until            text,
    delivered_at           text,
    last_error_code        text,
    created_at             text    not null,
    updated_at             text    not null,
    unique (event_id, subscription_public_id),
    check (
        (state = 'sending' and claim_token is not null and claim_until is not null)
        or (state <> 'sending' and claim_token is null and claim_until is null)
    ),
    check (
        (state = 'sent' and delivered_at is not null)
        or (state <> 'sent' and delivered_at is null)
    )
);

CREATE TABLE notification_events
(
    id                 integer primary key,
    public_id          text    not null unique,
    account_id         integer not null references auth_accounts (id),
    category           text    not null,
    dedupe_key         text    not null,
    route              text    not null,
    payload_json       text    not null
        check (json_valid(payload_json) = 1 and json_type(payload_json) = 'object'),
    occurred_at        text    not null,
    deliver_after      text    not null,
    read_at            text,
    read_by_session_id integer references auth_sessions (id),
    created_at         text    not null,
    unique (account_id, category, dedupe_key),
    check (length(trim(category)) > 0),
    check (length(trim(dedupe_key)) > 0),
    check (substr(route, 1, 1) = '/'),
    check (deliver_after >= occurred_at),
    check (read_at is null or read_at >= occurred_at),
    check (
        (read_at is null and read_by_session_id is null)
        or read_at is not null
    )
);

CREATE TABLE notification_preferences
(
    account_id        integer not null references auth_accounts (id),
    category          text    not null,
    in_app_enabled    integer not null check (in_app_enabled in (0, 1)),
    push_enabled      integer not null check (push_enabled in (0, 1)),
    sound_enabled     integer not null check (sound_enabled in (0, 1)),
    quiet_starts_local text   not null,
    quiet_ends_local   text   not null,
    timezone          text    not null,
    updated_at        text    not null,
    primary key (account_id, category),
    check (length(trim(category)) > 0),
    check (length(quiet_starts_local) = 5),
    check (length(quiet_ends_local) = 5),
    check (length(trim(timezone)) > 0)
);

CREATE TABLE problem_complexity
(
    synonyms   TEXT   not null primary key,
    for_weak   DOUBLE not null,
    for_strong DOUBLE not null
);

CREATE TABLE problem_revisions
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

CREATE TABLE problem_synonym_groups
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
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

CREATE TABLE problem_synonym_members
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

CREATE TABLE "problems"
(
    id               INTEGER
        primary key,
    group_id         text
        references groups,
    lesson           INTEGER         not null,
    prob             INTEGER         not null,
    item             TEXT            not null,
    title            text            not null,
    prob_text        text            not null,
    prob_type        integer         not null,
    ans_type         integer,
    ans_validation   text,
    validation_error text,
    cor_ans          text,
    cor_ans_checker  text,
    wrong_ans        text,
    congrat          text,
    synonyms         text default '' not null, public_id text
    check (
        public_id is null
        or (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        )
    ),
    unique (group_id, lesson, prob, item)
);

CREATE TABLE push_subscriptions
(
    id              integer primary key,
    public_id       text    not null unique,
    account_id      integer not null references auth_accounts (id),
    session_id      integer not null references auth_sessions (id),
    endpoint        text    not null unique,
    p256dh          text    not null,
    auth_secret     text    not null,
    expiration_time integer,
    user_agent      text,
    created_at      text    not null,
    updated_at      text    not null,
    check (length(trim(endpoint)) > 0),
    check (length(trim(p256dh)) > 0),
    check (length(trim(auth_secret)) > 0),
    check (expiration_time is null or expiration_time > 0)
);

CREATE TABLE questions
(
    id                   INTEGER primary key,
    ts                   TIMESTAMP not null,
    answered             BOOLEAN   not null default false,

    user_id              INTEGER references users,
    chat_id              INTEGER   not null,
    question_msg_id      INTEGER   not null,
    question_text        TEXT      null,

    sos_chat_id          INTEGER   not null,
    sos_header_msg_id    INTEGER   not null,
    sos_forwarded_msg_id INTEGER   not null,
    answer_text          TEXT      null,
    unique (sos_chat_id, sos_forwarded_msg_id)
);

CREATE TABLE reaction_enum
(
    reaction_id      INTEGER primary key,
    reaction         TEXT    not null,
    reaction_type_id INTEGER not null references reaction_type_enum
);

CREATE TABLE reaction_type_enum
(
    reaction_type_id INTEGER primary key,
    reaction_type    TEXT not null unique
);

CREATE TABLE reactions
(
    id                   INTEGER primary key,
    ts                   TEXT,
    result_id            INT references results,
    zoom_conversation_id INT references zoom_conversation,
    reaction_id          INT not null references reaction_enum,
    reaction_type_id     INT not null references reaction_type_enum
);

CREATE TABLE "results"
(
    id                   INTEGER
        primary key,
    student_id           INTEGER   not null
        references users,
    problem_id           INTEGER   not null
        references problems,
    group_id             text
        references groups,
    lesson               INTEGER   not null,
    teacher_id           INTEGER
        references users,
    ts                   timestamp not null,
    verdict              integer   not null,
    answer               TEXT,
    res_type             integer,
    check_time_spent_sec int default null,
    zoom_conversation_id INT
        references zoom_conversation
);

CREATE TABLE seasons
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    code               text    not null unique
        check (length(trim(code)) > 0),
    title              text    not null
        check (length(trim(title)) > 0),
    starts_on          text    not null,
    ends_on            text    not null,
    timezone           text    not null default 'Europe/Moscow'
        check (length(trim(timezone)) > 0),
    session_expires_on text    not null,
    status             text    not null
        check (status in ('draft', 'active', 'archived')),
    created_at         text    not null,
    updated_at         text    not null,
    check (starts_on <= ends_on),
    check (session_expires_on >= starts_on)
);

CREATE TABLE signons
(
    ts         timestamp not null,
    user_id    INTEGER references users,
    chat_id    INTEGER   not null,
    first_name TEXT,
    last_name  TEXT,
    username   TEXT,
    token      text
);

CREATE TABLE solution_reveals
(
    id              integer primary key,
    student_user_id integer not null references users (id),
    problem_id      integer not null references problems (id),
    publication_id  integer not null references lesson_publications (id),
    revealed_at     text    not null,
    request_id      text    not null check (length(trim(request_id)) > 0),
    unique (student_user_id, problem_id, publication_id)
);

CREATE TABLE staff_scopes
(
    id            integer primary key,
    staff_user_id integer not null references users (id),
    course_id     integer not null references courses (id),
    group_id      text,
    role          text    not null
        check (role in ('teacher', 'admin')),
    valid_from    text    not null,
    valid_to      text,
    granted_by    integer references users (id),
    revoked_by    integer references users (id),
    reason        text,
    created_at    text    not null,
    updated_at    text    not null,
    version       integer not null default 1
        check (version > 0),
    check (valid_to is null or valid_to > valid_from),
    check (reason is null or length(trim(reason)) > 0),
    check (
        (valid_to is null and revoked_by is null)
        or valid_to is not null
    ),
    foreign key (course_id, group_id)
        references groups (course_id, group_id)
);

CREATE TABLE states
(
    user_id         INTEGER primary key unique references users,
    state           INTEGER,
    problem_id      INTEGER references problems,
    last_student_id INTEGER references users,
    last_teacher_id INTEGER references users,
    oral_problem_id INTEGER references users,
    info            blob default null
);

CREATE TABLE student_strength
(
    student_id  integer not null primary key,
    simple_prob DOUBLE  not null,
    compl_prob  DOUBLE  not null
);

CREATE TABLE submission_attachments
(
    id                  integer primary key,
    public_id           text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    entry_id            integer not null references submission_entries (id),
    asset_id            integer not null references media_assets (id),
    -- Ordinals are deliberately sparse and non-negative. SQLite does not defer
    -- UNIQUE checks, so reorder code needs temporary high values; the separate
    -- count trigger, not the ordinal range, enforces the product limit of ten.
    ordinal             integer not null check (ordinal >= 0),
    client_filename     text check (client_filename is null or length(client_filename) <= 512),
    upload_status       text    not null
        check (upload_status in ('pending', 'stored', 'failed', 'locked')),
    created_at          text    not null,
    locked_at           text,
    locked_by_result_id integer references results (id),
    unique (entry_id, ordinal),
    check (
        (upload_status = 'locked' and locked_at is not null and locked_by_result_id is not null)
        or (upload_status <> 'locked' and locked_at is null and locked_by_result_id is null)
    ),
    check (locked_at is null or locked_at >= created_at)
);

CREATE TABLE submission_entries
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    thread_id            integer not null references submission_threads (id),
    author_kind          text    not null
        check (author_kind in ('student', 'teacher', 'admin', 'ai', 'system')),
    author_user_id       integer references users (id),
    channel              text    not null
        check (channel in ('pwa', 'telegram', 'staff', 'system')),
    channel_group_key    text
        check (
            channel_group_key is null
            or (
                length(channel_group_key) between 1 and 200
                and channel_group_key = trim(channel_group_key)
            )
        ),
    entry_kind           text    not null
        check (entry_kind in ('text', 'submission', 'teacher_comment', 'ai_comment', 'system_event')),
    state                text    not null
        check (state in ('draft', 'uploading', 'submitted', 'deleted', 'locked')),
    text                 text    check (text is null or length(text) <= 100000),
    client_created_at    text,
    server_received_at   text    not null,
    idempotency_key      text
        check (
            idempotency_key is null
            or (
                length(idempotency_key) between 1 and 200
                and idempotency_key = trim(idempotency_key)
            )
        ),
    payload_sha256       text
        check (
            payload_sha256 is null
            or (
                length(payload_sha256) = 64
                and payload_sha256 not glob '*[^0-9a-f]*'
            )
        ),
    legacy_discussion_id integer unique references written_tasks_discussions (id),
    version              integer not null default 1 check (version > 0),
    locked_at            text,
    deleted_at           text, problem_revision_id integer references problem_revisions (id),
    check ((idempotency_key is null) = (payload_sha256 is null)),
    check (channel_group_key is null or channel = 'telegram'),
    check (
        (author_kind in ('student', 'teacher', 'admin') and author_user_id is not null)
        or (author_kind in ('ai', 'system') and author_user_id is null)
    ),
    check (
        (author_kind = 'student' and entry_kind in ('text', 'submission'))
        or (author_kind in ('teacher', 'admin') and entry_kind = 'teacher_comment')
        or (author_kind = 'ai' and entry_kind = 'ai_comment')
        or (author_kind = 'system' and entry_kind = 'system_event')
    ),
    check (
        (state = 'locked' and locked_at is not null and deleted_at is null)
        or (state = 'deleted' and deleted_at is not null and locked_at is null)
        or (state not in ('locked', 'deleted') and locked_at is null and deleted_at is null)
    ),
    check (locked_at is null or locked_at >= server_received_at),
    check (deleted_at is null or deleted_at >= server_received_at)
);

CREATE TABLE submission_entry_replacements
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    thread_id            integer not null references submission_threads (id),
    student_user_id      integer not null references users (id),
    replaced_entry_id    integer not null unique references submission_entries (id),
    replacement_entry_id integer not null unique references submission_entries (id),
    idempotency_key      text    not null
        check (
            length(idempotency_key) between 1 and 200
            and idempotency_key = trim(idempotency_key)
        ),
    replaced_at          text    not null,
    unique (student_user_id, idempotency_key),
    check (replaced_entry_id <> replacement_entry_id)
);

CREATE TABLE submission_material_reassignment_items
(
    reassignment_id integer not null references submission_material_reassignments (id),
    source_entry_id integer not null references submission_entries (id),
    item_kind       text    not null check (item_kind in ('entry_text', 'attachment')),
    attachment_id   integer references submission_attachments (id),
    ordinal         integer not null check (ordinal >= 0),
    primary key (reassignment_id, ordinal),
    check (
        (item_kind = 'entry_text' and attachment_id is null)
        or (item_kind = 'attachment' and attachment_id is not null)
    )
);

CREATE TABLE submission_material_reassignments
(
    id                   integer primary key,
    public_id            text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id      integer not null references users (id),
    source_thread_id     integer not null,
    target_thread_id     integer not null,
    source_problem_id    integer not null references problems (id),
    target_problem_id    integer not null references problems (id),
    performed_by_user_id integer not null references users (id),
    reason               text
        check (reason is null or (length(trim(reason)) between 1 and 2000)),
    request_id           text    not null
        check (length(request_id) between 1 and 200 and request_id = trim(request_id)),
    created_at           text    not null,
    foreign key (source_thread_id, student_user_id, source_problem_id)
        references submission_threads (id, student_user_id, problem_id),
    foreign key (target_thread_id, student_user_id, target_problem_id)
        references submission_threads (id, student_user_id, problem_id),
    unique (performed_by_user_id, request_id),
    check (source_thread_id <> target_thread_id),
    check (source_problem_id <> target_problem_id)
);

CREATE TABLE submission_review_annotations
(
    id             integer primary key,
    public_id      text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    review_id      integer not null references submission_reviews (id),
    attachment_id  integer not null references submission_attachments (id),
    schema_version integer not null check (schema_version = 1),
    rotation       integer not null check (rotation in (0, 90, 180, 270)),
    marks_json     text    not null
        check (
            json_valid(marks_json) = 1
            and json_type(marks_json) = 'array'
            and json_array_length(marks_json) between 1 and 250
            and length(marks_json) <= 1000000
        ),
    payload_sha256 text    not null
        check (length(payload_sha256) = 64 and payload_sha256 not glob '*[^0-9a-f]*'),
    created_at     text    not null,
    unique (review_id, attachment_id),
    foreign key (review_id, attachment_id)
        references submission_review_evidence_attachments (review_id, attachment_id)
);

CREATE TABLE submission_review_events
(
    id          integer primary key,
    public_id   text not null unique,
    review_id   integer not null references submission_reviews (id),
    event_kind  text not null check (event_kind in ('completed')),
    payload_json text not null check (json_valid(payload_json) = 1),
    created_at  text not null
);

CREATE TABLE submission_review_evidence_attachments
(
    review_id     integer not null references submission_reviews (id),
    attachment_id integer not null references submission_attachments (id),
    entry_id      integer not null references submission_entries (id),
    asset_id      integer not null references media_assets (id),
    ordinal       integer not null check (ordinal >= 0),
    primary key (review_id, attachment_id),
    foreign key (review_id, entry_id)
        references submission_review_evidence_entries (review_id, entry_id),
    foreign key (attachment_id, entry_id)
        references submission_attachments (id, entry_id)
);

CREATE TABLE submission_review_evidence_entries
(
    review_id          integer not null references submission_reviews (id),
    entry_id           integer not null references submission_entries (id),
    thread_id          integer not null references submission_threads (id),
    problem_id         integer not null references problems (id),
    entry_version      integer not null check (entry_version > 0),
    server_received_at text    not null,
    primary key (review_id, entry_id),
    foreign key (entry_id, thread_id)
        references submission_entries (id, thread_id)
);

CREATE TABLE submission_review_internal_reaction_events
(
    id            integer primary key,
    public_id     text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    review_id     integer not null references submission_reviews (id),
    actor_user_id integer not null references users (id),
    event_kind    text    not null check (event_kind in ('selected', 'changed', 'deleted')),
    reaction_id   integer references reaction_enum (reaction_id),
    state_version integer not null check (state_version > 0),
    created_at    text    not null,
    unique (review_id, state_version),
    check (
        (event_kind = 'deleted' and reaction_id is null)
        or (event_kind in ('selected', 'changed') and reaction_id is not null)
    )
);

CREATE TABLE submission_review_internal_reactions
(
    review_id       integer primary key references submission_reviews (id),
    actor_user_id   integer not null references users (id),
    reaction_id     integer references reaction_enum (reaction_id),
    created_at      text    not null,
    editable_until  text    not null,
    updated_at      text    not null,
    deleted_at      text,
    version         integer not null check (version > 0),
    check (editable_until >= created_at),
    check (updated_at between created_at and editable_until),
    check (
        (reaction_id is not null and deleted_at is null)
        or (reaction_id is null and deleted_at is not null)
    ),
    check (deleted_at is null or deleted_at = updated_at)
);

CREATE TABLE submission_review_student_reaction_events
(
    id            integer primary key,
    public_id     text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    review_id     integer not null references submission_reviews (id),
    actor_user_id integer not null references users (id),
    event_kind    text    not null check (event_kind in ('selected', 'changed', 'deleted')),
    reaction_id   integer references reaction_enum (reaction_id),
    state_version integer not null check (state_version > 0),
    created_at    text    not null,
    unique (review_id, state_version),
    check (
        (event_kind = 'deleted' and reaction_id is null)
        or (event_kind in ('selected', 'changed') and reaction_id is not null)
    )
);

CREATE TABLE submission_review_student_reactions
(
    review_id       integer primary key references submission_reviews (id),
    actor_user_id   integer not null references users (id),
    reaction_id     integer references reaction_enum (reaction_id),
    created_at      text    not null,
    editable_until  text    not null,
    updated_at      text    not null,
    deleted_at      text,
    version         integer not null check (version > 0),
    check (editable_until >= created_at),
    check (updated_at between created_at and editable_until),
    check (
        (reaction_id is not null and deleted_at is null)
        or (reaction_id is null and deleted_at is not null)
    ),
    check (deleted_at is null or deleted_at = updated_at)
);

CREATE TABLE submission_reviews
(
    id                        integer primary key,
    public_id                 text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    thread_id                 integer not null references submission_threads (id),
    -- Queue rows are deleted by the same transaction.  These are immutable
    -- provenance snapshots rather than foreign keys to ephemeral work items.
    queue_id                  integer not null,
    queue_public_id           text    not null,
    reviewer_user_id          integer not null references users (id),
    evidence_through_entry_id integer not null references submission_entries (id),
    expected_thread_version   integer not null check (expected_thread_version > 0),
    verdict                   integer not null,
    comment_entry_id          integer references submission_entries (id),
    result_id                 integer not null unique references results (id),
    review_duration_sec       integer check (review_duration_sec is null or review_duration_sec >= 0),
    source                    text    not null check (source in ('staff', 'telegram', 'ai')),
    idempotency_key           text    not null
        check (length(idempotency_key) between 1 and 200 and idempotency_key = trim(idempotency_key)),
    payload_sha256            text    not null
        check (length(payload_sha256) = 64 and payload_sha256 not glob '*[^0-9a-f]*'),
    created_at                text    not null,
    unique (reviewer_user_id, idempotency_key)
);

CREATE TABLE submission_threads
(
    id                    integer primary key,
    public_id             text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id       integer not null references users (id),
    problem_id            integer not null references problems (id),
    -- The public conditionRevisionId contract names the source/content
    -- revision. A scope trigger below proves the concrete problem has a
    -- problem_revision inside that content revision.
    condition_revision_id integer not null references content_revisions (id),
    status                 text    not null
        check (status in ('open', 'awaiting_review', 'needs_work', 'accepted', 'closed')),
    latest_result_id       integer,
    latest_entry_at        text    not null,
    created_at             text    not null,
    updated_at             text    not null,
    version                integer not null default 1 check (version > 0),
    foreign key (latest_result_id, student_user_id, problem_id)
        references results (id, student_id, problem_id),
    check (latest_entry_at >= created_at),
    check (updated_at >= created_at),
    check (status not in ('needs_work', 'accepted') or latest_result_id is not null)
);

CREATE TABLE support_entries
(
    id                 integer primary key,
    public_id          text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    thread_id          integer not null references support_threads (id),
    author_kind        text    not null
        check (author_kind in ('student', 'teacher', 'admin', 'system')),
    author_user_id     integer references users (id),
    text               text check (text is null or length(text) <= 100000),
    asset_id           integer references media_assets (id),
    channel            text    not null
        check (channel in ('pwa', 'telegram', 'staff', 'system')),
    client_created_at  text,
    server_received_at text    not null,
    idempotency_key    text
        check (
            idempotency_key is null
            or (
                length(idempotency_key) between 1 and 200
                and idempotency_key = trim(idempotency_key)
            )
        ),
    payload_sha256     text
        check (
            payload_sha256 is null
            or (
                length(payload_sha256) = 64
                and payload_sha256 not glob '*[^0-9a-f]*'
            )
        ),
    legacy_question_id integer references questions (id),
    legacy_problem_id  integer,
    created_at         text    not null,
    check ((idempotency_key is null) = (payload_sha256 is null)),
    check (text is not null or asset_id is not null),
    check (text is null or length(trim(text)) > 0),
    check (
        (author_kind in ('student', 'teacher', 'admin') and author_user_id is not null)
        or (author_kind = 'system' and author_user_id is null)
    ),
    check (
        (author_kind = 'student' and channel in ('pwa', 'telegram'))
        or (author_kind in ('teacher', 'admin') and channel in ('staff', 'telegram'))
        or (author_kind = 'system' and channel = 'system')
    ),
    check (server_received_at >= created_at)
);

CREATE TABLE support_threads
(
    id                integer primary key,
    public_id         text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id   integer not null references users (id),
    problem_id        integer references problems (id),
    group_lesson_id   integer references group_lessons (id),
    kind              text    not null
        check (kind in ('problem_question', 'sos', 'general')),
    latest_entry_at   text    not null,
    created_at        text    not null,
    updated_at        text    not null,
    version           integer not null default 1 check (version > 0),
    check (latest_entry_at >= created_at),
    check (updated_at >= created_at),
    check (
        (kind = 'problem_question' and problem_id is not null and group_lesson_id is not null)
        or (kind = 'general' and problem_id is null and group_lesson_id is not null)
        or (kind = 'sos' and problem_id is null)
    )
);

CREATE TABLE survey_assigns
(
    id        INTEGER primary key,
    user_id   INTEGER not null references users,
    survey_id INTEGER not null references surveys,
    unique (user_id)
);

CREATE TABLE survey_choices
(
    id        INTEGER primary key,
    survey_id INTEGER not null references surveys,
    text      TEXT    not null
);

CREATE TABLE survey_results
(
    id            INTEGER primary key,
    survey_id     INTEGER   not null references surveys,
    user_id       INTEGER   not null references users,
    selection_ids TEXT      not null,
    ts            timestamp not null,
    unique (survey_id, user_id)
);

CREATE TABLE surveys
(
    id          INTEGER primary key,
    survey_type CHAR(1)   not null,
    is_active   BOOL      not null,
    question    TEXT      not null,
    ts          timestamp not null
);

CREATE TABLE telegram_bindings
(
    id                  integer primary key,
    public_id           text    not null unique,
    owner_type          text    not null check (owner_type in ('course', 'group')),
    owner_course_id     integer references courses (id),
    owner_group_id      text references groups (group_id),
    purpose             text    not null
        check (purpose in ('news_source', 'materials_target')),
    chat_id             integer not null check (chat_id <> 0),
    message_thread_id   integer check (message_thread_id is null or message_thread_id > 0),
    title_cached        text check (
        title_cached is null
        or (title_cached = trim(title_cached) and length(title_cached) between 1 and 200)
    ),
    status              text    not null check (status in ('draft', 'verified', 'disabled')),
    verified_at         text,
    created_by_user_id  integer not null references users (id),
    updated_by_user_id  integer not null references users (id),
    created_at          text    not null,
    updated_at          text    not null,
    version             integer not null default 1 check (version > 0),
    check (
        (owner_type = 'course' and owner_course_id is not null and owner_group_id is null)
        or (owner_type = 'group' and owner_course_id is null and owner_group_id is not null)
    ),
    check (
        (status = 'verified' and verified_at is not null)
        or status <> 'verified'
    )
);

CREATE TABLE test_attempts
(
    id                     integer primary key,
    public_id              text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    student_user_id        integer not null references users (id),
    problem_id             integer not null references problems (id),
    problem_revision_id    integer not null,
    answer_payload_json    text    not null
        check (
            json_valid(answer_payload_json) = 1
            and json_type(answer_payload_json) = 'object'
            and json_type(answer_payload_json, '$.displayAnswer') = 'text'
        ),
    normalized_answer_json text
        check (
            normalized_answer_json is null
            or json_valid(normalized_answer_json) = 1
        ),
    parse_status           text    not null
        check (parse_status in ('valid', 'invalid_format')),
    counts_as_attempt      integer not null
        check (counts_as_attempt in (0, 1)),
    check_status           text    not null
        check (check_status in ('pending_configuration', 'pending', 'checked', 'failed')),
    client_created_at      text    not null,
    server_received_at     text    not null,
    clock_skew_seconds     integer,
    clock_suspicious       integer not null default 0
        check (clock_suspicious in (0, 1)),
    idempotency_key        text    not null
        check (
            length(idempotency_key) between 1 and 200
            and idempotency_key = trim(idempotency_key)
        ),
    payload_sha256         text    not null
        check (
            length(payload_sha256) = 64
            and payload_sha256 not glob '*[^0-9a-f]*'
        ),
    checker_version        text
        check (checker_version is null or length(trim(checker_version)) > 0),
    verdict                integer,
    result_id              integer,
    created_at             text    not null,
    checked_at             text,
    unique (student_user_id, idempotency_key),
    foreign key (problem_revision_id, problem_id)
        references problem_revisions (id, problem_id),
    foreign key (result_id, student_user_id, problem_id)
        references results (id, student_id, problem_id),
    check (server_received_at >= created_at),
    check (
        (clock_suspicious = 0 and (clock_skew_seconds is null or abs(clock_skew_seconds) <= 3600))
        or (clock_suspicious = 1 and clock_skew_seconds is not null and abs(clock_skew_seconds) > 3600)
    ),
    check ((verdict is null) = (result_id is null)),
    check (
        (
            parse_status = 'invalid_format'
            and counts_as_attempt = 0
            and normalized_answer_json is null
            and check_status = 'checked'
            and checker_version is null
            and verdict is null
            and result_id is null
            and checked_at is not null
        )
        or (
            parse_status = 'valid'
            and counts_as_attempt = 1
            and normalized_answer_json is not null
            and (
                (
                    check_status = 'pending_configuration'
                    and checker_version is null
                    and verdict is null
                    and result_id is null
                    and checked_at is null
                )
                or (
                    check_status = 'pending'
                    and checker_version is not null
                    and verdict is null
                    and result_id is null
                    and checked_at is null
                )
                or (
                    check_status = 'checked'
                    and checker_version is not null
                    and verdict is not null
                    and result_id is not null
                    and checked_at is not null
                )
                or (
                    check_status = 'failed'
                    and checker_version is not null
                    and verdict is null
                    and result_id is null
                    and checked_at is not null
                )
            )
        )
    )
);

CREATE TABLE user_changes_log
(
    ts          timestamp not null,
    user_id     INTEGER   not null references users,
    change_type text      not null,
    new_value   text      not null
);

CREATE TABLE "users"
(
    id             INTEGER
        primary key,
    chat_id        INTEGER
        unique,
    type           INTEGER not null,
    group_id       text
        references groups,
    name           TEXT    not null,
    surname        TEXT    not null,
    middlename     TEXT,
    token          TEXT
        unique,
    online         INTEGER,
    grade          int,
    birthday       int,
    allowed_groups text
, public_id text
    check (
        public_id is null
        or (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        )
    ));

CREATE TABLE verdicts
(
    id   INTEGER primary key,
    tick TEXT not null,
    val  REAL not null
);

CREATE TABLE waitlist
(
    id         INTEGER primary key unique,
    student_id INTEGER   not null unique references users,
    entered    timestamp not null,
    problem_id INTEGER   not null references problems
);

CREATE TABLE webtokens
(
    user_id  INTEGER primary key unique references users,
    webtoken TEXT not null unique
);

CREATE TABLE written_tasks_discussions
(
    id          INTEGER primary key unique,
    ts          timestamp not null,
    student_id  INTEGER   not null references users,
    problem_id  INTEGER   not null references problems,
    teacher_id  INTEGER references users,
    text        TEXT,
    attach_path TEXT,
    chat_id     INTEGER,
    tg_msg_id   INTEGER
);

CREATE TABLE written_tasks_queue
(
    id               integer primary key unique,
    public_id        text unique
        check (
            public_id is null
            or (
                length(public_id) between 1 and 128
                and public_id not glob '*[^a-z0-9._:-]*'
                and substr(public_id, 1, 1) glob '[a-z0-9]'
                and substr(public_id, -1, 1) glob '[a-z0-9]'
            )
        ),
    ts               timestamp not null,
    student_id       integer   not null references users,
    problem_id       integer   not null references problems,
    cur_status       integer   not null,
    teacher_ts       timestamp,
    teacher_id       integer references users,
    claim_token      text
        check (
            claim_token is null
            or (
                length(claim_token) between 1 and 128
                and claim_token not glob '*[^a-z0-9._:-]*'
                and substr(claim_token, 1, 1) glob '[a-z0-9]'
                and substr(claim_token, -1, 1) glob '[a-z0-9]'
            )
        ),
    claimed_at       text,
    lease_expires_at text,
    lease_version    integer not null default 0 check (lease_version >= 0),
    updated_at       text    not null
        default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    unique (student_id, problem_id),
    check (
        claim_token is null
        or (
            teacher_id is not null
            and claimed_at is not null
            and lease_expires_at is not null
            and lease_expires_at > claimed_at
        )
    ),
    check (
        claim_token is not null
        or (claimed_at is null and lease_expires_at is null)
    ),
    check (teacher_id is null or typeof(teacher_id) = 'integer')
);

CREATE TABLE z_settings
(
    id        INTEGER primary key,
    key       text      not null unique,
    value     text      not null,
    change_ts timestamp not null
);

CREATE TABLE z_ui_messages
(
    id        INTEGER primary key,
    key       text      not null unique,
    value     text      not null,
    change_ts timestamp not null
);

CREATE TABLE "zoom_conversation"
(
    id                   INTEGER
        primary key,
    ts                   TEXT    not null,
    student_id           INTEGER not null
        references users,
    teacher_id           INTEGER not null
        references users,
    group_id             text
        references groups,
    lesson               INTEGER not null,
    check_time_spent_sec INTEGER
);

CREATE TABLE zoom_events
(
    id                 INTEGER primary key,
    event_ts           TIMESTAMP not null,
    event              TEXT      not null,
    zoom_user_name     TEXT,
    zoom_user_id       INTEGER,
    breakout_room_uuid TEXT,
    user_id            INTEGER references users
);

CREATE TABLE zoom_queue
(
    zoom_user_name TEXT      not null primary key unique,
    enter_ts       timestamp not null,
    status         INTEGER   not null
);

CREATE INDEX auth_accounts_audience_status_idx
    on auth_accounts (audience, status);

CREATE UNIQUE INDEX auth_accounts_linked_user_audience_uq
    on auth_accounts (linked_user_id, audience)
    where linked_user_id is not null;

CREATE INDEX auth_events_account_occurred_idx
    on auth_events (account_id, occurred_at, id);

CREATE INDEX auth_events_request_idx
    on auth_events (request_id);

CREATE INDEX auth_events_session_occurred_idx
    on auth_events (session_id, occurred_at, id);

CREATE INDEX auth_events_type_occurred_idx
    on auth_events (event_type, occurred_at, id);

CREATE INDEX auth_refresh_consumed_secrets_expires_idx
    on auth_refresh_consumed_secrets (expires_at);

CREATE INDEX auth_sessions_account_revoked_expires_idx
    on auth_sessions (account_id, revoked_at, expires_at);

CREATE INDEX auth_sessions_audience_revoked_expires_idx
    on auth_sessions (audience, revoked_at, expires_at);

CREATE INDEX auth_sessions_expires_idx
    on auth_sessions (expires_at);

CREATE INDEX auth_throttle_buckets_locked_idx
    on auth_throttle_buckets (locked_until)
    where locked_until is not null;

CREATE INDEX auth_throttle_buckets_updated_idx
    on auth_throttle_buckets (updated_at);

CREATE INDEX classroom_assignment_delivery_batches_plan_idx
    on classroom_assignment_delivery_batches (assignment_plan_id, id);

CREATE INDEX classroom_assignment_delivery_recipients_student_idx
    on classroom_assignment_delivery_recipients
       (student_user_id, course_enrollment_id, batch_id);

CREATE INDEX classroom_assignment_plans_event_timeline_idx
    on classroom_assignment_plans (in_person_event_id, id);

CREATE UNIQUE INDEX classroom_assignment_plans_one_confirmed_uq
    on classroom_assignment_plans (in_person_event_id)
    where state = 'confirmed';

CREATE UNIQUE INDEX classroom_assignment_plans_one_working_uq
    on classroom_assignment_plans (in_person_event_id)
    where state in ('draft', 'stale');

CREATE INDEX classroom_assignments_enrollment_history_idx
    on classroom_assignments (course_enrollment_id, plan_id);

CREATE INDEX classroom_assignments_room_idx
    on classroom_assignments (plan_id, classroom_id, course_enrollment_id);

CREATE INDEX classroom_events_timeline_idx
    on classroom_events (classroom_id, id);

CREATE INDEX classroom_layout_rooms_group_idx
    on classroom_layout_rooms (layout_version_id, group_lesson_id, classroom_id);

CREATE INDEX classroom_layout_versions_event_timeline_idx
    on classroom_layout_versions (in_person_event_id, id);

CREATE UNIQUE INDEX classroom_layout_versions_one_confirmed_uq
    on classroom_layout_versions (in_person_event_id)
    where state = 'confirmed';

CREATE UNIQUE INDEX classroom_layout_versions_one_draft_uq
    on classroom_layout_versions (in_person_event_id)
    where state = 'draft';

CREATE INDEX classrooms_status_name_idx
    on classrooms (status, normalized_name, id);

CREATE INDEX content_derivatives_asset_idx
    on content_derivatives (asset_id, revision_id)
    where asset_id is not null;

CREATE INDEX content_problem_matches_problem_idx
    on content_problem_matches (problem_id, content_revision_id)
    where problem_id is not null;

CREATE INDEX content_revision_assets_asset_idx
    on content_revision_assets (asset_id, revision_id);

CREATE INDEX content_revisions_source_created_idx
    on content_revisions (source_id, revision_number, created_at, id);

CREATE INDEX content_sources_group_kind_idx
    on content_sources (group_lesson_id, kind, archived_at, id);

CREATE UNIQUE INDEX content_sources_one_active_material_uq
    on content_sources (group_lesson_id, kind)
    where archived_at is null;

CREATE INDEX course_enrollment_events_timeline_idx
    on course_enrollment_events (enrollment_id, occurred_at, id);

CREATE INDEX course_enrollment_events_type_timeline_idx
    on course_enrollment_events (event_type, occurred_at, id);

CREATE INDEX course_enrollments_active_group_idx
    on course_enrollments (active_group_id, status, student_user_id);

CREATE INDEX course_enrollments_course_status_idx
    on course_enrollments (course_id, status, student_user_id);

CREATE INDEX course_group_access_enrollment_history_idx
    on course_group_access (enrollment_id, valid_from, valid_to);

CREATE INDEX course_group_access_group_active_idx
    on course_group_access (course_id, group_id, valid_to, enrollment_id);

CREATE UNIQUE INDEX course_group_access_one_active_uq
    on course_group_access (enrollment_id, group_id)
    where valid_to is null;

CREATE INDEX course_lessons_course_number_idx
    on course_lessons (course_id, lesson_number, id);

CREATE INDEX course_schedule_rules_history_idx
    on course_schedule_rules (course_id, schedule_field, rule_version, id);

CREATE UNIQUE INDEX course_schedule_rules_one_active_uq
    on course_schedule_rules (course_id, schedule_field)
    where state = 'active';

CREATE UNIQUE INDEX course_schedule_rules_one_draft_uq
    on course_schedule_rules (course_id, schedule_field)
    where state = 'draft';

CREATE INDEX courses_season_status_order_idx
    on courses (season_id, status, sort_order, id);

CREATE INDEX family_student_links_student_revoked_idx
    on family_student_links (student_user_id, revoked_at);

CREATE INDEX group_lessons_course_group_idx
    on group_lessons (course_id, group_id, course_lesson_id, id);

CREATE INDEX group_schedule_overrides_history_idx
    on group_schedule_overrides
       (course_id, group_id, schedule_field, override_version, id);

CREATE UNIQUE INDEX group_schedule_overrides_one_active_uq
    on group_schedule_overrides (course_id, group_id, schedule_field)
    where state = 'active';

CREATE UNIQUE INDEX group_schedule_overrides_one_draft_uq
    on group_schedule_overrides (course_id, group_id, schedule_field)
    where state = 'draft';

CREATE UNIQUE INDEX groups_course_group_uq
    on groups (course_id, group_id);

CREATE UNIQUE INDEX groups_course_public_name_uq
    on groups (course_id, public_name)
    where course_id is not null;

CREATE UNIQUE INDEX groups_course_short_code_uq
    on groups (course_id, short_code)
    where course_id is not null;

CREATE UNIQUE INDEX groups_public_id_uq
    on groups (public_id)
    where public_id is not null;

CREATE INDEX hint_reveals_student_timeline_idx
    on hint_reveals (student_user_id, revealed_at, id);

CREATE INDEX idempotency_records_expiry_idx
    on idempotency_records (expires_at, id)
    where expires_at is not null;

CREATE INDEX in_person_event_group_lessons_lesson_idx
    on in_person_event_group_lessons (group_lesson_id, in_person_event_id);

CREATE INDEX in_person_events_season_time_idx
    on in_person_events (season_id, starts_at, id);

CREATE UNIQUE INDEX lesson_publications_one_published_uq
    on lesson_publications (group_lesson_id, kind)
    where state = 'published';

CREATE UNIQUE INDEX lesson_publications_one_scheduled_uq
    on lesson_publications (group_lesson_id, kind)
    where state = 'scheduled';

CREATE INDEX lesson_publications_timeline_idx
    on lesson_publications (group_lesson_id, kind, created_at, id);

CREATE INDEX lesson_window_changes_timeline_idx
    on lesson_window_changes (lesson_window_id, id);

CREATE INDEX lesson_window_schedule_sources_rule_idx
    on lesson_window_schedule_sources (course_schedule_rule_id, lesson_window_id);

CREATE INDEX lesson_windows_close_idx
    on lesson_windows (submission_closes_at, group_lesson_id);

CREATE UNIQUE INDEX media_assets_content_hash_version_uq
    on media_assets (storage_namespace, sha256, conversion_version)
    where storage_namespace in ('content', 'generated') and deleted_at is null;

CREATE INDEX media_assets_namespace_created_idx
    on media_assets (storage_namespace, created_at, id);

CREATE INDEX notification_deliveries_due_idx
    on notification_deliveries (state, next_attempt_at, id);

CREATE INDEX notification_events_account_unread_idx
    on notification_events (account_id, read_at, occurred_at desc, id desc);

CREATE UNIQUE INDEX problem_revisions_id_problem_uq
    on problem_revisions (id, problem_id);

CREATE INDEX problem_revisions_title_idx
    on problem_revisions (normalized_title, content_revision_id, problem_id);

CREATE INDEX problem_synonym_groups_lesson_status_idx
    on problem_synonym_groups (course_lesson_id, status, id);

CREATE UNIQUE INDEX problem_synonym_members_group_lesson_active_uq
    on problem_synonym_members (synonym_group_id, group_lesson_id)
    where removed_at is null;

CREATE INDEX problem_synonym_members_history_idx
    on problem_synonym_members (synonym_group_id, added_at, id);

CREATE UNIQUE INDEX problem_synonym_members_problem_active_uq
    on problem_synonym_members (problem_id)
    where removed_at is null;

CREATE INDEX problems_by_synonyms
    on problems (synonyms);

CREATE UNIQUE INDEX problems_public_id_uq
    on problems (public_id)
    where public_id is not null;

CREATE INDEX push_subscriptions_account_idx
    on push_subscriptions (account_id, updated_at desc);

CREATE INDEX results_by_student_problem
    on results (student_id, problem_id);

CREATE UNIQUE INDEX results_id_student_problem_uq
    on results (id, student_id, problem_id);

CREATE INDEX results_teacher_id_lesson_index
    on results (teacher_id, lesson)
    where res_type = 2;

CREATE INDEX solution_reveals_student_timeline_idx
    on solution_reveals (student_user_id, revealed_at, id);

CREATE INDEX staff_scopes_lookup_idx
    on staff_scopes (staff_user_id, course_id, group_id, valid_to);

CREATE UNIQUE INDEX staff_scopes_one_active_course_role_uq
    on staff_scopes (staff_user_id, course_id, role)
    where group_id is null and valid_to is null;

CREATE UNIQUE INDEX staff_scopes_one_active_group_role_uq
    on staff_scopes (staff_user_id, course_id, group_id, role)
    where group_id is not null and valid_to is null;

CREATE INDEX submission_attachments_asset_idx
    on submission_attachments (asset_id, id);

CREATE INDEX submission_attachments_entry_order_idx
    on submission_attachments (entry_id, ordinal, id);

CREATE UNIQUE INDEX submission_attachments_id_entry_uq
    on submission_attachments (id, entry_id);

CREATE UNIQUE INDEX submission_entries_author_idempotency_uq
    on submission_entries (author_user_id, idempotency_key)
    where idempotency_key is not null;

CREATE UNIQUE INDEX submission_entries_id_thread_uq
    on submission_entries (id, thread_id);

CREATE INDEX submission_entries_legacy_group_idx
    on submission_entries (channel_group_key, id)
    where channel = 'telegram' and channel_group_key is not null;

CREATE INDEX submission_entries_thread_history_idx
    on submission_entries (thread_id, server_received_at, id);

CREATE INDEX submission_entry_replacements_thread_history_idx
    on submission_entry_replacements (thread_id, replaced_at, id);

CREATE INDEX submission_material_reassignment_items_projection_idx
    on submission_material_reassignment_items
       (source_entry_id, item_kind, attachment_id, reassignment_id, ordinal);

CREATE INDEX submission_material_reassignments_student_history_idx
    on submission_material_reassignments (student_user_id, created_at, id);

CREATE INDEX submission_review_annotations_attachment_idx
    on submission_review_annotations (attachment_id, review_id);

CREATE INDEX submission_review_evidence_attachments_asset_idx
    on submission_review_evidence_attachments (asset_id, review_id);

CREATE INDEX submission_review_evidence_attachments_attachment_idx
    on submission_review_evidence_attachments (attachment_id, review_id);

CREATE INDEX submission_review_evidence_entries_entry_idx
    on submission_review_evidence_entries (entry_id, review_id);

CREATE INDEX submission_review_internal_reaction_events_review_idx
    on submission_review_internal_reaction_events (review_id, created_at, id);

CREATE INDEX submission_review_student_reaction_events_review_idx
    on submission_review_student_reaction_events (review_id, created_at, id);

CREATE INDEX submission_reviews_thread_history_idx
    on submission_reviews (thread_id, created_at, id);

CREATE UNIQUE INDEX submission_threads_id_owner_problem_uq
    on submission_threads (id, student_user_id, problem_id);

CREATE UNIQUE INDEX submission_threads_one_active_uq
    on submission_threads (student_user_id, problem_id)
    where status <> 'closed';

CREATE INDEX submission_threads_review_queue_idx
    on submission_threads (latest_entry_at, id)
    where status = 'awaiting_review';

CREATE INDEX submission_threads_student_updated_idx
    on submission_threads (student_user_id, updated_at desc, id desc);

CREATE UNIQUE INDEX support_entries_author_idempotency_uq
    on support_entries (author_user_id, idempotency_key)
    where idempotency_key is not null;

CREATE INDEX support_entries_legacy_question_idx
    on support_entries (legacy_question_id, id)
    where legacy_question_id is not null;

CREATE INDEX support_entries_thread_timeline_idx
    on support_entries (thread_id, server_received_at, id);

CREATE UNIQUE INDEX support_threads_general_question_uq
    on support_threads (student_user_id, group_lesson_id)
    where kind = 'general';

CREATE UNIQUE INDEX support_threads_problem_question_uq
    on support_threads (student_user_id, group_lesson_id, problem_id)
    where kind = 'problem_question';

CREATE INDEX support_threads_staff_timeline_idx
    on support_threads (group_lesson_id, latest_entry_at desc, id desc);

CREATE INDEX support_threads_student_timeline_idx
    on support_threads (student_user_id, latest_entry_at desc, id desc);

CREATE INDEX telegram_bindings_course_idx
    on telegram_bindings (owner_course_id, purpose, status, id);

CREATE INDEX telegram_bindings_group_idx
    on telegram_bindings (owner_group_id, purpose, status, id);

CREATE UNIQUE INDEX telegram_bindings_owner_destination_uq
    on telegram_bindings (
        owner_type,
        ifnull(owner_course_id, -1),
        ifnull(owner_group_id, ''),
        purpose,
        chat_id,
        ifnull(message_thread_id, -1)
    );

CREATE INDEX test_attempts_pending_configuration_idx
    on test_attempts (problem_id, server_received_at, id)
    where check_status = 'pending_configuration';

CREATE INDEX test_attempts_student_problem_counted_idx
    on test_attempts (student_user_id, problem_id, server_received_at, id)
    where counts_as_attempt = 1;

CREATE INDEX test_attempts_student_problem_history_idx
    on test_attempts (student_user_id, problem_id, server_received_at desc, id desc);

CREATE UNIQUE INDEX users_public_id_uq
    on users (public_id)
    where public_id is not null;

CREATE INDEX waitlist_by_student
    on waitlist (student_id);

CREATE INDEX written_tasks_discussions_by_task
    on written_tasks_discussions (student_id, problem_id, ts);

CREATE INDEX written_tasks_queue_by_tst
    on written_tasks_queue (ts desc);

CREATE INDEX written_tasks_queue_claim_token_idx
    on written_tasks_queue (claim_token, id)
    where claim_token is not null;

CREATE INDEX written_tasks_queue_lease_expiry_idx
    on written_tasks_queue (lease_expires_at, id)
    where claim_token is not null;

CREATE INDEX written_tasks_queue_problem_waiting_idx
    on written_tasks_queue (problem_id, ts, id);

CREATE INDEX zoom_queue_by_ts
    on zoom_queue (enter_ts);

CREATE VIEW reaction_enum_view AS
SELECT *
FROM reaction_enum
         JOIN reaction_type_enum USING (reaction_type_id);

CREATE VIEW reaction_view AS
SELECT rct.ts,
       reaction_type,
       problem_id,
       result_id,
       stud.name || ' ' || stud.surname || ' ' || stud.middlename    AS student_name,
       reaction_enum.reaction,
       teach.name || ' ' || teach.surname || ' ' || teach.middlename AS teacher_name,
       coalesce(r.lesson, zc.lesson)                                 as lesson,
       coalesce(r.group_id, zc.group_id)                             as group_id,
       verdict,
       coalesce(r.check_time_spent_sec, zc.check_time_spent_sec)     as check_time_spent_sec
FROM reactions rct
         JOIN reaction_enum USING (reaction_id)
         JOIN reaction_type_enum USING (reaction_type_id)
         LEFT JOIN results r ON rct.result_id = r.id
         LEFT JOIN zoom_conversation zc on rct.zoom_conversation_id = zc.id
         LEFT JOIN users AS stud ON (stud.id = coalesce(r.student_id, zc.student_id))
         LEFT JOIN users AS teach ON (teach.id = coalesce(r.teacher_id, zc.teacher_id));

CREATE TRIGGER auth_accounts_audience_update
before update of audience on auth_accounts
for each row
when new.audience <> old.audience and (
    exists (
        select 1 from auth_sessions where account_id = old.id
    )
    or exists (
        select 1 from family_student_links where family_account_id = old.id
    )
)
begin
    select raise(abort, 'account audience is immutable after links or sessions exist');
end;

CREATE TRIGGER auth_accounts_linked_user_immutable
before update of linked_user_id on auth_accounts
for each row
when new.linked_user_id is not old.linked_user_id
begin
    select raise(abort, 'auth account linked user is immutable');
end;

CREATE TRIGGER auth_sessions_audience_insert
before insert on auth_sessions
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.account_id and audience = new.audience
)
begin
    select raise(abort, 'auth session audience does not match account');
end;

CREATE TRIGGER auth_sessions_audience_update
before update of account_id, audience on auth_sessions
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.account_id and audience = new.audience
)
begin
    select raise(abort, 'auth session audience does not match account');
end;

CREATE TRIGGER classroom_assignments_delete_working_only
before delete on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

CREATE TRIGGER classroom_assignments_insert_working_only
before insert on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = new.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

CREATE TRIGGER classroom_assignments_update_working_only
before update on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

CREATE TRIGGER classroom_events_delete_forbidden
before delete on classroom_events
for each row
begin
    select raise(abort, 'classroom event deletion is forbidden');
end;

CREATE TRIGGER classroom_events_immutable_update
before update on classroom_events
for each row
begin
    select raise(abort, 'classroom event is immutable');
end;

CREATE TRIGGER classroom_layout_rooms_delete_draft_only
before delete on classroom_layout_rooms
for each row
when (select state from classroom_layout_versions where id = old.layout_version_id) <> 'draft'
begin
    select raise(abort, 'only a draft classroom layout can be edited');
end;

CREATE TRIGGER classroom_layout_rooms_insert_draft_only
before insert on classroom_layout_rooms
for each row
when (select state from classroom_layout_versions where id = new.layout_version_id) <> 'draft'
begin
    select raise(abort, 'only a draft classroom layout can be edited');
end;

CREATE TRIGGER classroom_layout_rooms_update_draft_only
before update on classroom_layout_rooms
for each row
when (select state from classroom_layout_versions where id = old.layout_version_id) <> 'draft'
begin
    select raise(abort, 'only a draft classroom layout can be edited');
end;

CREATE TRIGGER classrooms_delete_forbidden
before delete on classrooms
for each row
begin
    select raise(abort, 'classroom deletion is forbidden');
end;

CREATE TRIGGER content_derivatives_asset_hash_insert
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

CREATE TRIGGER content_derivatives_delete_forbidden
before delete on content_derivatives
for each row
begin
    select raise(abort, 'content derivative deletion is forbidden');
end;

CREATE TRIGGER content_derivatives_invalidation_once
before update on content_derivatives
for each row
when old.invalidated_at is not null
begin
    select raise(abort, 'content derivative invalidation is immutable');
end;

CREATE TRIGGER content_derivatives_payload_immutable
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

CREATE TRIGGER content_problem_matches_delete_forbidden
before delete on content_problem_matches
for each row
begin
    select raise(abort, 'content problem match deletion is forbidden');
end;

CREATE TRIGGER content_problem_matches_immutable_update
before update on content_problem_matches
for each row
begin
    select raise(abort, 'resolved content problem match is immutable');
end;

CREATE TRIGGER content_revision_assets_delete_forbidden
before delete on content_revision_assets
for each row
begin
    select raise(abort, 'content revision asset deletion is forbidden');
end;

CREATE TRIGGER content_revision_assets_immutable_update
before update on content_revision_assets
for each row
begin
    select raise(abort, 'content revision asset is immutable');
end;

CREATE TRIGGER content_revisions_delete_forbidden
before delete on content_revisions
for each row
begin
    select raise(abort, 'content revision deletion is forbidden');
end;

CREATE TRIGGER content_revisions_lineage_insert
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

CREATE TRIGGER content_revisions_source_immutable
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

CREATE TRIGGER content_revisions_status_transition_guard
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

CREATE TRIGGER content_revisions_terminal_state_immutable
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

CREATE TRIGGER content_sources_delete_forbidden
before delete on content_sources
for each row
begin
    select raise(abort, 'content source deletion is forbidden');
end;

CREATE TRIGGER content_sources_identity_archive_guard
before update on content_sources
for each row
when not (
    new.public_id is old.public_id
    and new.group_lesson_id is old.group_lesson_id
    and new.kind is old.kind
    and new.logical_filename is old.logical_filename
    and new.source_encoding is old.source_encoding
    and new.created_by_user_id is old.created_by_user_id
    and new.created_at is old.created_at
    and old.archived_at is null
    and new.archived_at is not null
    and new.archived_at >= old.created_at
)
begin
    select raise(abort, 'content source identity/archive transition is invalid');
end;

CREATE TRIGGER course_schedule_rules_delete_forbidden
before delete on course_schedule_rules
for each row
begin
    select raise(abort, 'course schedule rule deletion is forbidden');
end;

CREATE TRIGGER course_schedule_rules_payload_immutable
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

CREATE TRIGGER course_schedule_rules_state_transition_guard
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

CREATE TRIGGER family_student_links_family_account_insert
before insert on family_student_links
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.family_account_id and audience = 'family'
)
begin
    select raise(abort, 'family_student_links requires a family account');
end;

CREATE TRIGGER family_student_links_family_account_update
before update of family_account_id on family_student_links
for each row
when not exists (
    select 1
    from auth_accounts
    where id = new.family_account_id and audience = 'family'
)
begin
    select raise(abort, 'family_student_links requires a family account');
end;

CREATE TRIGGER group_schedule_overrides_delete_forbidden
before delete on group_schedule_overrides
for each row
begin
    select raise(abort, 'group schedule override deletion is forbidden');
end;

CREATE TRIGGER group_schedule_overrides_payload_immutable
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

CREATE TRIGGER group_schedule_overrides_rule_active_confirm
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

CREATE TRIGGER group_schedule_overrides_rule_scope_insert
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

CREATE TRIGGER group_schedule_overrides_state_transition_guard
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

CREATE TRIGGER hint_reveals_delete_forbidden
before delete on hint_reveals
for each row
begin
    select raise(abort, 'hint reveal deletion is forbidden');
end;

CREATE TRIGGER hint_reveals_immutable_update
before update on hint_reveals
for each row
begin
    select raise(abort, 'hint reveal is immutable');
end;

CREATE TRIGGER hint_reveals_publication_kind_insert
before insert on hint_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    join content_problem_matches as problem_match
      on problem_match.content_revision_id = publication.revision_id
     and problem_match.problem_id = new.problem_id
     and problem_match.resolved_at is not null
     and problem_match.decision <> 'omit'
    where publication.id = new.publication_id
      and publication.kind = 'hint'
      and publication.state = 'published'
)
begin
    select raise(abort, 'hint reveal requires a published matched hint');
end;

CREATE TRIGGER idempotency_records_account_scope_insert
before insert on idempotency_records
for each row
when not exists (
    select 1
    from auth_accounts as account
    where account.id = new.account_id
      and account.audience = new.audience
)
begin
    select raise(abort, 'idempotency account audience mismatch');
end;

CREATE TRIGGER idempotency_records_identity_immutable
before update on idempotency_records
for each row
when new.audience is not old.audience
    or new.account_id is not old.account_id
    or new.operation is not old.operation
    or new.idempotency_key is not old.idempotency_key
    or new.payload_sha256 is not old.payload_sha256
    or new.created_at is not old.created_at
    or new.expires_at is not old.expires_at
begin
    select raise(abort, 'idempotency record identity is immutable');
end;

CREATE TRIGGER idempotency_records_state_transition_guard
before update on idempotency_records
for each row
when not (
    old.state = 'processing'
    and new.state in ('completed', 'failed')
)
begin
    select raise(abort, 'invalid idempotency state transition');
end;

CREATE TRIGGER lesson_publications_activation_scope_insert
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

CREATE TRIGGER lesson_publications_delete_forbidden
before delete on lesson_publications
for each row
begin
    select raise(abort, 'publication deletion is forbidden');
end;

CREATE TRIGGER lesson_publications_identity_immutable
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

CREATE TRIGGER lesson_publications_revision_scope_insert
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

CREATE TRIGGER lesson_publications_revision_scope_update
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

CREATE TRIGGER lesson_publications_state_transition_guard
before update on lesson_publications
for each row
when new.state is not old.state and not (
    (old.state = 'scheduled' and new.state in ('published', 'hidden', 'superseded'))
    or (old.state = 'published' and new.state in ('hidden', 'superseded'))
)
begin
    select raise(abort, 'invalid publication state transition');
end;

CREATE TRIGGER lesson_publications_supersedes_scope_insert
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

CREATE TRIGGER lesson_publications_terminal_audit_guard
before update on lesson_publications
for each row
when not (
    old.state in ('scheduled', 'published')
    and new.state in ('hidden', 'superseded')
    and new.state is not old.state
    and new.version = old.version + 1
    and old.terminal_by_user_id is null
    and old.terminal_at is null
    and new.public_id is old.public_id
    and new.group_lesson_id is old.group_lesson_id
    and new.kind is old.kind
    and new.revision_id is old.revision_id
    and new.scheduled_at is old.scheduled_at
    and new.published_at is old.published_at
    and (
        (new.state = 'hidden' and new.hidden_at is not null)
        or (new.state = 'superseded' and new.hidden_at is old.hidden_at)
    )
    and new.created_by_user_id is old.created_by_user_id
    and new.published_by_user_id is old.published_by_user_id
    and new.provenance_kind is old.provenance_kind
    and new.supersedes_publication_id is old.supersedes_publication_id
    and new.activated_from_schedule_id is old.activated_from_schedule_id
    and new.created_at is old.created_at
    and new.updated_at >= old.updated_at
    and new.terminal_by_user_id is not null
    and new.terminal_at is not null
    and new.terminal_at is new.updated_at
    and new.terminal_at >= old.created_at
)
begin
    select raise(abort, 'publication terminal audit/version transition is invalid');
end;

CREATE TRIGGER lesson_publications_terminal_insert_guard
before insert on lesson_publications
for each row
when new.state not in ('scheduled', 'published')
    or (
        new.provenance_kind = 'interactive'
        and (
            new.created_by_user_id is null
            or (new.state = 'scheduled' and new.published_by_user_id is not null)
            or (new.state = 'published' and new.published_by_user_id is null)
        )
    )
    or (
        new.provenance_kind = 'legacy_backfill'
        and (
            new.state <> 'published'
            or new.created_by_user_id is not null
            or new.published_by_user_id is not null
            or new.supersedes_publication_id is not null
            or new.activated_from_schedule_id is not null
        )
    )
    or new.terminal_by_user_id is not null
    or new.terminal_at is not null
begin
    select raise(abort, 'publication must begin in an active non-terminal state');
end;

CREATE TRIGGER lesson_window_changes_delete_forbidden
before delete on lesson_window_changes
for each row
begin
    select raise(abort, 'lesson window audit deletion is forbidden');
end;

CREATE TRIGGER lesson_window_changes_immutable_update
before update on lesson_window_changes
for each row
begin
    select raise(abort, 'lesson window audit is immutable');
end;

CREATE TRIGGER lesson_window_schedule_sources_delete_forbidden
before delete on lesson_window_schedule_sources
for each row
begin
    select raise(abort, 'lesson window schedule source deletion is forbidden');
end;

CREATE TRIGGER lesson_window_schedule_sources_immutable_update
before update on lesson_window_schedule_sources
for each row
begin
    select raise(abort, 'lesson window schedule source is immutable');
end;

CREATE TRIGGER lesson_window_schedule_sources_scope_insert
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

CREATE TRIGGER media_assets_locked_submission_immutable
before update on media_assets
for each row
when exists (
    select 1
    from submission_attachments as attachment
    where attachment.asset_id = old.id
      and attachment.upload_status = 'locked'
)
begin
    select raise(abort, 'locked submission media asset is immutable');
end;

CREATE TRIGGER media_assets_review_evidence_immutable
before update on media_assets
for each row
when exists (
    select 1 from submission_review_evidence_attachments as evidence
    where evidence.asset_id = old.id
)
begin
    select raise(abort, 'reviewed submission media asset is immutable');
end;

CREATE TRIGGER problem_revisions_delete_forbidden
before delete on problem_revisions
for each row
begin
    select raise(abort, 'problem revision deletion is forbidden');
end;

CREATE TRIGGER problem_revisions_immutable_update
before update on problem_revisions
for each row
begin
    select raise(abort, 'problem revision is immutable');
end;

CREATE TRIGGER problem_revisions_match_insert
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

CREATE TRIGGER problem_synonym_members_delete_forbidden
before delete on problem_synonym_members
for each row
begin
    select raise(abort, 'synonym member deletion is forbidden');
end;

CREATE TRIGGER problem_synonym_members_identity_immutable
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

CREATE TRIGGER problem_synonym_members_removed_immutable
before update on problem_synonym_members
for each row
when old.removed_at is not null
begin
    select raise(abort, 'removed synonym member is immutable');
end;

CREATE TRIGGER problem_synonym_members_scope_insert
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

CREATE TRIGGER problems_public_id_fill_after_insert
after insert on problems
for each row
when new.public_id is null
begin
    update problems
    set public_id = 'problem-' || lower(hex(randomblob(16)))
    where id = new.id;
end;

CREATE TRIGGER problems_public_id_immutable
before update on problems
for each row
when old.public_id is not null and new.public_id is not old.public_id
begin
    select raise(abort, 'problem public identity is immutable');
end;

CREATE TRIGGER solution_reveals_delete_forbidden
before delete on solution_reveals
for each row
begin
    select raise(abort, 'solution reveal deletion is forbidden');
end;

CREATE TRIGGER solution_reveals_immutable_update
before update on solution_reveals
for each row
begin
    select raise(abort, 'solution reveal is immutable');
end;

CREATE TRIGGER solution_reveals_publication_kind_insert
before insert on solution_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    join content_problem_matches as problem_match
      on problem_match.content_revision_id = publication.revision_id
     and problem_match.problem_id = new.problem_id
     and problem_match.resolved_at is not null
     and problem_match.decision <> 'omit'
    where publication.id = new.publication_id
      and publication.kind = 'solution'
      and publication.state = 'published'
)
begin
    select raise(abort, 'solution reveal requires a published matched solution');
end;

CREATE TRIGGER submission_attachments_asset_contract_insert
before insert on submission_attachments
for each row
when not exists (
    select 1
    from media_assets as asset
    where asset.id = new.asset_id
      and asset.storage_namespace = 'submission'
      and asset.media_type = 'image/webp'
      and asset.deleted_at is null
      and asset.width between 1 and 1920
      and asset.height between 1 and 1920
)
begin
    select raise(abort, 'submission attachment requires final webp asset');
end;

CREATE TRIGGER submission_attachments_delete_guard
before delete on submission_attachments
for each row
when old.upload_status = 'locked' or exists (
    select 1
    from submission_entries as entry
    where entry.id = old.entry_id
      and entry.state = 'locked'
)
begin
    select raise(abort, 'locked submission attachment deletion is forbidden');
end;

CREATE TRIGGER submission_attachments_entry_mutable_insert
before insert on submission_attachments
for each row
when not exists (
    select 1
    from submission_entries as entry
    where entry.id = new.entry_id
      and entry.state in ('draft', 'uploading', 'submitted')
)
begin
    select raise(abort, 'submission attachment entry is not mutable');
end;

CREATE TRIGGER submission_attachments_entry_mutable_update
before update on submission_attachments
for each row
when not exists (
    select 1
    from submission_entries as entry
    where entry.id = new.entry_id
      and entry.state in ('draft', 'uploading', 'submitted')
)
begin
    select raise(abort, 'submission attachment entry is not mutable');
end;

CREATE TRIGGER submission_attachments_identity_immutable
before update on submission_attachments
for each row
when new.public_id is not old.public_id
    or new.entry_id is not old.entry_id
    or new.asset_id is not old.asset_id
    or new.client_filename is not old.client_filename
    or new.created_at is not old.created_at
begin
    select raise(abort, 'submission attachment identity is immutable');
end;

CREATE TRIGGER submission_attachments_lock_result_scope_update
before update of upload_status, locked_by_result_id on submission_attachments
for each row
when new.upload_status = 'locked' and not exists (
    select 1
    from submission_entries as entry
    join submission_threads as thread on thread.id = entry.thread_id
    join results as result on result.id = new.locked_by_result_id
    join media_assets as asset on asset.id = new.asset_id
    where entry.id = new.entry_id
      and result.student_id = thread.student_user_id
      and result.problem_id = thread.problem_id
      and result.res_type = 2
      and asset.immutable_at is not null
)
begin
    select raise(abort, 'submission attachment lock is outside review evidence');
end;

CREATE TRIGGER submission_attachments_locked_immutable
before update on submission_attachments
for each row
when old.upload_status = 'locked'
begin
    select raise(abort, 'locked submission attachment is immutable');
end;

CREATE TRIGGER submission_attachments_max_ten_insert
before insert on submission_attachments
for each row
when (
    select count(*)
    from submission_attachments as attachment
    where attachment.entry_id = new.entry_id
) >= 10
begin
    select raise(abort, 'submission entry accepts at most ten attachments');
end;

CREATE TRIGGER submission_attachments_review_evidence_delete_forbidden
before delete on submission_attachments
for each row
when exists (
    select 1 from submission_review_evidence_attachments as evidence
    where evidence.attachment_id = old.id
)
begin
    select raise(abort, 'reviewed submission attachment deletion is forbidden');
end;

CREATE TRIGGER submission_attachments_review_evidence_immutable
before update on submission_attachments
for each row
when exists (
    select 1 from submission_review_evidence_attachments as evidence
    where evidence.attachment_id = old.id
)
begin
    select raise(abort, 'reviewed submission attachment is immutable');
end;

CREATE TRIGGER submission_attachments_review_evidence_insert_forbidden
before insert on submission_attachments
for each row
when exists (
    select 1 from submission_review_evidence_entries as evidence
    where evidence.entry_id = new.entry_id
)
begin
    select raise(abort, 'reviewed submission attachment set is immutable');
end;

CREATE TRIGGER submission_attachments_state_transition_guard
before update of upload_status on submission_attachments
for each row
when new.upload_status is not old.upload_status and not (
    (old.upload_status = 'pending' and new.upload_status in ('stored', 'failed'))
    or (old.upload_status = 'failed' and new.upload_status in ('pending', 'stored'))
    or (old.upload_status = 'stored' and new.upload_status = 'locked')
)
begin
    select raise(abort, 'invalid submission attachment state transition');
end;

CREATE TRIGGER submission_attachments_submitted_nonempty_delete
before delete on submission_attachments
for each row
when exists (
    select 1
    from submission_entries as entry
    where entry.id = old.entry_id
      and entry.state = 'submitted'
      and trim(coalesce(entry.text, '')) = ''
      and (
          select count(*)
          from submission_attachments as attachment
          where attachment.entry_id = old.entry_id
      ) <= 1
)
begin
    select raise(abort, 'submitted entry must keep text or an attachment');
end;

CREATE TRIGGER submission_entries_author_scope_insert
before insert on submission_entries
for each row
when new.author_kind = 'student' and not exists (
    select 1
    from submission_threads as thread
    where thread.id = new.thread_id
      and thread.student_user_id = new.author_user_id
)
begin
    select raise(abort, 'student submission entry author is outside thread scope');
end;

CREATE TRIGGER submission_entries_author_scope_update
before update on submission_entries
for each row
when new.author_kind = 'student' and not exists (
    select 1
    from submission_threads as thread
    where thread.id = new.thread_id
      and thread.student_user_id = new.author_user_id
)
begin
    select raise(abort, 'student submission entry author is outside thread scope');
end;

CREATE TRIGGER submission_entries_delete_forbidden
before delete on submission_entries
for each row
begin
    select raise(abort, 'submission entry deletion is forbidden');
end;

CREATE TRIGGER submission_entries_identity_immutable
before update on submission_entries
for each row
when new.public_id is not old.public_id
    or new.thread_id is not old.thread_id
    or new.problem_revision_id is not old.problem_revision_id
    or new.author_kind is not old.author_kind
    or new.author_user_id is not old.author_user_id
    or new.channel is not old.channel
    or new.channel_group_key is not old.channel_group_key
    or new.entry_kind is not old.entry_kind
    or new.client_created_at is not old.client_created_at
    or new.server_received_at is not old.server_received_at
    or new.idempotency_key is not old.idempotency_key
    or new.legacy_discussion_id is not old.legacy_discussion_id
begin
    select raise(abort, 'submission entry identity is immutable');
end;

CREATE TRIGGER submission_entries_lock_requires_attachments_locked
before update of state on submission_entries
for each row
when new.state = 'locked' and exists (
    select 1
    from submission_attachments as attachment
    where attachment.entry_id = new.id
      and attachment.upload_status <> 'locked'
)
begin
    select raise(abort, 'submission entry lock requires locked attachments');
end;

CREATE TRIGGER submission_entries_nonempty_insert
before insert on submission_entries
for each row
when new.state in ('submitted', 'locked')
    and coalesce(length(trim(new.text)), 0) = 0
begin
    select raise(abort, 'submitted entry requires text or stored attachment');
end;

CREATE TRIGGER submission_entries_nonempty_update
before update of state, text on submission_entries
for each row
when new.state in ('submitted', 'locked')
    and coalesce(length(trim(new.text)), 0) = 0
    and not exists (
        select 1
        from submission_attachments as attachment
        where attachment.entry_id = new.id
          and attachment.upload_status in ('stored', 'locked')
    )
begin
    select raise(abort, 'submitted entry requires text or stored attachment');
end;

CREATE TRIGGER submission_entries_problem_revision_scope_insert
before insert on submission_entries
for each row
when (
    new.author_kind = 'student'
    and new.problem_revision_id is null
) or (
    new.problem_revision_id is not null
    and not exists (
        select 1
        from submission_threads as thread
        join problem_revisions as problem_revision
          on problem_revision.id = new.problem_revision_id
         and problem_revision.problem_id = thread.problem_id
        where thread.id = new.thread_id
    )
)
begin
    select raise(abort, 'submission entry problem revision is outside thread scope');
end;

CREATE TRIGGER submission_entries_problem_revision_scope_update
before update on submission_entries
for each row
when (
    new.author_kind = 'student'
    and new.problem_revision_id is null
) or (
    new.problem_revision_id is not null
    and not exists (
        select 1
        from submission_threads as thread
        join problem_revisions as problem_revision
          on problem_revision.id = new.problem_revision_id
         and problem_revision.problem_id = thread.problem_id
        where thread.id = new.thread_id
    )
)
begin
    select raise(abort, 'submission entry problem revision is outside thread scope');
end;

CREATE TRIGGER submission_entries_review_evidence_immutable
before update on submission_entries
for each row
when exists (
    select 1 from submission_review_evidence_entries as evidence
    where evidence.entry_id = old.id
)
begin
    select raise(abort, 'reviewed submission entry is immutable');
end;

CREATE TRIGGER submission_entries_state_transition_guard
before update of state on submission_entries
for each row
when new.state is not old.state and not (
    (old.state = 'draft' and new.state in ('uploading', 'submitted', 'deleted'))
    or (old.state = 'uploading' and new.state in ('draft', 'submitted', 'deleted'))
    or (old.state = 'submitted' and new.state in ('deleted', 'locked'))
)
begin
    select raise(abort, 'invalid submission entry state transition');
end;

CREATE TRIGGER submission_entries_terminal_immutable
before update on submission_entries
for each row
when old.state in ('locked', 'deleted')
begin
    select raise(abort, 'locked or deleted submission entry is immutable');
end;

CREATE TRIGGER submission_entries_version_guard
before update on submission_entries
for each row
when new.version <> old.version + 1
begin
    select raise(abort, 'submission entry update requires next version');
end;

CREATE TRIGGER submission_entry_replacements_delete_forbidden
before delete on submission_entry_replacements
for each row
begin
    select raise(abort, 'submission replacement deletion is forbidden');
end;

CREATE TRIGGER submission_entry_replacements_immutable_update
before update on submission_entry_replacements
for each row
begin
    select raise(abort, 'submission replacement is immutable');
end;

CREATE TRIGGER submission_entry_replacements_scope_insert
before insert on submission_entry_replacements
for each row
when not exists (
    select 1
    from submission_threads as thread
    join submission_entries as replaced
      on replaced.id = new.replaced_entry_id
     and replaced.thread_id = thread.id
     and replaced.author_kind = 'student'
     and replaced.author_user_id = thread.student_user_id
     and replaced.state = 'deleted'
    join submission_entries as replacement
      on replacement.id = new.replacement_entry_id
     and replacement.thread_id = thread.id
     and replacement.author_kind = 'student'
     and replacement.author_user_id = thread.student_user_id
     and replacement.state = 'submitted'
    where thread.id = new.thread_id
      and thread.student_user_id = new.student_user_id
)
begin
    select raise(abort, 'submission replacement is outside mutable thread scope');
end;

CREATE TRIGGER submission_material_reassignment_items_delete_forbidden
before delete on submission_material_reassignment_items
for each row
begin
    select raise(abort, 'submission reassignment item deletion is forbidden');
end;

CREATE TRIGGER submission_material_reassignment_items_immutable_update
before update on submission_material_reassignment_items
for each row
begin
    select raise(abort, 'submission reassignment item is immutable');
end;

CREATE TRIGGER submission_material_reassignment_items_scope_insert
before insert on submission_material_reassignment_items
for each row
when not exists (
    select 1
    from submission_material_reassignments as reassignment
    join submission_entries as entry
      on entry.id = new.source_entry_id
     and entry.thread_id = reassignment.source_thread_id
    where reassignment.id = new.reassignment_id
      and (
          (
              new.item_kind = 'entry_text'
              and new.attachment_id is null
              and coalesce(length(trim(entry.text)), 0) > 0
          )
          or (
              new.item_kind = 'attachment'
              and exists (
                  select 1
                  from submission_attachments as attachment
                  where attachment.id = new.attachment_id
                    and attachment.entry_id = entry.id
              )
          )
      )
)
begin
    select raise(abort, 'submission reassignment item is outside source scope');
end;

CREATE TRIGGER submission_material_reassignments_delete_forbidden
before delete on submission_material_reassignments
for each row
begin
    select raise(abort, 'submission material reassignment deletion is forbidden');
end;

CREATE TRIGGER submission_material_reassignments_immutable_update
before update on submission_material_reassignments
for each row
begin
    select raise(abort, 'submission material reassignment is immutable');
end;

CREATE TRIGGER submission_review_annotations_delete_forbidden
before delete on submission_review_annotations
for each row
begin
    select raise(abort, 'completed review annotation deletion is forbidden');
end;

CREATE TRIGGER submission_review_annotations_immutable_update
before update on submission_review_annotations
for each row
begin
    select raise(abort, 'completed review annotation is immutable');
end;

CREATE TRIGGER submission_review_annotations_scope_insert
before insert on submission_review_annotations
for each row
when not exists (
    select 1
    from submission_review_evidence_attachments as evidence
    where evidence.review_id = new.review_id
      and evidence.attachment_id = new.attachment_id
)
begin
    select raise(abort, 'review annotation is outside immutable evidence');
end;

CREATE TRIGGER submission_review_events_delete_forbidden
before delete on submission_review_events
for each row
begin
    select raise(abort, 'submission review event deletion is forbidden');
end;

CREATE TRIGGER submission_review_events_immutable_update
before update on submission_review_events
for each row
begin
    select raise(abort, 'submission review event is immutable');
end;

CREATE TRIGGER submission_review_evidence_attachments_delete_forbidden
before delete on submission_review_evidence_attachments
for each row
begin
    select raise(abort, 'review evidence attachment deletion is forbidden');
end;

CREATE TRIGGER submission_review_evidence_attachments_immutable_update
before update on submission_review_evidence_attachments
for each row
begin
    select raise(abort, 'review evidence attachment is immutable');
end;

CREATE TRIGGER submission_review_evidence_attachments_scope_insert
before insert on submission_review_evidence_attachments
for each row
when not exists (
    select 1
    from submission_attachments as attachment
    where attachment.id = new.attachment_id
      and attachment.entry_id = new.entry_id
      and attachment.asset_id = new.asset_id
      and attachment.ordinal = new.ordinal
      and attachment.upload_status = 'stored'
)
begin
    select raise(abort, 'review evidence attachment is outside entry scope');
end;

CREATE TRIGGER submission_review_evidence_entries_delete_forbidden
before delete on submission_review_evidence_entries
for each row
begin
    select raise(abort, 'review evidence entry deletion is forbidden');
end;

CREATE TRIGGER submission_review_evidence_entries_immutable_update
before update on submission_review_evidence_entries
for each row
begin
    select raise(abort, 'review evidence entry is immutable');
end;

CREATE TRIGGER submission_review_evidence_entries_scope_insert
before insert on submission_review_evidence_entries
for each row
when not exists (
    select 1
    from submission_reviews as review
    join submission_threads as target_thread on target_thread.id = review.thread_id
    join submission_threads as evidence_thread
      on evidence_thread.id = new.thread_id
     and evidence_thread.student_user_id = target_thread.student_user_id
     and evidence_thread.problem_id = new.problem_id
    join submission_entries as entry
      on entry.id = new.entry_id
     and entry.thread_id = evidence_thread.id
     and entry.author_kind = 'student'
     and entry.state = 'submitted'
     and entry.version = new.entry_version
     and entry.server_received_at = new.server_received_at
    where review.id = new.review_id
)
begin
    select raise(abort, 'review evidence entry is outside student/thread scope');
end;

CREATE TRIGGER submission_review_internal_reaction_events_delete_forbidden
before delete on submission_review_internal_reaction_events
for each row
begin
    select raise(abort, 'internal review reaction event deletion is forbidden');
end;

CREATE TRIGGER submission_review_internal_reaction_events_immutable_update
before update on submission_review_internal_reaction_events
for each row
begin
    select raise(abort, 'internal review reaction event is immutable');
end;

CREATE TRIGGER submission_review_internal_reaction_events_scope_insert
before insert on submission_review_internal_reaction_events
for each row
when not exists (
    select 1
    from submission_review_internal_reactions as state
    where state.review_id = new.review_id
      and state.actor_user_id = new.actor_user_id
      and state.version = new.state_version
      and (
          (new.event_kind = 'deleted' and state.reaction_id is null)
          or (
              new.event_kind in ('selected', 'changed')
              and state.reaction_id = new.reaction_id
          )
      )
)
begin
    select raise(abort, 'internal review reaction event does not match current state');
end;

CREATE TRIGGER submission_review_internal_reactions_delete_forbidden
before delete on submission_review_internal_reactions
for each row
begin
    select raise(abort, 'internal review reaction deletion is forbidden');
end;

CREATE TRIGGER submission_review_internal_reactions_scope_insert
before insert on submission_review_internal_reactions
for each row
when not exists (
    select 1
    from submission_reviews as review
    left join reaction_enum as reaction
      on reaction.reaction_id = new.reaction_id
     and reaction.reaction_type_id = 100
    where review.id = new.review_id
      and review.reviewer_user_id = new.actor_user_id
      and (new.reaction_id is null or reaction.reaction_id is not null)
)
begin
    select raise(abort, 'internal review reaction is outside reviewer/type scope');
end;

CREATE TRIGGER submission_review_internal_reactions_update_guard
before update on submission_review_internal_reactions
for each row
when new.review_id is not old.review_id
    or new.actor_user_id is not old.actor_user_id
    or new.created_at is not old.created_at
    or new.editable_until is not old.editable_until
    or new.version <> old.version + 1
    or new.updated_at <= old.updated_at
    or new.updated_at > old.editable_until
    or (
        new.reaction_id is not null
        and not exists (
            select 1 from reaction_enum
            where reaction_id = new.reaction_id and reaction_type_id = 100
        )
    )
begin
    select raise(abort, 'invalid internal review reaction update');
end;

CREATE TRIGGER submission_review_student_reaction_events_delete_forbidden
before delete on submission_review_student_reaction_events
for each row
begin
    select raise(abort, 'student review reaction event deletion is forbidden');
end;

CREATE TRIGGER submission_review_student_reaction_events_immutable_update
before update on submission_review_student_reaction_events
for each row
begin
    select raise(abort, 'student review reaction event is immutable');
end;

CREATE TRIGGER submission_review_student_reaction_events_scope_insert
before insert on submission_review_student_reaction_events
for each row
when not exists (
    select 1
    from submission_review_student_reactions as state
    where state.review_id = new.review_id
      and state.actor_user_id = new.actor_user_id
      and state.version = new.state_version
      and (
          (new.event_kind = 'deleted' and state.reaction_id is null)
          or (
              new.event_kind in ('selected', 'changed')
              and state.reaction_id = new.reaction_id
          )
      )
)
begin
    select raise(abort, 'student review reaction event does not match current state');
end;

CREATE TRIGGER submission_review_student_reactions_delete_forbidden
before delete on submission_review_student_reactions
for each row
begin
    select raise(abort, 'student review reaction deletion is forbidden');
end;

CREATE TRIGGER submission_review_student_reactions_scope_insert
before insert on submission_review_student_reactions
for each row
when not exists (
    select 1
    from submission_reviews as review
    join submission_threads as thread on thread.id = review.thread_id
    left join reaction_enum as reaction
      on reaction.reaction_id = new.reaction_id
     and reaction.reaction_type_id = 0
    where review.id = new.review_id
      and thread.student_user_id = new.actor_user_id
      and (new.reaction_id is null or reaction.reaction_id is not null)
)
begin
    select raise(abort, 'student review reaction is outside owner/type scope');
end;

CREATE TRIGGER submission_review_student_reactions_update_guard
before update on submission_review_student_reactions
for each row
when new.review_id is not old.review_id
    or new.actor_user_id is not old.actor_user_id
    or new.created_at is not old.created_at
    or new.editable_until is not old.editable_until
    or new.version <> old.version + 1
    or new.updated_at <= old.updated_at
    or new.updated_at > old.editable_until
    or (
        new.reaction_id is not null
        and not exists (
            select 1 from reaction_enum
            where reaction_id = new.reaction_id and reaction_type_id = 0
        )
    )
begin
    select raise(abort, 'invalid student review reaction update');
end;

CREATE TRIGGER submission_reviews_delete_forbidden
before delete on submission_reviews
for each row
begin
    select raise(abort, 'completed submission review deletion is forbidden');
end;

CREATE TRIGGER submission_reviews_immutable_update
before update on submission_reviews
for each row
begin
    select raise(abort, 'completed submission review is immutable');
end;

CREATE TRIGGER submission_reviews_scope_insert
before insert on submission_reviews
for each row
when not exists (
    select 1
    from submission_threads as thread
    join submission_entries as evidence
      on evidence.id = new.evidence_through_entry_id
     and evidence.thread_id = thread.id
     and evidence.author_kind = 'student'
    join results as result
      on result.id = new.result_id
     and result.student_id = thread.student_user_id
     and result.problem_id = thread.problem_id
     and result.res_type = 2
    left join submission_entries as comment
      on comment.id = new.comment_entry_id
    where thread.id = new.thread_id
      and (
          new.comment_entry_id is null
          or (
              comment.thread_id = thread.id
              and comment.author_user_id = new.reviewer_user_id
              and comment.author_kind in ('teacher', 'admin')
              and comment.entry_kind = 'teacher_comment'
              and comment.state = 'locked'
          )
      )
)
begin
    select raise(abort, 'submission review target is outside result/evidence scope');
end;

CREATE TRIGGER submission_threads_delete_forbidden
before delete on submission_threads
for each row
begin
    select raise(abort, 'submission thread deletion is forbidden');
end;

CREATE TRIGGER submission_threads_identity_immutable
before update on submission_threads
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.condition_revision_id is not old.condition_revision_id
    or new.created_at is not old.created_at
begin
    select raise(abort, 'submission thread identity is immutable');
end;

CREATE TRIGGER submission_threads_problem_revision_scope_insert
before insert on submission_threads
for each row
when not exists (
    select 1
    from problem_revisions as problem_revision
    where problem_revision.problem_id = new.problem_id
      and problem_revision.content_revision_id = new.condition_revision_id
)
begin
    select raise(abort, 'submission thread condition revision is outside problem scope');
end;

CREATE TRIGGER submission_threads_result_kind_insert
before insert on submission_threads
for each row
when new.latest_result_id is not null and not exists (
    select 1
    from results as result
    where result.id = new.latest_result_id
      and result.student_id = new.student_user_id
      and result.problem_id = new.problem_id
      and result.res_type = 2
)
begin
    select raise(abort, 'submission thread latest result is not written evidence');
end;

CREATE TRIGGER submission_threads_result_kind_update
before update of latest_result_id on submission_threads
for each row
when new.latest_result_id is not null and not exists (
    select 1
    from results as result
    where result.id = new.latest_result_id
      and result.student_id = new.student_user_id
      and result.problem_id = new.problem_id
      and result.res_type = 2
)
begin
    select raise(abort, 'submission thread latest result is not written evidence');
end;

CREATE TRIGGER submission_threads_state_transition_guard
before update of status on submission_threads
for each row
when new.status is not old.status and not (
    (old.status = 'open' and new.status in ('awaiting_review', 'closed'))
    or (
        old.status = 'awaiting_review'
        and new.status in ('needs_work', 'accepted', 'closed')
    )
    or (
        old.status in ('needs_work', 'accepted')
        and new.status in ('awaiting_review', 'closed')
    )
)
begin
    select raise(abort, 'invalid submission thread state transition');
end;

CREATE TRIGGER submission_threads_version_guard
before update on submission_threads
for each row
when new.version <> old.version + 1
    or new.updated_at < old.updated_at
    or new.latest_entry_at < old.latest_entry_at
begin
    select raise(abort, 'submission thread update requires next version and monotonic time');
end;

CREATE TRIGGER support_entries_asset_scope_insert
before insert on support_entries
for each row
when new.asset_id is not null and not exists (
    select 1 from media_assets as asset
    where asset.id = new.asset_id
      and asset.storage_namespace = 'submission'
      and asset.deleted_at is null
)
begin
    select raise(abort, 'support entry asset is unavailable');
end;

CREATE TRIGGER support_entries_author_scope_insert
before insert on support_entries
for each row
when (
    new.author_kind = 'student'
    and not exists (
        select 1 from support_threads as thread
        where thread.id = new.thread_id
          and thread.student_user_id = new.author_user_id
    )
) or (
    new.author_kind in ('teacher', 'admin')
    and exists (
        select 1 from support_threads as thread
        where thread.id = new.thread_id
          and thread.student_user_id = new.author_user_id
    )
)
begin
    select raise(abort, 'support entry author is outside thread scope');
end;

CREATE TRIGGER support_entries_delete_forbidden
before delete on support_entries
for each row
begin
    select raise(abort, 'support entry deletion is forbidden');
end;

CREATE TRIGGER support_entries_identity_immutable
before update on support_entries
for each row
begin
    select raise(abort, 'support entry is immutable');
end;

CREATE TRIGGER support_threads_delete_forbidden
before delete on support_threads
for each row
begin
    select raise(abort, 'support thread deletion is forbidden');
end;

CREATE TRIGGER support_threads_identity_immutable
before update on support_threads
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.group_lesson_id is not old.group_lesson_id
    or new.kind is not old.kind
    or new.created_at is not old.created_at
begin
    select raise(abort, 'support thread identity is immutable');
end;

CREATE TRIGGER support_threads_problem_scope_insert
before insert on support_threads
for each row
when new.kind = 'problem_question' and not exists (
    select 1
    from problem_revisions as problem_revision
    join content_revisions as revision
      on revision.id = problem_revision.content_revision_id
    join content_sources as source on source.id = revision.source_id
    where problem_revision.problem_id = new.problem_id
      and source.group_lesson_id = new.group_lesson_id
)
begin
    select raise(abort, 'support problem is outside group lesson scope');
end;

CREATE TRIGGER support_threads_version_guard
before update on support_threads
for each row
when new.version <> old.version + 1
    or new.updated_at < old.updated_at
    or new.latest_entry_at < old.latest_entry_at
begin
    select raise(abort, 'support thread update requires next version and monotonic time');
end;

CREATE TRIGGER test_attempts_check_transition_guard
before update on test_attempts
for each row
when not (
    old.check_status = 'pending_configuration'
    and new.check_status in ('pending', 'checked', 'failed')
) and not (
    old.check_status = 'pending'
    and new.check_status in ('checked', 'failed')
)
begin
    select raise(abort, 'invalid test attempt check transition');
end;

CREATE TRIGGER test_attempts_delete_forbidden
before delete on test_attempts
for each row
begin
    select raise(abort, 'test attempt deletion is forbidden');
end;

CREATE TRIGGER test_attempts_payload_immutable
before update on test_attempts
for each row
when new.public_id is not old.public_id
    or new.student_user_id is not old.student_user_id
    or new.problem_id is not old.problem_id
    or new.problem_revision_id is not old.problem_revision_id
    or new.answer_payload_json is not old.answer_payload_json
    or new.normalized_answer_json is not old.normalized_answer_json
    or new.parse_status is not old.parse_status
    or new.counts_as_attempt is not old.counts_as_attempt
    or new.client_created_at is not old.client_created_at
    or new.server_received_at is not old.server_received_at
    or new.clock_skew_seconds is not old.clock_skew_seconds
    or new.clock_suspicious is not old.clock_suspicious
    or new.idempotency_key is not old.idempotency_key
    or new.payload_sha256 is not old.payload_sha256
    or new.created_at is not old.created_at
begin
    select raise(abort, 'test attempt payload is immutable');
end;

CREATE TRIGGER test_attempts_result_contract_insert
before insert on test_attempts
for each row
when new.result_id is not null and not exists (
    select 1
    from results as result
    where result.id = new.result_id
      and result.student_id = new.student_user_id
      and result.problem_id = new.problem_id
      and result.verdict = new.verdict
      and result.res_type = 1
      and result.answer is json_extract(new.answer_payload_json, '$.displayAnswer')
)
begin
    select raise(abort, 'test attempt result mismatch');
end;

CREATE TRIGGER test_attempts_result_contract_update
before update on test_attempts
for each row
when new.result_id is not null and not exists (
    select 1
    from results as result
    where result.id = new.result_id
      and result.student_id = new.student_user_id
      and result.problem_id = new.problem_id
      and result.verdict = new.verdict
      and result.res_type = 1
      and result.answer is json_extract(new.answer_payload_json, '$.displayAnswer')
)
begin
    select raise(abort, 'test attempt result mismatch');
end;

CREATE TRIGGER written_tasks_queue_public_id_fill_after_insert
after insert on written_tasks_queue
for each row
when new.public_id is null
begin
    update written_tasks_queue
    set public_id = 'review-queue-' || lower(hex(randomblob(16)))
    where id = new.id;
end;

CREATE TRIGGER written_tasks_queue_public_id_immutable
before update of public_id on written_tasks_queue
for each row
when old.public_id is not null and new.public_id is not old.public_id
begin
    select raise(abort, 'review queue public identity is immutable');
end;
