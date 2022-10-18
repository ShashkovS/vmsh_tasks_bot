-- Сначала добавим столбец id — primary key
-- Это можно сделать только черед промежуточную таблицу и перенос всех данных туда
CREATE TABLE IF NOT EXISTS results_dg_tmp
(
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    level      TEXT    NOT NULL,
    lesson       INTEGER NOT NULL,
    teacher_id INTEGER   NULL,
    ts         timestamp NOT NULL,
    verdict    integer   NOT NULL,
    answer     TEXT      NULL,
    res_type   integer null,
    check_time_spent_sec int null default null,
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

insert into results_dg_tmp (student_id, problem_id, level, lesson, teacher_id, ts, verdict, answer, res_type)
select student_id, problem_id, level, lesson, teacher_id, ts, verdict, answer, res_type from results;

drop index results_by_student_solved;
drop index results_by_student_problem;
drop table results;

alter table results_dg_tmp
    rename to results;

create index if not exists results_by_student_solved on results
(student_id, level, lesson) where verdict > 0;

create index if not exists results_by_student_problem on results
(student_id, problem_id);
