"""Phase-10 Staff course/group catalog HTTP proof."""

from __future__ import annotations

import json

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


def _season(*, code: str = "2027-28") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "code": code,
        "title": "2027–2028",
        "startsOn": "2027-09-01",
        "endsOn": "2028-05-31",
        "sessionExpiresOn": "2028-08-10",
        "status": "active",
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
async def test_admin_creates_first_class_season(classroom_http):
    teacher = await classroom_http.client.post(
        "/staff/api/v1/seasons",
        json=_season(),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    created = await classroom_http.client.post(
        "/staff/api/v1/seasons",
        json=_season(code=" 2027-28 "),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    season = (await created.json())["season"]
    assert season["code"] == "2027-28"

    listed = await classroom_http.client.get(
        f'/staff/api/v1/courses?seasonId={season["seasonId"]}',
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert listed.status == 200
    assert (await listed.json())["season"] == season

    duplicate = await classroom_http.client.post(
        "/staff/api/v1/seasons",
        json=_season(code="2027-28"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409
    assert (await duplicate.json())["error"]["code"] == "season_duplicate"


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

    def audit_rows(connection):
        return connection.execute(
            "SELECT event.action, event.object_type, event.object_id, "
            "event.before_json, event.after_json, account.public_id AS actor_account_id "
            "FROM audit_events AS event LEFT JOIN auth_accounts AS account "
            "ON account.id = event.actor_account_id "
            "WHERE event.object_type IN ('course', 'group') ORDER BY event.id"
        ).fetchall()

    events = classroom_http.factory.run_read(audit_rows)
    assert [(event["action"], event["object_type"]) for event in events] == [
        ("course.created", "course"),
        ("group.created", "group"),
        ("group.updated", "group"),
        ("course.updated", "course"),
    ]
    assert all(
        event["actor_account_id"] == "classroom-http-account-admin" for event in events
    )
    assert json.loads(events[0]["after_json"])["status"] == "draft"
    assert json.loads(events[2]["before_json"])["status"] == "active"
    assert json.loads(events[2]["after_json"])["status"] == "archived"
    assert json.loads(events[3]["before_json"])["status"] == "draft"
    assert json.loads(events[3]["after_json"])["status"] == "archived"


@pytest.mark.asyncio
async def test_catalog_rejects_unknown_fields_and_duplicate_group_identity(
    classroom_http,
):
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


@pytest.mark.asyncio
async def test_course_write_rolls_back_when_its_audit_row_cannot_be_saved(
    classroom_http,
):
    def install_failure(connection):
        connection.execute(
            "CREATE TRIGGER audit_course_test_failure BEFORE INSERT ON audit_events "
            "WHEN new.object_type = 'course' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )

    classroom_http.factory.run_write(install_failure)
    response = await classroom_http.client.post(
        "/staff/api/v1/courses",
        json=_course(season_id="classroom-layout-season", code="rollback-proof"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 500

    def state(connection):
        course_count = connection.execute(
            "SELECT count(*) AS count FROM courses WHERE code = 'rollback-proof'"
        ).fetchone()["count"]
        audit_count = connection.execute(
            "SELECT count(*) AS count FROM audit_events "
            "WHERE object_id LIKE 'course.%' AND action = 'course.created'"
        ).fetchone()["count"]
        return course_count, audit_count

    assert classroom_http.factory.run_read(state) == (0, 0)
