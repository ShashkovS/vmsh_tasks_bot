"""Phase-8 proof for durable Web Push delivery, quiet hours and retry."""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web

from apps import pwa_app
from db_methods.pwa import PwaConnectionFactory
from db_methods.pwa.notifications import insert_event
from helpers.pwa.push_delivery import deliver_web_push_once
from helpers.pwa.web_push import WebPushTransportError
from helpers.config import Config
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from models.pwa.push_subscriptions import register_subscription
from pwa_tests.integration.test_phase8_notification_core import (
    NOW,
    _apply,
    _migrations,
    _rollback,
    _seed_account,
)


MIGRATION_ID = "0065.pwa_notification_deliveries"
DELIVERY_TIME = datetime(2026, 10, 5, 20, 0, tzinfo=UTC)


def _key(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _prepare_database(tmp_path, *, endpoint: str = "https://push.example.test/device"):
    database_path = tmp_path / "push-delivery.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        account_id, session_id = _seed_account(connection)
        register_subscription(
            connection,
            account_id=account_id,
            session_id=session_id,
            endpoint=endpoint,
            p256dh=_key(b"\x04" + b"p" * 64),
            auth_secret=_key(b"a" * 16),
            expiration_time=None,
            user_agent="Synthetic Browser",
            now=NOW,
        )
        insert_event(
            connection,
            public_id="notification.classroom-push",
            account_id=account_id,
            category="classroom_assignment",
            dedupe_key="classroom:push",
            route="/student/",
            payload_json=json.dumps(
                {
                    "courseId": "course-assignment",
                    "courseName": "Математика",
                    "groupName": "Начинающие",
                    "classroomName": "202",
                }
            ),
            occurred_at=NOW,
            deliver_after=NOW,
            created_at=NOW,
        )
    return database_path, PwaConnectionFactory(database_path)


def test_notification_delivery_migration_up_down_up(tmp_path):
    database_path = tmp_path / "push-delivery-schema.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0064.pwa_push_subscriptions"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name LIKE 'notification_deliveries%'"
            ).fetchone()[0]
            == 0
        )

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name LIKE 'notification_deliveries%'"
            ).fetchone()[0]
            == 2
        )

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name LIKE 'notification_deliveries%'"
            ).fetchone()[0]
            == 0
        )
    _apply(database_path, {MIGRATION_ID})


def test_vapid_configuration_fails_closed_in_production():
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-production",
        pwa_instance="production",
        config_name="production",
        production_mode=True,
        pwa_vapid_public_key="public-only",
    )
    with pytest.raises(RuntimeError, match="all VAPID settings"):
        pwa_app.configure(app)

    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="e2e",
        config_name="e2e",
        pwa_vapid_public_key="public",
        pwa_vapid_private_key="private",
        pwa_vapid_subject="vmsh@179.ru",
    )
    with pytest.raises(RuntimeError, match="VAPID subject"):
        pwa_app.configure(app)


async def test_delivery_is_idempotent_and_quiet_hours_only_silence(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)
    sent: list[tuple[dict[str, object], dict[str, object]]] = []

    async def sender(subscription, payload):
        sent.append((subscription, payload))

    first = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)
    repeated = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)

    assert first == {
        "claimed": 1,
        "sent": 1,
        "retried": 0,
        "failed": 0,
        "suppressed": 0,
    }
    assert repeated["claimed"] == 0
    assert len(sent) == 1
    assert sent[0][1] == {
        "schemaVersion": 1,
        "eventId": "notification.classroom-push",
        "category": "classroom_assignment",
        "title": "Назначена аудитория",
        "body": "Математика · Начинающие · аудитория 202",
        "route": "/student/",
        "silent": True,
        "occurredAt": NOW,
    }
    row = factory.run_read(
        lambda connection: connection.execute(
            "SELECT state, attempt_count, delivered_at FROM notification_deliveries"
        ).fetchone()
    )
    assert row["state"] == "sent"
    assert row["attempt_count"] == 1
    assert row["delivered_at"] is not None


async def test_review_batch_push_uses_the_aggregated_count(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)
    factory.run_write(
        lambda connection: connection.execute(
            "UPDATE notification_events SET category = 'review_completed', "
            "route = '/student/notifications', payload_json = ?, deliver_after = ?",
            (json.dumps({"count": 3}), DELIVERY_TIME.isoformat()),
        )
    )
    sent = []

    async def sender(_subscription, payload):
        sent.append(payload)

    result = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)

    assert result["sent"] == 1
    assert sent[0]["body"] == "Проверено задач: 3. Результаты уже в кабинете."


async def test_temporary_failure_retries_without_duplicate_row(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)
    calls = 0

    async def sender(_subscription, _payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise WebPushTransportError(status_code=503)

    first = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)
    too_early = await deliver_web_push_once(
        factory, sender, now=DELIVERY_TIME + timedelta(seconds=59)
    )
    second = await deliver_web_push_once(
        factory, sender, now=DELIVERY_TIME + timedelta(seconds=61)
    )

    assert first["retried"] == 1
    assert too_early["claimed"] == 0
    assert second["sent"] == 1
    assert calls == 2
    row = factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS total, max(attempt_count) AS attempts "
            "FROM notification_deliveries"
        ).fetchone()
    )
    assert row == {"total": 1, "attempts": 2}


async def test_gone_subscription_is_removed_and_not_retried(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)

    async def sender(_subscription, _payload):
        raise WebPushTransportError(status_code=410)

    result = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)
    assert result["failed"] == 1
    assert (
        factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS total FROM push_subscriptions"
            ).fetchone()["total"]
        )
        == 0
    )
    row = factory.run_read(
        lambda connection: connection.execute(
            "SELECT state, last_error_code FROM notification_deliveries"
        ).fetchone()
    )
    assert row == {"state": "failed", "last_error_code": "subscription_gone"}


async def test_disabled_preference_creates_auditable_suppression(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)
    factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO notification_preferences "
            "(account_id, category, in_app_enabled, push_enabled, sound_enabled, "
            "quiet_starts_local, quiet_ends_local, timezone, updated_at) "
            "SELECT account_id, category, 1, 0, 1, '21:00', '09:00', "
            "'Europe/Moscow', ? FROM notification_events LIMIT 1",
            (NOW,),
        )
    )

    async def sender(_subscription, _payload):
        pytest.fail("disabled preference reached the transport")

    result = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)
    assert result["claimed"] == 0
    row = factory.run_read(
        lambda connection: connection.execute(
            "SELECT state, last_error_code FROM notification_deliveries"
        ).fetchone()
    )
    assert row == {
        "state": "suppressed",
        "last_error_code": "preference_disabled",
    }


async def test_course_override_wins_over_enabled_global_preference(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)
    factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO notification_course_preferences "
            "(account_id, course_id, category, push_enabled, updated_at) "
            "SELECT account_id, 1, category, 0, ? FROM notification_events LIMIT 1",
            (NOW,),
        )
    )

    async def sender(_subscription, _payload):
        pytest.fail("course-disabled event reached the transport")

    result = await deliver_web_push_once(factory, sender, now=DELIVERY_TIME)
    assert result["claimed"] == 0
    row = factory.run_read(
        lambda connection: connection.execute(
            "SELECT state, last_error_code FROM notification_deliveries"
        ).fetchone()
    )
    assert row == {
        "state": "suppressed",
        "last_error_code": "preference_disabled",
    }


async def test_configured_scheduler_starts_and_stops(tmp_path):
    _database_path, factory = _prepare_database(tmp_path)
    delivered = []

    async def sender(_subscription, payload):
        delivered.append(payload)

    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="push-scheduler-test",
        config_name="push_scheduler_test",
        pwa_vapid_public_key="public",
        pwa_vapid_private_key="private",
        pwa_vapid_subject="mailto:vmsh@179.ru",
    )
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    app[pwa_app.PWA_PUSH_SENDER] = sender

    await pwa_app.on_push_delivery_startup(app)
    for _ in range(50):
        if delivered:
            break
        await asyncio.sleep(0.01)
    await pwa_app.on_push_delivery_shutdown(app)

    assert len(delivered) == 1
    assert app[pwa_app.PWA_PUSH_DELIVERY_TASK].done()
