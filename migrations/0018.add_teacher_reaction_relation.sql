-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

DROP TABLE IF EXISTS teacher_reaction_enum;
CREATE TABLE teacher_reaction_enum
(
    reaction_id INT PRIMARY KEY,
    reaction    TEXT UNIQUE NOT NULL
);


INSERT INTO teacher_reaction_enum
VALUES (0, '🔥 Суперское решение.'),
       (1, '😕 Жуткая муть.'),
       (2, '😠 Решение, вероятно, списано.');

DROP TABLE IF EXISTS teacher_reaction;
CREATE TABLE IF NOT EXISTS teacher_reaction
(
    ts          TEXT,
    result_id   INT,
    reaction_id INT,
    FOREIGN KEY (reaction_id) REFERENCES teacher_reaction_enum (reaction_id),
    FOREIGN KEY (result_id) REFERENCES results (id)
);


CREATE VIEW IF NOT EXISTS teacher_reaction_view AS
SELECT *
FROM teacher_reaction
         JOIN teacher_reaction_enum using (reaction_id)
         JOIN results on teacher_reaction.result_id = results.id
;
