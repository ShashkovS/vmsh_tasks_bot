"""Current result projection, shared by legacy and PWA adapters.

See vmshpwa/docs/written-result-precedence.md and migration 0110. Older isolated legacy
fixtures can still use the raw ledger; migrated runtimes use the SQL view.
"""


# The same winner as the 0111 baseline views, restricted before aggregation.
# See docs/sqlite-admission-performance.md (4 Oct CPU incident) and the parity
# tests in pwa_tests/integration/test_written_result_precedence.py.
STUDENT_EFFECTIVE_RESULTS_CTES = """
student_teacher_choices AS MATERIALIZED (
    WITH candidates AS (
        SELECT r.student_id, pg.logical_key, max(r.id) AS written_result_id,
               NULL AS manual_result_id
        FROM results r
        JOIN result_problem_groups pg ON pg.problem_id = r.problem_id
        WHERE r.student_id = :student_user_id AND r.res_type = 2
        GROUP BY r.student_id, pg.logical_key
        UNION ALL
        SELECT c.student_id, pg.logical_key, NULL, max(c.result_id)
        FROM live_mark_cells c
        JOIN result_problem_groups pg ON pg.problem_id = c.problem_id
        JOIN results r ON r.id = c.result_id AND r.res_type IN (3, 4)
        WHERE c.student_id = :student_user_id
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
    LEFT JOIN results w ON w.id = written_result_id
    LEFT JOIN verdicts wv ON wv.id = w.verdict
    LEFT JOIN results m ON m.id = manual_result_id
    LEFT JOIN verdicts mv ON mv.id = m.verdict
), student_effective_results AS (
    SELECT r.* FROM student_teacher_choices choices
    JOIN results r ON r.id = choices.result_id
    UNION ALL
    SELECT r.* FROM results r
    LEFT JOIN result_problem_groups pg ON pg.problem_id = r.problem_id
    LEFT JOIN student_teacher_choices choices
        ON choices.student_id = r.student_id AND choices.logical_key = pg.logical_key
    LEFT JOIN live_mark_cells c
        ON c.student_id = r.student_id AND c.problem_id = r.problem_id
    WHERE r.student_id = :student_user_id
      AND (coalesce(r.res_type, 0) NOT IN (2, 3, 4) OR choices.result_id IS NULL)
      AND choices.manual_result_id IS NULL
      AND ((c.result_id IS NOT NULL AND r.id = c.result_id)
        OR (c.result_id IS NULL AND NOT EXISTS (
            SELECT 1 FROM live_mark_results lm WHERE lm.result_id = r.id)))
      AND (r.res_type <> 1 OR NOT EXISTS (
            SELECT 1 FROM test_attempt_result_events e WHERE e.result_id = r.id)
        OR EXISTS (SELECT 1 FROM test_attempts a WHERE a.result_id = r.id))
)
"""


def result_source(connection) -> str:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='view' AND name='effective_results'"
    ).fetchone()
    return "effective_results" if exists else "results"


def result_problem_join(connection) -> str:
    """Project the selected source result onto each confirmed problem alias."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='view' AND name='result_problem_groups'"
    ).fetchone()
    if exists:
        return """JOIN result_problem_groups source ON source.problem_id=r.problem_id
        JOIN result_problem_groups target ON target.logical_key=source.logical_key
        JOIN problems p ON p.id=target.problem_id"""
    return "JOIN problems p ON p.id=r.problem_id"
