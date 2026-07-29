"""Authenticated HTTP proof for scheduled group banners."""

from __future__ import annotations

import pytest

from apps import pwa_app
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _body(*, audience: str = "both", html: str = "<b>Разбор в 17:00</b>"):
    return {
        "schemaVersion": 1,
        "groupId": "classroom-layout-group",
        "audience": audience,
        "html": html,
        "startsAt": "2020-01-01T00:00:00Z",
        "endsAt": "2030-01-01T00:00:00Z",
        "priority": 10,
        "dismissible": True,
    }


@pytest.mark.asyncio
async def test_admin_creates_updates_and_cancels_banner(classroom_http):
    teacher = await classroom_http.client.get(
        "/staff/api/v1/group-banners",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    cursors_before = dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"])
    created = await classroom_http.client.post(
        "/staff/api/v1/group-banners",
        json=_body(html='<b>Разбор</b><a href="javascript:alert(1)">войти</a>'),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    item = (await created.json())["item"]
    assert item["group"] == {
        "groupId": "classroom-layout-group",
        "name": "Начинающие",
        "courseId": "classroom-layout-course",
        "courseName": "Математика",
    }
    assert "javascript" not in item["html"]
    assert created.headers["ETag"] == f'"{item["bannerId"]}:v1"'
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        audience: cursor + 1 for audience, cursor in cursors_before.items()
    }

    listed = await classroom_http.client.get(
        "/staff/api/v1/group-banners?status=active&groupId=classroom-layout-group",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert listed.status == 200
    assert [entry["bannerId"] for entry in (await listed.json())["items"]] == [
        item["bannerId"]
    ]

    stale = await classroom_http.client.patch(
        f"/staff/api/v1/group-banners/{item['bannerId']}",
        json={
            key: value
            for key, value in _body(audience="student").items()
            if key != "groupId"
        },
        headers=_headers(unsafe=True, if_match=f'"{item["bannerId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409

    updated = await classroom_http.client.patch(
        f"/staff/api/v1/group-banners/{item['bannerId']}",
        json={
            key: value
            for key, value in _body(audience="student").items()
            if key != "groupId"
        },
        headers=_headers(unsafe=True, if_match=f'"{item["bannerId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert updated.status == 200, await updated.text()
    assert (await updated.json())["item"]["version"] == 2

    cancelled = await classroom_http.client.post(
        f"/staff/api/v1/group-banners/{item['bannerId']}/cancel",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{item["bannerId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert cancelled.status == 200
    assert (await cancelled.json())["item"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_student_and_family_only_receive_their_active_banners(classroom_http):
    for audience in ("student", "family"):
        response = await classroom_http.client.post(
            "/staff/api/v1/group-banners",
            json=_body(audience=audience, html=f"<i>{audience}</i>"),
            headers=_headers(unsafe=True),
            cookies=_cookies(classroom_http, "admin"),
        )
        assert response.status == 201, await response.text()

    student = await classroom_http.client.get(
        "/student/api/v1/banners/active",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[
                AuthAudience.STUDENT
            ].access_name: classroom_http.student_cookie
        },
    )
    family = await classroom_http.client.get(
        "/family/api/v1/banners/active",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.FAMILY].access_name: classroom_http.family_cookie
        },
    )
    assert student.status == family.status == 200
    assert [item["html"] for item in (await student.json())["items"]] == [
        "<i>student</i>"
    ]
    assert [item["html"] for item in (await family.json())["items"]] == [
        "<i>family</i>"
    ]
