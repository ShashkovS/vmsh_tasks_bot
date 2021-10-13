CREATE TABLE IF NOT EXISTS user_changes_log
(
    ts          timestamp NOT NULL,
    user_id     INTEGER   not null,
    change_type text      not null,
    new_value   text      not null,
    FOREIGN KEY (user_id) REFERENCES users (id)
);


delete
from user_changes_log
where 1 = 1;

-- Подливаем исторические данные
insert into user_changes_log
with tot as (
    select '2021-08-01T00:00:00.000000' as ts, level, id as student_id
    from users
    where type = 1
    union all
    select ts, level, student_id
    from results
    union all
    select ts, p.level, student_id
    from written_tasks_discussions wd
             join problems p
                  on wd.problem_id = p.id
    where teacher_id is null
),
     next as (
         select tot.student_id, tot.ts, tot.level, lag(tot.level, 1, null) OVER win prev_level, lag(tot.student_id, 1, null) OVER win prev_student_id
         from tot
             window win as (order by student_id, ts)
     )
select ts, student_id, 'L', level
from next
where level != prev_level
   or student_id != prev_student_id
order by ts
;


insert into user_changes_log
select '2021-08-01T00:00:00.000000' as ts, id as student_id, 'O', online
from users
where type = 1
order by ts
;
