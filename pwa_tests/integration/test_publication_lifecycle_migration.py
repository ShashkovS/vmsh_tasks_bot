"""0112 preserves live content and atomically rebuilds publication constraints.

See vmshpwa/docs/content-recovery-20261004.md; 0111 is an immutable baseline.
"""

import sqlite3
from contextlib import closing

import pytest
import yoyo

from db_methods.pwa import apply_schema_migrations
from db_methods.pwa.migrations import MIGRATIONS_ROOT
from models.pwa.content import ContentKind, PublicationState
from pwa_tests.integration.test_content_repository import (
    NOW,
    _append_ready_revision,
    _create_group_lesson,
    _create_source_revision,
    content_fixture,
)


MIGRATION_ID = "0112.scheduled_publication_lifecycle"
MIGRATION_FILE = next(
    item
    for item in yoyo.read_migrations(str(MIGRATIONS_ROOT))
    if item.id == MIGRATION_ID
)
MIGRATION_FILE.load()
MIGRATION = vars(MIGRATION_FILE.module)


def _snapshot(connection):
    objects = connection.execute(
        "SELECT type, name, sql FROM sqlite_schema "
        "WHERE sql IS NOT NULL AND name NOT LIKE '_yoyo%' "
        "AND name <> 'yoyo_lock' ORDER BY type, name"
    ).fetchall()
    data = {}
    for kind, name, _sql in objects:
        if kind == "table":
            quoted = '"' + name.replace('"', '""') + '"'
            data[name] = connection.execute(f"SELECT * FROM {quoted}").fetchall()
    return objects, data


async def _activated_fixture(fixture):
    _, lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="migration-course",
        course_id=fixture.course_id,
        lesson_number=78,
        group_id="content-a",
        group_lesson_public_id="migration-group",
    )
    source, first = await _create_source_revision(
        fixture, group_lesson_id=lesson.id, suffix="migration-first"
    )
    second = await _append_ready_revision(
        fixture,
        source_id=source.id,
        suffix="migration-second",
        expected_previous_revision_number=1,
    )
    scheduled = await fixture.repository.create_publication(
        public_id="migration-scheduled",
        group_lesson_id=lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=first.id,
        state=PublicationState.SCHEDULED,
        scheduled_at=NOW,
        actor_user_id=fixture.actor_user_id,
    )
    activated = await fixture.repository.activate_scheduled_publication(
        scheduled_public_id=scheduled.public_id,
        expected_version=scheduled.version,
        published_public_id="migration-active",
        actor_user_id=fixture.actor_user_id,
    )
    return lesson, second, activated


def _restore_baseline(connection):
    MIGRATION["rollback"](connection)
    connection.execute(
        "DELETE FROM _yoyo_migration WHERE migration_id=?", (MIGRATION_ID,)
    )
    connection.commit()


@pytest.mark.parametrize("legacy_fk_defect", [False, True])
async def test_live_baseline_migration_preserves_all_rows_and_dependent_objects(
    content_fixture,
    legacy_fk_defect,
):
    fixture = content_fixture
    _lesson, _second, activated = await _activated_fixture(fixture)
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        if legacy_fk_defect:
            connection.execute(
                "CREATE TABLE legacy_fk_probe (id integer primary key, "
                "parent_id integer references users(id))"
            )
            connection.execute("INSERT INTO legacy_fk_probe VALUES (1, 999999999)")
            connection.commit()
        connection.execute("PRAGMA foreign_keys=ON")
        _restore_baseline(connection)
        objects_before, rows_before = _snapshot(connection)
        assert "condition" in rows_before["lesson_publications"][0]
        fk_errors_before = connection.execute("PRAGMA foreign_key_check").fetchall()
        assert bool(fk_errors_before) == legacy_fk_defect

    assert apply_schema_migrations(fixture.database_path).is_current
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        objects_after, rows_after = _snapshot(connection)
        expected_objects = [
            (kind, name, sql.replace(MIGRATION["OLD_CHECK"], MIGRATION["NEW_CHECK"]))
            if name == "lesson_publications"
            else (kind, name, sql)
            for kind, name, sql in objects_before
        ]
        assert objects_after == expected_objects
        assert rows_after == rows_before
        assert (
            connection.execute("PRAGMA foreign_key_check").fetchall()
            == fk_errors_before
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT state, activated_from_schedule_id FROM lesson_publications WHERE id=?",
            (activated.id,),
        ).fetchone() == ("published", activated.activated_from_schedule_id)


async def test_rebuild_failure_after_table_drop_restores_data_and_schema(
    content_fixture,
):
    fixture = content_fixture
    await _activated_fixture(fixture)
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        _restore_baseline(connection)
        before = _snapshot(connection)
        denied = []

        def authorizer(action, arg1, arg2, _database, _trigger):
            if action == sqlite3.SQLITE_ALTER_TABLE:
                denied.append((arg1, arg2))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorizer)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                MIGRATION["apply"](connection)
        finally:
            connection.set_authorizer(None)
        assert denied == [("main", "lesson_publications_0112")]
        assert not connection.in_transaction
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert _snapshot(connection) == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


async def test_terminal_schedule_history_blocks_destructive_migration_rollback(
    content_fixture,
):
    fixture = content_fixture
    lesson, second, activated = await _activated_fixture(fixture)
    await fixture.repository.replace_publication(
        public_id="migration-replacement",
        group_lesson_id=lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=second.id,
        state=PublicationState.PUBLISHED,
        expected_current_public_id=activated.public_id,
        expected_current_version=activated.version,
        actor_user_id=fixture.actor_user_id,
        cancel_scheduled=True,
    )
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        before = _snapshot(connection)
        with pytest.raises(RuntimeError, match="Retain migration 0112"):
            MIGRATION["rollback"](connection)
        assert _snapshot(connection) == before
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE lesson_publications SET published_at=NULL WHERE id=?",
                (activated.id,),
            )
