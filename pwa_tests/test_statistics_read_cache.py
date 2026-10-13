"""Snapshot fences, freshness and scope isolation; scoped-reads-20261013.md."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from apps.pwa_api.statistics_cache import StatisticsReadCache
from apps.pwa_api.errors import PwaApiError


@pytest.mark.asyncio
async def test_statistics_ttl_copies_scope_invalidation_and_bounds():
    now = [0.0]
    cache = StatisticsReadCache(clock=lambda: now[0])
    load = AsyncMock(return_value={"rows": [1]})
    a = ("summary", "a", ("g1",))
    b = ("summary", "b", ("g1",))
    result = await cache.get(a, load)
    result["rows"].append(2)
    assert await cache.get(a, load) == {"rows": [1]}
    await cache.get(b, load)
    cache.invalidate(["courses/a/statistics"])
    assert set(cache.cache.entries) == {b}
    now[0] = 59
    await cache.get(b, load)
    assert load.await_count == 2
    now[0] = 60
    await cache.get(b, load)
    assert load.await_count == 3
    for index in range(130):
        await cache.get(("summary", "a", (str(index),)), load)
    assert len(cache.cache.entries) == 128
    assert cache.cache.bytes <= 64 * 1024**2
    cache.invalidate()
    assert cache.cache.bytes == 0


@pytest.mark.asyncio
async def test_forced_refresh_fences_old_work_and_shares_new_fill():
    cache = StatisticsReadCache()
    started, release = asyncio.Event(), asyncio.Event()
    key = ("main", "a", ())

    async def old():
        started.set()
        await release.wait()
        return "old"

    reader = asyncio.create_task(cache.get(key, old))
    await started.wait()
    new_started, new_release = asyncio.Event(), asyncio.Event()
    count = 0

    async def new():
        nonlocal count
        count += 1
        new_started.set()
        await new_release.wait()
        return "new"

    fresh = asyncio.create_task(cache.get(key, new, force_refresh=True))
    await new_started.wait()
    concurrent = asyncio.create_task(cache.get(key, new, force_refresh=True))
    await asyncio.sleep(0)
    release.set()
    new_release.set()
    assert await reader == "old"
    assert await fresh == await concurrent == "new"
    assert count == 1
    assert await cache.get(key, new) == "new"


@pytest.mark.asyncio
async def test_expired_computation_cannot_return_a_snapshot_older_than_sixty_seconds():
    now = [0.0]
    cache = StatisticsReadCache(clock=lambda: now[0])

    async def slow():
        now[0] = 60
        return "expired"

    with pytest.raises(PwaApiError):
        await cache.get(("main", "a", ()), slow)
    assert not cache.cache.entries


@pytest.mark.asyncio
async def test_statistics_bypasses_shared_cache_when_nats_is_unavailable():
    available = [True]
    cache = StatisticsReadCache(available=lambda: available[0])
    load = AsyncMock(side_effect=[1, 2, 3])
    key = ("summary", "course", ())
    assert await cache.get(key, load) == 1
    available[0] = False
    assert await cache.get(key, load) == 2
    assert await cache.get(key, load) == 3
    assert not cache.cache.entries
