"""Published teacher-scoped export, vmshpwa/docs/whiteboard-export.md."""

import pytest
from pwa_tests.integration.test_content_http_api import (
    content_http as shared_content_http,
    _cookie,
    _headers,
    _prepare_published_test_problem,
)


# Reuse the real API fixture without collecting its test module.
content_http = shared_content_http


@pytest.mark.asyncio
async def test_whiteboard_published_scope_and_statistics(content_http):
    fixture = content_http
    await _prepare_published_test_problem(fixture)
    base = "/staff/api/v1/whiteboard-export"
    for identity in ("student", "family"):
        response = await fixture.client.get(
            base, cookies=_cookie(fixture, identity), headers=_headers()
        )
        assert response.status in (401, 403)
    for identity in ("admin", "teacher"):
        response = await fixture.client.get(
            base, cookies=_cookie(fixture, identity), headers=_headers()
        )
        assert response.status == 200, await response.text()
        catalog = await response.json()
        assert len(catalog["sheets"]) == 1
        response = await fixture.client.get(
            base + "/" + fixture.group_lesson_a,
            cookies=_cookie(fixture, identity),
            headers=_headers(),
        )
        assert response.status == 200, await response.text()
        data = await response.json()
        assert data["document"]["materialKind"] == "condition"
        assert data["document"]["problems"][0]["title"] == "Целое число"
        assert data["statisticsError"] is False
        assert data["statistics"]["participantCount"] == 0
        assert data["statistics"]["problems"][0]["points"] == 0
        assert set(data["statistics"]["problems"][0]) == {
            "problemId",
            "label",
            "title",
            "points",
            "tried",
            "share",
        }
        response = await fixture.client.get(
            base + "/" + fixture.group_lesson_b,
            cookies=_cookie(fixture, identity),
            headers=_headers(),
        )
        assert response.status == 404


@pytest.mark.asyncio
async def test_whiteboard_archive_foreign_scope_and_optional_statistics(
    content_http, monkeypatch
):
    from dataclasses import replace
    from apps.pwa_api import whiteboard_export_routes

    fixture = content_http
    await _prepare_published_test_problem(fixture)
    await _prepare_published_test_problem(
        replace(fixture, group_lesson_a=fixture.group_lesson_b)
    )
    fixture.factory.run_write(
        lambda c: c.execute(
            "UPDATE group_lessons SET status='archived' WHERE public_id=?",
            (fixture.group_lesson_a,),
        )
    )
    base = "/staff/api/v1/whiteboard-export"
    response = await fixture.client.get(
        base, cookies=_cookie(fixture, "teacher"), headers=_headers()
    )
    assert [s["groupLessonId"] for s in (await response.json())["sheets"]] == [
        fixture.group_lesson_a
    ]
    for path in (
        "/" + fixture.group_lesson_b,
        "/" + fixture.group_lesson_b + "/assets/ma-1",
    ):
        response = await fixture.client.get(
            base + path, cookies=_cookie(fixture, "teacher"), headers=_headers()
        )
        assert response.status == 403
    response = await fixture.client.get(
        base + "/" + fixture.group_lesson_a,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert response.status == 200, await response.text()
    response = await fixture.client.get(
        base + "/" + fixture.group_lesson_b,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert response.status == 200

    def broken(*args):
        raise RuntimeError("statistics unavailable")

    monkeypatch.setattr(whiteboard_export_routes, "course_facts", broken)
    response = await fixture.client.get(
        base + "/" + fixture.group_lesson_a,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    payload = await response.json()
    assert payload["statisticsError"] and payload["statistics"] is None
    response = await fixture.client.get(
        base + "/" + fixture.group_lesson_a + "?statistics=0",
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    payload = await response.json()
    assert payload["statisticsError"] is False and payload["statistics"] is None
    response = await fixture.client.get(
        base + "/" + fixture.group_lesson_a + "/assets/ma-9999",
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert response.status == 404


@pytest.mark.asyncio
async def test_export_metrics_equal_staff_statistics(content_http):
    from pwa_tests.integration.test_content_http_api import _timestamp

    fixture = content_http
    problem, revision = await _prepare_published_test_problem(fixture)
    response = await fixture.client.post(
        f"/student/api/v1/problems/{problem}/test-attempts",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac05",
            "problemRevision": {"conditionRevisionId": revision, "configVersion": 1},
            "displayAnswer": "7",
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert response.status in (200, 201), await response.text()
    response = await fixture.client.get(
        "/staff/api/v1/statistics?courseId=c-1&groupId=g-1&lessonNumber=41",
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert response.status == 200, await response.text()
    basic = (await response.json())["basicLesson"]["groups"][0]
    response = await fixture.client.get(
        "/staff/api/v1/whiteboard-export/" + fixture.group_lesson_a,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    stats = (await response.json())["statistics"]
    assert stats["participantCount"] == basic["participantCount"] == 1
    assert stats["problems"] == [
        {
            k: v
            for k, v in row.items()
            if k not in ("difficultyWeak", "difficultyStrong")
        }
        for row in basic["problems"]
    ]
    assert stats["problems"][0]["share"] == 100
