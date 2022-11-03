-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

DROP TABLE IF EXISTS game_map_chests;
CREATE TABLE game_map_chests
(
    id         INTEGER PRIMARY KEY,
    ts         timestamp NOT NULL,
    student_id INTEGER NOT NULL,
    command_id INTEGER NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    bonus      INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    UNIQUE (student_id, command_id, x, y)
);
