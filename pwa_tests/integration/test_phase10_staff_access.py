"""Authenticated HTTP proof for teacher course/group scope management."""

from __future__ import annotations

from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    TEACHER_ID,
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_only_admin_lists_staff_access(
    classroom_http: ClassroomHttpFixture,
) -> None:
    teacher = await classroom_http.client.get(
        "/staff/api/v1/staff-access",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403
    assert (await teacher.json())["error"]["code"] == "forbidden"

    response = await classroom_http.client.get(
        "/staff/api/v1/staff-access",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    member = next(
        item
        for item in payload["members"]
        if item["staffUserId"] == "classroom-http-teacher"
    )
    assert member == {
        "staffUserId": "classroom-http-teacher",
        "name": "Мария",
        "surname": "Учитель",
        "middleName": None,
        "role": "teacher",
        "account": {
            "accountId": "classroom-http-account-teacher",
            "username": "classroom-http-teacher",
            "status": "active",
        },
        "scopes": [
            {
                "courseId": "classroom-layout-course",
                "courseCode": "math-layout",
                "courseName": "Математика",
                "courseStatus": "active",
                "groupId": "classroom-layout-group",
                "groupCode": "н",
                "groupName": "Начинающие",
                "groupStatus": "active",
                "version": 1,
            }
        ],
    }


async def test_admin_replaces_scope_and_teacher_sees_it_on_next_request(
    classroom_http: ClassroomHttpFixture,
) -> None:
    # The shared auth fixture deliberately freezes its clock in October. Scope
    # writes use real UTC, so make this row an ordinary already-active grant.
    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE staff_scopes SET valid_from = '2026-01-05T12:00:00.000000Z' "
            "WHERE staff_user_id = ?",
            (TEACHER_ID,),
        )
    )
    response = await classroom_http.client.put(
        "/staff/api/v1/staff-members/classroom-http-teacher/scopes",
        json={
            "schemaVersion": 1,
            "expectedScopes": [
                {
                    "courseId": "classroom-layout-course",
                    "groupId": "classroom-layout-group",
                    "version": 1,
                }
            ],
            "scopes": [{"courseId": "classroom-layout-course", "groupId": None}],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    member = (await response.json())["member"]
    assert [(scope["courseId"], scope["groupId"]) for scope in member["scopes"]] == [
        ("classroom-layout-course", None)
    ]

    me = await classroom_http.client.get(
        "/staff/api/v1/auth/me",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert me.status == 200, await me.text()
    assert [
        (scope["courseId"], scope["groupId"])
        for scope in (await me.json())["principal"]["scopes"]
    ] == [("classroom-layout-course", None)]

    def history(connection):
        return connection.execute(
            "SELECT group_id, valid_to, granted_by, revoked_by, reason "
            "FROM staff_scopes WHERE staff_user_id = ? ORDER BY id",
            (TEACHER_ID,),
        ).fetchall()

    rows = classroom_http.factory.run_read(history)
    assert len(rows) == 2
    assert rows[0]["valid_to"] is not None
    assert rows[0]["revoked_by"] == ADMIN_ID
    assert rows[0]["reason"] == "staff_access_editor"
    assert rows[1]["group_id"] is None
    assert rows[1]["granted_by"] == ADMIN_ID


async def test_scope_replace_rejects_stale_redundant_and_unknown_targets(
    classroom_http: ClassroomHttpFixture,
) -> None:
    url = "/staff/api/v1/staff-members/classroom-http-teacher/scopes"
    expected = [
        {
            "courseId": "classroom-layout-course",
            "groupId": "classroom-layout-group",
            "version": 1,
        }
    ]
    redundant = await classroom_http.client.put(
        url,
        json={
            "schemaVersion": 1,
            "expectedScopes": expected,
            "scopes": [
                {"courseId": "classroom-layout-course", "groupId": None},
                {
                    "courseId": "classroom-layout-course",
                    "groupId": "classroom-layout-group",
                },
            ],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert redundant.status == 422
    assert (await redundant.json())["error"]["code"] == "redundant_group_scope"

    invalid = await classroom_http.client.put(
        url,
        json={
            "schemaVersion": 1,
            "expectedScopes": expected,
            "scopes": [
                {
                    "courseId": "classroom-layout-course",
                    "groupId": "another-course-group",
                }
            ],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert invalid.status == 422
    assert (await invalid.json())["error"]["code"] == "invalid_target"

    stale = await classroom_http.client.put(
        url,
        json={"schemaVersion": 1, "expectedScopes": [], "scopes": []},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"


async def test_admin_scope_is_fixed_global_access(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.put(
        "/staff/api/v1/staff-members/classroom-http-admin/scopes",
        json={"schemaVersion": 1, "expectedScopes": [], "scopes": []},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 422
    assert (await response.json())["error"]["code"] == "admin_scope_fixed"
