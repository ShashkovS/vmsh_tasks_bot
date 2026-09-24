"""Manual calculation shares CLI math, lock and atomic publication."""

import asyncio
import sqlite3
import threading

import pytest

from models.pwa.statistics_recalculation import (
    StatisticsRecalculation,
    RecalculationConflict,
)
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)
URL = "/staff/api/v1/statistics/recalculate"


async def test_admin_start_replay_and_atomic_completion(classroom_http):
    client = classroom_http.client
    kwargs = dict(
        headers=_headers(unsafe=True), cookies=_cookies(classroom_http, "admin")
    )
    body = {"courseId": "c-1", "idempotencyKey": "manual-test"}
    response = await client.post(URL, json=body, **kwargs)
    assert response.status == 202
    first = await response.json()
    for _ in range(100):
        response = await client.get(URL + "?courseId=c-1", **kwargs)
        state = await response.json()
        if not state["busy"]:
            break
        await asyncio.sleep(0.02)
    assert state["operation"]["state"] == "completed", state
    assert state["operation"]["runId"]
    response = await client.post(URL, json=body, **kwargs)
    replay = await response.json()
    assert replay["operation"]["operationId"] == first["operation"]["operationId"]
    assert replay["operation"]["runId"] == state["operation"]["runId"]
    assert (
        classroom_http.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM statistics_recalculations"
            ).fetchone()["n"]
        )
        == 1
    )


@pytest.mark.parametrize("persona", ["teacher", "student", "family"])
async def test_non_admin_cannot_recalculate(classroom_http, persona):
    for method in ("get", "post"):
        kwargs = dict(
            headers=_headers(unsafe=True),
            cookies=(
                _cookies(classroom_http, persona)
                if persona == "teacher"
                else {
                    COOKIE_POLICY[AuthAudience(persona)].access_name: getattr(
                        classroom_http, persona + "_cookie"
                    )
                }
            ),
        )
        if method == "post":
            kwargs["json"] = {"courseId": "c-1", "idempotencyKey": "forbidden"}
        response = await getattr(classroom_http.client, method)(
            URL + "?courseId=c-1", **kwargs
        )
        assert response.status in (401, 403)


async def test_csrf_rejected(classroom_http):
    response = await classroom_http.client.post(
        URL,
        json={"courseId": "c-1", "idempotencyKey": "csrf"},
        cookies=_cookies(classroom_http, "admin"),
        headers={**_headers(), "Origin": "https://evil.example"},
    )
    assert response.status == 403


def test_lock_failure_and_interrupted_recovery(classroom_http, monkeypatch):
    factory = classroom_http.factory
    course_id, actor = factory.run_read(
        lambda c: (
            c.execute("SELECT id FROM courses WHERE public_id='c-1'").fetchone()["id"],
            c.execute("SELECT id FROM users LIMIT 1").fetchone()["id"],
        )
    )
    service = StatisticsRecalculation(factory.database_path)
    entered, release = threading.Event(), threading.Event()

    def fail(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("Injected computation failure")

    monkeypatch.setattr("models.pwa.statistics_recalculation.calculate_course", fail)
    try:
        first = service.start(course_id, actor, "first")
        assert entered.wait(5)
        with pytest.raises(RecalculationConflict):
            service.start(course_id + 1000, actor, "first")
        assert service.status(course_id)["busy"]
        second = service.start(course_id, actor, "second")
        assert second["busy"]
        assert second["operation"]["operationId"] == first["operation"]["operationId"]
        release.set()
        service.close()
        assert service.status(course_id)["operation"]["state"] == "failed"
        factory.run_write(
            lambda c: c.execute(
                "INSERT INTO statistics_recalculations(operation_id,course_id,actor_user_id,idempotency_key,state,started_at) "
                "VALUES('orphan',?,?,'orphan','running','2099-01-01T00:00:00Z')",
                (course_id, actor),
            )
        )
        lock = service.lock()
        assert service.status(course_id)["operation"]["state"] == "running"
        lock.close()
        assert service.status(course_id)["operation"]["errorCode"] == "interrupted"
    finally:
        release.set()
        service.close()


def test_migration_roundtrip(tmp_path):
    path = tmp_path / "migration.sqlite3"
    current = "0092.pwa_statistics_recalculation"
    _apply(path, {m.id for m in _migrations() if m.id <= current})
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM statistics_recalculations"
            ).fetchone()[0]
            == 0
        )
    _rollback(path, {current})
    with sqlite3.connect(path) as connection:
        assert not connection.execute(
            "SELECT name FROM sqlite_master WHERE name='statistics_recalculations'"
        ).fetchall()
    _apply(path, {current})
