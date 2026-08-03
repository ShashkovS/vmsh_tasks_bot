"""Phase-8 proof for the explicit one-per-group Family lesson digest."""

from __future__ import annotations

import json

import pytest

from apps import pwa_app
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from pwa_tests.integration import test_classroom_catalog_http_api as classroom_support


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _path() -> str:
    return (
        "/staff/api/v1/group-lessons/"
        "classroom-layout-group-lesson/family-digest"
    )


def _family_cookies(fixture) -> dict[str, str]:
    return {
        COOKIE_POLICY[AuthAudience.FAMILY].access_name: fixture.family_cookie,
    }


def _student_cookies(fixture) -> dict[str, str]:
    return {
        COOKIE_POLICY[AuthAudience.STUDENT].access_name: fixture.student_cookie,
    }


@pytest.mark.asyncio
async def test_admin_previews_sends_and_does_not_repeat_family_digest(classroom_http):
    classroom_support._seed_layout_scope(classroom_http.factory)

    teacher = await classroom_http.client.get(
        _path(),
        headers=classroom_support._headers(),
        cookies=classroom_support._cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    preview_response = await classroom_http.client.get(
        _path(),
        headers=classroom_support._headers(),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = (await preview_response.json())["digest"]
    assert preview == {
        "groupLessonId": "classroom-layout-group-lesson",
        "courseId": "classroom-layout-course",
        "courseName": "Математика",
        "groupId": "classroom-layout-group",
        "groupName": "Начинающие",
        "lessonNumber": 41,
        "studentCount": 1,
        "familyCount": 1,
        "alreadySentFamilyCount": 0,
        "pendingFamilyCount": 1,
        "unlinkedStudents": [],
    }

    invalid_body = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1, "automatic": True},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert invalid_body.status == 422

    cursors_before = dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"])
    sent_response = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert sent_response.status == 200, await sent_response.text()
    sent = await sent_response.json()
    assert sent["createdFamilyCount"] == 1
    assert sent["digest"] == {
        **preview,
        "alreadySentFamilyCount": 1,
        "pendingFamilyCount": 0,
    }
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_before,
        "family": cursors_before["family"] + 1,
    }

    def stored(connection):
        event = connection.execute(
            "SELECT account.public_id AS account_public_id, event.category, "
            "event.dedupe_key, event.route, event.payload_json "
            "FROM notification_events AS event "
            "JOIN auth_accounts AS account ON account.id = event.account_id"
        ).fetchone()
        audits = connection.execute(
            "SELECT action, object_type, object_id, request_id, after_json "
            "FROM audit_events WHERE action = 'family_digest.sent'"
        ).fetchall()
        return event, audits

    event, audits = classroom_http.factory.run_read(stored)
    assert event["account_public_id"] == "classroom-http-account-family"
    assert event["category"] == "review_completed"
    assert event["dedupe_key"] == (
        "family-digest:classroom-layout-group-lesson"
    )
    assert event["route"] == "/family/children/classroom-layout-student"
    assert json.loads(event["payload_json"]) == {
        "kind": "family_lesson_digest",
        "courseId": "classroom-layout-course",
        "courseName": "Математика",
        "groupId": "classroom-layout-group",
        "groupName": "Начинающие",
        "groupLessonId": "classroom-layout-group-lesson",
        "lessonNumber": 41,
        "studentIds": ["classroom-layout-student"],
    }
    assert len(audits) == 1
    assert tuple(audits[0][key] for key in ("action", "object_type", "object_id")) == (
        "family_digest.sent",
        "group_lesson",
        "classroom-layout-group-lesson",
    )
    assert audits[0]["request_id"] == "classroom.http.test"
    assert json.loads(audits[0]["after_json"]) == {
        "createdFamilyCount": 1,
        "eligibleFamilyCount": 1,
        "groupId": "classroom-layout-group",
        "lessonNumber": 41,
    }

    family_events = await classroom_http.client.get(
        "/family/api/v1/notification-events",
        headers=classroom_support._headers(),
        cookies=_family_cookies(classroom_http),
    )
    assert family_events.status == 200
    family_item = (await family_events.json())["items"][0]
    assert family_item["category"] == "review_completed"
    assert family_item["route"] == "/family/children/classroom-layout-student"
    assert family_item["payload"]["kind"] == "family_lesson_digest"

    student_events = await classroom_http.client.get(
        "/student/api/v1/notification-events",
        headers=classroom_support._headers(),
        cookies=_student_cookies(classroom_http),
    )
    assert student_events.status == 200
    assert (await student_events.json())["items"] == []

    cursors_after_first = dict(
        classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]
    )
    repeated_response = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert repeated_response.status == 200
    assert (await repeated_response.json())["createdFamilyCount"] == 0
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_first
    )
    counts = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM notification_events) AS events, "
            "(SELECT count(*) FROM audit_events "
            "WHERE action = 'family_digest.sent') AS audits"
        ).fetchone()
    )
    assert counts == {"events": 1, "audits": 1}


@pytest.mark.asyncio
async def test_digest_preview_reports_unlinked_and_reaches_only_late_family(
    classroom_http,
):
    classroom_support._seed_layout_scope(classroom_http.factory)

    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE family_student_links SET revoked_at = updated_at "
            "WHERE student_user_id = ?",
            (classroom_support.STUDENT_ID,),
        )
    )
    unlinked_response = await classroom_http.client.get(
        _path(),
        headers=classroom_support._headers(),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    unlinked = (await unlinked_response.json())["digest"]
    assert (unlinked["familyCount"], unlinked["pendingFamilyCount"]) == (0, 0)
    assert unlinked["unlinkedStudents"] == [
        {
            "studentId": "classroom-layout-student",
            "displayName": "Белова Анна",
        }
    ]
    empty_send = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert (await empty_send.json())["createdFamilyCount"] == 0

    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE family_student_links SET revoked_at = NULL "
            "WHERE student_user_id = ?",
            (classroom_support.STUDENT_ID,),
        )
    )
    first_send = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert (await first_send.json())["createdFamilyCount"] == 1

    def add_late_family(connection):
        now = classroom_support.NOW.isoformat().replace("+00:00", "Z")
        account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, display_name, "
            "provisioning_source, credential_kind, credential_hash, status, "
            "created_at, updated_at) VALUES "
            "('classroom-http-account-family-late', 'family', 'late-family', "
            "'late-family', 'Вторая семья', 'synthetic-test', 'password', ?, "
            "'active', ?, ?) RETURNING id",
            (classroom_support.TEST_HASHER.hash("late-password"), now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at) VALUES (?, ?, 'родитель', 0, ?, ?)",
            (account_id, classroom_support.STUDENT_ID, now, now),
        )

    classroom_http.factory.run_write(add_late_family)
    late_preview_response = await classroom_http.client.get(
        _path(),
        headers=classroom_support._headers(),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    late_preview = (await late_preview_response.json())["digest"]
    assert (
        late_preview["familyCount"],
        late_preview["alreadySentFamilyCount"],
        late_preview["pendingFamilyCount"],
    ) == (2, 1, 1)

    late_send = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert (await late_send.json())["createdFamilyCount"] == 1
    rows = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.public_id, count(*) AS total "
            "FROM notification_events AS event "
            "JOIN auth_accounts AS account ON account.id = event.account_id "
            "GROUP BY account.id ORDER BY account.public_id"
        ).fetchall()
    )
    assert [(row["public_id"], row["total"]) for row in rows] == [
        ("classroom-http-account-family", 1),
        ("classroom-http-account-family-late", 1),
    ]


@pytest.mark.asyncio
async def test_family_digest_rejects_missing_or_inactive_lesson(classroom_http):
    missing = await classroom_http.client.get(
        _path(),
        headers=classroom_support._headers(),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert missing.status == 404

    classroom_support._seed_layout_scope(classroom_http.factory)
    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE group_lessons SET status = 'archived' "
            "WHERE public_id = 'classroom-layout-group-lesson'"
        )
    )
    inactive = await classroom_http.client.post(
        _path(),
        json={"schemaVersion": 1},
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(classroom_http, "admin"),
    )
    assert inactive.status == 409
    assert (await inactive.json())["error"]["code"] == "group_lesson_not_active"
