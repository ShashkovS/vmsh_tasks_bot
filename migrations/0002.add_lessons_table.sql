CREATE TABLE IF NOT EXISTS lessons
(
    id               INTEGER PRIMARY KEY,
    level            TEXT    NOT NULL,
    lesson           INTEGER NOT NULL,
    UNIQUE (lesson, level)
);

insert into lessons (lesson, level)
select distinct p.lesson, p.level
from problems p
where (p.lesson, p.level) not in (select l.lesson, l.level from lessons l)
;
