import asyncio
import threading

import pytest
from aiohttp import web

import main as main_module
from db_methods.pwa import (
    DatabaseLifecycleBusyError,
    PwaConnectionFactory,
    SchemaMismatchError,
    apply_schema_migrations,
    maintenance_database_lock,
)
from helpers.config import Config
from main import ENABLED_ADAPTERS, PWA_DATABASE, create_app


class MarkerAdapter:
    @staticmethod
    def configure(app: web.Application) -> None:
        async def marker(_request: web.Request) -> web.Response:
            return web.Response(text="ok")

        app.router.add_get("/marker", marker)


class FailingStartupAdapter:
    @staticmethod
    def configure(app: web.Application) -> None:
        async def fail_after_database_context(_app: web.Application) -> None:
            raise RuntimeError("synthetic later startup failure")

        app.on_startup.append(fail_after_database_context)


def test_explicit_empty_adapter_list_stays_empty():
    runtime = Config(runtime_profile="legacy", config_name="factory-test")
    app = create_app([], runtime_config=runtime)

    assert app[ENABLED_ADAPTERS] == ()
    assert not [
        route for route in app.router.routes() if route.resource.canonical == "/marker"
    ]


def test_factory_composes_only_selected_adapters():
    runtime = Config(runtime_profile="legacy", config_name="factory-test")
    app = create_app([MarkerAdapter], runtime_config=runtime)

    assert app[ENABLED_ADAPTERS] == (MarkerAdapter,)
    assert [route.method for route in app.router.routes()] == ["HEAD", "GET"]


@pytest.mark.asyncio
async def test_pwa_startup_refuses_to_create_or_migrate_database(tmp_path):
    database_path = tmp_path / "missing.sqlite3"
    runtime = Config(
        runtime_profile="pwa-agent",
        config_name="factory-test",
        db_filename=str(database_path),
    )
    app = create_app([], runtime_config=runtime)
    app.freeze()

    with pytest.raises(SchemaMismatchError, match="explicit migration command"):
        await app.startup()
    assert not database_path.exists()


@pytest.mark.asyncio
async def test_pwa_startup_exposes_verified_connection_factory(tmp_path):
    database_path = tmp_path / "current.sqlite3"
    apply_schema_migrations(database_path)
    runtime = Config(
        runtime_profile="pwa-agent",
        config_name="factory-test",
        db_filename=str(database_path),
    )
    app = create_app([], runtime_config=runtime)
    app.freeze()

    await app.startup()
    try:
        assert isinstance(app[PWA_DATABASE].factory, PwaConnectionFactory)
        assert app[PWA_DATABASE].factory.database_path == database_path
        assert app[PWA_DATABASE].lifecycle_lock is not None
        assert app[PWA_DATABASE].lifecycle_lock.acquired
        with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
            maintenance_database_lock(database_path).acquire()
    finally:
        await app.shutdown()

    # aiohttp drains active handlers after on_shutdown and only then runs
    # cleanup contexts; the shared pathname lock must cover that whole window.
    assert app[PWA_DATABASE].factory is not None
    assert app[PWA_DATABASE].lifecycle_lock is not None
    with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
        maintenance_database_lock(database_path).acquire()

    await app.cleanup()
    assert app[PWA_DATABASE].factory is None
    assert app[PWA_DATABASE].lifecycle_lock is None
    with maintenance_database_lock(database_path) as maintenance:
        assert maintenance.acquired


@pytest.mark.asyncio
async def test_pwa_startup_releases_lifecycle_lock_when_schema_check_fails(tmp_path):
    database_path = tmp_path / "missing.sqlite3"
    runtime = Config(
        runtime_profile="pwa-agent",
        config_name="factory-test",
        db_filename=str(database_path),
    )
    app = create_app([], runtime_config=runtime)
    app.freeze()

    with pytest.raises(SchemaMismatchError):
        await app.startup()

    with maintenance_database_lock(database_path) as maintenance:
        assert maintenance.acquired


@pytest.mark.asyncio
async def test_runner_cleanup_releases_lock_after_later_startup_failure(tmp_path):
    database_path = tmp_path / "current.sqlite3"
    apply_schema_migrations(database_path)
    runtime = Config(
        runtime_profile="pwa-agent",
        config_name="factory-test",
        db_filename=str(database_path),
    )
    app = create_app([FailingStartupAdapter], runtime_config=runtime)
    runner = web.AppRunner(app)

    with pytest.raises(RuntimeError, match="later startup failure"):
        await runner.setup()

    with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
        maintenance_database_lock(database_path).acquire()
    await runner.cleanup()
    with maintenance_database_lock(database_path) as maintenance:
        assert maintenance.acquired


@pytest.mark.asyncio
async def test_cancelled_schema_preflight_holds_lock_until_worker_finishes(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "current.sqlite3"
    database_path.touch()
    started = threading.Event()
    finish = threading.Event()

    def blocking_factory(_database_path):
        started.set()
        assert finish.wait(timeout=5)
        return object()

    monkeypatch.setattr(main_module, "PwaConnectionFactory", blocking_factory)
    runtime = Config(
        runtime_profile="pwa-agent",
        config_name="factory-test",
        db_filename=str(database_path),
    )
    app = create_app([], runtime_config=runtime)
    app.freeze()
    startup = asyncio.create_task(app.startup())
    assert await asyncio.to_thread(started.wait, 2)

    startup.cancel()
    with pytest.raises(asyncio.CancelledError):
        await startup
    with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
        maintenance_database_lock(database_path).acquire()

    finish.set()
    for _attempt in range(100):
        await asyncio.sleep(0.01)
        try:
            maintenance = maintenance_database_lock(database_path).acquire()
        except DatabaseLifecycleBusyError:
            continue
        maintenance.release()
        break
    else:
        pytest.fail("preflight worker completed but lifecycle lock was not released")
