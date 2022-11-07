CREATE TABLE IF NOT EXISTS zoom_conversation (
    zoom_conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    student_id INT,
    teacher_id INT,
    student_reaction_id INT NULL,
    teacher_reaction_id INT NULL,
    FOREIGN KEY (student_id) REFERENCES users(id)
    FOREIGN KEY (student_reaction_id) REFERENCES reaction_enum(reaction_id)
    FOREIGN KEY (teacher_id) REFERENCES users(id)
    FOREIGN KEY (teacher_reaction_id) REFERENCES reaction_enum(reaction_id)
);

DROP VIEW IF EXISTS zoom_conversation_view;
CREATE VIEW zoom_conversation_view AS
WITH users_ AS (SELECT id, name||' '||surname||' '||middlename AS fio FROM users)
SELECT
	zoom_conversation_id,
	ts,
	users_s.fio AS student_name,
	users_t.fio AS teacher_name,
	student_reaction_enum.reaction AS student_reaction,
	teacher_reaction_enum.reaction AS teacher_reaction
FROM
	zoom_conversation
	LEFT JOIN users_ AS users_s ON (users_s.id = student_id)
    LEFT JOIN users_ AS users_t ON (users_t.id = teacher_id)
    LEFT JOIN reaction_enum AS student_reaction_enum ON (zoom_conversation.student_reaction_id = student_reaction_enum.reaction_id)
	LEFT JOIN reaction_enum AS teacher_reaction_enum ON (zoom_conversation.teacher_reaction_id = teacher_reaction_enum.reaction_id)
;


ALTER TABLE reaction ADD COLUMN zoom_conversation_id INT NULL REFERENCES zoom_conversation (zoom_conversation_id);
ALTER TABLE results ADD COLUMN zoom_conversation_id INT NULL REFERENCES zoom_conversation (zoom_conversation_id);
