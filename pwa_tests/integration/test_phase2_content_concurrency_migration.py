"""Exact migration rehearsal for Phase-2 concurrency hardening (0042)."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0042.pwa_content_concurrency"
FOLLOWING_MIGRATION_ID = "0043.pwa_lesson_window_audit"
EXPECTED_COLUMNS = {
    "content_revisions": {
        "compile_claim_token",
        "compile_claimed_at",
        "compile_lease_expires_at",
        "compile_attempt_count",
        "compile_completed_at",
    },
    "lesson_publications": {
        "terminal_by_user_id",
        "terminal_at",
        "provenance_kind",
    },
}
EXPECTED_OBJECTS = {
    "content_sources_one_active_material_uq",
    "content_sources_identity_archive_guard",
    "content_sources_delete_forbidden",
    "lesson_publications_terminal_insert_guard",
    "lesson_publications_terminal_audit_guard",
}


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


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _objects(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
        )
    }


def test_phase2_content_concurrency_exact_up_down_up(tmp_path):
    database_path = tmp_path / "phase2-content-concurrency.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0041.pwa_content_lessons"
    }
    pre_hardening = {
        item.id
        for item in migrations.values()
        if item.id not in {MIGRATION_ID, FOLLOWING_MIGRATION_ID}
    }
    _apply(database_path, pre_hardening)

    with sqlite3.connect(database_path) as connection:
        before_columns = {
            table: _columns(connection, table) for table in EXPECTED_COLUMNS
        }
        before_objects = _objects(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        for table, columns in EXPECTED_COLUMNS.items():
            assert columns <= _columns(connection, table)
        assert EXPECTED_OBJECTS <= _objects(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert {
            table: _columns(connection, table) for table in EXPECTED_COLUMNS
        } == before_columns
        assert _objects(connection) == before_objects
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        for table, columns in EXPECTED_COLUMNS.items():
            assert columns <= _columns(connection, table)
        assert EXPECTED_OBJECTS <= _objects(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
