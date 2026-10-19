"""Migration 0113 retains terminal content and all references during rebuild.

See vmshpwa/docs/content-recovery-20261004.md (repeat upload incident).
"""

import sqlite3
from contextlib import closing

import pytest
import yoyo

from db_methods.pwa import apply_schema_migrations
from db_methods.pwa.migrations import MIGRATIONS_ROOT
from models.pwa.content import ContentKind, SourceRevisionPayload
from pwa_tests.integration.test_publication_lifecycle_migration import (
    _activated_fixture,
    _snapshot,
    content_fixture,
)


MIGRATION_ID = "0113.content_upload_compiler_generation"
MIGRATION_FILE = next(item for item in yoyo.read_migrations(str(MIGRATIONS_ROOT))
                      if item.id == MIGRATION_ID)
MIGRATION_FILE.load()
MIGRATION = vars(MIGRATION_FILE.module)


def _restore_previous(connection):
    MIGRATION["rollback"](connection)
    connection.execute("DELETE FROM _yoyo_migration WHERE migration_id=?", (MIGRATION_ID,))
    connection.commit()


@pytest.mark.parametrize("legacy_fk_defect", [False, True])
async def test_upload_generation_migration_preserves_product_rows_and_dependents(
    content_fixture, legacy_fk_defect,
):
    fixture = content_fixture
    await _activated_fixture(fixture)
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        if legacy_fk_defect:
            connection.execute("CREATE TABLE legacy_upload_probe (id INTEGER PRIMARY KEY, "
                               "parent_id INTEGER REFERENCES users(id))")
            connection.execute("INSERT INTO legacy_upload_probe VALUES (1, 999999999)")
            connection.commit()
        connection.execute("PRAGMA foreign_keys=ON")
        _restore_previous(connection)
        objects_before, rows_before = _snapshot(connection)
        foreign_keys_before = sorted(connection.execute("PRAGMA foreign_key_check").fetchall())
    assert apply_schema_migrations(fixture.database_path).is_current
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        objects_after, rows_after = _snapshot(connection)
        expected = [(kind, name, sql.replace(MIGRATION['OLD_CHECK'], MIGRATION['NEW_CHECK']))
                    if name == 'content_revisions' else (kind, name, sql)
                    for kind, name, sql in objects_before]
        assert objects_after == expected
        assert rows_after == rows_before
        assert sorted(connection.execute("PRAGMA foreign_key_check").fetchall()) == foreign_keys_before
        assert connection.execute("PRAGMA integrity_check").fetchall() == [('ok',)]


async def test_upload_generation_rebuild_failure_is_atomic(content_fixture):
    fixture = content_fixture
    await _activated_fixture(fixture)
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        _restore_previous(connection)
        before = _snapshot(connection)

        def authorizer(action, _arg1, _arg2, _database, _trigger):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_ALTER_TABLE else sqlite3.SQLITE_OK

        connection.set_authorizer(authorizer)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                MIGRATION["apply"](connection)
        finally:
            connection.set_authorizer(None)
        assert not connection.in_transaction
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert _snapshot(connection) == before


async def test_compiler_generation_history_blocks_destructive_rollback(content_fixture):
    fixture = content_fixture
    lesson, _second, activated = await _activated_fixture(fixture)
    original = await fixture.repository.get_revision(f'cr-{activated.revision_id}')
    payload = SourceRevisionPayload.from_bytes(
        original.latex_text.encode('utf-8'), encoding='utf-8',
        provenance={'logicalFilename': 'migration-first.tex'},
    )
    upgraded = await fixture.repository.resolve_source_and_append_revision(
        source_public_id='unused-source', revision_public_id='migration-new-generation',
        group_lesson_id=lesson.id, kind=ContentKind.CONDITION,
        logical_filename='migration-first.tex', payload=payload,
        actor_user_id=fixture.actor_user_id, parser_version='fixture-parser-v2',
    )
    assert upgraded.revision.source_sha256 == original.source_sha256
    assert await fixture.repository.get_revision(original.public_id) == original
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        before = _snapshot(connection)
        with pytest.raises(RuntimeError, match='Retain migration 0113'):
            MIGRATION['rollback'](connection)
        assert _snapshot(connection) == before
        # Same compiler generation still has a durable SQL uniqueness guard.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE content_revisions SET parser_version=? WHERE id=?",
                (original.parser_version, upgraded.revision.id),
            )
