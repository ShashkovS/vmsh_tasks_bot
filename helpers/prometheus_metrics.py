"""Bounded-cardinality Prometheus instrumentation for the aiohttp app."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from aiohttp import web
from aiohttp.web_urldispatcher import SystemRoute
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)


METRICS_PATH = "/metrics"
UNMATCHED_ROUTE = "unmatched"
_WEBSOCKET_HANDLER_ATTRIBUTE = "__vmsh_websocket_handler__"

HTTP_REQUESTS = Counter(
    "vmsh_http_requests",
    "Total number of HTTP requests handled by aiohttp.",
    ("method", "route", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "vmsh_http_request_duration_seconds",
    "Time spent processing HTTP requests in aiohttp.",
    ("method", "route"),
    buckets=(
        0.005,
        0.010,
        0.025,
        0.050,
        0.100,
        0.250,
        0.500,
        1.000,
        2.500,
        5.000,
        10.000,
    ),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "vmsh_http_requests_in_progress",
    "HTTP requests currently being processed by aiohttp.",
    ("method", "route"),
    multiprocess_mode="livesum",
)
WEBSOCKET_CONNECTIONS = Gauge(
    "vmsh_websocket_connections",
    "Currently open WebSocket connections.",
    ("route",),
    multiprocess_mode="livesum",
)


Handler = TypeVar("Handler", bound=Callable[..., object])


def canonical_route(request: web.Request) -> str:
    """Return aiohttp's route template without using the concrete request path."""

    route = getattr(request.match_info, "route", None)
    if route is None or isinstance(route, SystemRoute):
        return UNMATCHED_ROUTE
    resource = route.resource
    canonical = resource.canonical if resource is not None else ""
    return canonical or UNMATCHED_ROUTE


def websocket_handler(handler: Handler) -> Handler:
    """Mark a known WebSocket handler so HTTP middleware can skip its lifetime."""

    setattr(handler, _WEBSOCKET_HANDLER_ATTRIBUTE, True)
    return handler


def _is_websocket_route(request: web.Request) -> bool:
    route = getattr(request.match_info, "route", None)
    return (
        route is not None
        and not isinstance(route, SystemRoute)
        and bool(getattr(route.handler, _WEBSOCKET_HANDLER_ATTRIBUTE, False))
    )


@web.middleware
async def prometheus_http_middleware(request: web.Request, handler):
    """Observe one bounded HTTP request while preserving application semantics."""

    route = canonical_route(request)
    if route == METRICS_PATH or _is_websocket_route(request):
        return await handler(request)

    method = request.method
    in_progress = HTTP_REQUESTS_IN_PROGRESS.labels(method=method, route=route)
    started = time.perf_counter()
    status = "500"
    in_progress.inc()
    try:
        response = await handler(request)
        status = str(response.status)
        return response
    except asyncio.CancelledError:
        status = "499"
        raise
    except web.HTTPException as error:
        status = str(error.status)
        raise
    except Exception:
        status = "500"
        raise
    finally:
        HTTP_REQUESTS.labels(method=method, route=route, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(
            time.perf_counter() - started
        )
        in_progress.dec()


@dataclass(slots=True)
class WebSocketMetricLease:
    """One idempotently closable gauge increment for an upgraded socket."""

    route: str
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        WEBSOCKET_CONNECTIONS.labels(route=self.route).dec()


def websocket_connection_opened(request: web.Request) -> WebSocketMetricLease:
    """Increment the active connection gauge after a successful upgrade."""

    route = canonical_route(request)
    WEBSOCKET_CONNECTIONS.labels(route=route).inc()
    return WebSocketMetricLease(route)


def websocket_connection_closed(lease: WebSocketMetricLease) -> None:
    """Balance one successful ``websocket_connection_opened`` call."""

    lease.close()


async def metrics(_request: web.Request) -> web.Response:
    """Expose only metrics collected through the Gunicorn multiprocess files."""

    registry = CollectorRegistry(support_collectors_without_names=True)
    multiprocess.MultiProcessCollector(registry)
    return web.Response(
        body=generate_latest(registry),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


def configure_prometheus(app: web.Application) -> None:
    """Install the outermost middleware and loopback-only scrape endpoint."""

    app.middlewares.append(prometheus_http_middleware)
    app.router.add_get(METRICS_PATH, metrics, allow_head=False)


__all__ = [
    "METRICS_PATH",
    "canonical_route",
    "configure_prometheus",
    "prometheus_http_middleware",
    "websocket_connection_closed",
    "websocket_connection_opened",
    "websocket_handler",
]
