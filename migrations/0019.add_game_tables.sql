-- Для корректной работы на винде требуется установить env'var
-- PYTHONUTF8=1

DROP TABLE IF EXISTS game_map_opened_cells;
CREATE TABLE game_map_opened_cells
(
    id         INT PRIMARY KEY,
    command_id INT NOT NULL,
    x          INT NOT NULL,
    y          INT NOT NULL,
    UNIQUE (command_id, x, y)
);


DROP TABLE IF EXISTS game_payments;
CREATE TABLE game_payments
(
    id         INT PRIMARY KEY,
    ts         timestamp NOT NULL,
    student_id INT       NOT NULL,
    amount     INT       NOT NULL,
    cell_id    INT       NOT NULL,
    FOREIGN KEY (student_id) REFERENCES user (id),
    FOREIGN KEY (cell_id) REFERENCES game_map_opened_cells (id)
);

DROP TABLE IF EXISTS game_student_commands;
CREATE TABLE game_students_commands
(
    id         INT PRIMARY KEY,
    student_id INT NOT NULL UNIQUE,
    command_id INT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES user (id)
);
