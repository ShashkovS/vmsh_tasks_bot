-- depends: 0091.pwa_test_result_live_mark_precedence
-- Durable manual a53 operations; vmshpwa/docs/lesson-statistics.md.
CREATE TABLE statistics_recalculations (
    operation_id text PRIMARY KEY,
    course_id integer NOT NULL REFERENCES courses(id),
    actor_user_id integer REFERENCES users(id) ON DELETE SET NULL,
    idempotency_key text NOT NULL,
    state text NOT NULL CHECK(state IN ('running','completed','failed')),
    started_at text NOT NULL,
    completed_at text,
    run_public_id text,
    error_code text,
    UNIQUE(actor_user_id, idempotency_key),
    CHECK ((state='running' AND completed_at IS NULL) OR
           (state IN ('completed','failed') AND completed_at IS NOT NULL))
);
CREATE INDEX statistics_recalculations_course ON statistics_recalculations(course_id, started_at DESC);
