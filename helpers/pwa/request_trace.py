"""Bounded, payload-free timings; see vmshpwa/docs/request-tracing.md."""

import asyncio
import json
import logging
import time
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock

from aiohttp import web
from helpers.prometheus_metrics import canonical_route

logger = logging.getLogger(__name__)


@dataclass
class RequestTrace:
    stages: dict = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)
    closed: bool = False

    def add(self, stage, elapsed):
        with self.lock:
            if not self.closed:
                item = self.stages.setdefault(stage, [0, 0.0])
                item[0] += 1
                item[1] += elapsed * 1000


current_trace: ContextVar[RequestTrace | None] = ContextVar(
    "request_trace", default=None
)


@contextmanager
def trace_stage(name):
    trace = current_trace.get()
    started = time.perf_counter() if trace is not None else 0
    try:
        yield
    finally:
        if trace is not None:
            trace.add(name, time.perf_counter() - started)


async def traced_thread(operation, *args):
    trace = current_trace.get()
    submitted = time.perf_counter()

    def run():
        if trace is not None:
            trace.add("db.thread_queue", time.perf_counter() - submitted)
        return operation(*args)

    return await asyncio.to_thread(run)


@web.middleware
async def request_trace_middleware(request, handler):
    route = canonical_route(request)
    if (
        "/api/v1/" not in route
        or request.headers.get("Upgrade", "").lower() == "websocket"
    ):
        return await handler(request)
    trace = RequestTrace()
    token = current_trace.set(trace)
    started = time.perf_counter()
    status = 500
    try:
        response = await handler(request)
        status = response.status
        return response
    except web.HTTPException as error:
        status = error.status
        raise
    except asyncio.CancelledError:
        status = 499
        raise
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        current_trace.reset(token)
        with trace.lock:
            trace.closed = True
            stages = {
                key: {"count": val[0], "ms": round(val[1], 2)}
                for key, val in trace.stages.items()
            }
        if elapsed >= 200:
            logger.info(
                "pwa_slow_request %s",
                json.dumps(
                    {
                        "request_id": request.get("request_id"),
                        "route": route,
                        "method": request.method,
                        "status": status,
                        "total_ms": round(elapsed, 2),
                        "stages": stages,
                    },
                    separators=(",", ":"),
                ),
            )


async def event_loop_trace_lifecycle(app):
    async def monitor():
        while True:
            started = time.perf_counter()
            await asyncio.sleep(1)
            lag = max(0, time.perf_counter() - started - 1)
            if lag >= 0.1:
                logger.info("pwa_event_loop_lag lag_ms=%.2f", lag * 1000)

    task = asyncio.create_task(monitor(), name="pwa-event-loop-trace")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
