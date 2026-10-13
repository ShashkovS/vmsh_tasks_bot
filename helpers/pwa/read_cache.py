"""Bounded worker dictionaries; see docs/performance/worker-read-cache.md."""

from __future__ import annotations

import asyncio
import sys
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import fields, is_dataclass


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
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.clock = clock
        self.entries = OrderedDict()
        self._pending = {}
        self._generation = 0
        self.bytes = 0

    def invalidate(self, predicate=None) -> None:
        self._generation += 1
        for key in list(self.entries):
            if predicate is None or predicate(key):
                self.bytes -= self.entries.pop(key)[2]
        # Existing readers finish, but cannot populate or serve an old fill.
        self._pending.clear()

    async def get(self, key, load: Callable[[], Awaitable], *, ttl_seconds=None):
        while True:
            now = self.clock()
            entry = self.entries.get(key)
            if entry is not None:
                value, expiry, size = entry
                if now < expiry:
                    self.entries.move_to_end(key)
                    return value
                self.bytes -= self.entries.pop(key)[2]
            generation = self._generation
            pending = self._pending.get(key)
            if pending is not None:
                await asyncio.shield(pending)
                continue
            pending = asyncio.get_running_loop().create_future()
            self._pending[key] = pending
            try:
                value = await load()
                if generation != self._generation:
                    continue
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
                return value
            finally:
                if self._pending.get(key) is pending:
                    self._pending.pop(key)
                pending.set_result(None)
