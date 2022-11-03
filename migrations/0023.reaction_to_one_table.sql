-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

DROP TABLE if EXISTS reaction_enum;
CREATE TABLE reaction_enum
(
    reaction_id      INT PRIMARY KEY,
    reaction         TEXT NOT NULL,
    reaction_type_id INT
);

INSERT INTO reaction_enum
        -- реакция ученика на письменную сдачу
VALUES (0, '👌 Ок. Всё ясно.', 0),
       (1, '😕 Непонятно, что не так...', 0),
       (2, '🙋 Не могу согласиться с проверкой!', 0),

        -- реакция учителя на письменную сдачу
       (3, '🔥 Суперское решение.', 1),
       (4, '😕 Жуткая муть.', 1),
       (5, '😠 Решение, вероятно, списано.', 1),

        -- реакция ученика на устную сдачу
       (6, '👌 С zoom-приёмом всё ОК.', 2),
       (7, '📡 Связь прервалась.', 2),
       (8, '🤔 Были непонятные вопросы.', 2),
       (9, '🤮 Общаться было неприятно.', 2),

        -- реакция учителя на устную сдачу
       (10, '👍 Внятно, уверенно.', 3),
       (11, '👎 Мутно, много ошибок.', 3),
       (12, '😠 Решение, вероятно, списано.', 3);

------------------------------------------

DROP TABLE if EXISTS reaction_type_enum;
CREATE TABLE reaction_type_enum
(
    reaction_type_id INT PRIMARY KEY,
    reaction_type    TEXT UNIQUE NOT NULL
);

INSERT INTO reaction_type_enum
VALUES (0, 'Письменно, ученик'),
       (1, 'Письменно, учитель'),
       (2, 'Устно, ученик'),
       (3, 'Устно, учитель');

------------------------------------------

DROP VIEW IF EXISTS reaction_enum_view;
CREATE VIEW reaction_enum_view AS
SELECT *
FROM reaction_enum
    JOIN reaction_type_enum USING (reaction_type_id);

------------------------------------------

CREATE TABLE IF NOT EXISTS reaction
(
    ts               TEXT,
    result_id        INT,
    reaction_id      INT,
    reaction_type_id INT,
    FOREIGN KEY (reaction_id) REFERENCES reaction_enum (reaction_id),
    FOREIGN KEY (reaction_type_id) REFERENCES reaction_type_enum (reaction_type_id),
    FOREIGN KEY (result_id) REFERENCES results (id)
);

DROP VIEW IF EXISTS reaction_view;
CREATE VIEW reaction_view AS
WITH users_ AS (SELECT id, name||' '||surname||' '||middlename AS fio FROM users)
SELECT
	reaction.ts,
	reaction_type,
	problem_id,
	result_id,
	users_s.fio AS student_name,
	reaction_enum.reaction,
	users_t.fio AS teacher_name,
	level,
	lesson,
	verdict,
	check_time_spent_sec
FROM reaction
    JOIN reaction_enum USING (reaction_id)
    JOIN reaction_type_enum USING (reaction_type_id)
    JOIN results ON reaction.result_id = results.id
    LEFT JOIN users_ AS users_s ON (users_s.id = student_id)
    LEFT JOIN users_ AS users_t ON (users_t.id = teacher_id)
;

INSERT INTO reaction (ts, result_id, reaction_id, reaction_type_id)
SELECT ts, result_id, reaction_id, 0 FROM student_reaction;

INSERT INTO reaction (ts, result_id, reaction_id, reaction_type_id)
SELECT ts, result_id + 3, reaction_id + 3, 1 FROM teacher_reaction;

DROP TABLE IF EXISTS student_reaction;
DROP TABLE IF EXISTS student_reaction_enum;
DROP VIEW IF EXISTS student_reaction_view;
DROP TABLE IF EXISTS teacher_reaction;
DROP TABLE IF EXISTS teacher_reaction_enum;
DROP VIEW IF EXISTS teacher_reaction_view;
