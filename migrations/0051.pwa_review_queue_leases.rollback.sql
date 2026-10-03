-- depends: 0050.pwa_submission_entry_replacements

drop index written_tasks_queue_claim_token_idx;
drop index written_tasks_queue_lease_expiry_idx;
drop index written_tasks_queue_problem_waiting_idx;

pragma legacy_alter_table = on;
alter table written_tasks_queue rename to written_tasks_queue_with_pwa_leases;

create table written_tasks_queue
(
    id         integer primary key unique,
    ts         timestamp not null,
    student_id integer   not null references users,
    problem_id integer   not null references problems,
    cur_status integer   not null,
    teacher_ts timestamp,
    teacher_id timestamp references users,
    unique (student_id, problem_id)
);

insert into written_tasks_queue
    (id, ts, student_id, problem_id, cur_status, teacher_ts, teacher_id)
select id, ts, student_id, problem_id, cur_status, teacher_ts, teacher_id
from written_tasks_queue_with_pwa_leases;

drop table written_tasks_queue_with_pwa_leases;

create index written_tasks_queue_by_tst
    on written_tasks_queue (ts desc);

pragma legacy_alter_table = off;
