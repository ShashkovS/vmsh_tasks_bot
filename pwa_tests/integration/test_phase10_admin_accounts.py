"""Authenticated account-lifecycle proof for the Phase-10 Staff directory."""

from __future__ import annotations

from apps.pwa_api import admin_account_routes
from pwa_tests.integration.test_classroom_catalog_http_api import (
    NOW,
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_only_admin_can_change_account_status(
    classroom_http: ClassroomHttpFixture,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        admin_account_routes,
        "_now",
        lambda: NOW.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )
    path = "/staff/api/v1/accounts/classroom-http-account-student/status"
    teacher = await classroom_http.client.patch(
        path,
        json={"schemaVersion": 1, "status": "blocked"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-student:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.patch(
        path,
        json={"schemaVersion": 1, "status": "blocked"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-student:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"classroom-http-account-student:v2"'
    assert (await response.json())["account"] == {
        "accountId": "classroom-http-account-student",
        "audience": "student",
        "status": "blocked",
        "credentialVersion": 2,
    }

    def stored(connection):
        account = connection.execute(
            "SELECT status, credential_version FROM auth_accounts "
            "WHERE public_id = 'classroom-http-account-student'"
        ).fetchone()
        event = connection.execute(
            "SELECT event_type, request_id, metadata_json FROM auth_events "
            "WHERE event_type = 'account.status_changed'"
        ).fetchone()
        sessions = connection.execute(
            "SELECT count(*) AS count FROM auth_sessions "
            "WHERE account_id = (SELECT id FROM auth_accounts "
            "WHERE public_id = 'classroom-http-account-student') "
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
        "/staff/api/v1/accounts/classroom-http-account-family/status",
        json={"schemaVersion": 1, "status": "active"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-family:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"classroom-http-account-family:v1"'
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
        "/staff/api/v1/accounts/classroom-http-account-student/credential",
        json={"schemaVersion": 1, "credential": "replacement-token-2026"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-student:v1"',
        ),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.post(
        "/staff/api/v1/accounts/classroom-http-account-student/credential",
        json={"schemaVersion": 1, "credential": "Replacement-Token-2026"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-student:v1"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["ETag"] == '"classroom-http-account-student:v2"'

    token = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT token FROM users WHERE public_id = 'classroom-layout-student'"
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


async def test_admin_rotates_family_password_without_returning_it(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.post(
        "/staff/api/v1/accounts/classroom-http-account-family/credential",
        json={"schemaVersion": 1, "credential": "new-family-password"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-family:v1"',
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
        "/staff/api/v1/accounts/classroom-http-account-family/status",
        json={"schemaVersion": 1, "status": "archived"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-family:v9"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert status.status == 409

    credential = await classroom_http.client.post(
        "/staff/api/v1/accounts/classroom-http-account-family/credential",
        json={"schemaVersion": 1, "credential": "new-family-password"},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-http-account-family:v9"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert credential.status == 409

    unchanged = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT status, credential_version FROM auth_accounts "
            "WHERE public_id = 'classroom-http-account-family'"
        ).fetchone()
    )
    assert tuple(unchanged.values()) == ("active", 1)
