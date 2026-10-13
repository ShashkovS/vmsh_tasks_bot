"""Bounded worker dictionaries; see docs/performance/worker-read-cache.md."""

from __future__ import annotations

import asyncio
import sys
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import fields, is_dataclass

from helpers.prometheus_metrics import READ_CACHE_BYTES, READ_CACHE_REQUESTS


def resident_size(value, seen=None) -> int:
    """Estimate the retained Python graph once on insertion, including ASTs."""
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    size = sys.getsizeof(value)
    if is_dataclass(value) and not isinstance(value, type):
        size += sum(
            resident_size(getattr(value, field.name), seen) for field in fields(value)
        )
    elif isinstance(value, Mapping):
        size += sum(
            resident_size(k, seen) + resident_size(v, seen) for k, v in value.items()
        )
    elif isinstance(value, (tuple, list, set, frozenset)):
        size += sum(resident_size(item, seen) for item in value)
    return size


class WorkerReadCache:
    """Coalesce misses without detached tasks; fence fills across invalidation."""

    def __init__(
        self,
        *,
        ttl_seconds=300,
        max_entries=4096,
        max_bytes=64 * 1024**2,
        clock: Callable[[], float] = time.monotonic,
        metric_name=None,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.clock = clock
        self.entries = OrderedDict()
        self._pending = {}
        self.bytes = 0
        if metric_name not in {None, "content", "auth", "branding", "statistics"}:
            raise ValueError("Unknown cache metric category")
        self.metric_name = metric_name

    def _measure(self, outcome=None):
        if self.metric_name is not None:
            READ_CACHE_BYTES.labels(self.metric_name).set(self.bytes)
            if outcome is not None:
                READ_CACHE_REQUESTS.labels(self.metric_name, outcome).inc()

    def invalidate(self, predicate=None) -> None:
        for key in list(self.entries):
            if predicate is None or predicate(key):
                self.bytes -= self.entries.pop(key)[2]
        # Each pending future is its own fence. Unrelated reads keep their fill;
        # scoped-reads-20261013.md also permits bounded old statistics responses.
        for key in list(self._pending):
            if predicate is None or predicate(key):
                self._pending.pop(key)
        self._measure("invalidate")

    async def get(
        self, key, load: Callable[[], Awaitable], *, ttl_seconds=None,
        force_refresh=False, retry_invalidated=True,
    ):
        if force_refresh and key in self.entries:
            self.bytes -= self.entries.pop(key)[2]
            self._measure()
        while True:
            now = self.clock()
            entry = self.entries.get(key)
            if entry is not None:
                value, expiry, size = entry
                if now < expiry:
                    self.entries.move_to_end(key)
                    self._measure("hit")
                    return value
                self.bytes -= self.entries.pop(key)[2]
            pending = self._pending.get(key)
            if pending is not None:
                self._measure("join")
                await asyncio.shield(pending)
                continue
            pending = asyncio.get_running_loop().create_future()
            self._pending[key] = pending
            self._measure("miss")
            try:
                value = await load()
                if self._pending.get(key) is not pending:
                    if retry_invalidated:
                        continue
                    return value
                # Missing records/failures never become cached denials.
                if value is not None:
                    size = resident_size(key) + resident_size(value)
                    ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
                    if size <= self.max_bytes and ttl > 0:
                        for old_key, (_, expiry, _) in list(self.entries.items()):
                            if expiry <= now:
                                self.bytes -= self.entries.pop(old_key)[2]
                        while self.entries and (
                            len(self.entries) >= self.max_entries
                            or self.bytes + size > self.max_bytes
                        ):
                            self.bytes -= self.entries.popitem(last=False)[1][2]
                        self.entries[key] = (value, now + ttl, size)
                        self.bytes += size
                self._measure("fill")
                return value
            finally:
                if self._pending.get(key) is pending:
                    self._pending.pop(key)
                pending.set_result(None)
