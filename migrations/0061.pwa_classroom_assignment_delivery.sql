-- depends: 0060.pwa_classroom_import_receipts

-- Phase 7D: an administrator explicitly announces one confirmed classroom plan.
-- Recipient facts are copied here so later room changes cannot rewrite history.
create table classroom_assignment_delivery_batches
(
    id                           integer primary key,
    public_id text generated always as ('cdb-' || id) virtual,
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

create index classroom_assignment_delivery_batches_plan_idx
    on classroom_assignment_delivery_batches (assignment_plan_id, id);

create table classroom_assignment_delivery_recipients
(
    batch_id                    integer not null
        references classroom_assignment_delivery_batches (id),
    student_user_id             integer not null references users (id),
    course_enrollment_id        integer not null references course_enrollments (id),
    group_lesson_id             integer not null references group_lessons (id),
    classroom_id                integer not null references classrooms (id),
    student_display_name        text    not null,
    event_name                  text    not null,
    course_name                 text    not null,
    group_name                  text    not null,
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

create index classroom_assignment_delivery_recipients_student_idx
    on classroom_assignment_delivery_recipients
       (student_user_id, course_enrollment_id, batch_id);
