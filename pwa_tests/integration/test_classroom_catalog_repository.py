"""Current-schema persistence and domain invariants for classrooms."""

from __future__ import annotations

from pwa_tests.sqlite_template import create_test_database

import sqlite3

import pytest

from db_methods.pwa.classrooms import (
    ClassroomNameConflict,
    ClassroomVersionConflict,
    create_classroom,
    list_classrooms,
    rename_classroom,
    set_classroom_status,
)
from models.pwa.classrooms import prepare_classroom_name


def test_catalog_create_rename_archive_restore_and_conflicts(tmp_path):
    database_path = tmp_path / "phase7-catalog-operations.sqlite3"
    create_test_database(database_path)
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
