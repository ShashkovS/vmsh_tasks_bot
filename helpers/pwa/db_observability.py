"""Admission diagnostics; contract: vmshpwa/docs/sqlite-admission-performance.md."""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

from prometheus_client import Gauge, Histogram

from helpers.pwa.request_trace import current_trace, trace_stage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
SLOW_SECONDS = 0.2
OWNER_INTERVAL = 1.0

# liveall supplies the worker PID automatically, and dead-worker cleanup removes
# its series. Request IDs, callback names and URLs never become metric labels.
WAITING = Gauge(
    "vmsh_db_waiting",
    "Operations waiting for admission",
    ["role"],
    multiprocess_mode="liveall",
)
ACTIVE = Gauge(
    "vmsh_db_active",
    "Operations holding admission slots",
    ["role"],
    multiprocess_mode="liveall",
)
BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1, 2.5, 5, 10, 30, 60)
WAIT = Histogram(
    "vmsh_db_admission_wait_seconds",
    "Admission wait including cancelled waits",
    ["role"],
    buckets=BUCKETS,
)
HOLD = Histogram(
    "vmsh_db_slot_hold_seconds",
    "Full admission slot lifetime",
    ["role"],
    buckets=BUCKETS,
)


@asynccontextmanager
async def observed_admission(role, slots, operation, queue_depth):
    trace = current_trace.get()
    identity = {
        "pid": os.getpid(),
        "role": role,
        "request_id": trace.request_id if trace else None,
        "route": trace.route if trace else None,
        "callback": getattr(operation, "__qualname__", type(operation).__qualname__),
    }

    def emit(event, elapsed, **extra):
        logger.info(
            "pwa_db_operation %s",
            json.dumps(
                {
                    **identity,
                    "event": event,
                    "duration_ms": round(elapsed * 1000, 2),
                    "queue_depth": queue_depth[role],
                    **extra,
                },
                separators=(",", ":"),
            ),
        )

    started = time.perf_counter()
    queue_depth[role] += 1
    WAITING.labels(role).inc()
    acquired = False
    try:
        with (
            trace_stage("db.admission_queue"),
            trace_stage(f"db.admission_queue.{role}"),
        ):
            await slots.acquire()
        acquired = True
    finally:
        queue_depth[role] -= 1
        WAITING.labels(role).dec()
        elapsed = time.perf_counter() - started
        WAIT.labels(role).observe(elapsed)
        if elapsed >= SLOW_SECONDS:
            emit("admitted" if acquired else "wait_cancelled", elapsed)

    started = time.perf_counter()
    ACTIVE.labels(role).inc()
    loop = asyncio.get_running_loop()
    timer = None

    def report_owner():
        nonlocal timer
        emit("holding", time.perf_counter() - started)
        timer = loop.call_later(OWNER_INTERVAL, report_owner)

    timer = loop.call_later(OWNER_INTERVAL, report_owner)
    outcome = "completed"
    try:
        yield
    except BaseException as error:
        outcome = "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
        raise
    finally:
        timer.cancel()
        elapsed = time.perf_counter() - started
        ACTIVE.labels(role).dec()
        HOLD.labels(role).observe(elapsed)
        slots.release()
        if elapsed >= SLOW_SECONDS:
            emit("released", elapsed, outcome=outcome)
