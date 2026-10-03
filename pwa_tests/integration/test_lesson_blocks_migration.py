"""Exact lifecycle checks for additive lesson-block persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0100.pwa_lesson_blocks"


def _migrations():
    return yoyo.read_migrations(str(MIGRATIONS_ROOT))


def _apply(path: Path, ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in ids)
    with yoyo.get_backend(f"sqlite:///{path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(selected))


def _rollback(path: Path, ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in ids)
    with yoyo.get_backend(f"sqlite:///{path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(selected))


def _dependencies(migrations: dict[str, object], migration_id: str) -> set[str]:
    output: set[str] = set()

    def visit(current: str) -> None:
        for item in migrations[current].depends:  # type: ignore[attr-defined]
            if item.id in output:
                continue
            output.add(item.id)
            visit(item.id)

    visit(migration_id)
    return output


def _objects(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name LIKE 'lesson_block%'"
            )
        }


def test_lesson_block_migration_is_additive_and_reversible(tmp_path: Path):
    path = tmp_path / "lesson-blocks.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0099.pwa_classroom_assignment_compaction"
    }

    _apply(path, _dependencies(migrations, MIGRATION_ID))
    assert _objects(path) == set()
    _apply(path, {MIGRATION_ID})
    assert _objects(path) == {
        "lesson_blocks",
        "lesson_block_revisions",
        "lesson_block_events",
        "lesson_blocks_due_idx",
        "lesson_blocks_waiting_lesson_idx",
        "lesson_block_revisions_block_idx",
        "lesson_block_events_block_idx",
        "lesson_block_revisions_immutable",
        "lesson_block_revisions_delete_forbidden",
        "lesson_blocks_revision_scope_insert",
        "lesson_blocks_revision_scope_update",
    }
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(path, {MIGRATION_ID})
    assert _objects(path) == set()
    _apply(path, {MIGRATION_ID})
    assert "lesson_blocks" in _objects(path)
