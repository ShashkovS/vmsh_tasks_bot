"""Bounded photo timings; docs/performance/2026-09-28-instrumentation.md."""

import asyncio
import time
from contextlib import contextmanager

from prometheus_client import Histogram

from helpers.pwa.request_trace import trace_stage

STAGES = frozenset({
    "upload.read", "image.normalize", "image.webp", "image.convert",
    "storage.put", "storage.get", "storage.head", "media.sign", "upload.sign", "upload.finalize",
})
MEDIA_STAGE_DURATION = Histogram(
    "vmsh_media_stage_duration_seconds",
    "Photo stage wall time, including failures and cancellations.",
    ("stage", "outcome"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)


@contextmanager
def media_stage(stage):
    if stage not in STAGES:
        raise ValueError("Unknown media diagnostic stage")
    started = time.perf_counter()
    outcome = "ok"
    try:
        with trace_stage(stage):
            yield
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except Exception:
        outcome = "error"
        raise
    finally:
        MEDIA_STAGE_DURATION.labels(stage, outcome).observe(time.perf_counter() - started)
