-- depends: 0076.pwa_account_provisioning_batches

-- V1 replaces only course-owned _BotSettings. Registration and the retired
-- game remain outside this table; save_sol_mode has no replacement because
-- PWA content and submissions are always persisted. See
-- vmshpwa/docs/google-loader-inventory-and-cutover.md.
create table course_runtime_settings
(
    course_id          integer primary key references courses (id),
    schema_version     integer not null check (schema_version = 1),
    values_json        text    not null check (length(values_json) between 2 and 4096),
    updated_by_user_id integer not null references users (id),
    updated_at         text    not null,
    version            integer not null default 1 check (version >= 1)
);
