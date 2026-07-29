"""Authenticated HTTP proof for admin-only PWA news visibility."""

from __future__ import annotations

import pytest

from apps import pwa_app
from db_methods.pwa.telegram_bindings import set_binding_status
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from models.pwa.news import ingest_telegram_news
from models.pwa.telegram_bindings import create_binding
from pwa_tests.integration.test_classroom_catalog_http_api import (
    _cookies,
    _headers,
)
from pwa_tests.integration.test_phase7_classroom_assignment_migration import NOW


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _seed_post(connection):
    binding = create_binding(
        connection,
        public_id="moderation-news-source",
        owner_type="course",
        owner_public_id="classroom-layout-course",
        purpose="news_source",
        chat_id=-700,
        message_thread_id=None,
        title_cached="Тестовый канал",
        actor_user_id=958_001,
        now=NOW,
    )
    set_binding_status(
        connection,
        public_id=str(binding["public_id"]),
        expected_version=1,
        status="verified",
        verified_at=NOW,
        title_cached=None,
        actor_user_id=958_001,
        now=NOW,
    )
    update = {
        "chat_id": -700,
        "message_id": 41,
        "media_group_id": None,
        "published_at": "2026-10-05T10:00:00Z",
        "edited_at": None,
        "deleted": False,
        "content": [{"type": "plain", "text": "Условия занятия"}],
        "media": [],
        "source_payload": {"message_id": 41},
    }
    result = ingest_telegram_news(connection, update=update, now=NOW)
    return result, update


@pytest.mark.asyncio
async def test_admin_hides_and_restores_news_without_changing_telegram(classroom_http):
    _, update = classroom_http.factory.run_write(_seed_post)
    teacher = await classroom_http.client.get(
        "/staff/api/v1/news",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    listed = await classroom_http.client.get(
        "/staff/api/v1/news",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert listed.status == 200, await listed.text()
    item = (await listed.json())["items"][0]
    assert item == {
        "postId": item["postId"],
        "source": "telegram",
        "channelTitle": "Тестовый канал",
        "ownerType": "course",
        "ownerId": "classroom-layout-course",
        "ownerName": "Математика",
        "publishedAt": "2026-10-05T10:00:00Z",
        "editedAt": None,
        "revision": 1,
        "textExcerpt": "Условия занятия",
        "mediaCount": 0,
        "visibility": "visible",
        "moderationReason": None,
        "visibilityUpdatedAt": NOW,
        "version": 1,
    }
    cursors_before = dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"])

    hidden = await classroom_http.client.patch(
        f"/staff/api/v1/news/{item['postId']}/visibility",
        json={"schemaVersion": 1, "state": "manual_hidden", "reason": "Дубль"},
        headers=_headers(unsafe=True, if_match=f'"{item["postId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert hidden.status == 200, await hidden.text()
    hidden_item = (await hidden.json())["item"]
    assert (hidden_item["visibility"], hidden_item["moderationReason"]) == (
        "manual_hidden",
        "Дубль",
    )
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        audience: cursor + 1 for audience, cursor in cursors_before.items()
    }

    student = await classroom_http.client.get(
        "/student/api/v1/news",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[
                AuthAudience.STUDENT
            ].access_name: classroom_http.student_cookie
        },
    )
    assert student.status == 200
    assert (await student.json())["items"] == []

    stale = await classroom_http.client.patch(
        f"/staff/api/v1/news/{item['postId']}/visibility",
        json={"schemaVersion": 1, "state": "visible", "reason": None},
        headers=_headers(unsafe=True, if_match=f'"{item["postId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    cursors_after_hide = dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"])

    restored = await classroom_http.client.patch(
        f"/staff/api/v1/news/{item['postId']}/visibility",
        json={"schemaVersion": 1, "state": "visible", "reason": None},
        headers=_headers(unsafe=True, if_match=f'"{item["postId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert restored.status == 200
    assert (await restored.json())["item"]["visibility"] == "visible"
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        audience: cursor + 1 for audience, cursor in cursors_after_hide.items()
    }

    visible = await classroom_http.client.get(
        "/student/api/v1/news",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[
                AuthAudience.STUDENT
            ].access_name: classroom_http.student_cookie
        },
    )
    assert len((await visible.json())["items"]) == 1

    deleted_update = {**update, "deleted": True}
    classroom_http.factory.run_write(
        lambda connection: ingest_telegram_news(
            connection, update=deleted_update, now="2026-10-05T12:05:00Z"
        )
    )
    source_deleted = await classroom_http.client.get(
        "/staff/api/v1/news?state=source_deleted",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    deleted_item = (await source_deleted.json())["items"][0]
    denied = await classroom_http.client.patch(
        f"/staff/api/v1/news/{item['postId']}/visibility",
        json={"schemaVersion": 1, "state": "visible", "reason": None},
        headers=_headers(
            unsafe=True,
            if_match=f'"{item["postId"]}:v{deleted_item["version"]}"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert denied.status == 409
    assert (await denied.json())["error"]["code"] == "news_visibility_not_allowed"
