from __future__ import annotations

import sqlite3

import pytest

from db_methods.pwa import (
    JournalModeMismatchError,
    PwaConnectionFactory,
    SchemaMismatchError,
    apply_schema_migrations,
    inspect_migration_state,
    require_current_schema,
)


def test_schema_migrations_are_explicit_and_repeatable(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"

    with pytest.raises(SchemaMismatchError, match="explicit migration command"):
        require_current_schema(database_path)
    assert not database_path.exists()

    first = apply_schema_migrations(database_path)
    second = apply_schema_migrations(database_path)

    assert first.is_current
    assert second.is_current
    assert first.expected == second.expected
    assert inspect_migration_state(database_path).is_current
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_runtime_connect_checks_but_does_not_apply_schema(tmp_path):
    database_path = tmp_path / "stale.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE existing_marker (id INTEGER PRIMARY KEY)")

    with pytest.raises(SchemaMismatchError):
        PwaConnectionFactory(database_path)

    with sqlite3.connect(database_path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert names == {"existing_marker"}


def test_schema_check_rejects_changed_and_future_migrations(tmp_path):
    database_path = tmp_path / "future.sqlite3"
    state = apply_schema_migrations(database_path)
    changed_id = state.expected[-1][0]

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE _yoyo_migration SET migration_hash = ? WHERE migration_id = ?",
            ("changed-hash", changed_id),
        )
        connection.execute(
            "INSERT INTO _yoyo_migration "
            "(migration_hash, migration_id, applied_at_utc) VALUES (?, ?, ?)",
            ("future-hash", "9999.future", "2026-07-27T00:00:00Z"),
        )

    mismatch = inspect_migration_state(database_path)
    assert mismatch.hash_mismatches == (changed_id,)
    assert mismatch.unexpected_current_generation == ("9999.future",)
    with pytest.raises(SchemaMismatchError) as error:
        require_current_schema(database_path)
    assert f"changed={changed_id}" in str(error.value)
    assert "unexpected=9999.future" in str(error.value)


def test_pre_merged_migration_history_remains_compatible(tmp_path):
    database_path = tmp_path / "legacy-history.sqlite3"
    apply_schema_migrations(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO _yoyo_migration "
            "(migration_hash, migration_id, applied_at_utc) VALUES (?, ?, ?)",
            ("legacy-hash", "0001.initial", "2020-01-01T00:00:00Z"),
        )

    assert require_current_schema(database_path).is_current
    PwaConnectionFactory(database_path)


def test_runtime_rejects_current_schema_outside_wal_mode(tmp_path):
    database_path = tmp_path / "wrong-journal.sqlite3"
    apply_schema_migrations(database_path)
    with sqlite3.connect(database_path, autocommit=True) as connection:
        assert (
            connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0] == "delete"
        )

    with pytest.raises(JournalModeMismatchError, match="explicit migration command"):
        PwaConnectionFactory(database_path)
