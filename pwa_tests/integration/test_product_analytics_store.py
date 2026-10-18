from datetime import UTC, datetime
import asyncio
import sqlite3

import pytest

from db_methods.pwa.product_analytics import (
    ProductAnalyticsConnectionFactory,
    prune_expired_events,
    school_year_cutoff,
)


def test_analytics_store_uses_wal_and_prunes_at_moscow_school_year_boundary(tmp_path):
    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    assert factory.run_read(
        lambda connection: connection.execute("PRAGMA journal_mode").fetchone()
    )["journal_mode"].casefold() == "wal"
    factory.run_write(
        lambda connection: connection.executemany(
            "INSERT INTO product_events (occurred_at, audience, account_public_id, session_public_id, event_type, route_id, entity_type, entity_public_id, viewport_width, viewport_height, device_pixel_ratio, pointer_type, display_mode) VALUES (?, 'student', 'u-2', 'a' * 32, 'page.view', '/', NULL, NULL, 800, 600, 2, 'fine', 'browser')",
            [("2026-08-09T20:59:59+00:00",), ("2026-08-10T21:00:00+00:00",)],
        )
    )
    removed = factory.run_write(
        lambda connection: prune_expired_events(
            connection, now=datetime(2026, 8, 20, tzinfo=UTC)
        )
    )
    assert removed == 1
    assert factory.run_read(
        lambda connection: connection.execute("SELECT COUNT(*) AS count FROM product_events").fetchone()
    )["count"] == 1


def test_school_year_cutoff_uses_tenth_of_august_in_moscow():
    assert school_year_cutoff(datetime(2026, 8, 9, 20, tzinfo=UTC)).isoformat() == "2025-08-09T21:00:00+00:00"
    assert school_year_cutoff(datetime(2026, 8, 10, 21, tzinfo=UTC)).isoformat() == "2026-08-09T21:00:00+00:00"


def event_row():
    return ("2026-10-18T12:00:00+00:00", "student", "u-1", "test-session",
            "page.view", "/", None, None, 800, 600, 1, "fine", "browser")


@pytest.mark.asyncio
async def test_runtime_uses_one_writer_batches_and_closes_before_unlock(tmp_path):
    from aiohttp import web
    from helpers.config import Config
    from helpers.pwa.app_keys import (
        PWA_ANALYTICS_DATABASE, RUNTIME_CONFIG, PwaAnalyticsDatabaseState,
    )
    from main import pwa_analytics_lifecycle
    from db_methods.pwa import maintenance_database_lock, DatabaseLifecycleBusyError

    path = tmp_path / "analytics.sqlite3"
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(runtime_profile="pwa-e2e", db_filename=str(tmp_path / "core"),
                                 pwa_analytics_db_filename=str(path))
    state = app[PWA_ANALYTICS_DATABASE] = PwaAnalyticsDatabaseState()
    lifecycle = pwa_analytics_lifecycle(app)
    await anext(lifecycle)
    factory = state.factory
    identities = [await factory.run_write_async(id) for _ in range(3)]
    assert len(set(identities)) == 1
    statements = []
    await factory.run_write_async(lambda c: c.set_trace_callback(statements.append))
    for _ in range(10):
        assert state.ingestor.submit([event_row()] * 10)
    with pytest.raises(DatabaseLifecycleBusyError):
        maintenance_database_lock(path).acquire()
    await lifecycle.aclose()
    assert state.factory is None and state.ingestor is None
    assert sum(s == "BEGIN IMMEDIATE" for s in statements) == 1
    with maintenance_database_lock(path), sqlite3.connect(path) as c:
        assert c.execute("SELECT count(*) FROM product_events").fetchone()[0] == 100
    assert factory._closed and all(worker._shutdown for worker in factory._executors.values())


@pytest.mark.asyncio
async def test_queue_bounds_failure_recovery_and_shutdown(tmp_path):
    from helpers.pwa.product_analytics import ProductAnalyticsIngestor

    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    factory.start_async_workers()
    ingestor = ProductAnalyticsIngestor(factory, capacity=20, delay=0)
    try:
        assert ingestor.submit([event_row()] * 20)
        assert not ingestor.submit([event_row()])
        await asyncio.wait_for(ingestor.queue.join(), 2)
        assert ingestor.submit([(None,) * 13])  # a failed batch must not kill the worker
        await asyncio.wait_for(ingestor.queue.join(), 2)
        assert ingestor.submit([event_row()])
        await ingestor.aclose()
        assert not ingestor.submit([event_row()])
        assert factory.run_read(lambda c: c.execute("SELECT count(*) n FROM product_events").fetchone())["n"] == 21
    finally:
        await ingestor.aclose()
        await factory.aclose()


@pytest.mark.asyncio
async def test_shutdown_drains_dispatched_sqlite_even_when_cancelled(tmp_path):
    import threading
    from helpers.pwa.product_analytics import ProductAnalyticsIngestor

    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    factory.start_async_workers()
    entered, release = threading.Event(), threading.Event()
    original = factory.run_write_async

    async def blocked(operation):
        def write(c):
            entered.set()
            release.wait(5)
            return operation(c)
        return await original(write)

    factory.run_write_async = blocked
    ingestor = ProductAnalyticsIngestor(factory, capacity=20, delay=0)
    ingestor.submit([event_row()])
    await asyncio.to_thread(entered.wait, 2)
    closing = asyncio.create_task(ingestor.aclose(timeout=0.01))
    try:
        await asyncio.sleep(0.03)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await closing
        await ingestor.aclose()
        await factory.aclose()
    assert ingestor.worker.done()
    assert ingestor.queue.empty()


@pytest.mark.asyncio
async def test_cancelled_analytics_preflight_retains_lock_until_constructor_ends(tmp_path, monkeypatch):
    import threading
    import main
    from aiohttp import web
    from helpers.config import Config
    from helpers.pwa.app_keys import PWA_ANALYTICS_DATABASE, RUNTIME_CONFIG, PwaAnalyticsDatabaseState
    from db_methods.pwa import maintenance_database_lock, DatabaseLifecycleBusyError

    path = tmp_path / "analytics.sqlite3"
    started, release = threading.Event(), threading.Event()
    def constructor(_path):
        started.set()
        assert release.wait(5)
        return object()
    monkeypatch.setattr(main, "ProductAnalyticsConnectionFactory", constructor)
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(runtime_profile="pwa-e2e", db_filename=str(tmp_path / "core"),
                                 pwa_analytics_db_filename=str(path))
    app[PWA_ANALYTICS_DATABASE] = PwaAnalyticsDatabaseState()
    lifecycle = main.pwa_analytics_lifecycle(app)
    startup = asyncio.create_task(anext(lifecycle))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        startup.cancel()
        with pytest.raises(asyncio.CancelledError):
            await startup
        with pytest.raises(DatabaseLifecycleBusyError):
            maintenance_database_lock(path).acquire()
    finally:
        release.set()
    for _ in range(100):
        await asyncio.sleep(0.01)
        try:
            maintenance = maintenance_database_lock(path).acquire()
        except DatabaseLifecycleBusyError:
            continue
        maintenance.release()
        break
    else:
        pytest.fail("analytics preflight leaked its lifecycle lock")


@pytest.mark.asyncio
async def test_cleanup_tolerates_background_worker_cancelled_by_legacy_shutdown(tmp_path):
    from helpers.pwa.product_analytics import ProductAnalyticsIngestor
    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    factory.start_async_workers()
    ingestor = ProductAnalyticsIngestor(factory)
    ingestor.submit([event_row()])
    ingestor.worker.cancel()
    await ingestor.aclose()
    await factory.aclose()
    assert ingestor.queue.empty() and ingestor.worker.cancelled()


@pytest.mark.asyncio
async def test_normal_shutdown_drains_telemetry_before_legacy_task_cancellation(tmp_path, monkeypatch):
    import main
    from aiohttp import web
    from helpers.pwa.app_keys import PWA_ANALYTICS_DATABASE, PwaAnalyticsDatabaseState
    from helpers.pwa.product_analytics import ProductAnalyticsIngestor
    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    factory.start_async_workers()
    ingestor = ProductAnalyticsIngestor(factory)
    app = web.Application()
    app[PWA_ANALYTICS_DATABASE] = PwaAnalyticsDatabaseState(factory=factory, ingestor=ingestor)
    async def legacy_shutdown(_logger, **_kwargs):
        assert ingestor.closed and ingestor.worker.done()
        assert ingestor.queue.empty()
    monkeypatch.setattr(main, "wait_for_valuable_tasks", legacy_shutdown)
    try:
        assert ingestor.submit([event_row()] * 20)
        await main.on_shutdown(app)
        assert factory.run_read(lambda c: c.execute("SELECT count(*) n FROM product_events").fetchone())["n"] == 20
    finally:
        await ingestor.aclose()
        await factory.aclose()
