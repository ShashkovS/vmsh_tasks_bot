"""Migration lifecycle for the replaceable test-attempt evaluation projection."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0095.pwa_test_attempt_projection"
LOOKUP_MIGRATION_ID = "0096.pwa_test_attempt_result_lookup"


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


def test_current_attempt_result_lookup_is_indexed(tmp_path):
    database_path = tmp_path / "test-attempt-result-lookup.sqlite3"
    migrations = {migration.id: migration for migration in _migrations()}
    assert {item.id for item in migrations[LOOKUP_MIGRATION_ID].depends} == {
        MIGRATION_ID
    }

    preceding = {
        item.id for item in migrations.values() if item.id < LOOKUP_MIGRATION_ID
    }
    _apply(database_path, preceding)
    with sqlite3.connect(database_path) as connection:
        before_plan = [
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT count(*) FROM effective_results"
            )
        ]
        assert not any("test_attempts_result_idx" in row for row in before_plan)

    _apply(database_path, {LOOKUP_MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        after_plan = [
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT count(*) FROM effective_results"
            )
        ]
        assert any("test_attempts_result_idx" in row for row in after_plan)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    _rollback(database_path, {LOOKUP_MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type='index' "
            "AND name='test_attempts_result_idx'"
        ).fetchone() is None
