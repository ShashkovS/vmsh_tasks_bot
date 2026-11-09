"""Measured sheet lookups; docs/performance/followups-20261018.md."""

from yoyo import step

__depends__ = {"0120.scoped_read_indexes"}

steps = [
    step(
        "CREATE INDEX submission_threads_public_id_idx ON submission_threads(public_id)",
        "DROP INDEX submission_threads_public_id_idx",
    ),
    step(
        "CREATE INDEX submission_review_evidence_entries_thread_review_idx "
        "ON submission_review_evidence_entries(thread_id, review_id)",
        "DROP INDEX submission_review_evidence_entries_thread_review_idx",
    ),
]
