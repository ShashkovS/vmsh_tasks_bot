"""Upgrade/rollback proof for account provisioning storage."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0076.pwa_account_provisioning_batches"


def _has_column(connection: sqlite3.Connection) -> bool:
    return any(
        row[1] == "provisioning_password_plaintext"
        for row in connection.execute("PRAGMA table_info(auth_accounts)")
    )


def _has_email_table(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' "
            "AND name = 'family_account_emails'"
        ).fetchone()
        is not None
    )


def test_account_batch_migration_up_down_up(tmp_path) -> None:
    database_path = tmp_path / "account-batches.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0075.pwa_staff_audit"
    }

    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert not _has_column(connection)
        assert not _has_email_table(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert _has_column(connection)
        assert _has_email_table(connection)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert not _has_column(connection)
        assert not _has_email_table(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert _has_column(connection)
        assert _has_email_table(connection)
