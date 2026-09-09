"""Real aiohttp/SQLite contract tests for Phase-1 authentication routes."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from argon2 import PasswordHasher
from aiohttp import WSMsgType, WSServerHandshakeError, web

from apps import pwa_app
from apps.pwa_api.first_admin import ensure_first_global_admin
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience, CredentialHasher


ORIGIN = "http://127.0.0.1:5380"
HOST = "127.0.0.1:5380"
TEST_HASHER = PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)
CREDENTIALS = {
    AuthAudience.STUDENT: "synthetic-student-token",
    AuthAudience.FAMILY: "synthetic-family-password",
    AuthAudience.STAFF: "synthetic-staff-password",
}
USERNAMES = {
    AuthAudience.STUDENT: "student-14",
    AuthAudience.FAMILY: "family-login",
    AuthAudience.STAFF: "staff-login",
}
STUDENT_USER_ID = 901_811
STAFF_USER_ID = 901_812
AUTH_HTTP_FACTORY = web.AppKey("auth_http_test_factory", PwaConnectionFactory)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _auth_config() -> AuthRuntimeConfig:
    return AuthRuntimeConfig(
        origins_by_audience=MappingProxyType(
            {audience: frozenset({ORIGIN}) for audience in AuthAudience}
        ),
        trusted_proxy_networks=(),
        trusted_proxy_hops=0,
        access_ttl_seconds=900,
        secure_cookies=False,
        signing_keys=("s" * 32,),
        refresh_pepper=b"r" * 32,
        throttle_pepper=b"t" * 32,
        test_only_defaults=True,
    )


def _seed_accounts(factory: PwaConnectionFactory) -> None:
    now = _timestamp()

    def seed(connection):
        connection.execute("DELETE FROM kv_logins")
        connection.executemany(
            "INSERT INTO users (id, type, name, surname, group_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (
                    STUDENT_USER_ID,
                    int(USER_TYPE.STUDENT),
                    "Ирина",
                    "Тестова",
                    None,
                ),
                (
                    STAFF_USER_ID,
                    int(USER_TYPE.TEACHER),
                    "Тестовый",
                    "Учитель",
                    None,
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO auth_accounts "
            "(id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, display_name, "
            "credential_kind, credential_hash, linked_user_id, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'synthetic-test', "
            "?, ?, ?, ?, 'active', ?, ?)",
            (
                (
                    1,
                    "student",
                    USERNAMES[AuthAudience.STUDENT],
                    USERNAMES[AuthAudience.STUDENT],
                    1,
                    None,
                    "telegram_token",
                    TEST_HASHER.hash(CREDENTIALS[AuthAudience.STUDENT]),
                    STUDENT_USER_ID,
                    now,
                    now,
                ),
                (
                    2,
                    "family",
                    USERNAMES[AuthAudience.FAMILY],
                    USERNAMES[AuthAudience.FAMILY],
                    None,
                    "Синтетический родитель",
                    "password",
                    TEST_HASHER.hash(CREDENTIALS[AuthAudience.FAMILY]),
                    None,
                    now,
                    now,
                ),
                (
                    3,
                    "staff",
                    USERNAMES[AuthAudience.STAFF],
                    USERNAMES[AuthAudience.STAFF],
                    None,
                    None,
                    "password",
                    TEST_HASHER.hash(CREDENTIALS[AuthAudience.STAFF]),
                    STAFF_USER_ID,
                    now,
                    now,
                ),
            ),
        )
        family_id = connection.execute(
            "SELECT id FROM auth_accounts WHERE public_id = 'a-2'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, "
            "is_primary, created_at, updated_at) VALUES (?, ?, 'родитель', 1, ?, ?)",
            (family_id, STUDENT_USER_ID, now, now),
        )

    factory.run_write(seed)


@pytest.fixture()
async def auth_http_client(tmp_path, aiohttp_client):
    database_path = tmp_path / "auth-http.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    _seed_accounts(factory)
    repository = PwaAuthRepository(factory, credential_hasher=TEST_HASHER)
    auth_config = _auth_config()
    service = await PwaAuthService.create(
        repository,
        auth_config,
        credential_hasher=CredentialHasher(TEST_HASHER),
    )
    app = web.Application()
    app[AUTH_HTTP_FACTORY] = factory
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="auth-http-test",
        config_name="auth_http_test",
        pwa_prototype=True,
        nats_server=None,
    )
    pwa_app.configure(
        app,
        broker=InProcessBroker("auth_http_test"),
        auth_runtime_config=auth_config,
        auth_service=service,
    )

    async def private_probe(_request: web.Request) -> web.Response:
        # Deliberately does not call authenticated_session(): the middleware's
        # default-private contract is what this probe protects.
        return web.json_response({"ok": True})

    app.router.add_get("/student/api/v1/private-probe", private_probe)
    app.router.add_post("/student/api/v1/private-probe", private_probe)
    app.router.add_get("/student/api/v1/auth/login", private_probe)

    async def database_lifecycle(_app):
        factory.start_async_workers()
        try:
            yield
        finally:
            await factory.aclose()

    app.cleanup_ctx.append(database_lifecycle)
    return await aiohttp_client(app)


def _headers(*, unsafe: bool = False) -> dict[str, str]:
    headers = {"Host": HOST, "X-Request-ID": "auth.http.test"}
    if unsafe:
        headers.update({"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"})
    return headers


def _login_body(audience: AuthAudience) -> dict[str, str]:
    credential_field = (
        "telegramToken" if audience is AuthAudience.STUDENT else "password"
    )
    return {
        "username": USERNAMES[audience],
        credential_field: CREDENTIALS[audience],
        "deviceLabel": f"Synthetic {audience.value} browser",
    }


def _set_cookie_values(response) -> list[str]:
    return response.headers.getall("Set-Cookie", [])


async def _student_login(client, *, device_label: str = "WebSocket test"):
    return await client.post(
        "/student/api/v1/auth/login",
        json={**_login_body(AuthAudience.STUDENT), "deviceLabel": device_label},
        headers=_headers(unsafe=True),
    )


async def _student_websocket(client, **kwargs):
    headers = {**_headers(), **kwargs.pop("headers", {})}
    return await client.ws_connect(
        "/student/ws",
        origin=ORIGIN,
        headers=headers,
        **kwargs,
    )


async def _expect_closed(websocket) -> None:
    message = await websocket.receive(timeout=2)
    assert message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING}


@pytest.mark.asyncio
@pytest.mark.parametrize("audience", list(AuthAudience))
async def test_login_sets_exact_audience_cookies_and_contract(
    auth_http_client,
    audience: AuthAudience,
):
    response = await auth_http_client.post(
        f"/{audience.value}/api/v1/auth/login",
        json=_login_body(audience),
        headers=_headers(unsafe=True),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["principal"]["audience"] == audience.value
    assert payload["currentSession"]["isCurrent"] is True
    assert (
        payload["policy"]["sessionExpiresAt"] == payload["currentSession"]["expiresAt"]
    )
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    assert not any(secret in serialized_payload for secret in CREDENTIALS.values())
    assert "password" not in serialized_payload.casefold()
    assert "telegramtoken" not in serialized_payload.casefold()
    assert "credentialhash" not in serialized_payload.casefold()
    cookies = _set_cookie_values(response)
    policy = COOKIE_POLICY[audience]
    assert len(cookies) == 2
    assert any(cookie.startswith(f"{policy.access_name}=") for cookie in cookies)
    assert any(cookie.startswith(f"{policy.refresh_name}=") for cookie in cookies)
    assert all(f"Path={policy.path}" in cookie for cookie in cookies)
    assert all("HttpOnly" in cookie and "SameSite=Lax" in cookie for cookie in cookies)
    assert all("Secure" not in cookie and "Domain=" not in cookie for cookie in cookies)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"] == "auth.http.test"

    if audience is AuthAudience.FAMILY:
        assert payload["principal"]["linkedChildren"] == [
            {
                "studentId": "u-901811",
                "displayName": "Ирина Тестова",
                "relationshipLabel": "родитель",
                "isPrimary": True,
            }
        ]
    if audience is AuthAudience.STAFF:
        assert payload["principal"]["role"] == "teacher"
        assert set(payload["principal"]["capabilities"]) == {
            capability.value
            for capability in Capability
            if capability.value
            in {
                "account.sessions.manage",
                "self.read",
                "course.read",
                "group.read",
                "student.read",
                "review.read",
                "review.write",
                "oral.manage",
                "student.active-group.write",
                "statistics.read",
            }
        }


@pytest.mark.asyncio
async def test_student_login_ignores_case_and_whitespace_in_both_credentials(
    auth_http_client,
):
    response = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json={
            "username": " S\tT\nU\u00a0D E N T-14 ",
            "telegramToken": " S\tY\nN\u00a0T H E T I C- S T U D E N T- T O K E N ",
        },
        headers=_headers(unsafe=True),
    )

    assert response.status == 200, await response.text()
    assert (await response.json())["principal"]["audience"] == "student"


@pytest.mark.asyncio
async def test_first_admin_bootstrap_can_login_through_staff_http_route(auth_http_client):
    """A fresh install must make the configured bootstrap password usable."""

    password = "synthetic-first-admin-password"
    factory = auth_http_client.app[AUTH_HTTP_FACTORY]
    created = await ensure_first_global_admin(
        factory,
        Config(first_admin_password=password),
        CredentialHasher(TEST_HASHER),
    )
    assert created is True

    response = await auth_http_client.post(
        "/staff/api/v1/auth/login",
        json={"username": "admin", "password": password},
        headers=_headers(unsafe=True),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["principal"]["accountId"] == "a-4"
    assert payload["principal"]["role"] == "admin"
    assert len(_set_cookie_values(response)) == 2


@pytest.mark.asyncio
async def test_origin_csrf_and_strict_body_fail_closed(auth_http_client):
    missing_origin = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json=_login_body(AuthAudience.STUDENT),
        headers=_headers(),
    )
    assert missing_origin.status == 403
    assert (await missing_origin.json())["error"]["code"] == "request_source_missing"

    wrong_origin = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json=_login_body(AuthAudience.STUDENT),
        headers={**_headers(), "Origin": "https://attacker.invalid"},
    )
    assert wrong_origin.status == 403

    extra_field = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json={**_login_body(AuthAudience.STUDENT), "audience": "student"},
        headers=_headers(unsafe=True),
    )
    assert extra_field.status == 422
    assert (await extra_field.json())["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_registered_audience_api_route_is_private_without_route_opt_in(
    auth_http_client,
):
    anonymous = await auth_http_client.get(
        "/student/api/v1/private-probe",
        headers=_headers(),
    )
    assert anonymous.status == 401
    assert (await anonymous.json())["error"]["code"] == "authentication_required"

    missing_origin = await auth_http_client.post(
        "/student/api/v1/private-probe",
        headers={**_headers(), "Content-Type": "application/json"},
        data="{}",
    )
    assert missing_origin.status == 403
    assert (await missing_origin.json())["error"]["code"] == "request_source_missing"

    origin_ok_but_anonymous = await auth_http_client.post(
        "/student/api/v1/private-probe",
        headers={**_headers(unsafe=True), "Content-Type": "application/json"},
        data="{}",
    )
    assert origin_ok_but_anonymous.status == 401

    future_same_resource_different_method = await auth_http_client.get(
        "/student/api/v1/auth/login",
        headers=_headers(),
    )
    assert future_same_resource_different_method.status == 401

    legacy = await auth_http_client.post("/api/pwa/health")
    assert legacy.status == 200


@pytest.mark.asyncio
async def test_me_sessions_revoke_refresh_replay_and_uniform_logout(auth_http_client):
    first_login = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json=_login_body(AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert first_login.status == 200, await first_login.text()
    first_context = await first_login.json()
    first_session_id = first_context["currentSession"]["sessionId"]
    refresh_name = COOKIE_POLICY[AuthAudience.STUDENT].refresh_name
    old_refresh = first_login.cookies[refresh_name].value

    me_response = await auth_http_client.get(
        "/student/api/v1/auth/me",
        headers=_headers(),
    )
    assert me_response.status == 200
    assert (await me_response.json())["currentSession"]["sessionId"] == first_session_id

    refreshed = await auth_http_client.post(
        "/student/api/v1/auth/refresh",
        json={},
        headers=_headers(unsafe=True),
    )
    assert refreshed.status == 200
    assert refreshed.cookies[refresh_name].value != old_refresh

    replay = await auth_http_client.post(
        "/student/api/v1/auth/refresh",
        json={},
        cookies={refresh_name: old_refresh},
        headers=_headers(unsafe=True),
    )
    assert replay.status == 401
    assert (await replay.json())["error"]["code"] == "session_revoked"

    after_replay = await auth_http_client.get(
        "/student/api/v1/auth/me",
        headers=_headers(),
    )
    assert after_replay.status == 401

    logout = await auth_http_client.post(
        "/student/api/v1/auth/logout",
        json={},
        cookies={refresh_name: "malformed"},
        headers=_headers(unsafe=True),
    )
    assert logout.status == 204
    cleared = _set_cookie_values(logout)
    assert len(cleared) == 2
    assert all("Max-Age=0" in cookie for cookie in cleared)


@pytest.mark.asyncio
async def test_logout_revokes_current_session_and_logout_all_revokes_other_devices(
    auth_http_client,
):
    refresh_name = COOKIE_POLICY[AuthAudience.STUDENT].refresh_name
    first_login = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json=_login_body(AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert first_login.status == 200
    first_refresh = first_login.cookies[refresh_name].value

    logout = await auth_http_client.post(
        "/student/api/v1/auth/logout",
        json={},
        headers=_headers(unsafe=True),
    )
    assert logout.status == 204
    assert all("Max-Age=0" in cookie for cookie in _set_cookie_values(logout))
    assert (
        await auth_http_client.get("/student/api/v1/auth/me", headers=_headers())
    ).status == 401
    revoked_refresh = await auth_http_client.post(
        "/student/api/v1/auth/refresh",
        json={},
        cookies={refresh_name: first_refresh},
        headers=_headers(unsafe=True),
    )
    assert revoked_refresh.status == 401

    first_device = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json={**_login_body(AuthAudience.STUDENT), "deviceLabel": "First device"},
        headers=_headers(unsafe=True),
    )
    first_device_refresh = first_device.cookies[refresh_name].value
    second_device = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json={**_login_body(AuthAudience.STUDENT), "deviceLabel": "Second device"},
        headers=_headers(unsafe=True),
    )
    assert second_device.status == 200

    logout_all_response = await auth_http_client.post(
        "/student/api/v1/auth/logout-all",
        json={},
        headers=_headers(unsafe=True),
    )
    assert logout_all_response.status == 204
    assert all(
        "Max-Age=0" in cookie for cookie in _set_cookie_values(logout_all_response)
    )
    assert (
        await auth_http_client.get("/student/api/v1/auth/me", headers=_headers())
    ).status == 401
    other_device_refresh = await auth_http_client.post(
        "/student/api/v1/auth/refresh",
        json={},
        cookies={refresh_name: first_device_refresh},
        headers=_headers(unsafe=True),
    )
    assert other_device_refresh.status == 401
    assert (await other_device_refresh.json())["error"]["code"] == "session_revoked"


@pytest.mark.asyncio
async def test_logout_revokes_valid_access_session_when_refresh_cookie_is_missing(
    auth_http_client,
):
    policy = COOKIE_POLICY[AuthAudience.STUDENT]
    logged_in = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json=_login_body(AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert logged_in.status == 200
    saved_refresh = logged_in.cookies[policy.refresh_name].value
    auth_http_client.session.cookie_jar.clear(
        lambda morsel: morsel.key == policy.refresh_name
    )

    logout = await auth_http_client.post(
        "/student/api/v1/auth/logout",
        json={},
        headers=_headers(unsafe=True),
    )
    assert logout.status == 204

    refresh_after_logout = await auth_http_client.post(
        "/student/api/v1/auth/refresh",
        json={},
        cookies={policy.refresh_name: saved_refresh},
        headers=_headers(unsafe=True),
    )
    assert refresh_after_logout.status == 401
    assert (await refresh_after_logout.json())["error"]["code"] == "session_revoked"


@pytest.mark.asyncio
async def test_access_cookie_cannot_cross_audience_and_device_revoke_is_account_scoped(
    auth_http_client,
):
    first = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json=_login_body(AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    first_id = (await first.json())["currentSession"]["sessionId"]
    second = await auth_http_client.post(
        "/student/api/v1/auth/login",
        json={**_login_body(AuthAudience.STUDENT), "deviceLabel": "Second browser"},
        headers=_headers(unsafe=True),
    )
    second_id = (await second.json())["currentSession"]["sessionId"]

    listed = await auth_http_client.get(
        "/student/api/v1/auth/sessions",
        headers=_headers(),
    )
    assert listed.status == 200
    sessions = (await listed.json())["sessions"]
    assert {session["sessionId"] for session in sessions} == {first_id, second_id}
    assert [session["sessionId"] for session in sessions if session["isCurrent"]] == [
        second_id
    ]

    revoked = await auth_http_client.delete(
        f"/student/api/v1/auth/sessions/{first_id}",
        headers=_headers(unsafe=True),
    )
    assert revoked.status == 204
    assert (
        await auth_http_client.get("/student/api/v1/auth/me", headers=_headers())
    ).status == 200

    cross_audience = await auth_http_client.get(
        "/family/api/v1/auth/me",
        headers=_headers(),
    )
    assert cross_audience.status == 401

    self_revoke = await auth_http_client.delete(
        f"/student/api/v1/auth/sessions/{second_id}",
        headers=_headers(unsafe=True),
    )
    assert self_revoke.status == 204
    assert all("Max-Age=0" in cookie for cookie in _set_cookie_values(self_revoke))


@pytest.mark.asyncio
async def test_websocket_requires_exact_origin_and_active_audience_cookie(
    auth_http_client,
):
    logged_in = await _student_login(auth_http_client)
    assert logged_in.status == 200
    policy = COOKIE_POLICY[AuthAudience.STUDENT]
    access_value = logged_in.cookies[policy.access_name].value

    with pytest.raises(WSServerHandshakeError) as missing_origin:
        await auth_http_client.ws_connect(
            "/student/ws",
            headers=_headers(),
        )
    assert missing_origin.value.status == 403

    with pytest.raises(WSServerHandshakeError) as wrong_origin:
        await auth_http_client.ws_connect(
            "/student/ws",
            origin="https://attacker.invalid",
            headers=_headers(),
        )
    assert wrong_origin.value.status == 403

    websocket = await _student_websocket(auth_http_client)
    assert (await websocket.receive_json())["type"] == "connected"
    await websocket.close()

    auth_http_client.session.cookie_jar.clear(
        lambda morsel: morsel.key == policy.access_name
    )
    with pytest.raises(WSServerHandshakeError) as missing_cookie:
        await _student_websocket(auth_http_client)
    assert missing_cookie.value.status == 401

    family_policy = COOKIE_POLICY[AuthAudience.FAMILY]
    with pytest.raises(WSServerHandshakeError) as cross_audience:
        await auth_http_client.ws_connect(
            "/family/ws",
            origin=ORIGIN,
            headers={
                **_headers(),
                "Cookie": f"{family_policy.access_name}={access_value}",
            },
        )
    assert cross_audience.value.status == 401
    assert (
        await auth_http_client.app[pwa_app.PWA_WEBSOCKET_REGISTRY].connection_count()
        == 0
    )


@pytest.mark.asyncio
async def test_expired_session_fails_before_websocket_upgrade(auth_http_client):
    logged_in = await _student_login(auth_http_client)
    context = await logged_in.json()
    session_id = context["currentSession"]["sessionId"]
    policy = COOKIE_POLICY[AuthAudience.STUDENT]
    access_value = logged_in.cookies[policy.access_name].value

    auth_http_client.app[AUTH_HTTP_FACTORY].run_write(
        lambda connection: connection.execute(
            "UPDATE auth_sessions SET "
            "created_at = '1999-01-01T00:00:00.000000Z', "
            "last_seen_at = '1999-01-01T00:00:00.000000Z', "
            "updated_at = '2000-01-01T00:00:00.000000Z', "
            "expires_at = '2000-01-01T00:00:00.000000Z' "
            "WHERE public_id = ?",
            (session_id,),
        )
    )

    with pytest.raises(WSServerHandshakeError) as expired:
        await auth_http_client.ws_connect(
            "/student/ws",
            origin=ORIGIN,
            headers={
                **_headers(),
                "Cookie": f"{policy.access_name}={access_value}",
            },
        )
    assert expired.value.status == 401
    assert (
        await auth_http_client.app[pwa_app.PWA_WEBSOCKET_REGISTRY].connection_count()
        == 0
    )


@pytest.mark.asyncio
async def test_revoke_between_websocket_auth_and_registration_never_connects(
    auth_http_client,
    monkeypatch,
):
    logged_in = await _student_login(auth_http_client)
    session_id = (await logged_in.json())["currentSession"]["sessionId"]
    registry = auth_http_client.app[pwa_app.PWA_WEBSOCKET_REGISTRY]
    original_register = registry.register_pending
    registration_reached = asyncio.Event()
    release_registration = asyncio.Event()

    async def blocked_register(*args, **kwargs):
        registration_reached.set()
        await release_registration.wait()
        return await original_register(*args, **kwargs)

    monkeypatch.setattr(registry, "register_pending", blocked_register)
    websocket_task = asyncio.create_task(_student_websocket(auth_http_client))
    await asyncio.wait_for(registration_reached.wait(), timeout=1)

    auth_http_client.app[AUTH_HTTP_FACTORY].run_write(
        lambda connection: connection.execute(
            "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = 'manual', "
            "version = version + 1 WHERE public_id = ?",
            (_timestamp(), session_id),
        )
    )
    close_report = await registry.close_session(
        audience="student",
        session_public_id=session_id,
    )
    assert close_report.selected == 0
    release_registration.set()

    websocket = await websocket_task
    await _expect_closed(websocket)
    assert await registry.connection_count() == 0


@pytest.mark.asyncio
async def test_authoritative_revalidation_closes_session_revoked_out_of_band(
    auth_http_client,
):
    logged_in = await _student_login(auth_http_client)
    session_id = (await logged_in.json())["currentSession"]["sessionId"]
    websocket = await _student_websocket(auth_http_client)
    assert (await websocket.receive_json())["type"] == "connected"

    auth_http_client.app[AUTH_HTTP_FACTORY].run_write(
        lambda connection: connection.execute(
            "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = 'manual', "
            "version = version + 1 WHERE public_id = ?",
            (_timestamp(), session_id),
        )
    )
    registry = auth_http_client.app[pwa_app.PWA_WEBSOCKET_REGISTRY]
    report = await registry.run_revalidation_once(
        lambda identity: pwa_app._revalidate_websocket_identity(
            auth_http_client.app,
            identity,
        )
    )

    assert report.selected == report.succeeded == 1
    await _expect_closed(websocket)
    assert await registry.connection_count() == 0


@pytest.mark.asyncio
async def test_manual_revoke_and_logout_all_close_every_matching_tab(
    auth_http_client,
):
    first_login = await _student_login(auth_http_client, device_label="First")
    first_session_id = (await first_login.json())["currentSession"]["sessionId"]
    first_tab = await _student_websocket(auth_http_client)
    second_tab = await _student_websocket(auth_http_client)
    assert (await first_tab.receive_json())["type"] == "connected"
    assert (await second_tab.receive_json())["type"] == "connected"

    second_login = await _student_login(auth_http_client, device_label="Second")
    assert second_login.status == 200
    current_tab = await _student_websocket(auth_http_client)
    assert (await current_tab.receive_json())["type"] == "connected"

    nonexistent = await auth_http_client.delete(
        f"/student/api/v1/auth/sessions/{'f' * 32}",
        headers=_headers(unsafe=True),
    )
    assert nonexistent.status == 204
    await current_tab.send_json({"type": "ping"})
    assert (await current_tab.receive_json())["type"] == "pong"

    revoked = await auth_http_client.delete(
        f"/student/api/v1/auth/sessions/{first_session_id}",
        headers=_headers(unsafe=True),
    )
    assert revoked.status == 204
    await _expect_closed(first_tab)
    await _expect_closed(second_tab)
    await current_tab.send_json({"type": "ping"})
    assert (await current_tab.receive_json())["type"] == "pong"

    logout_all = await auth_http_client.post(
        "/student/api/v1/auth/logout-all",
        json={},
        headers=_headers(unsafe=True),
    )
    assert logout_all.status == 204
    await _expect_closed(current_tab)
    assert (
        await auth_http_client.app[pwa_app.PWA_WEBSOCKET_REGISTRY].connection_count()
        == 0
    )


@pytest.mark.asyncio
async def test_refresh_verified_logout_closes_socket_but_wrong_secret_cannot(
    auth_http_client,
):
    policy = COOKIE_POLICY[AuthAudience.STUDENT]
    await _student_login(auth_http_client, device_label="Refresh valid")
    first_socket = await _student_websocket(auth_http_client)
    assert (await first_socket.receive_json())["type"] == "connected"
    auth_http_client.session.cookie_jar.clear(
        lambda morsel: morsel.key == policy.access_name
    )

    refresh_only_logout = await auth_http_client.post(
        "/student/api/v1/auth/logout",
        json={},
        headers=_headers(unsafe=True),
    )
    assert refresh_only_logout.status == 204
    await _expect_closed(first_socket)

    second_login = await _student_login(auth_http_client, device_label="Refresh forged")
    second_session_id = (await second_login.json())["currentSession"]["sessionId"]
    second_socket = await _student_websocket(auth_http_client)
    assert (await second_socket.receive_json())["type"] == "connected"
    auth_http_client.session.cookie_jar.clear(
        lambda morsel: morsel.key in {policy.access_name, policy.refresh_name}
    )

    uniform_logout = await auth_http_client.post(
        "/student/api/v1/auth/logout",
        json={},
        cookies={policy.refresh_name: f"{second_session_id}.wrong-secret"},
        headers=_headers(unsafe=True),
    )
    assert uniform_logout.status == 204
    await second_socket.send_json({"type": "ping"})
    assert (await second_socket.receive_json())["type"] == "pong"
    await second_socket.close()
