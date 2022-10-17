CREATE TABLE student_reaction_enum (
    reaction_id INT PRIMARY KEY,
    emoji INT,  -- ord('<emoji>')
    reaction TEXT UNIQUE NOT NULL
);


INSERT INTO student_reaction_enum VALUES
    (0, 128076, 'Ок. Всё понял.'),
    (1, 128533, 'Что-то всё-равно непонятно...'),
    (2, 128587, 'Не согласен!');


CREATE TABLE student_reaction (
    problem_id INT PRIMARY KEY,
    ts TEXT,
    student_id INT,
    teacher_id INT,
    chat_id INT,
    tg_msg_id INT,
    reaction INT,
    FOREIGN KEY (reaction) REFERENCES student_reaction_enum(reaction_id)
);


CREATE VIEW student_reaction_view AS
	SELECT problem_id, ts, student_id, teacher_id, chat_id, tg_msg_id, student_reaction_enum.reaction FROM
		student_reaction JOIN student_reaction_enum
		ON (student_reaction.reaction = student_reaction_enum.reaction_id);
