"""RAM hit, invalidation, cancellation and session-boundary regression proofs."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web

from apps.pwa_api.middleware import PWA_AUTH_STATE, PwaAuthState
from apps.pwa_api.read_cache import CachedContentRepository, InvalidatingBroker
from apps import pwa_app
from helpers.nats_brocker import InProcessBroker, NatsBroker
from helpers.pwa.read_cache import WorkerReadCache
from models.pwa.auth import AuthAudience
from pwa_tests.test_auth_service import NOW, _access_cookie, _current, _service


@pytest.mark.asyncio
async def test_twenty_concurrent_misses_share_one_read_and_ttl_is_fixed():
    now = [10.0]
    cache = WorkerReadCache(ttl_seconds=5, clock=lambda: now[0])
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return calls

    tasks = [asyncio.create_task(cache.get("lesson", load)) for _ in range(20)]
    await started.wait()
    release.set()
    assert await asyncio.gather(*tasks) == [1] * 20
    now[0] = 14
    assert await cache.get("lesson", load) == 1
    now[0] = 15
    assert await cache.get("lesson", load) == 2


@pytest.mark.asyncio
async def test_old_inflight_fill_is_never_served_after_publication():
    cache = WorkerReadCache()
    started, release = asyncio.Event(), asyncio.Event()
    revision = ["old"]

    async def load():
        value = revision[0]
        started.set()
        if value == "old":
            await release.wait()
        return value

    old_reader = asyncio.create_task(cache.get("lesson", load))
    await started.wait()
    cache.invalidate()
    revision[0] = "new"
    assert await cache.get("lesson", load) == "new"
    release.set()
    assert await old_reader == "new"
    assert await cache.get("lesson", load) == "new"


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_read():
    cache = WorkerReadCache()
    started, release = asyncio.Event(), asyncio.Event()

    async def load():
        started.set()
        await release.wait()
        return "ready"

    leader = asyncio.create_task(cache.get("lesson", load))
    await started.wait()
    waiter = asyncio.create_task(cache.get("lesson", load))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    assert await leader == "ready"
    assert not cache._pending


@pytest.mark.asyncio
async def test_cancelled_leader_wakes_waiter_and_failures_are_not_cached():
    cache = WorkerReadCache()
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        started.set()
        if calls == 1:
            await release.wait()
        return "ready"

    leader = asyncio.create_task(cache.get("lesson", load))
    await started.wait()
    waiter = asyncio.create_task(cache.get("lesson", load))
    await asyncio.sleep(0)
    leader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await leader
    assert await waiter == "ready"
    failing = AsyncMock(side_effect=[ValueError("failed"), "recovered"])
    with pytest.raises(ValueError):
        await cache.get("other", failing)
    assert await cache.get("other", failing) == "recovered"


@pytest.mark.asyncio
async def test_cache_has_entry_and_resident_memory_bounds():
    cache = WorkerReadCache(max_entries=2, max_bytes=4096)
    for key in range(3):
        await cache.get(key, AsyncMock(return_value="value"))
    assert list(cache.entries) == [1, 2]
    large = AsyncMock(return_value="x" * 8192)
    await cache.get("large", large)
    await cache.get("large", large)
    assert large.await_count == 2
    assert cache.bytes <= 4096
    cache.invalidate()
    assert cache.bytes == 0


@pytest.mark.asyncio
async def test_content_copy_resource_keys_and_disconnected_fallback():
    available = [True]
    repo = SimpleNamespace(get_published_content=AsyncMock(return_value={"blocks": []}))
    cached = CachedContentRepository(repo, available=lambda: available[0])
    scope = dict(group_lesson_public_id="lesson-one", kind="condition")
    first = await cached.get_published_content(**scope)
    first["blocks"].append("private decoration")
    cached.invalidate(["banners", "live-results"])
    assert await cached.get_published_content(**scope) == {"blocks": []}
    assert repo.get_published_content.await_count == 1
    await cached.get_published_content(**scope, released_only=True)
    assert repo.get_published_content.await_count == 2
    cached.invalidate(["group-lessons/lesson-one/problem-release"])
    await cached.get_published_content(**scope)
    assert repo.get_published_content.await_count == 3
    available[0] = False
    await cached.get_published_content(**scope)
    await cached.get_published_content(**scope)
    assert repo.get_published_content.await_count == 5


@pytest.mark.asyncio
async def test_worker_broadcast_and_failed_publish_clear_local_cache():
    broker = InProcessBroker("read_cache_test")
    await broker.setup()
    apps = []
    for _ in range(2):
        app = web.Application()
        app[pwa_app.PWA_CONTENT_REPOSITORY] = CachedContentRepository(SimpleNamespace())
        await app[pwa_app.PWA_CONTENT_REPOSITORY].cache.get(
            ("content", "lesson-one"), AsyncMock(return_value="old")
        )

        async def receive(payload, worker=app):
            pwa_app.invalidate_worker_reads(worker, "pwa_invalidate", payload)

        await broker.subscribe("pwa_invalidate", receive)
        apps.append(app)
    sender = InvalidatingBroker(
        broker,
        lambda topic, payload: pwa_app.invalidate_worker_reads(apps[0], topic, payload),
    )
    payload = {"resources": ["group-lessons/lesson-one/content/condition"]}
    await sender.publish("pwa_invalidate", payload)
    assert all(not app[pwa_app.PWA_CONTENT_REPOSITORY].cache.entries for app in apps)
    await apps[0][pwa_app.PWA_CONTENT_REPOSITORY].cache.get(
        ("content", "lesson-one"), AsyncMock(return_value="old")
    )
    failed = InvalidatingBroker(
        SimpleNamespace(publish=AsyncMock(side_effect=OSError("offline"))),
        sender.invalidate,
    )
    with pytest.raises(OSError):
        await failed.publish("pwa_invalidate", payload)
    assert not apps[0][pwa_app.PWA_CONTENT_REPOSITORY].cache.entries
    await broker.disconnect()


@pytest.mark.asyncio
async def test_reconnect_clears_worker_caches():
    cache = WorkerReadCache()
    await cache.get("lesson", AsyncMock(return_value="old"))
    broker = NatsBroker("read_cache_reconnect_test")

    async def reconnect():
        cache.invalidate()

    broker.set_reconnect_callback(reconnect)
    await broker._on_reconnect()
    assert not cache.entries


def auth_fixture():
    repository = SimpleNamespace(
        get_current_session=AsyncMock(return_value=_current()),
        list_course_enrollments=AsyncMock(return_value=()),
        revoke_session=AsyncMock(return_value=True),
    )
    service = _service(repository)
    service.enable_read_cache()
    return service, repository


async def authenticate(service, cookie):
    return await service.authenticate_access(
        audience=AuthAudience.STUDENT,
        access_cookie_value=cookie,
        request_id="cache-proof",
        client_address="127.0.0.1",
    )


@pytest.mark.asyncio
async def test_auth_hits_verify_signature_and_expire_without_sliding_ttl():
    service, repository = auth_fixture()
    now = [NOW]
    service._clock = lambda: now[0]
    cookie = _access_cookie(service)
    first = await authenticate(service, cookie)
    assert first is not None
    assert await authenticate(service, cookie) is first
    assert repository.get_current_session.await_count == 1
    assert repository.list_course_enrollments.await_count == 1
    assert await authenticate(service, cookie + "tampered") is None
    assert repository.get_current_session.await_count == 1
    now[0] = first.access_expires_at + timedelta(seconds=1)
    assert await authenticate(service, cookie) is None


@pytest.mark.asyncio
async def test_auth_session_expiry_missing_session_and_logout_control():
    service, repository = auth_fixture()
    now = [NOW]
    service._clock = lambda: now[0]
    current = _current()
    repository.get_current_session.return_value = replace(
        current, session=replace(current.session, expires_at=NOW + timedelta(seconds=5))
    )
    cookie = _access_cookie(service)
    first = await authenticate(service, cookie)
    assert first is not None
    now[0] += timedelta(seconds=6)
    assert await authenticate(service, cookie) is None
    now[0] = NOW
    repository.get_current_session.return_value = current
    approved = await authenticate(service, cookie)
    assert approved is not None
    # The owner explicitly accepts stale authority inside the bounded TTL.
    repository.get_current_session.return_value = None
    assert await authenticate(service, cookie) is approved
    app = web.Application()
    app[PWA_AUTH_STATE] = PwaAuthState(
        runtime_config=service.runtime_config, service=service
    )
    pwa_app.invalidate_worker_reads(
        app,
        "pwa_session_control",
        {
            "version": 1,
            "type": "auth.close",
            "audience": "student",
            "scope": "session",
            "targetId": current.session.public_id,
        },
    )
    repository.get_current_session.return_value = None
    assert await authenticate(service, cookie) is None
    assert await authenticate(service, cookie) is None
    assert repository.get_current_session.await_count == 4
