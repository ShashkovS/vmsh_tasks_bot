"""Exact additive migration lifecycle for private PWA support threads."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0056.pwa_support_threads"


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


def _objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name LIKE 'support_%'"
            )
        }


def test_support_thread_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase6-support.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0055.pwa_submission_review_student_reactions"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)
    assert _objects(database_path) == set()

    expected = {
        "support_threads",
        "support_threads_problem_question_uq",
        "support_threads_general_question_uq",
        "support_threads_student_timeline_idx",
        "support_threads_staff_timeline_idx",
        "support_threads_problem_scope_insert",
        "support_threads_identity_immutable",
        "support_threads_version_guard",
        "support_threads_delete_forbidden",
        "support_entries",
        "support_entries_author_idempotency_uq",
        "support_entries_thread_timeline_idx",
        "support_entries_legacy_question_idx",
        "support_entries_author_scope_insert",
        "support_entries_asset_scope_insert",
        "support_entries_identity_immutable",
        "support_entries_delete_forbidden",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert {
            str(row[1])
            for row in connection.execute("PRAGMA table_xinfo(support_threads)")
        } == {
            "id",
            "public_id",
            "student_user_id",
            "problem_id",
            "group_lesson_id",
            "kind",
            "latest_entry_at",
            "created_at",
            "updated_at",
            "version",
        }
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _objects(database_path) == set()

    _apply(database_path, {MIGRATION_ID})
    assert _objects(database_path) == expected
