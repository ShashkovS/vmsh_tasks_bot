"""Scoped result/session reads; docs/performance/scoped-reads-20261013.md."""

from yoyo import step

__depends__ = {"0119.text_origin"}

steps = [
    step(
        "CREATE INDEX results_by_problem_student ON results(problem_id, student_id, id)",
        "DROP INDEX results_by_problem_student",
    ),
    step(
        "CREATE INDEX live_mark_operations_active_context ON live_mark_operations(context_id) "
        "WHERE kind='mark' AND undone_at IS NULL",
        "DROP INDEX live_mark_operations_active_context",
    ),
]
