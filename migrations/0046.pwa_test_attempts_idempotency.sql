-- depends: 0045.pwa_material_reveal_matches

-- Phase 4 append-only test attempts and reusable HTTP idempotency ledger.
-- Authoritative contracts:
-- vmshpwa/dev/development-plan/08-phase-4-test-submissions.md and
-- vmshpwa/dev/development-plan/02-data-model.md, section `test_attempts`.
-- Legacy Telegram continues to write `results`; the PWA repository will
-- dual-write one matching result in the same transaction.

create table idempotency_records
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

create index idempotency_records_expiry_idx
    on idempotency_records (expires_at, id)
    where expires_at is not null;

create trigger idempotency_records_account_scope_insert
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

create trigger idempotency_records_identity_immutable
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

create trigger idempotency_records_state_transition_guard
before update on idempotency_records
for each row
when not (
    old.state = 'processing'
    and new.state in ('completed', 'failed')
)
begin
    select raise(abort, 'invalid idempotency state transition');
end;

-- Composite keys let SQLite enforce that an immutable attempt references the
-- exact problem revision and, after checking, the exact legacy result owner.
create unique index problem_revisions_id_problem_uq
    on problem_revisions (id, problem_id);

create unique index results_id_student_problem_uq
    on results (id, student_id, problem_id);

create table test_attempts
(
    id                     integer primary key,
    public_id text generated always as ('ta-' || id) virtual,
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

create index test_attempts_student_problem_history_idx
    on test_attempts (student_user_id, problem_id, server_received_at desc, id desc);

create index test_attempts_student_problem_counted_idx
    on test_attempts (student_user_id, problem_id, server_received_at, id)
    where counts_as_attempt = 1;

create index test_attempts_pending_configuration_idx
    on test_attempts (problem_id, server_received_at, id)
    where check_status = 'pending_configuration';

create trigger test_attempts_payload_immutable
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

create trigger test_attempts_check_transition_guard
before update on test_attempts
for each row
when not (
    old.check_status = 'pending_configuration'
    and new.check_status in ('pending', 'checked', 'failed')
) and not (
    old.check_status = 'pending'
    and new.check_status in ('checked', 'failed')
) and not (
    old.check_status = 'checked'
    and new.check_status = 'checked'
    and new.checker_version is not old.checker_version
)
begin
    select raise(abort, 'invalid test attempt check transition');
end;

create trigger test_attempts_result_contract_insert
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

create trigger test_attempts_result_contract_update
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

create trigger test_attempts_delete_forbidden
before delete on test_attempts
for each row
begin
    select raise(abort, 'test attempt deletion is forbidden');
end;
