"""Authenticated HTTP proof for the Staff student-directory editor."""

from __future__ import annotations

from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    TEACHER_ID,
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_teacher_directory_is_scope_filtered_and_hides_account_links(
    classroom_http: ClassroomHttpFixture,
) -> None:
    teacher_list = await classroom_http.client.get(
        "/staff/api/v1/student-enrollments",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher_list.status == 200, await teacher_list.text()
    students = (await teacher_list.json())["students"]
    assert [student["studentId"] for student in students] == [
        "classroom-layout-student"
    ]
    assert students[0]["webAccount"] is None
    assert students[0]["usernameSuggestion"] is None
    assert students[0]["familyAccounts"] == []

    forbidden_update = await classroom_http.client.put(
        "/staff/api/v1/course-enrollments/classroom-layout-enrollment",
        json={
            "schemaVersion": 1,
            "activeGroupId": "classroom-layout-group",
            "allowedGroupIds": ["classroom-layout-group"],
            "attendanceMode": "online",
            "status": "active",
        },
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert forbidden_update.status == 403
    assert (await forbidden_update.json())["error"]["code"] == "forbidden"


async def test_admin_directory_contains_accounts_family_and_course_access(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.get(
        "/staff/api/v1/student-enrollments",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    student = next(
        item
        for item in payload["students"]
        if item["studentId"] == "classroom-layout-student"
    )
    assert student == {
        "studentId": "classroom-layout-student",
        "surname": "Белова",
        "name": "Анна",
        "middleName": None,
        "grade": None,
        "birthday": None,
        "strength": None,
        "usernameSuggestion": None,
        "webAccount": {
            "accountId": "classroom-http-account-student",
            "username": "classroom-http-student",
            "status": "active",
            "credentialVersion": 1,
        },
        "familyAccounts": [
            {
                "accountId": "classroom-http-account-family",
                "username": "classroom-http-family",
                "displayName": "Семья Беловой",
                "status": "active",
                "credentialVersion": 1,
                "relationshipLabel": "родитель",
                "isPrimary": True,
            }
        ],
        "enrollments": [
            {
                "enrollmentId": "classroom-layout-enrollment",
                "course": {
                    "courseId": "classroom-layout-course",
                    "code": "math-layout",
                    "name": "Математика",
                    "subjectCode": "math",
                },
                "activeGroupId": "classroom-layout-group",
                "allowedGroups": [
                    {
                        "groupId": "classroom-layout-group",
                        "code": "н",
                        "name": "Начинающие",
                        "status": "active",
                        "colorKey": "beginner",
                        "sortOrder": 1,
                    }
                ],
                "attendanceMode": "in_person",
                "status": "active",
                "version": 1,
            }
        ],
    }


async def test_admin_directory_suggests_only_unique_canonical_student_logins(
    classroom_http: ClassroomHttpFixture,
) -> None:
    def seed(connection) -> None:
        connection.executemany(
            "INSERT INTO users "
            "(id, public_id, type, name, surname, birthday, token) "
            "VALUES (?, ?, 1, ?, ?, ?, ?)",
            (
                (
                    958020,
                    "student-login-ready",
                    "Сергей",
                    "Шашков",
                    "2013-03-07",
                    "SafeBatchTokenA8",
                ),
                (
                    958021,
                    "student-login-collision-a",
                    "Анна",
                    "Иванова",
                    "2012-01-02",
                    "SafeBatchTokenB8",
                ),
                (
                    958022,
                    "student-login-collision-b",
                    "Алина",
                    "Иванова",
                    "2011-04-02",
                    "SafeBatchTokenC8",
                ),
                (
                    958023,
                    "student-login-invalid",
                    "Борис",
                    "Петров",
                    None,
                    "SafeBatchTokenD8",
                ),
            ),
        )

    classroom_http.factory.run_write(seed)
    response = await classroom_http.client.get(
        "/staff/api/v1/student-enrollments",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    students = {item["studentId"]: item for item in (await response.json())["students"]}

    assert students["student-login-ready"]["usernameSuggestion"] == {
        "username": "shashkov-07",
        "state": "ready",
    }
    for student_id in ("student-login-collision-a", "student-login-collision-b"):
        assert students[student_id]["usernameSuggestion"] == {
            "username": "ivanova-02",
            "state": "collision",
        }
    assert students["student-login-invalid"]["usernameSuggestion"] == {
        "username": None,
        "state": "invalid_identity",
    }


def _seed_second_group(classroom_http: ClassroomHttpFixture) -> None:
    now = "2026-01-05T12:00:00.000000Z"

    def seed(connection) -> None:
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, public_id, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "('layout-advanced', 'п', 'Продолжающие', 2, 1, 0, 0, 0, 1.0, "
            "'classroom-layout-group-advanced', ?, 'active', 'intermediate', ?, ?)",
            (course_id, now, now),
        )
        connection.execute(
            "UPDATE course_group_access SET valid_from = ?, created_at = ?, "
            "updated_at = ? WHERE valid_to IS NULL",
            (now, now, now),
        )

    classroom_http.factory.run_write(seed)


def _allow_second_group_for_student(
    classroom_http: ClassroomHttpFixture,
) -> None:
    now = "2026-01-05T12:00:00.000000Z"

    def seed(connection) -> None:
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
        enrollment_id = connection.execute(
            "SELECT id FROM course_enrollments "
            "WHERE public_id = 'classroom-layout-enrollment'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'layout-advanced', ?, ?, ?)",
            (enrollment_id, course_id, now, now, now),
        )

    classroom_http.factory.run_write(seed)


def _allow_second_group_for_teacher(classroom_http: ClassroomHttpFixture) -> None:
    now = "2026-01-05T12:00:00.000000Z"

    def seed(connection) -> None:
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, created_at, "
            "updated_at) VALUES (?, ?, 'layout-advanced', 'teacher', ?, ?, ?)",
            (TEACHER_ID, course_id, now, now, now),
        )

    classroom_http.factory.run_write(seed)


async def test_teacher_changes_only_active_group_inside_scope(
    classroom_http: ClassroomHttpFixture,
) -> None:
    _seed_second_group(classroom_http)
    _allow_second_group_for_student(classroom_http)

    body = {
        "schemaVersion": 1,
        "activeGroupId": "classroom-layout-group-advanced",
        "allowedGroupIds": [
            "classroom-layout-group",
            "classroom-layout-group-advanced",
        ],
        "attendanceMode": "in_person",
        "status": "active",
    }
    forbidden = await classroom_http.client.put(
        "/staff/api/v1/course-enrollments/classroom-layout-enrollment",
        json=body,
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert forbidden.status == 403

    _allow_second_group_for_teacher(classroom_http)

    response = await classroom_http.client.put(
        "/staff/api/v1/course-enrollments/classroom-layout-enrollment",
        json=body,
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )

    assert response.status == 200, await response.text()
    assert (await response.json())["enrollment"]["activeGroupId"] == (
        "classroom-layout-group-advanced"
    )
    event = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT event_type, actor_user_id FROM course_enrollment_events"
        ).fetchone()
    )
    assert tuple(event.values()) == ("active_group_changed", TEACHER_ID)


async def test_admin_changes_group_mode_and_allowed_access_atomically(
    classroom_http: ClassroomHttpFixture,
) -> None:
    _seed_second_group(classroom_http)
    path = "/staff/api/v1/course-enrollments/classroom-layout-enrollment"
    body = {
        "schemaVersion": 1,
        "activeGroupId": "classroom-layout-group-advanced",
        "allowedGroupIds": [
            "classroom-layout-group",
            "classroom-layout-group-advanced",
        ],
        "attendanceMode": "online",
        "status": "active",
    }

    stale = await classroom_http.client.put(
        path,
        json=body,
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v2"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409

    invalid = await classroom_http.client.put(
        path,
        json={**body, "allowedGroupIds": ["classroom-layout-group"]},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert invalid.status == 422
    assert (await invalid.json())["error"]["code"] == "invalid_enrollment"

    response = await classroom_http.client.put(
        path,
        json=body,
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"classroom-layout-enrollment:v2"'
    enrollment = (await response.json())["enrollment"]
    assert enrollment["activeGroupId"] == "classroom-layout-group-advanced"
    assert enrollment["attendanceMode"] == "online"
    assert {group["groupId"] for group in enrollment["allowedGroups"]} == {
        "classroom-layout-group",
        "classroom-layout-group-advanced",
    }

    # Replaying the complete desired state is a no-op, not a new audit event.
    unchanged = await classroom_http.client.put(
        path,
        json=body,
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v2"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert unchanged.status == 200, await unchanged.text()
    assert unchanged.headers["ETag"] == '"classroom-layout-enrollment:v2"'

    def rows(connection):
        enrollment_row = connection.execute(
            "SELECT active_group_id, attendance_mode, version, updated_by "
            "FROM course_enrollments "
            "WHERE public_id = 'classroom-layout-enrollment'"
        ).fetchone()
        access_rows = connection.execute(
            "SELECT group_id FROM course_group_access "
            "WHERE valid_to IS NULL ORDER BY group_id"
        ).fetchall()
        event_rows = connection.execute(
            "SELECT event_type, source, actor_user_id "
            "FROM course_enrollment_events ORDER BY id"
        ).fetchall()
        legacy_user = connection.execute(
            "SELECT group_id, online FROM users "
            "WHERE public_id = 'classroom-layout-student'"
        ).fetchone()
        return enrollment_row, access_rows, event_rows, legacy_user

    enrollment_row, access_rows, event_rows, legacy_user = (
        classroom_http.factory.run_read(rows)
    )
    assert tuple(enrollment_row.values()) == (
        "layout-advanced",
        "online",
        2,
        ADMIN_ID,
    )
    assert [row["group_id"] for row in access_rows] == [
        "layout-advanced",
        "layout-beginner",
    ]
    assert [tuple(row.values()) for row in event_rows] == [
        ("active_group_changed", "staff", ADMIN_ID),
        ("attendance_mode_changed", "staff", ADMIN_ID),
    ]
    assert tuple(legacy_user.values()) == ("layout-advanced", 1)


async def test_admin_can_revoke_old_access_and_pause_enrollment(
    classroom_http: ClassroomHttpFixture,
) -> None:
    _seed_second_group(classroom_http)
    path = "/staff/api/v1/course-enrollments/classroom-layout-enrollment"
    response = await classroom_http.client.put(
        path,
        json={
            "schemaVersion": 1,
            "activeGroupId": "classroom-layout-group-advanced",
            "allowedGroupIds": ["classroom-layout-group-advanced"],
            "attendanceMode": "in_person",
            "status": "paused",
        },
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-enrollment:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"classroom-layout-enrollment:v2"'

    def rows(connection):
        access = connection.execute(
            "SELECT group_id, valid_to, reason FROM course_group_access "
            "ORDER BY group_id"
        ).fetchall()
        events = connection.execute(
            "SELECT event_type FROM course_enrollment_events ORDER BY id"
        ).fetchall()
        return access, events

    access, events = classroom_http.factory.run_read(rows)
    assert access[0]["group_id"] == "layout-advanced"
    assert access[0]["valid_to"] is None
    assert tuple(access[1].values())[0] == "layout-beginner"
    assert access[1]["valid_to"] is not None
    assert access[1]["reason"] == "staff_update"
    assert [event["event_type"] for event in events] == [
        "active_group_changed",
        "status_changed",
    ]
