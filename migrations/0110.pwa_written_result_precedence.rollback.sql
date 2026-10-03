DROP VIEW effective_results;
DROP VIEW teacher_result_choices;
DROP VIEW result_problem_groups;
DROP INDEX results_written_current_idx;
DROP TRIGGER live_results_insert;
DROP TRIGGER live_results_update;
DROP TRIGGER live_results_delete;
CREATE TRIGGER live_results_insert AFTER INSERT ON results
WHEN EXISTS(SELECT 1 FROM problems WHERE id=new.problem_id)
 AND EXISTS(SELECT 1 FROM users WHERE id=new.student_id) BEGIN
    INSERT INTO live_mark_cells(student_id,problem_id,version,result_id)
    VALUES(new.student_id,new.problem_id,1,
           CASE WHEN new.res_type IN (3,4) THEN new.id END)
    ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1,
        result_id=CASE
            WHEN new.res_type IN (3,4) THEN new.id
            WHEN new.res_type=1
             AND new.id>coalesce(live_mark_cells.result_id,0)
             AND EXISTS(
                SELECT 1 FROM verdicts WHERE id=new.verdict AND val>=0.8
            ) THEN NULL
            ELSE live_mark_cells.result_id
        END;
END;

CREATE TRIGGER live_results_update AFTER UPDATE OF verdict, teacher_id ON results
WHEN EXISTS(SELECT 1 FROM problems WHERE id=new.problem_id)
 AND EXISTS(SELECT 1 FROM users WHERE id=new.student_id) BEGIN
    INSERT INTO live_mark_cells(student_id,problem_id,version)
    VALUES(new.student_id,new.problem_id,1)
    ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1,
        result_id=CASE
            WHEN new.res_type=1
             AND new.id>coalesce(live_mark_cells.result_id,0)
             AND EXISTS(
                SELECT 1 FROM verdicts WHERE id=new.verdict AND val>=0.8
             ) THEN NULL
            ELSE live_mark_cells.result_id
        END;
END;

CREATE TRIGGER live_results_delete AFTER DELETE ON results BEGIN
    UPDATE live_mark_cells SET version=version+1
    WHERE student_id=old.student_id AND problem_id=old.problem_id;
END;

create view effective_results as
    select r.* from results r
    left join live_mark_cells c
      on c.student_id=r.student_id and c.problem_id=r.problem_id
    where ((c.result_id is not null and r.id=c.result_id)
       or (c.result_id is null and not exists (
           select 1 from live_mark_results m where m.result_id=r.id)))
      and (r.res_type<>1 or not exists (
           select 1 from test_attempt_result_events e
           where e.result_id=r.id)
       or exists (
           select 1 from test_attempts a
           where a.result_id=r.id));
