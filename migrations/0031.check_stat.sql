-- Статистика проверки письменных
create index results_teacher_id_lesson_index
    on results (teacher_id, lesson)
    where res_type = 2
;
