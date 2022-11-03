-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

DROP TABLE IF EXISTS game_map_flags;
CREATE TABLE game_map_flags
(
    id         INT PRIMARY KEY,
    student_id INT NOT NULL,
    command_id INT NOT NULL,
    x          INT NOT NULL,
    y          INT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    UNIQUE (student_id, command_id)
);

