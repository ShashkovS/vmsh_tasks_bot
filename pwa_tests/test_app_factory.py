import pytest
from aiohttp import web

from db_methods.pwa import (
    PwaConnectionFactory,
    SchemaMismatchError,
    apply_schema_migrations,
)
from helpers.config import Config
from main import ENABLED_ADAPTERS, PWA_DATABASE, create_app


class MarkerAdapter:
    @staticmethod
    def configure(app: web.Application) -> None:
        async def marker(_request: web.Request) -> web.Response:
            return web.Response(text="ok")

        app.router.add_get("/marker", marker)


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
    finally:
        await app.shutdown()
