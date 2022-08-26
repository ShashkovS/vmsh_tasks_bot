CREATE TABLE IF NOT EXISTS media_groups
(
    media_group_id INTEGER NOT NULL PRIMARY KEY UNIQUE,
    problem_id INTEGER NOT NULL,
    ts timestamp NOT NULL,
    FOREIGN KEY (problem_id) REFERENCES problems (id)
);
