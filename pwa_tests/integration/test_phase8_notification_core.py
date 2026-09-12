"""Phase-8 proof for the small account-scoped notification core."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from db_methods.pwa.notifications import insert_event
from models.pwa.notifications import (
    InvalidNotificationPreference,
    NotificationNotFound,
    acknowledge_event,
    read_events,
    read_preferences,
    update_preference,
)
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    NOW,
    _insert_parents,
)


MIGRATION_ID = "0063.pwa_notification_core"
ACCOUNT_PUBLIC_ID = "a-1"


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


def _notification_objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name IN ("
                "'notification_events', 'notification_events_account_unread_idx', "
                "'notification_preferences')"
            )
        }


def test_notification_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "notification-schema.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0062.pwa_classroom_delivery_retries"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})
    assert _notification_objects(database_path) == set()

    expected = {
        "notification_events",
        "notification_events_account_unread_idx",
        "notification_preferences",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _notification_objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _notification_objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
    assert _notification_objects(database_path) == expected


def _seed_account(connection: sqlite3.Connection) -> tuple[int, int]:
    _insert_parents(connection)
    account_id = connection.execute(
        "INSERT INTO auth_accounts "
        "(id, audience, username, username_normalized, "
        "username_algorithm_version, provisioning_source, credential_kind, "
        "credential_hash, linked_user_id, status, created_at, updated_at) "
        "VALUES (1, 'student', 'notification-student', 'notification-student', "
        "1, 'synthetic-test', 'telegram_token', 'hash', 1, "
        "'active', ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()["id"]
    session_id = connection.execute(
        "INSERT INTO auth_sessions "
        "(public_id, account_id, audience, refresh_secret_hash, credential_version, "
        "created_at, updated_at, last_seen_at, expires_at) VALUES "
        "('11111111111111111111111111111111', ?, 'student', ?, 1, ?, ?, ?, ?) "
        "RETURNING id",
        (account_id, "1" * 64, NOW, NOW, NOW, "2027-08-10T00:00:00Z"),
    ).fetchone()["id"]
    return int(account_id), int(session_id)


def test_preferences_use_product_defaults_and_store_one_override(tmp_path):
    database_path = tmp_path / "notification-preferences.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        account_id, _session_id = _seed_account(connection)

        defaults = read_preferences(connection, account_id)
        assert len(defaults) == 9
        assert (
            next(item for item in defaults if item["category"] == "oral_window")[
                "push_enabled"
            ]
            is False
        )
        assert (
            next(item for item in defaults if item["category"] == "review_completed")[
                "push_enabled"
            ]
            is True
        )

        stored = update_preference(
            connection,
            account_id=account_id,
            category="news",
            in_app_enabled=True,
            push_enabled=False,
            sound_enabled=False,
            quiet_starts_local="22:30",
            quiet_ends_local="08:15",
            timezone="Europe/Moscow",
            now=NOW,
        )
        assert stored == {
            "category": "news",
            "in_app_enabled": 1,
            "push_enabled": 0,
            "sound_enabled": 0,
            "quiet_starts_local": "22:30",
            "quiet_ends_local": "08:15",
            "timezone": "Europe/Moscow",
            "updated_at": NOW,
        }
        with pytest.raises(InvalidNotificationPreference, match="unknown_category"):
            update_preference(
                connection,
                account_id=account_id,
                category="marketing",
                in_app_enabled=True,
                push_enabled=True,
                sound_enabled=True,
                quiet_starts_local="21:00",
                quiet_ends_local="09:00",
                timezone="Europe/Moscow",
                now=NOW,
            )


def test_event_read_is_idempotent_and_account_scoped(tmp_path):
    database_path = tmp_path / "notification-events.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        account_id, session_id = _seed_account(connection)
        assert insert_event(
            connection,
            account_id=account_id,
            category="classroom_assignment",
            dedupe_key="classroom:one",
            route="/student/",
            payload_json=json.dumps({"classroomName": "201"}),
            occurred_at=NOW,
            deliver_after=NOW,
            created_at=NOW,
        )
        assert not insert_event(
            connection,
            account_id=account_id,
            category="classroom_assignment",
            dedupe_key="classroom:one",
            route="/student/",
            payload_json="{}",
            occurred_at=NOW,
            deliver_after=NOW,
            created_at=NOW,
        )

        items = read_events(
            connection, account_id=account_id, limit=10, unread_only=True, now=NOW
        )
        assert items[0]["payload"] == {"classroomName": "201"}
        first = acknowledge_event(
            connection,
            account_id=account_id,
            event_public_id="n-1",
            session_id=session_id,
            now="2026-10-05T12:00:03Z",
        )
        repeated = acknowledge_event(
            connection,
            account_id=account_id,
            event_public_id="n-1",
            session_id=session_id,
            now="2026-10-05T12:00:10Z",
        )
        assert first == repeated
        assert (
            read_events(
                connection,
                account_id=account_id,
                limit=10,
                unread_only=True,
                now=NOW,
            )
            == []
        )
        with pytest.raises(NotificationNotFound):
            acknowledge_event(
                connection,
                account_id=account_id + 1,
                event_public_id="n-1",
                session_id=session_id,
                now=NOW,
            )


def test_event_list_applies_in_app_preference_and_oral_default(tmp_path):
    database_path = tmp_path / "notification-visibility.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        account_id, _session_id = _seed_account(connection)
        for category in ("news", "oral_window"):
            assert insert_event(
                connection,
                account_id=account_id,
                category=category,
                dedupe_key=f"{category}:one",
                route="/student/",
                payload_json="{}",
                occurred_at=NOW,
                deliver_after=NOW,
                created_at=NOW,
            )

        # News is on and oral-window events are off by default.
        assert [
            item["category"]
            for item in read_events(
                connection,
                account_id=account_id,
                limit=10,
                unread_only=False,
                now=NOW,
            )
        ] == ["news"]

        update_preference(
            connection,
            account_id=account_id,
            category="news",
            in_app_enabled=False,
            push_enabled=True,
            sound_enabled=True,
            quiet_starts_local="21:00",
            quiet_ends_local="09:00",
            timezone="Europe/Moscow",
            now=NOW,
        )
        update_preference(
            connection,
            account_id=account_id,
            category="oral_window",
            in_app_enabled=True,
            push_enabled=False,
            sound_enabled=False,
            quiet_starts_local="21:00",
            quiet_ends_local="09:00",
            timezone="Europe/Moscow",
            now=NOW,
        )
        assert [
            item["category"]
            for item in read_events(
                connection,
                account_id=account_id,
                limit=10,
                unread_only=False,
                now=NOW,
            )
        ] == ["oral_window"]


def test_event_is_not_visible_before_deliver_after(tmp_path):
    database_path = tmp_path / "notification-schedule.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        account_id, _session_id = _seed_account(connection)
        assert insert_event(
            connection,
            account_id=account_id,
            category="news",
            dedupe_key="news:future",
            route="/student/news/future",
            payload_json="{}",
            occurred_at="2026-10-05T13:00:00Z",
            deliver_after="2026-10-05T13:00:00Z",
            created_at=NOW,
        )
        assert (
            read_events(
                connection,
                account_id=account_id,
                limit=10,
                unread_only=False,
                now=NOW,
            )
            == []
        )
        assert (
            len(
                read_events(
                    connection,
                    account_id=account_id,
                    limit=10,
                    unread_only=False,
                    now="2026-10-05T13:00:00Z",
                )
            )
            == 1
        )
