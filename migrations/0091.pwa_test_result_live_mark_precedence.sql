-- depends: 0090.pwa_support_photos
-- A later accepted automatic test result supersedes an older live manual mark.
-- See vmshpwa/docs/live-marking.md, "Принятый контракт".
DROP TRIGGER live_results_insert;
DROP TRIGGER live_results_update;

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

-- Repair cells pinned by the old trigger. Result ids are the immutable ledger
-- order: a later manual mark still wins and therefore is deliberately retained.
UPDATE live_mark_cells
SET result_id=NULL, version=version+1
WHERE result_id IS NOT NULL
  AND EXISTS(
      SELECT 1
      FROM results AS automatic_result
      JOIN verdicts AS automatic_verdict
        ON automatic_verdict.id=automatic_result.verdict
      WHERE automatic_result.student_id=live_mark_cells.student_id
        AND automatic_result.problem_id=live_mark_cells.problem_id
        AND automatic_result.res_type=1
        AND automatic_result.id>live_mark_cells.result_id
        AND automatic_verdict.val>=0.8
  );
