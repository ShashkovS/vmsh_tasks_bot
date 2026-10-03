"""Phase-8 proof for course/group Telegram binding ownership."""

from __future__ import annotations

import json
import sqlite3

import pytest

from db_methods.pwa.telegram_bindings import set_binding_status
from models.pwa.telegram_bindings import create_binding, effective_bindings
from pwa_tests.integration.test_classroom_catalog_http_api import (
    _cookies,
    _headers,
)
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0066.pwa_telegram_bindings"
NOW = "2026-10-05T12:00:00.000000Z"
pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def test_telegram_binding_migration_up_down_up(tmp_path):
    database_path = tmp_path / "telegram-bindings.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0065.pwa_notification_deliveries"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name LIKE 'telegram_bindings%'"
            ).fetchone()[0]
            == 0
        )
    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name LIKE 'telegram_bindings%'"
            ).fetchone()[0]
            == 4
        )
    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name LIKE 'telegram_bindings%'"
            ).fetchone()[0]
            == 0
        )
    _apply(database_path, {MIGRATION_ID})


@pytest.mark.asyncio
async def test_admin_crud_is_strict_and_teacher_is_forbidden(classroom_http):
    teacher = await classroom_http.client.get(
        "/staff/api/v1/telegram-bindings",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    owners = await classroom_http.client.get(
        "/staff/api/v1/telegram-binding-owners",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert owners.status == 200
    assert (await owners.json())["courses"] == [
        {
            "courseId": "c-1",
            "courseName": "Математика",
            "status": "active",
            "groups": [
                {
                    "groupId": "g-5",
                    "groupName": "Начинающие",
                    "status": "active",
                }
            ],
        }
    ]

    request = {
        "schemaVersion": 1,
        "ownerType": "course",
        "ownerId": "c-1",
        "purpose": "news_source",
        "chatId": -100179000001,
        "messageThreadId": None,
        "titleCached": "Новости математики",
    }
    created = await classroom_http.client.post(
        "/staff/api/v1/telegram-bindings",
        json=request,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    item = (await created.json())["binding"]
    assert item == {
        "publicId": item["publicId"],
        "ownerType": "course",
        "ownerId": "c-1",
        "ownerName": "Математика",
        "courseId": "c-1",
        "courseName": "Математика",
        "purpose": "news_source",
        "chatId": -100179000001,
        "messageThreadId": None,
        "titleCached": "Новости математики",
        "status": "draft",
        "verifiedAt": None,
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
        "version": 1,
    }

    duplicate = await classroom_http.client.post(
        "/staff/api/v1/telegram-bindings",
        json=request,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409, await duplicate.text()
    assert (await duplicate.json())["error"]["code"] == "telegram_binding_duplicate"

    listed = await classroom_http.client.get(
        "/staff/api/v1/telegram-bindings?courseId=c-1",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert listed.status == 200
    assert [row["publicId"] for row in (await listed.json())["items"]] == [
        item["publicId"]
    ]

    stale = await classroom_http.client.put(
        f"/staff/api/v1/telegram-bindings/{item['publicId']}",
        json={**request, "titleCached": "Другое название"},
        headers=_headers(unsafe=True, if_match=f'"{item["publicId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409

    updated = await classroom_http.client.put(
        f"/staff/api/v1/telegram-bindings/{item['publicId']}",
        json={**request, "titleCached": "  Канал курса  "},
        headers=_headers(unsafe=True, if_match=f'"{item["publicId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert updated.status == 200, await updated.text()
    assert (await updated.json())["binding"]["titleCached"] == "Канал курса"

    disabled = await classroom_http.client.post(
        f"/staff/api/v1/telegram-bindings/{item['publicId']}/disable",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{item["publicId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert disabled.status == 200
    assert (await disabled.json())["binding"]["status"] == "disabled"

    restored = await classroom_http.client.post(
        f"/staff/api/v1/telegram-bindings/{item['publicId']}/restore-draft",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{item["publicId"]}:v3"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert restored.status == 200
    assert (await restored.json())["binding"]["status"] == "draft"

    verified = await classroom_http.client.post(
        f"/staff/api/v1/telegram-bindings/{item['publicId']}/verify",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{item["publicId"]}:v4"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert verified.status == 200, await verified.text()
    verified_item = (await verified.json())["binding"]
    assert (verified_item["status"], verified_item["titleCached"]) == (
        "verified",
        "Проверенный канал",
    )
    assert classroom_http.telegram_binding_checks == [
        (-100179000001, None, "news_source")
    ]

    def audit_rows(connection):
        return connection.execute(
            "SELECT event.action, event.before_json, event.after_json, "
            "account.public_id AS actor_account_id FROM audit_events AS event "
            "LEFT JOIN auth_accounts AS account ON account.id = event.actor_account_id "
            "WHERE event.object_type = 'telegram_binding' ORDER BY event.id"
        ).fetchall()

    events = classroom_http.factory.run_read(audit_rows)
    assert [event["action"] for event in events] == [
        "telegram_binding.created",
        "telegram_binding.updated",
        "telegram_binding.disabled",
        "telegram_binding.draft_restored",
        "telegram_binding.verified",
    ]
    assert all(
        event["actor_account_id"] == "a-1" for event in events
    )
    assert json.loads(events[1]["before_json"])["titleCached"] == "Новости математики"
    assert json.loads(events[1]["after_json"])["titleCached"] == "Канал курса"
    assert json.loads(events[-1]["before_json"])["status"] == "draft"
    assert json.loads(events[-1]["after_json"])["status"] == "verified"

    timeline = await classroom_http.client.get(
        "/staff/api/v1/audit?objectType=telegram_binding",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert timeline.status == 200
    timeline_items = (await timeline.json())["items"]
    assert {event["action"] for event in timeline_items} == {
        "telegram_binding.created",
        "telegram_binding.updated",
        "telegram_binding.disabled",
        "telegram_binding.draft_restored",
        "telegram_binding.verified",
    }
    assert all(event["objectType"] == "telegram_binding" for event in timeline_items)
    assert all(
        "token" not in key.casefold()
        for event in timeline_items
        for side in (event["before"], event["after"])
        for key in (side or {})
    )


@pytest.mark.asyncio
async def test_binding_write_rolls_back_when_audit_insert_fails(classroom_http):
    def install_failure(connection):
        connection.execute(
            "CREATE TRIGGER audit_telegram_binding_test_failure "
            "BEFORE INSERT ON audit_events "
            "WHEN new.object_type = 'telegram_binding' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )

    classroom_http.factory.run_write(install_failure)
    response = await classroom_http.client.post(
        "/staff/api/v1/telegram-bindings",
        json={
            "schemaVersion": 1,
            "ownerType": "course",
            "ownerId": "c-1",
            "purpose": "materials_target",
            "chatId": -100179000099,
            "messageThreadId": None,
            "titleCached": "Rollback proof",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 500

    def state(connection):
        binding_count = connection.execute(
            "SELECT count(*) AS count FROM telegram_bindings "
            "WHERE chat_id = -100179000099"
        ).fetchone()["count"]
        audit_count = connection.execute(
            "SELECT count(*) AS count FROM audit_events "
            "WHERE object_type = 'telegram_binding'"
        ).fetchone()["count"]
        return binding_count, audit_count

    assert classroom_http.factory.run_read(state) == (0, 0)


@pytest.mark.asyncio
async def test_news_adds_course_and_group_while_material_target_overrides(
    classroom_http,
):
    def seed(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'c-1'"
        ).fetchone()["id"]
        group_id = connection.execute(
            "SELECT group_id FROM groups WHERE public_id = 'g-5'"
        ).fetchone()["group_id"]
        rows = []
        for suffix, owner_type, owner_id, purpose, chat_id in (
            ("course-news", "course", "c-1", "news_source", -101),
            ("group-news", "group", "g-5", "news_source", -102),
            (
                "course-materials",
                "course",
                "c-1",
                "materials_target",
                -103,
            ),
            (
                "group-materials",
                "group",
                "g-5",
                "materials_target",
                -104,
            ),
        ):
            row = create_binding(
                connection,
                owner_type=owner_type,
                owner_public_id=owner_id,
                purpose=purpose,
                chat_id=chat_id,
                message_thread_id=None,
                title_cached=suffix,
                actor_user_id=958_001,
                now=NOW,
            )
            rows.append(row)
            set_binding_status(
                connection,
                public_id=str(row["public_id"]),
                expected_version=1,
                status="verified",
                verified_at=NOW,
                title_cached=None,
                actor_user_id=958_001,
                now=NOW,
            )
        news = effective_bindings(
            connection,
            course_id=course_id,
            group_id=group_id,
            purpose="news_source",
        )
        materials = effective_bindings(
            connection,
            course_id=course_id,
            group_id=group_id,
            purpose="materials_target",
        )
        return news, materials

    news, materials = classroom_http.factory.run_write(seed)
    assert [item["chat_id"] for item in news] == [-101, -102]
    assert [item["chat_id"] for item in materials] == [-104]
