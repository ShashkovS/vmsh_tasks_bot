"""Reversible queue holds for lost photographs; docs/deploy/deferred-reviews.md."""
from yoyo import step

# Independent of the production-only 0123 lookup-index migration.
__depends__ = {"0122.ai_review_assistant"}

steps = [step("""CREATE TABLE deferred_review_queue (
    queue_id INTEGER PRIMARY KEY,
    batch TEXT NOT NULL,
    student_id INTEGER NOT NULL REFERENCES users(id),
    problem_id INTEGER NOT NULL REFERENCES problems(id),
    queue_json TEXT NOT NULL CHECK(json_valid(queue_json)),
    evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)),
    reason TEXT NOT NULL,
    held_at TEXT NOT NULL,
    restored_at TEXT
)""", "DROP TABLE deferred_review_queue")]
