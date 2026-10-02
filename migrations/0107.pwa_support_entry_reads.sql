-- depends: 0106.pwa_figure_presentation
-- vmshpwa/docs/question-attention.md: per-answer visibility, shared by devices.
create table support_entry_reads (
    entry_id integer primary key references support_entries(id),
    student_user_id integer not null references users(id),
    read_at text not null
);

create trigger support_entry_reads_owner_insert
before insert on support_entry_reads
when not exists (
    select 1 from support_entries e join support_threads t on t.id = e.thread_id
    where e.id = new.entry_id and e.author_kind in ('teacher', 'admin')
      and t.student_user_id = new.student_user_id and new.read_at >= e.server_received_at
)
begin
    select raise(abort, 'support read must belong to the reply owner');
end;

-- Existing replies form the baseline; installing this feature creates no backlog.
insert into support_entry_reads(entry_id, student_user_id, read_at)
select e.id, t.student_user_id,
       max(e.server_received_at, strftime('%Y-%m-%dT%H:%M:%f000Z', 'now'))
from support_entries e join support_threads t on t.id = e.thread_id
where e.author_kind in ('teacher', 'admin');
