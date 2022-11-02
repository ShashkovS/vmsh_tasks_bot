DROP TABLE IF EXISTS zoom_conversation;
CREATE TABLE zoom_conversation (
    zoom_conversation_id INT PRIMARY KEY,
    ts                   TEXT,
    student_id           INT,
    teacher_id           INT,
    student_reaction_id  INT,
    teacher_reaction_id  INT,
    FOREIGN KEY (student_id) REFERENCES users (id)
    FOREIGN KEY (teacher_id) REFERENCES users (id)
    FOREIGN KEY (student_reaction_id) REFERENCES reaction (reaction_id)
    FOREIGN KEY (teacher_reaction_id) REFERENCES reaction (reaction_id)
);