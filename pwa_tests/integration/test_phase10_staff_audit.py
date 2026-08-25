"""Phase-10 admin audit API proof."""

from __future__ import annotations

import json
import sqlite3

import pytest

from apps.pwa_api import admin_account_routes
from db_methods.pwa.audit import insert_audit_event
from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    NOW,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _seed(classroom_http) -> None:
    def write(connection) -> None:
        for index in range(3):
            insert_audit_event(
                connection,
                actor_user_id=ADMIN_ID,
                actor_account_public_id="a-1",
                audience="staff",
                action="account.status_changed",
                object_type="account",
                object_id=f"account.student-{index}",
                request_id=f"audit-request-{index}",
                before_json=json.dumps({"status": "active"}),
                after_json=json.dumps({"status": "blocked", "version": index + 2}),
                occurred_at=f"2026-10-05T12:0{index}:00.000000Z",
            )

    classroom_http.factory.run_write(write)


@pytest.mark.asyncio
async def test_audit_is_admin_only_and_returns_safe_changes(
    classroom_http, monkeypatch
) -> None:
    monkeypatch.setattr(
        admin_account_routes,
        "_now",
        lambda: NOW.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )
    teacher = await classroom_http.client.get(
        "/staff/api/v1/audit",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    changed = await classroom_http.client.patch(
        "/staff/api/v1/accounts/a-3/status",
        json={"schemaVersion": 1, "status": "blocked"},
        headers=_headers(unsafe=True, if_match='"a-3:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert changed.status == 200, await changed.text()

    response = await classroom_http.client.get(
        "/staff/api/v1/audit?objectType=account&q=classroom.http.test",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["Cache-Control"] == "no-store"
    body = await response.json()
    assert body["nextCursor"] is None
    assert body["items"] == [
        {
            "eventId": body["items"][0]["eventId"],
            "occurredAt": body["items"][0]["occurredAt"],
            "audience": "staff",
            "action": "account.status_changed",
            "objectType": "account",
            "objectId": "a-3",
            "requestId": "classroom.http.test",
            "actor": {
                "userId": "u-958001",
                "accountId": "a-1",
                "displayName": "Администратор Иван",
            },
            "before": {"status": "active"},
            "after": {"status": "blocked"},
        }
    ]
    serialized = json.dumps(body).casefold()
    assert "credential_hash" not in serialized
    assert "password" not in serialized


@pytest.mark.asyncio
async def test_audit_uses_stable_cursor_and_rejects_unknown_inputs(
    classroom_http,
) -> None:
    _seed(classroom_http)
    first = await classroom_http.client.get(
        "/staff/api/v1/audit?limit=1",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert first.status == 200
    first_body = await first.json()
    assert first_body["items"][0]["eventId"] == "ae-3"
    assert first_body["nextCursor"] == "ae-3"

    second = await classroom_http.client.get(
        f"/staff/api/v1/audit?limit=1&cursor={first_body['nextCursor']}",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert second.status == 200
    assert (await second.json())["items"][0]["eventId"] == "ae-2"

    for query in (
        "cursor=audit.missing",
        "objectType=unknown",
        "limit=0",
        "unexpected=value",
        "q=one&q=two",
    ):
        invalid = await classroom_http.client.get(
            f"/staff/api/v1/audit?{query}",
            headers=_headers(),
            cookies=_cookies(classroom_http, "admin"),
        )
        assert invalid.status == 422, query


def test_audit_rows_are_immutable(classroom_http) -> None:
    _seed(classroom_http)

    def mutate(connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="audit event is immutable"):
            connection.execute(
                "UPDATE audit_events SET action = 'changed' WHERE public_id = ?",
                ("ae-1",),
            )
        with pytest.raises(
            sqlite3.IntegrityError, match="audit event deletion is forbidden"
        ):
            connection.execute(
                "DELETE FROM audit_events WHERE public_id = ?", ("ae-1",)
            )

    classroom_http.factory.run_write(mutate)
