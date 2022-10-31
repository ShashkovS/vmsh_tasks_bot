alter table game_map_opened_cells
    rename to game_map_opened_cells_tmp;
alter table game_payments
    rename to game_payments_tmp;
alter table game_students_commands
    rename to game_students_commands_tmp;
alter table game_map_flags
    rename to game_map_flags_tmp;


CREATE TABLE game_map_opened_cells
(
    id         INTEGER PRIMARY KEY,
    command_id INTEGER NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    UNIQUE (command_id, x, y)
);


CREATE TABLE game_payments
(
    id         INTEGER PRIMARY KEY,
    ts         timestamp NOT NULL,
    student_id INTEGER   NOT NULL,
    amount     INTEGER   NOT NULL,
    cell_id    INTEGER   NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (cell_id) REFERENCES game_map_opened_cells (id)
);



CREATE TABLE game_students_commands
(
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL UNIQUE,
    command_id INTEGER NOT NULL,
    level      text    not null,
    FOREIGN KEY (student_id) REFERENCES users (id)
);



CREATE TABLE game_map_flags
(
    id         INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    command_id INTEGER NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id),
    UNIQUE (student_id, command_id)
);

insert into game_map_flags
select t.rowid, student_id, command_id, x, y
from game_map_flags_tmp t;

insert into game_map_opened_cells
select t.rowid, command_id, x, y
from game_map_opened_cells_tmp t;

insert into game_payments
select t.rowid, ts, student_id, amount, cell_id
from game_payments_tmp t;

insert into game_students_commands
select t.rowid, student_id, command_id, level
from game_students_commands_tmp t;

drop table game_map_opened_cells_tmp;
drop table game_payments_tmp;
drop table game_students_commands_tmp;
drop table game_map_flags_tmp;
