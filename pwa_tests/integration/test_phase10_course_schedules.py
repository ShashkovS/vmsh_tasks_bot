"""Phase-10 independent course/group schedule HTTP proof."""

from __future__ import annotations

import pytest

from pwa_tests.integration.test_content_http_api import _cookie, _headers


pytest_plugins = ("pwa_tests.integration.test_content_http_api",)


def _rule(field: str, *, day: int, time: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "field": field,
        "dayOffset": day,
        "localTime": time,
        "timezone": "Europe/Moscow",
    }


def _override(
    field: str,
    *,
    mode: str,
    day: int | None = None,
    time: str | None = None,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "field": field,
        "mode": mode,
        "dayOffset": day,
        "localTime": time,
        "timezone": "Europe/Moscow" if mode == "override" else None,
    }


@pytest.mark.asyncio
async def test_admin_confirms_course_schedule_rule_after_impact_preview(content_http):
    teacher = await content_http.client.get(
        "/staff/api/v1/courses/course-content-http/schedule-rules",
        cookies=_cookie(content_http, "teacher"),
        headers=_headers(),
    )
    assert teacher.status == 403

    empty = await content_http.client.get(
        "/staff/api/v1/courses/course-content-http/schedule-rules",
        cookies=_cookie(content_http, "admin"),
        headers=_headers(),
    )
    assert empty.status == 200
    empty_body = await empty.json()
    assert empty_body["rules"] == []
    assert empty_body["draftImpacts"] == []

    created = await content_http.client.put(
        "/staff/api/v1/courses/course-content-http/schedule-rules",
        json=_rule("opens_at", day=0, time="16:30"),
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True),
    )
    assert created.status == 201, await created.text()
    body = await created.json()
    assert body["impact"] == {"groupLessons": 2, "materializedWindows": 0}
    assert body["rule"] | {"ruleId": "ignored"} == {
        "ruleId": "ignored",
        "field": "opens_at",
        "ruleVersion": 1,
        "dayOffset": 0,
        "localTime": "16:30:00",
        "timezone": "Europe/Moscow",
        "state": "draft",
        "version": 1,
    }

    rule_id = body["rule"]["ruleId"]
    resumed = await content_http.client.get(
        "/staff/api/v1/courses/course-content-http/schedule-rules",
        cookies=_cookie(content_http, "admin"),
        headers=_headers(),
    )
    assert (await resumed.json())["draftImpacts"] == [
        {"ruleId": rule_id, "groupLessons": 2, "materializedWindows": 0}
    ]
    stale = await content_http.client.post(
        f"/staff/api/v1/course-schedule-rules/{rule_id}/confirm",
        json={"schemaVersion": 1},
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True, if_match=f'"{rule_id}:v2"'),
    )
    assert stale.status == 409

    confirmed = await content_http.client.post(
        f"/staff/api/v1/course-schedule-rules/{rule_id}/confirm",
        json={"schemaVersion": 1},
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
    )
    assert confirmed.status == 200, await confirmed.text()
    confirmed_body = await confirmed.json()
    assert (confirmed_body["rule"]["state"], confirmed_body["rule"]["version"]) == (
        "active",
        2,
    )


@pytest.mark.asyncio
async def test_group_override_is_based_on_current_active_course_rule(content_http):
    course_draft = await content_http.client.put(
        "/staff/api/v1/courses/course-content-http/schedule-rules",
        json=_rule("hint_scheduled_at", day=5, time="12:00"),
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True),
    )
    course_body = await course_draft.json()
    course_rule_id = course_body["rule"]["ruleId"]
    course_confirmed = await content_http.client.post(
        f"/staff/api/v1/course-schedule-rules/{course_rule_id}/confirm",
        json={"schemaVersion": 1},
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True, if_match=course_draft.headers["ETag"]),
    )
    assert course_confirmed.status == 200

    draft = await content_http.client.put(
        "/staff/api/v1/groups/group-content-http-a/schedule-overrides",
        json=_override("hint_scheduled_at", mode="override", day=5, time="15:00"),
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True),
    )
    assert draft.status == 201, await draft.text()
    draft_body = await draft.json()
    override_id = draft_body["override"]["overrideId"]
    assert draft_body["override"] | {"overrideId": "ignored", "baseRuleId": 0} == {
        "overrideId": "ignored",
        "field": "hint_scheduled_at",
        "overrideVersion": 1,
        "mode": "override",
        "dayOffset": 5,
        "localTime": "15:00:00",
        "timezone": "Europe/Moscow",
        "baseRuleId": 0,
        "state": "draft",
        "version": 1,
    }

    confirmed = await content_http.client.post(
        f"/staff/api/v1/group-schedule-overrides/{override_id}/confirm",
        json={"schemaVersion": 1},
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True, if_match=draft.headers["ETag"]),
    )
    assert confirmed.status == 200, await confirmed.text()
    assert (await confirmed.json())["override"]["state"] == "active"

    listed = await content_http.client.get(
        "/staff/api/v1/groups/group-content-http-a/schedule-overrides",
        cookies=_cookie(content_http, "admin"),
        headers=_headers(),
    )
    assert listed.status == 200
    result = await listed.json()
    assert [item["state"] for item in result["courseRules"]] == ["active"]
    assert [item["state"] for item in result["overrides"]] == ["active"]


@pytest.mark.asyncio
async def test_group_schedule_rejects_missing_base_and_invalid_disabled_cutoff(content_http):
    missing_base = await content_http.client.put(
        "/staff/api/v1/groups/group-content-http-a/schedule-overrides",
        json=_override("solution_scheduled_at", mode="inherit"),
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True),
    )
    assert missing_base.status == 409
    assert (await missing_base.json())["error"]["code"] == "course_schedule_incomplete"

    course_draft = await content_http.client.put(
        "/staff/api/v1/courses/course-content-http/schedule-rules",
        json=_rule("submission_closes_at", day=6, time="21:00"),
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True),
    )
    rule_id = (await course_draft.json())["rule"]["ruleId"]
    confirmed = await content_http.client.post(
        f"/staff/api/v1/course-schedule-rules/{rule_id}/confirm",
        json={"schemaVersion": 1},
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True, if_match=course_draft.headers["ETag"]),
    )
    assert confirmed.status == 200

    disabled = await content_http.client.put(
        "/staff/api/v1/groups/group-content-http-a/schedule-overrides",
        json=_override("submission_closes_at", mode="disabled"),
        cookies=_cookie(content_http, "admin"),
        headers=_headers(unsafe=True),
    )
    assert disabled.status == 422
    assert (await disabled.json())["error"]["code"] == "validation_error"
