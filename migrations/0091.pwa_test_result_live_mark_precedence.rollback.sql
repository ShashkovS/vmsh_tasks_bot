DROP TRIGGER live_results_update;
DROP TRIGGER live_results_insert;

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
