-- Once used, removing the display mapping would corrupt historical labels.
CREATE TABLE fresh_sets_rollback_guard (n INTEGER CHECK (n = 0));
INSERT INTO fresh_sets_rollback_guard SELECT count(*) FROM content_problem_slots;
DROP TABLE fresh_sets_rollback_guard;
DROP VIEW active_problems;
DROP VIEW problem_catalog;
DROP TABLE content_problem_slots;
