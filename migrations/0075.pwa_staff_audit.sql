-- depends: 0074.pwa_problem_import_receipts

-- Phase 10 keeps one compact, searchable index of administrative writes.
-- Domain-specific immutable histories remain authoritative for full provenance.
create table audit_events
(
    id               integer primary key,
    public_id        text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    actor_user_id    integer references users (id),
    actor_account_id integer references auth_accounts (id),
    audience         text    not null
        check (audience in ('student', 'family', 'staff', 'system')),
    action           text    not null check (length(trim(action)) between 1 and 128),
    object_type      text    not null check (length(trim(object_type)) between 1 and 64),
    object_id        text    not null check (length(trim(object_id)) between 1 and 128),
    request_id       text    not null check (length(trim(request_id)) between 1 and 128),
    before_json      text
        check (before_json is null or (
            json_valid(before_json) = 1 and json_type(before_json) = 'object'
        )),
    after_json       text
        check (after_json is null or (
            json_valid(after_json) = 1 and json_type(after_json) = 'object'
        )),
    occurred_at      text    not null,
    ip_prefix        text
);

create index audit_events_timeline_idx
    on audit_events (occurred_at desc, id desc);

create index audit_events_action_timeline_idx
    on audit_events (action, occurred_at desc, id desc);

create index audit_events_object_timeline_idx
    on audit_events (object_type, object_id, occurred_at desc, id desc);

create index audit_events_request_idx on audit_events (request_id);

create trigger audit_events_immutable_update
before update on audit_events
for each row
begin
    select raise(abort, 'audit event is immutable');
end;

create trigger audit_events_delete_forbidden
before delete on audit_events
for each row
begin
    select raise(abort, 'audit event deletion is forbidden');
end;
