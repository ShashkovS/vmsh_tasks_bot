-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

drop table if exists student_reaction_enum;
CREATE TABLE student_reaction_enum
(
    reaction_id INT PRIMARY KEY,
    reaction    TEXT UNIQUE NOT NULL
);


INSERT INTO student_reaction_enum
VALUES (0, '👌 Ок. Всё ясно.'),
       (1, '😕 Непонятно, что не так...'),
       (2, '🙋 Не могу согласиться с проверкой!');

drop table if exists student_reaction;
CREATE TABLE if not exists student_reaction
(
    ts          TEXT,
    result_id   INT,
    reaction_id INT,
    FOREIGN KEY (reaction_id) REFERENCES student_reaction_enum (reaction_id),
    FOREIGN KEY (result_id) REFERENCES results (id)
);


CREATE VIEW if not exists student_reaction_view AS
SELECT *
FROM student_reaction
         JOIN student_reaction_enum using (reaction_id)
         JOIN results on student_reaction.result_id = results.id
;
