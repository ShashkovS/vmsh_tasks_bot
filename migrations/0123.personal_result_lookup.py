"""Avoid per-read temporary indexes; peak-read-admission-20261019.md."""

from yoyo import step

__depends__ = {"0122.ai_review_assistant"}

steps = [
    step(
        "CREATE INDEX live_mark_cells_result_idx ON live_mark_cells(result_id) "
        "WHERE result_id IS NOT NULL",
        "DROP INDEX live_mark_cells_result_idx",
    ),
]
