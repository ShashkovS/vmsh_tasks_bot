-- depends: 0050.pwa_submission_entry_replacements

-- Phase 6 first replaces the incorrectly typed legacy teacher_id column and
-- adds an explicit renewable lease.  Legacy Telegram reads/writes keep their
-- original columns; PWA claims use claim_token + lease_version and never infer
-- ownership from cur_status alone.  Authoritative contract:
-- vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md.
-- legacy_alter_table keeps the rebuild local to this table.  In particular it
-- does not force SQLite to reparse unrelated later-generation triggers in
-- deliberately partial migration fixtures.
pragma legacy_alter_table = on;
alter table written_tasks_queue rename to written_tasks_queue_before_pwa_leases;

create table written_tasks_queue
(
    id               integer primary key unique,
    public_id text generated always as ('wq-' || id) virtual,
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

-- Invalid historical teacher values fail this insert through the type/FK
-- constraints instead of silently becoming another user.  SQLite NUMERIC
-- affinity already stores legitimate integer IDs as integers.
insert into written_tasks_queue
(
    id, ts, student_id, problem_id, cur_status, teacher_ts,
    teacher_id, claim_token, claimed_at, lease_expires_at, lease_version,
    updated_at
)
select
    id,
    ts,
    student_id,
    problem_id,
    cur_status,
    teacher_ts,
    teacher_id,
    null,
    null,
    null,
    0,
    coalesce(teacher_ts, ts)
from written_tasks_queue_before_pwa_leases;

drop table written_tasks_queue_before_pwa_leases;

create index written_tasks_queue_by_tst
    on written_tasks_queue (ts desc);

create index written_tasks_queue_problem_waiting_idx
    on written_tasks_queue (problem_id, ts, id);

create index written_tasks_queue_lease_expiry_idx
    on written_tasks_queue (lease_expires_at, id)
    where claim_token is not null;

create index written_tasks_queue_claim_token_idx
    on written_tasks_queue (claim_token, id)
    where claim_token is not null;

pragma legacy_alter_table = off;
