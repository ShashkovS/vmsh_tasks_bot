"""Regression coverage for analytics validation, including cached PWA clients."""

import pytest

from apps.pwa_api.product_analytics_routes import _route_id
from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def event(route="/tasks/vmsh/:id/:id"):
    return {
        "eventType": "page.view", "routeId": route,
        "viewportWidth": 1280, "viewportHeight": 720,
        "devicePixelRatio": 2, "pointerType": "fine", "displayMode": "browser",
    }


@pytest.mark.parametrize("group", ["н", "п", "э", "%D0%BD", "%D0%BF", "%D1%8D"])
def test_cached_client_group_is_normalized(group):
    assert _route_id(f"/tasks/vmsh/{group}/:id") == "/tasks/vmsh/:id/:id"


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/tasks/vmsh/:id/:id", "/tasks/vmsh/н/:id", "/tasks/vmsh/%D0%BD/:id"])
async def test_valid_events_are_accepted(classroom_http, route):
    response = await classroom_http.client.post(
        "/staff/api/v1/analytics/events",
        json={"events": [event(route)]},
        headers=_headers(unsafe=True), cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 204, await response.text()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"events": []}, {"events": [event()] * 21},
    {"events": [event("/tasks?answer=secret")]},
    {"events": [event("/tasks#answer")]},
    {"events": [event("https://example.com/tasks")]},
    {"events": [{**event(), "eventType": "unknown"}]},
    {"events": [{**event(), "viewportWidth": "1280"}]},
])
async def test_invalid_event_returns_422_not_type_error(classroom_http, payload):
    response = await classroom_http.client.post(
        "/staff/api/v1/analytics/events", json=payload,
        headers=_headers(unsafe=True), cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 422, await response.text()


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "unknown=1", "from=garbage", "from=2020-01-01", "audience=unknown",
    "eventType=unknown", "limit=garbage", "before=garbage",
])
async def test_invalid_report_filter_returns_422(classroom_http, monkeypatch, query):
    from apps.pwa_api import product_analytics_routes as routes

    # Filters run before any DB operations; isolate from optional analytics lifecycle.
    monkeypatch.setattr(routes, "_analytics_factory", lambda request: object())
    response = await classroom_http.client.get(
        f"/staff/api/v1/analytics/events?{query}",
        headers=_headers(), cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 422, await response.text()


@pytest.mark.asyncio
async def test_normalized_route_is_stored(classroom_http, monkeypatch, tmp_path):
    from apps.pwa_api import product_analytics_routes as routes
    from db_methods.pwa.product_analytics import ProductAnalyticsConnectionFactory

    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    monkeypatch.setattr(routes, "_analytics_factory", lambda request: factory)
    response = await classroom_http.client.post(
        "/staff/api/v1/analytics/events",
        json={"events": [event("/tasks/vmsh/%D0%BD/:id")]},
        headers=_headers(unsafe=True), cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 204, await response.text()
    row = factory.run_read(lambda db: db.execute("SELECT route_id FROM product_events").fetchone())
    assert row["route_id"] == "/tasks/vmsh/:id/:id"
