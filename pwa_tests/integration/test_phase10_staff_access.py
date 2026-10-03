"""Authenticated HTTP proof for teacher course/group scope management."""

from __future__ import annotations

import json

from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    TEACHER_ID,
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_admin_creates_teacher_account(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.post(
        "/staff/api/v1/staff-members",
        json={
            "schemaVersion": 1,
            "surname": "Новый",
            "name": "Преподаватель",
            "middleName": None,
            "role": "teacher",
            "username": "teacher-new",
            "password": "teacher-password-179",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 201, await response.text()
    member = (await response.json())["member"]
    assert member["role"] == "teacher"
    assert member["account"]["username"] == "teacher-new"
    assert member["scopes"] == []

    duplicate = await classroom_http.client.post(
        "/staff/api/v1/staff-members",
        json={
            "schemaVersion": 1,
            "surname": "Другой",
            "name": "Учитель",
            "middleName": None,
            "role": "teacher",
            "username": "teacher-new",
            "password": "another-password-179",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409

    teacher = await classroom_http.client.post(
        "/staff/api/v1/staff-members",
        json={
            "schemaVersion": 1,
            "surname": "Запрещено",
            "name": "Учителю",
            "middleName": None,
            "role": "teacher",
            "username": "teacher-forbidden",
            "password": "teacher-password-179",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403


async def test_admin_creates_admin_and_promotes_teacher(
    classroom_http: ClassroomHttpFixture,
) -> None:
    created = await classroom_http.client.post(
        "/staff/api/v1/staff-members",
        json={
            "schemaVersion": 1,
            "surname": "Новый",
            "name": "Администратор",
            "middleName": None,
            "role": "admin",
            "username": "admin-new",
            "password": "admin-password-179",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    assert (await created.json())["member"]["role"] == "admin"

    promoted = await classroom_http.client.patch(
        "/staff/api/v1/staff-members/u-958002/role",
        json={"schemaVersion": 1, "role": "admin"},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert promoted.status == 200, await promoted.text()
    member = (await promoted.json())["member"]
    assert member["role"] == "admin"
    assert member["scopes"] == []


async def test_admin_creates_teacher_batch_with_shared_scopes_atomically(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.post(
        "/staff/api/v1/staff-members/batch",
        json={
            "schemaVersion": 1,
            "rows": [
                {
                    "surname": "Пакетный",
                    "name": "Первый",
                    "middleName": None,
                    "username": "teacher-batch-one",
                    "password": "teacher-batch-password-one",
                },
                {
                    "surname": "Пакетный",
                    "name": "Второй",
                    "middleName": "Тестович",
                    "username": "teacher-batch-two",
                    "password": "teacher-batch-password-two",
                },
            ],
            "scopes": [
                {
                    "courseId": "c-1",
                    "groupId": "g-5",
                }
            ],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 201, await response.text()
    assert (await response.json())["counts"] == {"total": 2, "created": 2}
    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.username, count(scope.id) AS scope_count "
            "FROM auth_accounts AS account "
            "JOIN users AS user ON user.id = account.linked_user_id "
            "LEFT JOIN staff_scopes AS scope ON scope.staff_user_id = user.id "
            "AND scope.valid_to IS NULL "
            "WHERE account.username IN ('teacher-batch-one', 'teacher-batch-two') "
            "GROUP BY account.username ORDER BY account.username"
        ).fetchall()
    )
    assert [(row["username"], row["scope_count"]) for row in stored] == [
        ("teacher-batch-one", 1),
        ("teacher-batch-two", 1),
    ]


async def test_teacher_batch_conflict_creates_nothing(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.post(
        "/staff/api/v1/staff-members/batch",
        json={
            "schemaVersion": 1,
            "rows": [
                {
                    "surname": "Новый",
                    "name": "Не создастся",
                    "middleName": None,
                    "username": "teacher-batch-rollback",
                    "password": "teacher-batch-password-new",
                },
                {
                    "surname": "Дубликат",
                    "name": "Логина",
                    "middleName": None,
                    "username": "classroom-http-teacher",
                    "password": "teacher-batch-password-duplicate",
                },
            ],
            "scopes": [{"courseId": "c-1", "groupId": None}],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 409, await response.text()
    count = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM auth_accounts WHERE username = ?",
            ("teacher-batch-rollback",),
        ).fetchone()["count"]
    )
    assert count == 0


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
        if item["staffUserId"] == "u-958002"
    )
    assert member == {
        "staffUserId": "u-958002",
        "name": "Мария",
        "surname": "Учитель",
        "middleName": None,
        "role": "teacher",
        "account": {
            "accountId": "a-2",
            "username": "classroom-http-teacher",
            "status": "active",
        },
        "scopes": [
            {
                "courseId": "c-1",
                "courseCode": "math-layout",
                "courseName": "Математика",
                "courseStatus": "active",
                "groupId": "g-5",
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
        "/staff/api/v1/staff-members/u-958002/scopes",
        json={
            "schemaVersion": 1,
            "expectedScopes": [
                {
                    "courseId": "c-1",
                    "groupId": "g-5",
                    "version": 1,
                }
            ],
            "scopes": [{"courseId": "c-1", "groupId": None}],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    member = (await response.json())["member"]
    assert [(scope["courseId"], scope["groupId"]) for scope in member["scopes"]] == [
        ("c-1", None)
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
    ] == [("c-1", None)]

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

    def audit(connection):
        return connection.execute(
            "SELECT action, object_id, before_json, after_json FROM audit_events "
            "WHERE object_type = 'staff_scope'"
        ).fetchone()

    event = classroom_http.factory.run_read(audit)
    assert event["action"] == "staff_scope.replaced"
    assert event["object_id"] == "u-958002"
    assert json.loads(event["before_json"]) == {
        "scopeCount": 1,
        "scopes": "c-1/g-5",
    }
    assert json.loads(event["after_json"]) == {
        "scopeCount": 1,
        "scopes": "c-1",
        "addedCount": 1,
        "removedCount": 1,
    }

    timeline = await classroom_http.client.get(
        "/staff/api/v1/audit?objectType=staff_scope",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert timeline.status == 200
    assert (await timeline.json())["items"][0]["objectType"] == "staff_scope"


async def test_scope_replace_rejects_stale_redundant_and_unknown_targets(
    classroom_http: ClassroomHttpFixture,
) -> None:
    url = "/staff/api/v1/staff-members/u-958002/scopes"
    expected = [
        {
            "courseId": "c-1",
            "groupId": "g-5",
            "version": 1,
        }
    ]
    redundant = await classroom_http.client.put(
        url,
        json={
            "schemaVersion": 1,
            "expectedScopes": expected,
            "scopes": [
                {"courseId": "c-1", "groupId": None},
                {
                    "courseId": "c-1",
                    "groupId": "g-5",
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
                    "courseId": "c-1",
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
        "/staff/api/v1/staff-members/u-958001/scopes",
        json={"schemaVersion": 1, "expectedScopes": [], "scopes": []},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 422
    assert (await response.json())["error"]["code"] == "admin_scope_fixed"


async def test_scope_replace_rolls_back_when_audit_insert_fails(
    classroom_http: ClassroomHttpFixture,
) -> None:
    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "CREATE TRIGGER audit_staff_scope_test_failure "
            "BEFORE INSERT ON audit_events "
            "WHEN new.object_type = 'staff_scope' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )
    )
    response = await classroom_http.client.put(
        "/staff/api/v1/staff-members/u-958002/scopes",
        json={
            "schemaVersion": 1,
            "expectedScopes": [
                {
                    "courseId": "c-1",
                    "groupId": "g-5",
                    "version": 1,
                }
            ],
            "scopes": [{"courseId": "c-1", "groupId": None}],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 500

    def state(connection):
        active = connection.execute(
            "SELECT course_id, group_id, version FROM staff_scopes "
            "WHERE staff_user_id = ? AND valid_to IS NULL",
            (TEACHER_ID,),
        ).fetchall()
        audits = connection.execute(
            "SELECT count(*) AS count FROM audit_events "
            "WHERE object_type = 'staff_scope'"
        ).fetchone()["count"]
        return active, audits

    active, audits = classroom_http.factory.run_read(state)
    assert len(active) == 1
    assert active[0]["group_id"] == "layout-beginner"
    assert active[0]["version"] == 1
    assert audits == 0
