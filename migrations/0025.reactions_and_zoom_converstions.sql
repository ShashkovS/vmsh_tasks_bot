-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

DROP TABLE if EXISTS reaction_enum;
CREATE TABLE reaction_enum
(
    reaction_id      INTEGER PRIMARY KEY,
    reaction         TEXT    NOT NULL,
    reaction_type_id INTEGER NOT NULL
);

INSERT INTO reaction_enum
    -- реакция ученика на письменную сдачу
VALUES (0, '👌 Ок. Всё ясно.', 0),
       (1, '😕 Непонятно, что не так...', 0),
       (2, '🙋 Не могу согласиться с проверкой!', 0),

       -- реакция учителя на письменную сдачу
       (100, '🔥 Суперское решение.', 100),
       (101, '😕 Жуткая муть.', 100),
       (102, '😠 Решение, вероятно, списано.', 100),

       -- реакция ученика на устную сдачу
       (200, '👌 С устным приёмом всё ОК.', 200),
       (201, '😀 Сдавать понравилось!', 200),
       (202, '📡 Связь прервалась.', 200),
       (203, '😰 Сдавать не понравилось...', 200),
       (204, '⌛ Это старые плюсики поставили...', 200),

       -- реакция учителя на устную сдачу
       (300, '👍 Внятно, уверенно.', 300),
       (301, '👎 Мутно, много ошибок.', 300),
       (302, '😠 Решение, вероятно, несамостоятельно.', 300),
       (303, '📡 Технические проблемы.', 300)
;

------------------------------------------

DROP TABLE if EXISTS reaction_type_enum;
CREATE TABLE reaction_type_enum
(
    reaction_type_id INTEGER PRIMARY KEY,
    reaction_type    TEXT UNIQUE NOT NULL
);

INSERT INTO reaction_type_enum
VALUES (0, 'Письменно, ученик'),
       (100, 'Письменно, учитель'),
       (200, 'Устно, ученик'),
       (300, 'Устно, учитель');

------------------------------------------

DROP VIEW IF EXISTS reaction_enum_view;
CREATE VIEW reaction_enum_view AS
SELECT *
FROM reaction_enum
         JOIN reaction_type_enum USING (reaction_type_id);


------------------------------------------

CREATE TABLE IF NOT EXISTS zoom_conversation
(
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    student_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    level      TEXT NOT NULL,
    lesson     INTEGER NOT NULL,
    check_time_spent_sec INTEGER NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);


ALTER TABLE results
    ADD COLUMN zoom_conversation_id INT NULL REFERENCES zoom_conversation (id);


------------------------------------------

CREATE TABLE IF NOT EXISTS reactions
(
    id                   INTEGER PRIMARY KEY,
    ts                   TEXT,
    result_id            INT NULL,
    zoom_conversation_id INT NULL,
    reaction_id          INT NOT NULL,
    reaction_type_id     INT NOT NULL,
    FOREIGN KEY (result_id) REFERENCES results (id),
    FOREIGN KEY (zoom_conversation_id) REFERENCES zoom_conversation (zoom_conversation_id),
    FOREIGN KEY (reaction_id) REFERENCES reaction_enum (reaction_id),
    FOREIGN KEY (reaction_type_id) REFERENCES reaction_type_enum (reaction_type_id)
);


------------------------------------------
-- Адаптация старых данных
------------------------------------------

INSERT INTO reactions (ts, result_id, reaction_id, reaction_type_id)
SELECT ts, result_id, reaction_id, 0
FROM student_reaction;

INSERT INTO reactions (ts, result_id, reaction_id, reaction_type_id)
SELECT ts, result_id, reaction_id + 100, 100
FROM teacher_reaction;

DROP TABLE IF EXISTS student_reaction;
DROP TABLE IF EXISTS student_reaction_enum;
DROP VIEW IF EXISTS student_reaction_view;
DROP TABLE IF EXISTS teacher_reaction;
DROP TABLE IF EXISTS teacher_reaction_enum;
DROP VIEW IF EXISTS teacher_reaction_view;



------------------------------------------
-- Вьюхи
------------------------------------------

DROP VIEW IF EXISTS reaction_view;
CREATE VIEW reaction_view AS
SELECT rct.ts,
       reaction_type,
       problem_id,
       result_id,
       stud.name || ' ' || stud.surname || ' ' || stud.middlename AS student_name,
       reaction_enum.reaction,
       teach.name || ' ' || teach.surname || ' ' || teach.middlename AS teacher_name,
       coalesce(r.lesson, zc.lesson) as lesson,
       coalesce(r.level, zc.level) as level,
       verdict,
       coalesce(r.check_time_spent_sec, zc.check_time_spent_sec) as check_time_spent_sec
FROM reactions rct
JOIN reaction_enum USING (reaction_id)
JOIN reaction_type_enum USING (reaction_type_id)
LEFT JOIN results r ON rct.result_id = r.id
LEFT JOIN zoom_conversation zc on rct.zoom_conversation_id = zc.id
LEFT JOIN users AS stud ON (stud.id = coalesce(r.student_id, zc.student_id))
LEFT JOIN users AS teach ON (teach.id = coalesce(r.teacher_id, zc.teacher_id))
;
