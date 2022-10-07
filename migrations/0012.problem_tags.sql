CREATE TABLE IF NOT EXISTS problem_tags
(
    problem_id INTEGER NOT NULL PRIMARY KEY UNIQUE,
    tags TEXT NOT NULL,
    ts timestamp NOT NULL,
    teacher_id INTEGER NULL,
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);
create index IF NOT EXISTS problem_tags_by_problem_id on problem_tags
(problem_id);

CREATE TABLE IF NOT EXISTS problem_tags_logs
(
    problem_id INTEGER NOT NULL,
    tags TEXT NOT NULL,
    ts timestamp NOT NULL,
    teacher_id INTEGER NULL,
    FOREIGN KEY (problem_id) REFERENCES problems (id),
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);
