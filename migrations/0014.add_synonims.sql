alter table problems
    add synonyms text default '' not null;

drop index results_by_student_solved;

create index results_by_student_solved
    on results (student_id, lesson)
    where verdict > 0;
