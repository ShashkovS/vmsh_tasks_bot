-- depends: 0086.pwa_review_history
-- vmshpwa/docs/live-marking.md: reversible live operations over the existing ledger.
CREATE TABLE live_mark_sessions (
    id TEXT PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE UNIQUE INDEX live_mark_sessions_active
    ON live_mark_sessions(teacher_id, course_id) WHERE finished_at IS NULL;
CREATE TABLE live_mark_visits (
    session_id TEXT NOT NULL REFERENCES live_mark_sessions(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    group_lesson_id INTEGER NOT NULL REFERENCES group_lessons(id),
    conversation_id INTEGER NOT NULL REFERENCES zoom_conversation(id),
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    praised_at TEXT,
    PRIMARY KEY(session_id, student_id, group_lesson_id)
);
CREATE TABLE live_mark_cells (
    student_id INTEGER NOT NULL REFERENCES users(id),
    problem_id INTEGER NOT NULL REFERENCES problems(id),
    version INTEGER NOT NULL DEFAULT 0,
    result_id INTEGER REFERENCES results(id),
    change_seq INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(student_id, problem_id)
);
CREATE TABLE live_mark_clock (id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL);
INSERT INTO live_mark_clock VALUES(1,0);
CREATE TRIGGER live_cell_insert AFTER INSERT ON live_mark_cells BEGIN
    UPDATE live_mark_clock SET seq=seq+1 WHERE id=1;
    UPDATE live_mark_cells SET change_seq=(SELECT seq FROM live_mark_clock WHERE id=1)
    WHERE student_id=new.student_id AND problem_id=new.problem_id;
END;
CREATE TRIGGER live_cell_update AFTER UPDATE OF version,result_id ON live_mark_cells BEGIN
    UPDATE live_mark_clock SET seq=seq+1 WHERE id=1;
    UPDATE live_mark_cells SET change_seq=(SELECT seq FROM live_mark_clock WHERE id=1)
    WHERE student_id=new.student_id AND problem_id=new.problem_id;
END;
CREATE TABLE live_mark_results (
    result_id INTEGER PRIMARY KEY REFERENCES results(id)
);
CREATE TABLE live_attendance (
    event_id INTEGER NOT NULL REFERENCES in_person_events(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    state TEXT NOT NULL CHECK(state IN ('unmarked','present','absent')),
    version INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY(event_id, student_id)
);
CREATE TABLE live_mark_operations (
    id TEXT PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    context_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('mark','attendance','transfer','reaction','praise','undo')),
    request_json TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    undone_at TEXT,
    undoable INTEGER NOT NULL DEFAULT 1 CHECK(undoable IN (0,1))
);
CREATE INDEX live_mark_operations_history
    ON live_mark_operations(teacher_id, context_id, created_at DESC);

-- All writers, including Telegram/rechecks, advance the conflict token.
CREATE TRIGGER live_results_insert AFTER INSERT ON results
WHEN EXISTS(SELECT 1 FROM problems WHERE id=new.problem_id)
 AND EXISTS(SELECT 1 FROM users WHERE id=new.student_id) BEGIN
    INSERT INTO live_mark_cells(student_id,problem_id,version,result_id)
    VALUES(new.student_id,new.problem_id,1,
           CASE WHEN new.res_type IN (3,4) THEN new.id END)
    ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1,
        result_id=CASE WHEN new.res_type IN (3,4) THEN new.id
                       ELSE live_mark_cells.result_id END;
END;
CREATE TRIGGER live_results_update AFTER UPDATE OF verdict, teacher_id ON results
WHEN EXISTS(SELECT 1 FROM problems WHERE id=new.problem_id)
 AND EXISTS(SELECT 1 FROM users WHERE id=new.student_id) BEGIN
    INSERT INTO live_mark_cells(student_id,problem_id,version)
    VALUES(new.student_id,new.problem_id,1)
    ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1;
END;
CREATE TRIGGER live_results_delete AFTER DELETE ON results BEGIN
    UPDATE live_mark_cells SET version=version+1
    WHERE student_id=old.student_id AND problem_id=old.problem_id;
END;
CREATE VIEW effective_results AS
    SELECT r.* FROM results r
    LEFT JOIN live_mark_cells c ON c.student_id=r.student_id AND c.problem_id=r.problem_id
    WHERE (c.result_id IS NOT NULL AND r.id=c.result_id)
       OR (c.result_id IS NULL AND NOT EXISTS (
           SELECT 1 FROM live_mark_results m WHERE m.result_id=r.id));

INSERT INTO reaction_enum(reaction_id,reaction,reaction_type_id) VALUES
    (304,'🤖 Похоже на ИИ.',300), (305,'👪 Помогают родители.',300);
