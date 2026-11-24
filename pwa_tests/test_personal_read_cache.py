"""Peak read admission: personal cache isolation and addressed fences."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from apps.pwa_api.personal_reads import PersonalReadCache


def key(kind="work", student="s1", course="c1", scope="l1"):
    return kind, student, course, scope


@pytest.mark.asyncio
async def test_personal_hits_single_flight_copies_ttl_and_disconnected_bypass():
    now = [10.0]
    available = [True]
    cache = PersonalReadCache(clock=lambda: now[0], available=lambda: available[0])
    load = AsyncMock(return_value={"grades": [1]})
    values = await asyncio.gather(*(cache.get(key(), load) for _ in range(20)))
    assert load.await_count == 1
    values[0]["grades"].append(2)
    assert (await cache.get(key(), load))["grades"] == [1]
    now[0] = 15
    await cache.get(key(), load)
    assert load.await_count == 2
    available[0] = False
    await cache.get(key(), load)
    await cache.get(key(), load)
    assert load.await_count == 4
    assert not cache.cache.entries


@pytest.mark.asyncio
async def test_work_event_changes_one_owner_and_all_affected_alias_lessons():
    cache = PersonalReadCache()
    keys = [
        key(),
        key(scope="l2"),
        key(scope="l3"),
        key(student="s2"),
        key("progress", scope=""),
        key("progress", student="s2", scope=""),
        key("latest", scope="g1"),
    ]
    for item in keys:
        await cache.get(item, AsyncMock(return_value=1))
    cache.invalidate(["banners"])
    assert set(cache.cache.entries) == set(keys)
    cache.invalidate(
        [
            "students/s1/work",
            "group-lessons/l1/work",
            "group-lessons/l2/work",
            "courses/c1/work",
            "courses/c1/statistics",
        ]
    )
    assert set(cache.cache.entries) == {keys[2], keys[3], keys[5], keys[6]}


@pytest.mark.asyncio
async def test_publication_changes_one_lesson_without_evicting_other_lessons():
    cache = PersonalReadCache()
    keys = [key(), key(scope="l2"), key(student="s2"), key(course="c2", scope="l4")]
    for item in keys:
        await cache.get(item, AsyncMock(return_value=1))
    cache.invalidate(
        ["group-lessons/l1/content/condition", "courses/c1/groups/g1/lessons"]
    )
    assert set(cache.cache.entries) == {keys[1], keys[3]}
    cache.invalidate(["courses"])
    assert not cache.cache.entries


@pytest.mark.asyncio
async def test_changed_inflight_personal_read_retries_but_other_student_keeps_fill():
    cache = PersonalReadCache()
    started, release = asyncio.Event(), asyncio.Event()
    value = [1]
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        captured = value[0]
        started.set()
        if captured == 1:
            await release.wait()
        return captured

    reader = asyncio.create_task(cache.get(key(), load))
    await started.wait()
    await cache.get(key(student="s2"), AsyncMock(return_value=7))
    cache.invalidate(["students/s1/work", "group-lessons/l1/work"])
    value[0] = 2
    release.set()
    assert await reader == 2
    assert calls == 2
    assert (
        await cache.get(key(student="s2"), AsyncMock(side_effect=AssertionError)) == 7
    )
