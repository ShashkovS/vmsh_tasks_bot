"""Phase-8 proof for browser Web Push subscription persistence and HTTP scope."""

from __future__ import annotations

from pwa_tests.sqlite_template import create_test_database

import base64
import sqlite3

import pytest

from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from models.pwa.push_subscriptions import (
    InvalidPushSubscription,
    register_subscription,
    unregister_subscription,
)
from pwa_tests.integration.test_classroom_catalog_http_api import _headers
from pwa_tests.integration.test_phase8_notification_core import NOW, _seed_account


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _key(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


P256DH = _key(b"\x04" + b"p" * 64)
AUTH_SECRET = _key(b"a" * 16)
ENDPOINT = "https://push.example.test/subscriptions/device-one"


def test_subscription_is_validated_upserted_and_deleted_by_account(tmp_path):
    database_path = tmp_path / "push-model.sqlite3"
    create_test_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        account_id, session_id = _seed_account(connection)

        public_id = register_subscription(
            connection,
            account_id=account_id,
            session_id=session_id,
            endpoint=ENDPOINT,
            p256dh=P256DH,
            auth_secret=AUTH_SECRET,
            expiration_time=None,
            user_agent="Synthetic Browser",
            now=NOW,
        )
        repeated_id = register_subscription(
            connection,
            account_id=account_id,
            session_id=session_id,
            endpoint=ENDPOINT,
            p256dh=_key(b"\x04" + b"q" * 64),
            auth_secret=AUTH_SECRET,
            expiration_time=1_800_000_000_000,
            user_agent="Updated Browser",
            now="2026-10-05T12:01:00Z",
        )
        assert repeated_id == public_id
        assert (
            connection.execute("SELECT count(*) FROM push_subscriptions").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT user_agent FROM push_subscriptions").fetchone()[
                0
            ]
            == "Updated Browser"
        )
        assert not unregister_subscription(
            connection, account_id=account_id + 1, endpoint=ENDPOINT
        )
        assert unregister_subscription(
            connection, account_id=account_id, endpoint=ENDPOINT
        )

        with pytest.raises(InvalidPushSubscription, match="endpoint"):
            register_subscription(
                connection,
                account_id=account_id,
                session_id=session_id,
                endpoint="http://push.example.test/insecure",
                p256dh=P256DH,
                auth_secret=AUTH_SECRET,
                expiration_time=None,
                user_agent=None,
                now=NOW,
            )


async def test_student_push_subscription_http_is_account_scoped(classroom_http):
    runtime = classroom_http.client.server.app[RUNTIME_CONFIG]
    runtime.pwa_vapid_public_key = P256DH
    cookie_name = COOKIE_POLICY[AuthAudience.STUDENT].access_name
    cookies = {cookie_name: classroom_http.student_cookie}

    config = await classroom_http.client.get(
        "/student/api/v1/push-subscriptions/config",
        headers=_headers(),
        cookies=cookies,
    )
    assert config.status == 200
    assert await config.json() == {
        "schemaVersion": 1,
        "enabled": True,
        "applicationServerKey": P256DH,
        "requestId": "classroom.http.test",
    }

    payload = {
        "schemaVersion": 1,
        "endpoint": ENDPOINT,
        "expirationTime": None,
        "keys": {"p256dh": P256DH, "auth": AUTH_SECRET},
    }
    created = await classroom_http.client.post(
        "/student/api/v1/push-subscriptions",
        json=payload,
        headers={**_headers(unsafe=True), "User-Agent": "Synthetic Browser"},
        cookies=cookies,
    )
    assert created.status == 200, await created.text()
    subscription_id = (await created.json())["subscriptionId"]
    assert subscription_id.startswith("push-")

    repeated = await classroom_http.client.post(
        "/student/api/v1/push-subscriptions",
        json=payload,
        headers=_headers(unsafe=True),
        cookies=cookies,
    )
    assert (await repeated.json())["subscriptionId"] == subscription_id
    assert (
        classroom_http.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) FROM push_subscriptions WHERE endpoint = ?",
                (ENDPOINT,),
            ).fetchone()["count(*)"]
        )
        == 1
    )

    family_delete = await classroom_http.client.delete(
        "/family/api/v1/push-subscriptions",
        json={"schemaVersion": 1, "endpoint": ENDPOINT},
        headers=_headers(unsafe=True),
        cookies={
            COOKIE_POLICY[AuthAudience.FAMILY].access_name: classroom_http.family_cookie
        },
    )
    assert (await family_delete.json())["deleted"] is False

    deleted = await classroom_http.client.delete(
        "/student/api/v1/push-subscriptions",
        json={"schemaVersion": 1, "endpoint": ENDPOINT},
        headers=_headers(unsafe=True),
        cookies=cookies,
    )
    assert deleted.status == 200
    assert (await deleted.json())["deleted"] is True


async def test_push_registration_fails_closed_without_vapid(classroom_http):
    response = await classroom_http.client.post(
        "/student/api/v1/push-subscriptions",
        json={
            "schemaVersion": 1,
            "endpoint": ENDPOINT,
            "expirationTime": None,
            "keys": {"p256dh": P256DH, "auth": AUTH_SECRET},
        },
        headers=_headers(unsafe=True),
        cookies={
            COOKIE_POLICY[AuthAudience.STUDENT].access_name: (
                classroom_http.student_cookie
            )
        },
    )
    assert response.status == 503
    assert (await response.json())["error"]["code"] == "push_not_configured"
