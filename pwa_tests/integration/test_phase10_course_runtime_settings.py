"""Phase-10 HTTP proof for typed per-course runtime settings."""

from __future__ import annotations

import json

import pytest

from models.pwa.course_runtime_settings import DEFAULT_COURSE_RUNTIME_SETTINGS
from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


PATH = "/staff/api/v1/courses/classroom-layout-course/runtime-settings"


@pytest.mark.asyncio
async def test_runtime_settings_are_admin_only_typed_and_optimistic(classroom_http):
    teacher = await classroom_http.client.get(
        PATH,
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    initial = await classroom_http.client.get(
        PATH,
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert initial.status == 200, await initial.text()
    assert initial.headers["ETag"] == ('"classroom-layout-course:runtime-settings:v0"')
    assert initial.headers["Cache-Control"] == "no-store"
    assert (await initial.json())["settings"] == {
        "courseId": "classroom-layout-course",
        "values": dict(DEFAULT_COURSE_RUNTIME_SETTINGS),
        "version": 0,
        "source": "defaults",
        "appliesAfter": "restart",
    }

    invalid = await classroom_http.client.put(
        PATH,
        json={
            "schemaVersion": 1,
            "values": {
                **DEFAULT_COURSE_RUNTIME_SETTINGS,
                "saveSolMode": "save_sol_in_tg_only",
            },
        },
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-course:runtime-settings:v0"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert invalid.status == 422

    values = {
        **DEFAULT_COURSE_RUNTIME_SETTINGS,
        "resultMode": "res_after",
        "testAttemptRateLimit": "rate_limit_none",
    }
    saved = await classroom_http.client.put(
        PATH,
        json={"schemaVersion": 1, "values": values},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-course:runtime-settings:v0"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert saved.status == 200, await saved.text()
    assert saved.headers["ETag"] == ('"classroom-layout-course:runtime-settings:v1"')
    assert (await saved.json())["settings"] == {
        "courseId": "classroom-layout-course",
        "values": values,
        "version": 1,
        "source": "stored",
        "appliesAfter": "restart",
    }

    stale = await classroom_http.client.put(
        PATH,
        json={"schemaVersion": 1, "values": values},
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-course:runtime-settings:v0"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"

    stored = await classroom_http.client.get(
        PATH,
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stored.status == 200
    assert (await stored.json())["settings"]["values"] == values

    def audit(connection):
        return connection.execute(
            "SELECT before_json, after_json FROM audit_events "
            "WHERE action = 'course_runtime_settings.updated'"
        ).fetchone()

    event = classroom_http.factory.run_read(audit)
    assert json.loads(event["before_json"])["source"] == "defaults"
    assert json.loads(event["after_json"])["values"] == values


@pytest.mark.asyncio
async def test_runtime_settings_missing_course_and_audit_failure_are_fail_closed(
    classroom_http,
):
    missing = await classroom_http.client.get(
        "/staff/api/v1/courses/missing-course/runtime-settings",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert missing.status == 404

    def install_failure(connection):
        connection.execute(
            "CREATE TRIGGER runtime_settings_audit_failure "
            "BEFORE INSERT ON audit_events "
            "WHEN new.object_type = 'course_runtime_settings' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )

    classroom_http.factory.run_write(install_failure)
    response = await classroom_http.client.put(
        PATH,
        json={
            "schemaVersion": 1,
            "values": dict(DEFAULT_COURSE_RUNTIME_SETTINGS),
        },
        headers=_headers(
            unsafe=True,
            if_match='"classroom-layout-course:runtime-settings:v0"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 500

    stored_count = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM course_runtime_settings"
        ).fetchone()["count"]
    )
    assert stored_count == 0
