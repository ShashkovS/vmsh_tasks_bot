"""Schema proof for durable manual classroom preferences."""

from __future__ import annotations

import sqlite3

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0097.pwa_classroom_assignment_preferences"


def _objects(database_path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE name LIKE 'classroom_assignment_preferences%'"
            )
        }


def test_classroom_assignment_preference_migration_up_down_up(tmp_path):
    database_path = tmp_path / "classroom-preferences.sqlite3"
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT))
    migration_by_id = {migration.id: migration for migration in migrations}
    migration = migration_by_id[MIGRATION_ID]
    assert {dependency.id for dependency in migration.depends} == {
        "0096.pwa_test_attempt_result_lookup"
    }

    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))

    expected = {
        "classroom_assignment_preferences",
        "classroom_assignment_preferences_room_idx",
    }
    assert _objects(database_path) == expected

    selected = migrations.filter(lambda item: item.id == MIGRATION_ID)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(selected))
    assert _objects(database_path) == set()

    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(selected))
    assert _objects(database_path) == expected
