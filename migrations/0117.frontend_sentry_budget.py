"""Persist frontend admission across workers; 2026-10-11 Sentry quota decision."""

from yoyo import step

__depends__ = {"0116.notification_push_candidate_index"}

# No event payload or principal IDs: helpers/pwa/sentry_budget.py owns admission.
steps = [
    step(
        "CREATE TABLE pwa_sentry_admissions ("
        "id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, "
        "lane TEXT NOT NULL CHECK (lane IN ('query', 'error')), "
        "signature TEXT NOT NULL CHECK (length(signature) = 8 "
        "AND signature NOT GLOB '*[^0-9a-f]*'))",
        "DROP TABLE pwa_sentry_admissions",
    ),
    step(
        "CREATE INDEX pwa_sentry_admissions_budget_idx "
        "ON pwa_sentry_admissions (lane, occurred_at, signature)",
        "DROP INDEX pwa_sentry_admissions_budget_idx",
    ),
]
