from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest
import yoyo

from db_methods.pwa import (
    JournalModeMismatchError,
    PwaConnectionFactory,
    SchemaMismatchError,
    apply_schema_migrations,
    inspect_migration_state,
    require_current_schema,
)
from db_methods.pwa.migrations import BASELINE_ID, MIGRATIONS_ROOT
from pwa_tests.sqlite_template import create_test_database


def test_schema_bootstrap_is_explicit_and_repeatable(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"

    with pytest.raises(SchemaMismatchError, match="explicit migration command"):
        require_current_schema(database_path)
    assert not database_path.exists()

    first = apply_schema_migrations(database_path)
    second = apply_schema_migrations(database_path)

    assert first.is_current
    assert second.is_current
    assert first.expected == second.expected
    assert [item[0] for item in first.expected] == [
        BASELINE_ID,
        "0112.scheduled_publication_lifecycle",
        "0113.content_upload_compiler_generation",
        "0115.vmsh_public_media_domain",
