"""Migration lifecycle for the replaceable test-attempt evaluation projection."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0095.pwa_test_attempt_projection"


def _attempt_columns(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(test_attempts)").fetchall()
    }


def test_test_attempt_projection_migration_roundtrip(tmp_path):
    database_path = tmp_path / "test-attempt-projection.sqlite3"
    migrations = {migration.id: migration for migration in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0094.pwa_shared_oral_windows"
    }
    preceding = {item.id for item in migrations.values() if item.id < MIGRATION_ID}
    _apply(database_path, preceding)

    with sqlite3.connect(database_path) as connection:
        before_view = connection.execute(
            "SELECT sql FROM sqlite_schema "
            "WHERE type = 'view' AND name = 'effective_results'"
        ).fetchone()[0]
        assert "evaluation_version" not in _attempt_columns(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert {
            "evaluation_version",
            "feedback",
            "checker_message",
        } <= _attempt_columns(connection)
        migrated_view = connection.execute(
            "SELECT sql FROM sqlite_schema "
            "WHERE type = 'view' AND name = 'effective_results'"
        ).fetchone()[0]
        assert "test_attempts" in migrated_view
        assert connection.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE type = 'table' AND name = 'test_attempt_result_events'"
        ).fetchone() == ("test_attempt_result_events",)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert "evaluation_version" not in _attempt_columns(connection)
        assert connection.execute(
            "SELECT 1 FROM sqlite_schema "
            "WHERE name = 'test_attempt_result_events'"
        ).fetchone() is None
        restored_view = connection.execute(
            "SELECT sql FROM sqlite_schema "
            "WHERE type = 'view' AND name = 'effective_results'"
        ).fetchone()[0]
        assert " ".join(restored_view.casefold().split()) == " ".join(
            before_view.casefold().split()
        )

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert "evaluation_version" in _attempt_columns(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
