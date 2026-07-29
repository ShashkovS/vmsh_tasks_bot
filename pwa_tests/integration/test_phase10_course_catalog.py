"""Phase-10 Staff course/group catalog HTTP proof."""

from __future__ import annotations

import pytest

from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _course(*, season_id: str, code: str = "physics-7") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "seasonId": season_id,
        "code": code,
        "name": "Физика 7",
        "subjectCode": "physics",
        "status": "draft",
        "sortOrder": 20,
        "accentKey": "physics",
    }


def _group(*, code: str = "dp2", name: str = "Динамика · 2") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "shortCode": code,
        "name": name,
        "status": "active",
        "colorKey": "continuing",
        "sortOrder": 2,
        "allowSelfSwitch": True,
        "scoreWeight": 1.25,
    }


@pytest.mark.asyncio
async def test_course_catalog_is_admin_only_and_reports_real_counts(classroom_http):
    teacher = await classroom_http.client.get(
        "/staff/api/v1/courses",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.get(
        "/staff/api/v1/courses",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["Cache-Control"] == "no-store"
    body = await response.json()
    assert body["season"] == {
        "seasonId": "classroom-layout-season",
        "code": "layout-season",
        "title": "Layout season",
        "status": "active",
    }
    assert body["courses"] == [
        {
            "courseId": "classroom-layout-course",
            "code": "math-layout",
            "name": "Математика",
            "subjectCode": "math",
            "status": "active",
            "sortOrder": 1,
            "accentKey": "math",
            "activeStudents": 1,
            "groups": [
                {
                    "groupId": "classroom-layout-group",
                    "shortCode": "н",
                    "name": "Начинающие",
                    "status": "active",
                    "colorKey": "beginner",
                    "sortOrder": 1,
                    "allowSelfSwitch": False,
                    "isDefault": False,
                    "isSystem": False,
                    "scoreWeight": 1.0,
                    "activeStudents": 1,
                    "version": 1,
                }
            ],
            "version": 1,
        }
    ]


@pytest.mark.asyncio
async def test_admin_creates_and_versioned_edits_courses_and_groups(classroom_http):
    course_request = _course(season_id="classroom-layout-season", code=" Physics-7 ")
    created = await classroom_http.client.post(
        "/staff/api/v1/courses",
        json=course_request,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    course = (await created.json())["course"]
    assert (course["code"], course["version"], course["groups"]) == (
        "physics-7",
        1,
        [],
    )

    duplicate = await classroom_http.client.post(
        "/staff/api/v1/courses",
        json=_course(season_id="classroom-layout-season", code="PHYSICS-7"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409
    assert (await duplicate.json())["error"]["code"] == "course_duplicate"

    group_created = await classroom_http.client.post(
        f"/staff/api/v1/courses/{course['courseId']}/groups",
        json=_group(code="DP2"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert group_created.status == 201, await group_created.text()
    group = (await group_created.json())["group"]
    assert group == {
        "groupId": group["groupId"],
        "shortCode": "dp2",
        "name": "Динамика · 2",
        "status": "active",
        "colorKey": "continuing",
        "sortOrder": 2,
        "allowSelfSwitch": True,
        "isDefault": False,
        "isSystem": False,
        "scoreWeight": 1.25,
        "activeStudents": 0,
        "version": 1,
    }

    group_body = {**_group(), "status": "archived"}
    stale = await classroom_http.client.put(
        f"/staff/api/v1/groups/{group['groupId']}",
        json=group_body,
        headers=_headers(unsafe=True, if_match=f'"{group["groupId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409

    archived = await classroom_http.client.put(
        f"/staff/api/v1/groups/{group['groupId']}",
        json=group_body,
        headers=_headers(unsafe=True, if_match=f'"{group["groupId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert archived.status == 200, await archived.text()
    assert ((await archived.json())["group"]["status"], archived.headers["ETag"]) == (
        "archived",
        f'"{group["groupId"]}:v2"',
    )

    def legacy_active(connection):
        return connection.execute(
            "SELECT is_active FROM groups WHERE public_id = ?", (group["groupId"],)
        ).fetchone()["is_active"]

    assert classroom_http.factory.run_read(legacy_active) == 0

    edited_course_body = {
        key: value for key, value in course_request.items() if key != "seasonId"
    }
    edited_course_body.update({"code": "physics-7", "status": "archived"})
    edited_course = await classroom_http.client.put(
        f"/staff/api/v1/courses/{course['courseId']}",
        json=edited_course_body,
        headers=_headers(unsafe=True, if_match=f'"{course["courseId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert edited_course.status == 200, await edited_course.text()
    assert (await edited_course.json())["course"]["version"] == 2

    listed = await classroom_http.client.get(
        "/staff/api/v1/courses?seasonId=classroom-layout-season",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert listed.status == 200
    physics = next(
        item for item in (await listed.json())["courses"] if item["code"] == "physics-7"
    )
    assert physics["status"] == "archived"
    assert physics["groups"][0]["status"] == "archived"


@pytest.mark.asyncio
async def test_catalog_rejects_unknown_fields_and_duplicate_group_identity(classroom_http):
    invalid = await classroom_http.client.post(
        "/staff/api/v1/courses",
        json={**_course(season_id="classroom-layout-season"), "unexpected": True},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert invalid.status == 422

    first = await classroom_http.client.post(
        "/staff/api/v1/courses/classroom-layout-course/groups",
        json=_group(code="i9a", name="Новая группа"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert first.status == 201, await first.text()
    duplicate = await classroom_http.client.post(
        "/staff/api/v1/courses/classroom-layout-course/groups",
        json=_group(code="I9A", name="Другая группа"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409
    assert (await duplicate.json())["error"]["code"] == "group_duplicate"
