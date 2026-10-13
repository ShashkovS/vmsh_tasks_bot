from __future__ import annotations

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, multiprocess

from helpers.prometheus_metrics import (
    METRICS_PATH,
    configure_prometheus,
    prometheus_http_middleware,
    websocket_connection_closed,
    websocket_connection_opened,
    websocket_handler,
)


def _registry() -> CollectorRegistry:
    registry = CollectorRegistry(support_collectors_without_names=True)
    multiprocess.MultiProcessCollector(registry)
    return registry


def _sample(name: str, labels: dict[str, str]) -> float:
    value = _registry().get_sample_value(name, labels)
    return 0.0 if value is None else value


def _counter(method: str, route: str, status: str) -> float:
    return _sample(
        "vmsh_http_requests_total",
        {"method": method, "route": route, "status": status},
    )


def _in_progress(method: str, route: str) -> float:
    return _sample(
        "vmsh_http_requests_in_progress",
        {"method": method, "route": route},
    )


def _duration_count(method: str, route: str) -> float:
    return _sample(
        "vmsh_http_request_duration_seconds_count",
        {"method": method, "route": route},
    )


async def _resolved_request(
    app: web.Application, method: str, path: str
) -> web.Request:
    request = make_mocked_request(method, path, app=app)
    request._match_info = await app.router.resolve(request)
    return request


@pytest.fixture
def metric_app() -> web.Application:
    app = web.Application()
    configure_prometheus(app)
    return app


@pytest.mark.asyncio
async def test_http_200_and_canonical_dynamic_route_labels(metric_app, aiohttp_client):
    async def user(request: web.Request) -> web.Response:
        return web.Response(text=request.match_info["id"])

    metric_app.router.add_get("/prom-users/{id}", user)
    client = await aiohttp_client(metric_app)
    route = "/prom-users/{id}"
    before = _counter("GET", route, "200")

    assert (await client.get("/prom-users/123")).status == 200
    assert (await client.get("/prom-users/456")).status == 200

    assert _counter("GET", route, "200") == before + 2
    assert _counter("GET", "/prom-users/123", "200") == 0
    assert _counter("GET", "/prom-users/456", "200") == 0


@pytest.mark.asyncio
async def test_unmatched_404_uses_bounded_label(metric_app, aiohttp_client):
    client = await aiohttp_client(metric_app)
    before = _counter("GET", "unmatched", "404")

    response = await client.get("/prom-missing/one-off-value")

    assert response.status == 404
    assert _counter("GET", "unmatched", "404") == before + 1


@pytest.mark.asyncio
async def test_http_exception_keeps_status_and_is_not_transformed(
    metric_app, aiohttp_client
):
    async def forbidden(_request: web.Request) -> web.Response:
        raise web.HTTPForbidden(text="no")

    route = "/prom-forbidden"
    metric_app.router.add_get(route, forbidden)
    client = await aiohttp_client(metric_app)
    before = _counter("GET", route, "403")

    response = await client.get(route)

    assert response.status == 403
    assert await response.text() == "no"
    assert _counter("GET", route, "403") == before + 1


@pytest.mark.asyncio
async def test_unhandled_exception_is_counted_and_reraised(metric_app):
    async def route_handler(_request: web.Request) -> web.Response:
        raise AssertionError("handler must be replaced")

    async def explode(_request: web.Request) -> web.Response:
        raise RuntimeError("synthetic failure")

    route = "/prom-explode"
    metric_app.router.add_get(route, route_handler)
    request = await _resolved_request(metric_app, "GET", route)
    before = _counter("GET", route, "500")
    in_progress_before = _in_progress("GET", route)

    with pytest.raises(RuntimeError, match="synthetic failure"):
        await prometheus_http_middleware(request, explode)

    assert _counter("GET", route, "500") == before + 1
    assert _in_progress("GET", route) == in_progress_before


@pytest.mark.asyncio
async def test_cancelled_error_is_counted_as_499_and_reraised(metric_app):
    async def route_handler(_request: web.Request) -> web.Response:
        raise AssertionError("handler must be replaced")

    async def cancelled(_request: web.Request) -> web.Response:
        raise asyncio.CancelledError

    route = "/prom-cancelled"
    metric_app.router.add_get(route, route_handler)
    request = await _resolved_request(metric_app, "GET", route)
    before = _counter("GET", route, "499")
    in_progress_before = _in_progress("GET", route)

    with pytest.raises(asyncio.CancelledError):
        await prometheus_http_middleware(request, cancelled)

    assert _counter("GET", route, "499") == before + 1
    assert _in_progress("GET", route) == in_progress_before


@pytest.mark.asyncio
async def test_in_progress_tracks_live_request_and_returns_to_baseline(
    metric_app, aiohttp_client
):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked(_request: web.Request) -> web.Response:
        entered.set()
        await release.wait()
        return web.Response()

    route = "/prom-blocked"
    metric_app.router.add_get(route, blocked)
    client = await aiohttp_client(metric_app)
    before = _in_progress("GET", route)

    pending = asyncio.create_task(client.get(route))
    await asyncio.wait_for(entered.wait(), timeout=2)
    assert _in_progress("GET", route) == before + 1

    release.set()
    response = await pending
    assert response.status == 200
    assert _in_progress("GET", route) == before


@pytest.mark.asyncio
async def test_metrics_exposition_contains_required_families_and_skips_itself(
    metric_app, aiohttp_client
):
    async def observed(_request: web.Request) -> web.Response:
        return web.Response()

    metric_app.router.add_get("/prom-observed", observed)
    client = await aiohttp_client(metric_app)
    assert (await client.get("/prom-observed")).status == 200
    before = _counter("GET", METRICS_PATH, "200")

    response = await client.get(METRICS_PATH)
    body = await response.text()

    assert response.status == 200
    assert response.headers["Content-Type"] == CONTENT_TYPE_LATEST
    assert "vmsh_http_requests_total" in body
    assert "vmsh_http_request_duration_seconds_bucket" in body
    assert "vmsh_http_request_duration_seconds_count" in body
    assert "vmsh_http_request_duration_seconds_sum" in body
    assert "vmsh_http_requests_in_progress" in body
    assert _counter("GET", METRICS_PATH, "200") == before


@pytest.mark.asyncio
async def test_websocket_gauge_is_balanced_and_session_is_excluded_from_latency(
    metric_app, aiohttp_client
):
    opened = asyncio.Event()
    release = asyncio.Event()

    @websocket_handler
    async def websocket(request: web.Request) -> web.WebSocketResponse:
        response = web.WebSocketResponse()
        await response.prepare(request)
        lease = websocket_connection_opened(request)
        opened.set()
        try:
            await release.wait()
        finally:
            websocket_connection_closed(lease)
            websocket_connection_closed(lease)
            await response.close()
        return response

    route = "/prom-ws"
    metric_app.router.add_get(route, websocket)
    client = await aiohttp_client(metric_app)
    gauge_before = _sample("vmsh_websocket_connections", {"route": route})
    duration_before = _duration_count("GET", route)

    connection_task = asyncio.create_task(client.ws_connect(route))
    await asyncio.wait_for(opened.wait(), timeout=2)
    connection = await connection_task
    assert _sample("vmsh_websocket_connections", {"route": route}) == gauge_before + 1

    release.set()
    await connection.receive(timeout=2)
    await connection.close()
    for _attempt in range(50):
        if _sample("vmsh_websocket_connections", {"route": route}) == gauge_before:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("WebSocket gauge did not return to its baseline")

    assert _duration_count("GET", route) == duration_before
