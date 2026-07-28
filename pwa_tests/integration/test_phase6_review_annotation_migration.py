"""Exact Phase-6D annotation migration lifecycle."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0053.pwa_submission_review_annotations"


def _migrations():
    return yoyo.read_migrations(str(MIGRATIONS_ROOT))


def _apply(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(selected))


def _rollback(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(selected))


def _has_table(database_path: Path) -> bool:
    with sqlite3.connect(database_path) as connection:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' "
                "AND name = 'submission_review_annotations'"
            ).fetchone()
            is not None
        )


def test_review_annotation_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase6-review-annotations.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0052.pwa_submission_reviews_evidence"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)
    assert not _has_table(database_path)

    _apply(database_path, {MIGRATION_ID})
    assert _has_table(database_path)
    with sqlite3.connect(database_path) as connection:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(submission_review_annotations)"
            )
        }
        assert columns == {
            "id",
            "public_id",
            "review_id",
            "attachment_id",
            "schema_version",
            "rotation",
            "marks_json",
            "payload_sha256",
            "created_at",
        }
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert not _has_table(database_path)

    _apply(database_path, {MIGRATION_ID})
    assert _has_table(database_path)
