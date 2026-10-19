"""Remaining pasted text provenance; vmshpwa/docs/paste-evidence.md."""

from yoyo import step

__depends__ = {"0118.teacher_work"}

steps = [
    step(
        "ALTER TABLE submission_entries ADD COLUMN text_origin_json TEXT "
        "CHECK (text_origin_json IS NULL OR "
        "(length(text_origin_json) <= 17000 AND json_valid(text_origin_json)))",
        "ALTER TABLE submission_entries DROP COLUMN text_origin_json",
    )
]
