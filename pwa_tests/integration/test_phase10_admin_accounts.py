"""Authenticated account-lifecycle proof for the Phase-10 Staff directory."""

from __future__ import annotations

from apps.pwa_api import admin_account_routes
from helpers.consts import USER_TYPE
from pwa_tests.integration.test_classroom_catalog_http_api import (
    NOW,
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_admin_soft_deletes_student_and_disables_student_login(
    classroom_http: ClassroomHttpFixture,
) -> None:
    path = "/staff/api/v1/students/u-958003"
    teacher = await classroom_http.client.delete(
        path,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    deleted = await classroom_http.client.delete(
        path,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert deleted.status == 200, await deleted.text()
    assert (await deleted.json())["deleted"] is True

    directory = await classroom_http.client.get(
        "/staff/api/v1/student-enrollments",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert directory.status == 200
    assert "u-958003" not in {student["studentId"] for student in (await directory.json())["students"]}

    old_session = await classroom_http.client.get(
        "/student/api/v1/auth/me",
        headers=_headers(),
        cookies={"vmsh_student_access": classroom_http.student_cookie},
    )
    assert old_session.status == 401
    login = await classroom_http.client.post(
        "/student/api/v1/auth/login",
        json={"username": "classroom-http-student", "telegramToken": "student-password"},
        headers=_headers(unsafe=True),
    )
    assert login.status == 401

    def stored(connection):
        user = connection.execute(
            "SELECT type, token, chat_id FROM users WHERE public_id = 'u-958003'"
        ).fetchone()
        account = connection.execute(
            "SELECT status, credential_version FROM auth_accounts WHERE public_id = 'a-3'"
        ).fetchone()
        event = connection.execute(
            "SELECT action FROM audit_events WHERE action = 'student.deleted'"
        ).fetchone()
        return user, account, event

    user, account, event = classroom_http.factory.run_read(stored)
    assert tuple(user.values()) == (int(USER_TYPE.DELETED), None, None)
    assert tuple(account.values()) == ("disabled", 2)
    assert event["action"] == "student.deleted"


async def test_only_admin_can_change_account_status(
    classroom_http: ClassroomHttpFixture,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        admin_account_routes,
        "_now",
        lambda: NOW.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )
    path = "/staff/api/v1/accounts/a-3/status"
    teacher = await classroom_http.client.patch(
        path,
        json={"schemaVersion": 1, "status": "blocked"},
        headers=_headers(
            unsafe=True,
            if_match='"a-3:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.patch(
        path,
        json={"schemaVersion": 1, "status": "blocked"},
        headers=_headers(
            unsafe=True,
            if_match='"a-3:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"a-3:v2"'
    assert (await response.json())["account"] == {
        "accountId": "a-3",
        "audience": "student",
        "status": "blocked",
        "credentialVersion": 2,
    }

    def stored(connection):
        account = connection.execute(
            "SELECT status, credential_version FROM auth_accounts "
            "WHERE public_id = 'a-3'"
        ).fetchone()
        event = connection.execute(
            "SELECT event_type, request_id, metadata_json FROM auth_events "
            "WHERE event_type = 'account.status_changed'"
        ).fetchone()
        sessions = connection.execute(
            "SELECT count(*) AS count FROM auth_sessions "
            "WHERE account_id = (SELECT id FROM auth_accounts "
            "WHERE public_id = 'a-3') "
            "AND revoked_at IS NULL"
        ).fetchone()["count"]
        return account, event, sessions

    account, event, sessions = classroom_http.factory.run_read(stored)
    assert tuple(account.values()) == ("blocked", 2)
    assert event["event_type"] == "account.status_changed"
    assert event["request_id"] == "classroom.http.test"
    assert '"actorUserId":958001' in event["metadata_json"]
    assert sessions == 0

    old_session = await classroom_http.client.get(
        "/student/api/v1/auth/me",
        headers=_headers(),
        cookies={
            "vmsh_student_access": classroom_http.student_cookie,
        },
    )
    assert old_session.status == 401


async def test_status_noop_preserves_version_and_writes_no_event(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.patch(
        "/staff/api/v1/accounts/a-4/status",
        json={"schemaVersion": 1, "status": "active"},
        headers=_headers(
            unsafe=True,
            if_match='"a-4:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"a-4:v1"'
    count = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM auth_events "
            "WHERE event_type = 'account.status_changed'"
        ).fetchone()["count"]
    )
    assert count == 0


async def test_admin_rotates_student_token_and_invalidates_old_session(
    classroom_http: ClassroomHttpFixture,
) -> None:
    teacher = await classroom_http.client.post(
        "/staff/api/v1/accounts/a-3/credential",
        json={"schemaVersion": 1, "credential": "replacement-token-2026"},
        headers=_headers(
            unsafe=True,
            if_match='"a-3:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.post(
        "/staff/api/v1/accounts/a-3/credential",
        json={"schemaVersion": 1, "credential": "Replacement-Token-2026"},
        headers=_headers(
            unsafe=True,
            if_match='"a-3:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"a-3:v2"'

    token = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT token FROM users WHERE public_id = 'u-958003'"
        ).fetchone()["token"]
    )
    assert token == "replacement-token-2026"

    login = await classroom_http.client.post(
        "/student/api/v1/auth/login",
        json={
            "username": "classroom-http-student",
            "telegramToken": "Replacement-Token-2026",
        },
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()


async def test_admin_creates_student_web_login_from_current_bot_token(
    classroom_http: ClassroomHttpFixture,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        admin_account_routes,
        "_now",
        lambda: NOW.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )
    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO users "
            "(id, type, name, surname, token, chat_id) VALUES "
            "(958010, ?, 'Лев', 'Новый', "
            "'CurrentBotToken2026', 958010)",
            (int(USER_TYPE.STUDENT),),
        )
    )
    path = "/staff/api/v1/students/u-958010/student-account"
    payload = {"schemaVersion": 1, "username": "  novyi-17  "}

    teacher = await classroom_http.client.post(
        path,
        json=payload,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.post(
        path,
        json=payload,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 201, await response.text()
    body = await response.json()
    assert body["account"]["audience"] == "student"
    assert body["account"]["status"] == "active"
    assert "token" not in str(body).casefold()

    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.username, account.username_normalized, "
            "account.credential_hash, event.event_type, event.metadata_json "
            "FROM auth_accounts AS account JOIN auth_events AS event "
            "ON event.account_id = account.id "
            "WHERE account.linked_user_id = 958010"
        ).fetchone()
    )
    assert stored["username"] == "novyi-17"
    assert stored["username_normalized"] == "novyi-17"
    assert stored["credential_hash"] != "currentbottoken2026"
    assert stored["event_type"] == "student.account_created"
    assert "CurrentBotToken2026" not in stored["metadata_json"]

    login = await classroom_http.client.post(
        "/student/api/v1/auth/login",
        json={"username": "NOVYI-17", "telegramToken": "CurrentBotToken2026"},
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()

    duplicate = await classroom_http.client.post(
        path,
        json=payload,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409
    assert (await duplicate.json())["error"]["code"] == "student_username_conflict"


async def test_student_web_login_creation_rejects_unsafe_legacy_token(
    classroom_http: ClassroomHttpFixture,
) -> None:
    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO users "
            "(id, type, name, surname, token, chat_id) VALUES "
            "(958011, ?, 'Ира', 'Тест', "
            "'123456', 958011)",
            (int(USER_TYPE.STUDENT),),
        )
    )
    response = await classroom_http.client.post(
        "/staff/api/v1/students/u-958011/student-account",
        json={"schemaVersion": 1, "username": "test-01"},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 422
    assert (await response.json())["error"]["code"] == "unsafe_student_credential"


async def test_admin_rotates_family_password_without_returning_it(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.post(
        "/staff/api/v1/accounts/a-4/credential",
        json={"schemaVersion": 1, "credential": "new-family-password"},
        headers=_headers(
            unsafe=True,
            if_match='"a-4:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    body = await response.json()
    assert body["account"]["credentialVersion"] == 2
    assert "credential" not in body["account"]

    login = await classroom_http.client.post(
        "/family/api/v1/auth/login",
        json={
            "username": "classroom-http-family",
            "password": "new-family-password",
        },
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()


async def test_status_and_credential_mutations_require_current_version(
    classroom_http: ClassroomHttpFixture,
) -> None:
    status = await classroom_http.client.patch(
        "/staff/api/v1/accounts/a-4/status",
        json={"schemaVersion": 1, "status": "archived"},
        headers=_headers(
            unsafe=True,
            if_match='"a-4:v9"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert status.status == 409

    credential = await classroom_http.client.post(
        "/staff/api/v1/accounts/a-4/credential",
        json={"schemaVersion": 1, "credential": "new-family-password"},
        headers=_headers(
            unsafe=True,
            if_match='"a-4:v9"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert credential.status == 409

    unchanged = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT status, credential_version FROM auth_accounts "
            "WHERE public_id = 'a-4'"
        ).fetchone()
    )
    assert tuple(unchanged.values()) == ("active", 1)


async def test_admin_creates_family_account_and_link_without_exposing_password(
    classroom_http: ClassroomHttpFixture,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        admin_account_routes,
        "_now",
        lambda: NOW.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )
    path = "/staff/api/v1/students/u-958003/family-accounts"
    payload = {
        "schemaVersion": 1,
        "username": "  Family   New  ",
        "displayName": "  Семья   Новая  ",
        "password": "initial-family-password",
        "relationshipLabel": "  родитель  ",
        "isPrimary": False,
    }
    teacher = await classroom_http.client.post(
        path,
        json=payload,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.post(
        path,
        json=payload,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 201, await response.text()
    body = await response.json()
    assert body["account"]["accountId"] == "a-5"
    assert {
        key: value for key, value in body["account"].items() if key != "accountId"
    } == {
        "username": "Family New",
        "displayName": "Семья Новая",
        "status": "active",
        "credentialVersion": 1,
    }
    assert body["link"] == {
        "studentId": "u-958003",
        "relationshipLabel": "родитель",
        "isPrimary": False,
    }
    assert "password" not in str(body).casefold()

    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.credential_hash, event.event_type, event.metadata_json "
            "FROM auth_accounts AS account JOIN auth_events AS event "
            "ON event.account_id = account.id "
            "WHERE account.username_normalized = 'family new'"
        ).fetchone()
    )
    assert stored["credential_hash"] != payload["password"]
    assert stored["event_type"] == "family.account_created"
    assert payload["password"] not in stored["metadata_json"]

    login = await classroom_http.client.post(
        "/family/api/v1/auth/login",
        json={"username": "FAMILY NEW", "password": payload["password"]},
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()

    duplicate = await classroom_http.client.post(
        path,
        json={**payload, "username": "family new"},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409
    assert (await duplicate.json())["error"]["code"] == "family_username_conflict"


async def test_admin_links_existing_family_to_second_child_and_can_revoke_link(
    classroom_http: ClassroomHttpFixture,
) -> None:
    second_student_id = 958004
    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO users (id, type, name, surname) "
            "VALUES (?, ?, 'Борис', 'Ветров')",
            (second_student_id, int(USER_TYPE.STUDENT)),
        )
    )
    path = "/staff/api/v1/students/u-958004/family-links"
    response = await classroom_http.client.post(
        path,
        json={
            "schemaVersion": 1,
            "familyUsername": " CLASSROOM-HTTP-FAMILY ",
            "relationshipLabel": "родитель",
            "isPrimary": True,
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    linked = await response.json()
    assert linked["account"]["accountId"] == "a-4"
    assert linked["link"]["studentId"] == "u-958004"

    family_access = await classroom_http.client.get(
        "/family/api/v1/children/u-958004/courses",
        headers=_headers(),
        cookies={"vmsh_family_access": classroom_http.family_cookie},
    )
    assert family_access.status == 200, await family_access.text()

    unlink = await classroom_http.client.delete(
        "/staff/api/v1/students/u-958004/family-links/"
        "a-4",
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert unlink.status == 200, await unlink.text()
    assert (await unlink.json())["revoked"] is True

    revoked_access = await classroom_http.client.get(
        "/family/api/v1/children/u-958004/courses",
        headers=_headers(),
        cookies={"vmsh_family_access": classroom_http.family_cookie},
    )
    assert revoked_access.status == 403
    event_types = classroom_http.factory.run_read(
        lambda connection: [
            row["event_type"]
            for row in connection.execute(
                "SELECT event_type FROM auth_events WHERE account_id = "
                "(SELECT id FROM auth_accounts "
                "WHERE public_id = 'a-4') "
                "AND event_type LIKE 'family.student_%' ORDER BY id"
            ).fetchall()
        ]
    )
    assert event_types == ["family.student_linked", "family.student_unlinked"]
