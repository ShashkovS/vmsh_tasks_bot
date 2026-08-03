"""Up/down/up proof for per-course runtime settings storage."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0077.pwa_course_runtime_settings"


def _has_table(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' "
            "AND name = 'course_runtime_settings'"
        ).fetchone()
        is not None
    )


def test_course_runtime_settings_migration_up_down_up(tmp_path) -> None:
    database_path = tmp_path / "course-runtime-settings.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0076.pwa_account_provisioning_batches"
    }

    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert not _has_table(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert _has_table(connection)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert not _has_table(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert _has_table(connection)
