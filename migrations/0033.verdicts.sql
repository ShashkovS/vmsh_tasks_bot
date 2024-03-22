-- Вопросы
create table IF NOT EXISTS verdicts
(
    id   INTEGER primary key,
    tick TEXT not null,
    val  REAL not null
);
delete from verdicts;
insert into verdicts (id, tick, val) values
( -32768, '⬜',  0.0),
( -2    , '🟥−',  0.0),
( -1    , '🟥−',  0.0),
(  11   , '🟥−',  0.0),
(  12   , '🟥−.',  0.05),
(  13   , '🟥∓',  0.25),
(  14   , '🟧+∕2',  0.5),
(  15   , '🟨±',  0.7),
(  16   , '✅+.',  0.95),
(  17   , '✅+',  1.0),
(  18   , '✅+',  1.0)
;

update results
set verdict = 18 where verdict = 1;
