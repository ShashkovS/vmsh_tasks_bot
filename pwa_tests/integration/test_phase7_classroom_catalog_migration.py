"""Exact migration and persistence proof for the Phase-7 classroom catalog."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.classrooms import (
    ClassroomNameConflict,
    ClassroomVersionConflict,
    create_classroom,
    list_classrooms,
    rename_classroom,
    set_classroom_status,
)
from db_methods.pwa.migrations import MIGRATIONS_ROOT
from models.pwa.classrooms import prepare_classroom_name


MIGRATION_ID = "0057.pwa_classroom_catalog"


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


def _catalog_objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE name LIKE 'classroom%' AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_classroom_catalog_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase7-classrooms.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0056.pwa_support_threads"
    }
    preceding = {
        item.id
        for item in migrations.values()
        if int(item.id.partition(".")[0]) < 57
    }
    _apply(database_path, preceding)
    assert _catalog_objects(database_path) == set()

    expected = {
        "classrooms",
        "classrooms_status_name_idx",
        "classrooms_delete_forbidden",
        "classroom_events",
        "classroom_events_timeline_idx",
        "classroom_events_immutable_update",
        "classroom_events_delete_forbidden",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _catalog_objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _catalog_objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
    assert _catalog_objects(database_path) == expected


def test_catalog_create_rename_archive_restore_and_conflicts(tmp_path):
    database_path = tmp_path / "phase7-catalog-operations.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        admin_id = connection.execute(
            "INSERT INTO users (type, name, surname) VALUES (?, ?, ?)",
            (2, "Test", "Admin"),
        ).lastrowid
        name, normalized = prepare_classroom_name("  Актовый зал  ")
        created = create_classroom(
            connection,
            name=name,
            normalized_name=normalized,
            actor_user_id=admin_id,
            request_id="request-1",
            now="2026-07-29T08:00:00Z",
        )
        assert created == {
            "public_id": "room-1",
            "name": "Актовый зал",
            "status": "active",
            "created_at": "2026-07-29T08:00:00Z",
            "updated_at": "2026-07-29T08:00:00Z",
            "version": 1,
        }

        duplicate_name, duplicate_normalized = prepare_classroom_name("АКТОВЫЙ ЗАЛ")
        with pytest.raises(ClassroomNameConflict):
            create_classroom(
                connection,
                name=duplicate_name,
                normalized_name=duplicate_normalized,
                actor_user_id=admin_id,
                request_id="request-2",
                now="2026-07-29T08:01:00Z",
            )

        renamed = rename_classroom(
            connection,
            public_id="room-1",
            expected_version=1,
            name="Большой зал",
            normalized_name="большой зал",
            actor_user_id=admin_id,
            request_id="request-3",
            now="2026-07-29T08:02:00Z",
        )
        assert renamed["version"] == 2
        with pytest.raises(ClassroomVersionConflict):
            rename_classroom(
                connection,
                public_id="room-1",
                expected_version=1,
                name="Старое имя",
                normalized_name="старое имя",
                actor_user_id=admin_id,
                request_id="request-4",
                now="2026-07-29T08:03:00Z",
            )

        archived = set_classroom_status(
            connection,
            public_id="room-1",
            expected_version=2,
            status="archived",
            actor_user_id=admin_id,
            request_id="request-5",
            now="2026-07-29T08:04:00Z",
        )
        assert archived["status"] == "archived"
        assert list_classrooms(connection, status="active") == []
        assert [row["name"] for row in list_classrooms(connection, status=None)] == [
            "Большой зал"
        ]

        restored = set_classroom_status(
            connection,
            public_id="room-1",
            expected_version=3,
            status="active",
            actor_user_id=admin_id,
            request_id="request-6",
            now="2026-07-29T08:05:00Z",
        )
        assert restored["version"] == 4
        events = connection.execute(
            "SELECT action, before_name, after_name FROM classroom_events ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in events] == [
            ("created", None, "Актовый зал"),
            ("renamed", "Актовый зал", "Большой зал"),
            ("archived", "Большой зал", "Большой зал"),
            ("restored", "Большой зал", "Большой зал"),
        ]
