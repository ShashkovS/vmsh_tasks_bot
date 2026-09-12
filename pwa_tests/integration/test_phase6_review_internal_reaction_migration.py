"""Exact Phase-6E internal Teacher-reaction migration lifecycle."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0054.pwa_submission_review_internal_reactions"


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


def _tables(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' "
                "AND name LIKE 'submission_review_internal_reaction%'"
            )
        }


def test_internal_reaction_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase6-review-internal-reactions.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0053.pwa_submission_review_annotations"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)
    assert _tables(database_path) == set()

    expected = {
        "submission_review_internal_reactions",
        "submission_review_internal_reaction_events",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _tables(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        state_columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(submission_review_internal_reactions)"
            )
        }
        assert state_columns == {
            "review_id",
            "actor_user_id",
            "reaction_id",
            "created_at",
            "editable_until",
            "updated_at",
            "deleted_at",
            "version",
        }
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _tables(database_path) == set()

    _apply(database_path, {MIGRATION_ID})
    assert _tables(database_path) == expected
