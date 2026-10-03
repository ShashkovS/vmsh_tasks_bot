-- depends: 0109.pwa_fresh_problem_sets
-- vmshpwa/docs/written-result-precedence.md: one current teacher result per
-- logical problem; retain manual pointers so written corrections are reversible.

CREATE INDEX results_written_current_idx
ON results(student_id, problem_id, id) WHERE res_type=2;

-- Legacy synonym lists are canonical sorted ID sets (DB_PROBLEM.update_synonyms).
-- Confirmed modern membership takes precedence; never merge courses or lessons.
CREATE VIEW result_problem_groups AS
SELECT p.id AS problem_id,
       CASE
         WHEN sg.id IS NOT NULL THEN 'synonym:' || sg.id
         WHEN trim(p.synonyms) <> '' THEN
           'legacy:' || coalesce(cast(g.course_id AS text), 'unassigned')
           || ':' || p.lesson || ':' || p.synonyms
         ELSE 'problem:' || p.id
       END AS logical_key
FROM problems p
LEFT JOIN groups g ON g.group_id=p.group_id
LEFT JOIN problem_synonym_members sm
  ON sm.problem_id=p.id AND sm.removed_at IS NULL
LEFT JOIN problem_synonym_groups sg
  ON sg.id=sm.synonym_group_id AND sg.status='active';

CREATE VIEW teacher_result_choices AS
WITH candidates AS (
  SELECT r.student_id, pg.logical_key, max(r.id) AS written_result_id,
         NULL AS manual_result_id
  FROM results r JOIN result_problem_groups pg ON pg.problem_id=r.problem_id
  WHERE r.res_type=2
  GROUP BY r.student_id, pg.logical_key
  UNION ALL
  SELECT c.student_id, pg.logical_key, NULL, max(c.result_id)
  FROM live_mark_cells c
  JOIN result_problem_groups pg ON pg.problem_id=c.problem_id
  JOIN results r ON r.id=c.result_id AND r.res_type IN (3,4)
  GROUP BY c.student_id, pg.logical_key
), latest AS (
  SELECT student_id, logical_key, max(written_result_id) AS written_result_id,
         max(manual_result_id) AS manual_result_id
  FROM candidates GROUP BY student_id, logical_key
)
SELECT latest.*,
       CASE
         WHEN manual_result_id IS NULL THEN written_result_id
         WHEN written_result_id IS NULL THEN manual_result_id
         WHEN manual_result_id > written_result_id OR mv.val > wv.val
           THEN manual_result_id
         ELSE written_result_id
       END AS result_id
FROM latest
LEFT JOIN results w ON w.id=written_result_id
LEFT JOIN verdicts wv ON wv.id=w.verdict
LEFT JOIN results m ON m.id=manual_result_id
LEFT JOIN verdicts mv ON mv.id=m.verdict;

DROP VIEW effective_results;
CREATE VIEW effective_results AS
WITH choices AS MATERIALIZED (SELECT * FROM teacher_result_choices)
SELECT r.* FROM choices JOIN results r ON r.id=choices.result_id
UNION ALL
SELECT r.* FROM results r
LEFT JOIN result_problem_groups pg ON pg.problem_id=r.problem_id
LEFT JOIN choices ON choices.student_id=r.student_id
                 AND choices.logical_key=pg.logical_key
LEFT JOIN live_mark_cells c ON c.student_id=r.student_id AND c.problem_id=r.problem_id
WHERE (coalesce(r.res_type,0) NOT IN (2,3,4) OR choices.result_id IS NULL)
  AND choices.manual_result_id IS NULL
  AND ((c.result_id IS NOT NULL AND r.id=c.result_id)
    OR (c.result_id IS NULL AND NOT EXISTS (
      SELECT 1 FROM live_mark_results lm WHERE lm.result_id=r.id)))
  AND (r.res_type<>1 OR NOT EXISTS (
      SELECT 1 FROM test_attempt_result_events e WHERE e.result_id=r.id)
    OR EXISTS (SELECT 1 FROM test_attempts a WHERE a.result_id=r.id));

-- All adapters advance the same conflict tokens, including synonym cells.
-- Automatic-test acceptance keeps exactly the precedence rule of migration 0091.
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
      WHEN new.res_type=1 AND new.id>coalesce(live_mark_cells.result_id,0)
       AND EXISTS(SELECT 1 FROM verdicts WHERE id=new.verdict AND val>=0.8)
        THEN NULL
      ELSE live_mark_cells.result_id
    END;
  INSERT INTO live_mark_cells(student_id,problem_id,version)
  SELECT new.student_id, peer.problem_id, 1
  FROM result_problem_groups source JOIN result_problem_groups peer
    ON peer.logical_key=source.logical_key
  WHERE source.problem_id=new.problem_id AND peer.problem_id<>new.problem_id
  ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1;
END;

CREATE TRIGGER live_results_update AFTER UPDATE OF verdict, teacher_id ON results
WHEN EXISTS(SELECT 1 FROM problems WHERE id=new.problem_id)
 AND EXISTS(SELECT 1 FROM users WHERE id=new.student_id) BEGIN
  INSERT INTO live_mark_cells(student_id,problem_id,version)
  VALUES(new.student_id,new.problem_id,1)
  ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1,
    result_id=CASE
      WHEN new.res_type=1 AND new.id>coalesce(live_mark_cells.result_id,0)
       AND EXISTS(SELECT 1 FROM verdicts WHERE id=new.verdict AND val>=0.8)
        THEN NULL
      ELSE live_mark_cells.result_id
    END;
  INSERT INTO live_mark_cells(student_id,problem_id,version)
  SELECT new.student_id, peer.problem_id, 1
  FROM result_problem_groups source JOIN result_problem_groups peer
    ON peer.logical_key=source.logical_key
  WHERE source.problem_id=new.problem_id AND peer.problem_id<>new.problem_id
  ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1;
END;

CREATE TRIGGER live_results_delete AFTER DELETE ON results BEGIN
  UPDATE live_mark_cells SET version=version+1
  WHERE student_id=old.student_id AND problem_id IN (
    SELECT peer.problem_id
    FROM result_problem_groups source JOIN result_problem_groups peer
      ON peer.logical_key=source.logical_key
    WHERE source.problem_id=old.problem_id
  );
END;

-- Historical statuses repair by projection, not by rewriting the ledger or
-- unpinning the manual result. Invalidate pre-migration cell/undo versions.
INSERT INTO live_mark_cells(student_id,problem_id,version)
SELECT choices.student_id, peer.problem_id, 1
FROM teacher_result_choices choices
JOIN result_problem_groups peer ON peer.logical_key=choices.logical_key
WHERE choices.written_result_id IS NOT NULL
ON CONFLICT(student_id,problem_id) DO UPDATE SET version=version+1;
