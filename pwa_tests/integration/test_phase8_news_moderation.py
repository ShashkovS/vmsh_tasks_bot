"""Authenticated HTTP proof for admin-only PWA news visibility."""

from __future__ import annotations

import json

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
        "published_at": "2026-07-05T10:00:00Z",
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
        "publishedAt": "2026-07-05T10:00:00Z",
        "editedAt": None,
        "revision": 1,
        "textExcerpt": "Условия занятия",
        "editableText": None,
        "mediaCount": 0,
        "visibility": "visible",
        "moderationReason": None,
        "visibilityUpdatedAt": NOW,
        "isScheduled": False,
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


@pytest.mark.asyncio
async def test_admin_reconciles_deleted_source_and_can_correct_the_mark(classroom_http):
    result, _ = classroom_http.factory.run_write(_seed_post)
    post_id = result["public_id"]
    admin_cookies = _cookies(classroom_http, "admin")
    unsafe_headers = _headers(unsafe=True, if_match=f'"{post_id}:v1"')

    teacher = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={
            "schemaVersion": 1,
            "sourceState": "deleted",
            "reason": "Пост отсутствует в канале",
        },
        headers=unsafe_headers,
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    deleted = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={
            "schemaVersion": 1,
            "sourceState": "deleted",
            "reason": "  Пост отсутствует в канале  ",
        },
        headers=unsafe_headers,
        cookies=admin_cookies,
    )
    assert deleted.status == 200, await deleted.text()
    deleted_item = (await deleted.json())["item"]
    assert (deleted_item["visibility"], deleted_item["version"]) == (
        "source_deleted",
        2,
    )

    student = await classroom_http.client.get(
        "/student/api/v1/news",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[
                AuthAudience.STUDENT
            ].access_name: classroom_http.student_cookie
        },
    )
    assert (await student.json())["items"] == []

    stale = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={
            "schemaVersion": 1,
            "sourceState": "present",
            "reason": "Отметка была ошибочной",
        },
        headers=unsafe_headers,
        cookies=admin_cookies,
    )
    assert stale.status == 409

    restored = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={
            "schemaVersion": 1,
            "sourceState": "present",
            "reason": "Отметка была ошибочной",
        },
        headers=_headers(unsafe=True, if_match=f'"{post_id}:v2"'),
        cookies=admin_cookies,
    )
    assert restored.status == 200, await restored.text()
    assert ((await restored.json())["item"]["visibility"]) == "visible"

    def stored_state(connection):
        post = connection.execute(
            "SELECT source_deleted_at FROM news_posts WHERE public_id = ?",
            (post_id,),
        ).fetchone()
        events = connection.execute(
            "SELECT action, before_json, after_json FROM audit_events "
            "WHERE object_type = 'news_post' ORDER BY id",
        ).fetchall()
        return post["source_deleted_at"], [dict(event) for event in events]

    source_deleted_at, events = classroom_http.factory.run_read(stored_state)
    assert source_deleted_at is None
    assert [event["action"] for event in events] == [
        "news_source.marked_deleted",
        "news_source.marked_present",
    ]
    assert json.loads(events[0]["after_json"])["reconciliationReason"] == (
        "Пост отсутствует в канале"
    )
    assert all("chat" not in (event["after_json"] or "").casefold() for event in events)

    timeline = await classroom_http.client.get(
        "/staff/api/v1/audit?objectType=news_post",
        headers=_headers(),
        cookies=admin_cookies,
    )
    assert timeline.status == 200
    assert len((await timeline.json())["items"]) == 2


@pytest.mark.asyncio
async def test_source_reconciliation_validates_transition_and_rolls_back_with_audit(
    classroom_http,
):
    result, _ = classroom_http.factory.run_write(_seed_post)
    post_id = result["public_id"]
    admin_cookies = _cookies(classroom_http, "admin")

    already_present = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={
            "schemaVersion": 1,
            "sourceState": "present",
            "reason": "Проверено",
        },
        headers=_headers(unsafe=True, if_match=f'"{post_id}:v1"'),
        cookies=admin_cookies,
    )
    assert already_present.status == 409

    missing_reason = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={"schemaVersion": 1, "sourceState": "deleted", "reason": "   "},
        headers=_headers(unsafe=True, if_match=f'"{post_id}:v1"'),
        cookies=admin_cookies,
    )
    assert missing_reason.status == 422

    def install_failure(connection):
        connection.execute(
            "CREATE TRIGGER audit_news_source_test_failure "
            "BEFORE INSERT ON audit_events "
            "WHEN new.object_type = 'news_post' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )

    classroom_http.factory.run_write(install_failure)
    failed = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/source-state",
        json={
            "schemaVersion": 1,
            "sourceState": "deleted",
            "reason": "Пост отсутствует в канале",
        },
        headers=_headers(unsafe=True, if_match=f'"{post_id}:v1"'),
        cookies=admin_cookies,
    )
    assert failed.status == 500

    def state(connection):
        row = connection.execute(
            "SELECT post.source_deleted_at, visibility.state, visibility.version "
            "FROM news_posts post JOIN news_visibility visibility "
            "ON visibility.post_id = post.id WHERE post.public_id = ?",
            (post_id,),
        ).fetchone()
        return (
            row["source_deleted_at"],
            row["state"],
            row["version"],
        )

    assert classroom_http.factory.run_read(state) == (None, "visible", 1)


@pytest.mark.asyncio
async def test_admin_schedules_local_news_without_releasing_it_early(classroom_http):
    body = {
        "schemaVersion": 1,
        "ownerType": "course",
        "ownerId": "classroom-layout-course",
        "text": "  Разбор задач состоится завтра в 17:00.  ",
        "publishedAt": "2099-08-04T13:00:00+00:00",
    }
    teacher = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json=body,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json=body,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    item = (await created.json())["item"]
    assert item == {
        **item,
        "source": "local",
        "channelTitle": None,
        "ownerType": "course",
        "ownerId": "classroom-layout-course",
        "publishedAt": "2099-08-04T13:00:00.000000Z",
        "revision": 1,
        "textExcerpt": "Разбор задач состоится завтра в 17:00.",
        "editableText": "Разбор задач состоится завтра в 17:00.",
        "mediaCount": 0,
        "visibility": "visible",
        "moderationReason": None,
        "isScheduled": True,
        "version": 1,
    }
    assert created.headers["ETag"] == f'"{item["postId"]}:v1"'

    student_cookies = {
        COOKIE_POLICY[AuthAudience.STUDENT].access_name: classroom_http.student_cookie
    }
    feed = await classroom_http.client.get(
        "/student/api/v1/news",
        headers=_headers(),
        cookies=student_cookies,
    )
    assert (await feed.json())["items"] == []
    notifications = await classroom_http.client.get(
        "/student/api/v1/notification-events",
        headers=_headers(),
        cookies=student_cookies,
    )
    assert notifications.status == 200, await notifications.text()
    assert (await notifications.json())["items"] == []

    def stored(connection):
        post = connection.execute(
            "SELECT source_type, published_at FROM news_posts WHERE public_id = ?",
            (item["postId"],),
        ).fetchone()
        revision = connection.execute(
            "SELECT text_plain, source_payload_json FROM news_revisions "
            "WHERE post_id = (SELECT id FROM news_posts WHERE public_id = ?)",
            (item["postId"],),
        ).fetchone()
        events = connection.execute(
            "SELECT account.audience, event.deliver_after "
            "FROM notification_events event "
            "JOIN auth_accounts account ON account.id = event.account_id "
            "WHERE event.dedupe_key = ? ORDER BY account.audience",
            (item["postId"],),
        ).fetchall()
        audit = connection.execute(
            "SELECT action, after_json FROM audit_events WHERE object_id = ?",
            (item["postId"],),
        ).fetchone()
        return dict(post), dict(revision), [dict(row) for row in events], dict(audit)

    post, revision, events, audit = classroom_http.factory.run_read(stored)
    assert post == {
        "source_type": "local",
        "published_at": "2099-08-04T13:00:00.000000Z",
    }
    assert revision["text_plain"] == "Разбор задач состоится завтра в 17:00."
    assert json.loads(revision["source_payload_json"])["schemaVersion"] == 1
    assert {event["audience"] for event in events} == {"student", "family"}
    assert {event["deliver_after"] for event in events} == {
        "2099-08-04T13:00:00.000000Z"
    }
    assert audit["action"] == "news_local.created"
    assert "Разбор задач" not in audit["after_json"]


@pytest.mark.asyncio
async def test_admin_edits_future_local_news_and_reschedules_notifications(
    classroom_http,
):
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "course",
            "ownerId": "classroom-layout-course",
            "text": "Первоначальный текст",
            "publishedAt": "2099-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201
    post_id = (await created.json())["item"]["postId"]

    teacher = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "Исправленный текст",
            "publishedAt": "2099-08-05T14:30:00Z",
        },
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    updated = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "  Исправленный текст  ",
            "publishedAt": "2099-08-05T14:30:00+00:00",
        },
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert updated.status == 200, await updated.text()
    item = (await updated.json())["item"]
    assert item["publishedAt"] == "2099-08-05T14:30:00.000000Z"
    assert item["revision"] == 2
    assert item["textExcerpt"] == "Исправленный текст"
    assert item["editableText"] == "Исправленный текст"
    assert item["version"] == 2
    assert updated.headers["ETag"] == f'"{post_id}:v2"'

    stale = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "Ещё одна версия",
            "publishedAt": "2099-08-06T14:30:00Z",
        },
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"

    def stored(connection):
        revisions = connection.execute(
            "SELECT revision_number, text_plain, source_payload_json "
            "FROM news_revisions WHERE post_id = "
            "(SELECT id FROM news_posts WHERE public_id = ?) "
            "ORDER BY revision_number",
            (post_id,),
        ).fetchall()
        events = connection.execute(
            "SELECT occurred_at, deliver_after FROM notification_events "
            "WHERE category = 'news' AND dedupe_key = ?",
            (post_id,),
        ).fetchall()
        audit = connection.execute(
            "SELECT before_json, after_json FROM audit_events "
            "WHERE object_id = ? AND action = 'news_local.updated'",
            (post_id,),
        ).fetchone()
        return (
            [dict(row) for row in revisions],
            [dict(row) for row in events],
            dict(audit),
        )

    revisions, events, audit = classroom_http.factory.run_read(stored)
    assert [revision["text_plain"] for revision in revisions] == [
        "Первоначальный текст",
        "Исправленный текст",
    ]
    assert json.loads(revisions[1]["source_payload_json"])["publishedAt"] == (
        "2099-08-05T14:30:00.000000Z"
    )
    assert {event["occurred_at"] for event in events} == {"2099-08-05T14:30:00.000000Z"}
    assert {event["deliver_after"] for event in events} == {
        "2099-08-05T14:30:00.000000Z"
    }
    assert "Исправленный текст" not in audit["before_json"]
    assert "Исправленный текст" not in audit["after_json"]


@pytest.mark.asyncio
async def test_admin_corrects_published_local_news_without_repeat_notification(
    classroom_http,
):
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "group",
            "ownerId": "classroom-layout-group",
            "text": "Уже в ленте",
            "publishedAt": "2020-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    original_item = (await created.json())["item"]
    post_id = original_item["postId"]

    def stored_delivery_state(connection):
        events = connection.execute(
            "SELECT public_id, account_id, category, dedupe_key, route, "
            "payload_json, occurred_at, deliver_after, read_at, created_at "
            "FROM notification_events WHERE category = 'news' AND dedupe_key = ? "
            "ORDER BY account_id",
            (post_id,),
        ).fetchall()
        deliveries = connection.execute(
            "SELECT public_id, event_id, subscription_public_id, state, "
            "attempt_count, next_attempt_at, delivered_at, created_at, updated_at "
            "FROM notification_deliveries WHERE event_id IN "
            "(SELECT id FROM notification_events WHERE dedupe_key = ?) "
            "ORDER BY id",
            (post_id,),
        ).fetchall()
        return [dict(row) for row in events], [dict(row) for row in deliveries]

    events_before, deliveries_before = classroom_http.factory.run_read(
        stored_delivery_state
    )
    assert len(events_before) == 2

    response = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "  Исправленный текст уже опубликованной новости  ",
        },
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 200, await response.text()
    item = (await response.json())["item"]
    assert item["publishedAt"] == original_item["publishedAt"]
    assert item["editedAt"] is not None
    assert item["revision"] == 2
    assert item["textExcerpt"] == "Исправленный текст уже опубликованной новости"
    assert item["isScheduled"] is False
    assert item["version"] == 2
    assert response.headers["ETag"] == f'"{post_id}:v2"'

    events_after, deliveries_after = classroom_http.factory.run_read(
        stored_delivery_state
    )
    assert events_after == events_before
    assert deliveries_after == deliveries_before

    for audience, cookie in (
        (AuthAudience.STUDENT, classroom_http.student_cookie),
        (AuthAudience.FAMILY, classroom_http.family_cookie),
    ):
        feed = await classroom_http.client.get(
            f"/{audience.value}/api/v1/news",
            headers=_headers(),
            cookies={COOKIE_POLICY[audience].access_name: cookie},
        )
        assert feed.status == 200
        feed_item = next(
            candidate
            for candidate in (await feed.json())["items"]
            if candidate["postId"] == post_id
        )
        assert feed_item["blocks"] == [
            {
                "kind": "text",
                "text": "Исправленный текст уже опубликованной новости",
            }
        ]
        assert feed_item["editedAt"] == item["editedAt"]
        assert feed_item["revision"] == 2

    changed_time = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "Ещё один текст",
            "publishedAt": "2099-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True, if_match=response.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert changed_time.status == 409
    assert (await changed_time.json())["error"]["code"] == (
        "local_news_publication_time_locked"
    )

    def revision_and_audit_state(connection):
        revisions = connection.execute(
            "SELECT text_plain FROM news_revisions WHERE post_id = "
            "(SELECT id FROM news_posts WHERE public_id = ?) ORDER BY revision_number",
            (post_id,),
        ).fetchall()
        audit = connection.execute(
            "SELECT before_json, after_json FROM audit_events "
            "WHERE object_id = ? AND action = 'news_local.updated'",
            (post_id,),
        ).fetchone()
        return [row["text_plain"] for row in revisions], dict(audit)

    revisions, audit = classroom_http.factory.run_read(revision_and_audit_state)
    assert revisions == [
        "Уже в ленте",
        "Исправленный текст уже опубликованной новости",
    ]
    assert "Исправленный текст" not in audit["before_json"]
    assert "Исправленный текст" not in audit["after_json"]


@pytest.mark.asyncio
async def test_admin_can_restore_previous_text_and_time_as_a_new_revision(
    classroom_http,
):
    original = {
        "schemaVersion": 1,
        "ownerType": "group",
        "ownerId": "classroom-layout-group",
        "text": "Первый вариант",
        "publishedAt": "2099-08-04T13:00:00Z",
    }
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json=original,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    post_id = (await created.json())["item"]["postId"]
    changed = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "Второй вариант",
            "publishedAt": "2099-08-05T14:00:00Z",
        },
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert changed.status == 200
    restored = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": original["text"],
            "publishedAt": original["publishedAt"],
        },
        headers=_headers(unsafe=True, if_match=changed.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert restored.status == 200, await restored.text()
    assert (await restored.json())["item"]["revision"] == 3

    def revision_hashes(connection):
        return connection.execute(
            "SELECT revision.source_hash FROM news_revisions revision "
            "JOIN news_posts post ON post.id = revision.post_id "
            "WHERE post.public_id = ? ORDER BY revision.revision_number",
            (post_id,),
        ).fetchall()

    hashes = classroom_http.factory.run_read(revision_hashes)
    assert len({row["source_hash"] for row in hashes}) == 3


@pytest.mark.asyncio
async def test_local_news_edit_rolls_back_revision_schedule_and_version_with_audit(
    classroom_http,
):
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "course",
            "ownerId": "classroom-layout-course",
            "text": "До сбоя аудита",
            "publishedAt": "2099-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    post_id = (await created.json())["item"]["postId"]

    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "CREATE TRIGGER fail_local_news_update_audit "
            "BEFORE INSERT ON audit_events "
            "WHEN new.action = 'news_local.updated' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )
    )
    failed = await classroom_http.client.patch(
        f"/staff/api/v1/news/{post_id}/local",
        json={
            "schemaVersion": 1,
            "text": "После сбоя аудита",
            "publishedAt": "2099-08-05T14:00:00Z",
        },
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert failed.status == 500

    def state(connection):
        post = connection.execute(
            "SELECT post.published_at, visibility.version, "
            "(SELECT count(*) FROM news_revisions revision "
            "WHERE revision.post_id = post.id) AS revision_count "
            "FROM news_posts post JOIN news_visibility visibility "
            "ON visibility.post_id = post.id WHERE post.public_id = ?",
            (post_id,),
        ).fetchone()
        event_times = connection.execute(
            "SELECT DISTINCT deliver_after FROM notification_events "
            "WHERE category = 'news' AND dedupe_key = ?",
            (post_id,),
        ).fetchall()
        return dict(post), {row["deliver_after"] for row in event_times}

    post, event_times = classroom_http.factory.run_read(state)
    assert post == {
        "published_at": "2099-08-04T13:00:00.000000Z",
        "version": 1,
        "revision_count": 1,
    }
    assert event_times == {"2099-08-04T13:00:00.000000Z"}


@pytest.mark.asyncio
async def test_published_local_news_reaches_student_and_family(classroom_http):
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "group",
            "ownerId": "classroom-layout-group",
            "text": "Аудитории опубликованы.",
            "publishedAt": "2020-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    post_id = (await created.json())["item"]["postId"]

    for audience, cookie in (
        (AuthAudience.STUDENT, classroom_http.student_cookie),
        (AuthAudience.FAMILY, classroom_http.family_cookie),
    ):
        response = await classroom_http.client.get(
            f"/{audience.value}/api/v1/news",
            headers=_headers(),
            cookies={COOKIE_POLICY[audience].access_name: cookie},
        )
        assert response.status == 200
        item = (await response.json())["items"][0]
        assert (item["postId"], item["source"], item["attribution"]) == (
            post_id,
            "local",
            None,
        )
        assert item["blocks"] == [{"kind": "text", "text": "Аудитории опубликованы."}]


@pytest.mark.asyncio
async def test_local_news_rejects_unknown_owner_and_invalid_content(classroom_http):
    cookies = _cookies(classroom_http, "admin")
    headers = _headers(unsafe=True)
    unknown = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "course",
            "ownerId": "course.missing",
            "text": "Текст",
            "publishedAt": "2026-08-04T13:00:00Z",
        },
        headers=headers,
        cookies=cookies,
    )
    assert unknown.status == 404
    invalid = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "course",
            "ownerId": "classroom-layout-course",
            "text": "   ",
            "publishedAt": "tomorrow",
        },
        headers=headers,
        cookies=cookies,
    )
    assert invalid.status == 422


@pytest.mark.asyncio
async def test_due_local_news_publishes_one_idempotent_refetch_hint(classroom_http):
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "course",
            "ownerId": "classroom-layout-course",
            "text": "Публикация по расписанию",
            "publishedAt": "2099-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201

    messages: list[dict[str, object]] = []

    async def record(payload):
        assert isinstance(payload, dict)
        messages.append(payload)

    await classroom_http.client.app[pwa_app.PWA_BROKER].subscribe(
        pwa_app.NATS_PWA_INVALIDATE,
        record,
    )
    assert await pwa_app.invalidate_due_local_news(
        classroom_http.client.app,
        after="2099-08-04T12:59:59.000000Z",
        through="2099-08-04T13:00:00.000000Z",
    )
    assert {str(message["audience"]) for message in messages} == {
        "student",
        "family",
        "staff",
    }
    assert all(
        message
        == {
            "resources": ["news", "notification-events"],
            "reason": "local-news-published",
            "audience": message["audience"],
        }
        for message in messages
    )

    messages.clear()
    assert not await pwa_app.invalidate_due_local_news(
        classroom_http.client.app,
        after="2099-08-04T13:00:00.000000Z",
        through="2099-08-04T13:00:05.000000Z",
    )
    assert messages == []


@pytest.mark.asyncio
async def test_hidden_local_news_does_not_trigger_due_invalidation(classroom_http):
    created = await classroom_http.client.post(
        "/staff/api/v1/news/local",
        json={
            "schemaVersion": 1,
            "ownerType": "group",
            "ownerId": "classroom-layout-group",
            "text": "Отменённая публикация",
            "publishedAt": "2099-08-04T13:00:00Z",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    item = (await created.json())["item"]
    hidden = await classroom_http.client.patch(
        f"/staff/api/v1/news/{item['postId']}/visibility",
        json={"schemaVersion": 1, "state": "manual_hidden", "reason": "Отменено"},
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert hidden.status == 200

    def notification_count(connection):
        return connection.execute(
            "SELECT count(*) AS total FROM notification_events "
            "WHERE category = 'news' AND dedupe_key = ?",
            (item["postId"],),
        ).fetchone()["total"]

    assert classroom_http.factory.run_read(notification_count) == 0

    assert not await pwa_app.invalidate_due_local_news(
        classroom_http.client.app,
        after="2099-08-04T12:59:59.000000Z",
        through="2099-08-04T13:00:00.000000Z",
    )

    restored = await classroom_http.client.patch(
        f"/staff/api/v1/news/{item['postId']}/visibility",
        json={"schemaVersion": 1, "state": "visible", "reason": None},
        headers=_headers(unsafe=True, if_match=hidden.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert restored.status == 200
    assert classroom_http.factory.run_read(notification_count) == 2
