"""Public, content-free admission; existing same-origin/auth boundaries remain."""

import pytest

from apps.pwa_api import sentry_admission_routes as routes
from pwa_tests.integration.test_classroom_catalog_http_api import _headers

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


@pytest.mark.asyncio
async def test_public_admission_before_login_and_shared_audience_reserve(classroom_http):
    for audience in ("student", "family", "staff"):
        response = await classroom_http.client.post(
            f"/{audience}/api/v1/observability/sentry-admission",
            json={"lane": "query", "signature": "deadbeef"},
            headers=_headers(unsafe=True),
        )
        assert response.status == 200
        assert await response.json() == {"allowed": audience == "student"}
        assert response.headers["Cache-Control"] == "no-store"
    assert classroom_http.factory.run_read(lambda db: db.execute(
        "SELECT count(*) AS total FROM pwa_sentry_admissions"
    ).fetchone()["total"]) == 1
    protected = await classroom_http.client.get("/staff/api/v1/courses", headers=_headers())
    assert protected.status == 401


@pytest.mark.asyncio
async def test_cross_origin_cannot_consume_budget(classroom_http):
    response = await classroom_http.client.post(
        "/student/api/v1/observability/sentry-admission",
        json={"lane": "error", "signature": "deadbeef"},
        headers={**_headers(unsafe=True), "Origin": "https://untrusted.example"},
    )
    assert response.status == 403
    assert classroom_http.factory.run_read(lambda db: db.execute(
        "SELECT count(*) AS total FROM pwa_sentry_admissions"
    ).fetchone()["total"]) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"lane": "query", "signature": "secret-answer"},
    {"lane": "unknown", "signature": "deadbeef"},
    {"lane": "error", "signature": "deadbeef", "answer": "secret"},
    {"lane": [], "signature": "deadbeef"},
])
async def test_invalid_payload_is_dropped_without_reservation(classroom_http, payload):
    response = await classroom_http.client.post(
        "/student/api/v1/observability/sentry-admission",
        json=payload, headers=_headers(unsafe=True),
    )
    assert response.status == 200
    assert await response.json() == {"allowed": False}
    assert classroom_http.factory.run_read(lambda db: db.execute(
        "SELECT count(*) AS total FROM pwa_sentry_admissions"
    ).fetchone()["total"]) == 0


@pytest.mark.asyncio
async def test_chunked_oversize_valid_prefix_is_dropped(classroom_http):
    async def body():
        yield b'{"lane":"error","signature":"deadbeef"}'
        yield b' ' * 1024

    response = await classroom_http.client.post(
        "/student/api/v1/observability/sentry-admission",
        data=body(), headers={**_headers(unsafe=True), "Content-Type": "application/json"},
    )
    assert response.status == 200
    assert await response.json() == {"allowed": False}


@pytest.mark.asyncio
async def test_db_unavailability_does_not_capture_a_new_error(classroom_http, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("Database is busy")

    monkeypatch.setattr(routes, "admit_frontend_event", unavailable)
    response = await classroom_http.client.post(
        "/student/api/v1/observability/sentry-admission",
        json={"lane": "error", "signature": "deadbeef"}, headers=_headers(unsafe=True),
    )
    assert response.status == 200
    assert await response.json() == {"allowed": False}
