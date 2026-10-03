"""Profile, persistence and admin HTTP boundaries from vmshpwa/docs/branding.md."""

import json
from types import SimpleNamespace

import pytest
from aiohttp import web
from apps.pwa_api.branding_routes import branding_routes
from apps.pwa_api.middleware import PWA_AUTHENTICATED_SESSION
from apps.pwa_app import pwa_error_middleware
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.branding import get_branding
from helpers.pwa.app_keys import PWA_DATABASE, PwaDatabaseState
from helpers.pwa.branding import brand_manifest
from helpers.pwa.i18n import locale_from_cookies
from models.pwa.auth import AuthAudience


@pytest.fixture
async def brand_client(tmp_path, aiohttp_client):
    path = tmp_path / "brand.sqlite3"
    apply_schema_migrations(path)
    factory = PwaConnectionFactory(path)

    @web.middleware
    async def synthetic_auth(request, handler):
        # Test wiring only; production uses the existing authenticated session middleware.
        principal = SimpleNamespace(
            audience=AuthAudience.STAFF,
            is_global_admin=request.headers.get("X-Test-Role") == "admin",
            linked_user_id=None,
            account_public_id=None,
        )
        request[PWA_AUTHENTICATED_SESSION] = SimpleNamespace(principal=principal)
        return await handler(request)

    app = web.Application(middlewares=[pwa_error_middleware, synthetic_auth])
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    app.add_routes(branding_routes)

    async def lifecycle(app):
        factory.start_async_workers()
        yield
        await factory.aclose()

    app.cleanup_ctx.append(lifecycle)
    return await aiohttp_client(app)


async def test_selection_permissions_conflict_and_persistence(brand_client):
    client = brand_client
    url = "/staff/api/v1/branding"
    assert await (await client.get(url)).json() == {"profileId": "vmsh", "version": 1}
    body = {"profileId": "tlf-prep-clubs", "version": 1}
    assert (await client.put(url, json=body)).status == 403
    assert (
        await client.put(url, json=body, headers={"X-Test-Role": "admin"})
    ).status == 200
    assert (
        await client.put(url, json=body, headers={"X-Test-Role": "admin"})
    ).status == 409
    for audience in ("student", "family", "staff"):
        response = await client.get(f"/{audience}/api/v1/branding")
        assert response.headers["Cache-Control"] == "no-store"
        assert await response.json() == {"profileId": "tlf-prep-clubs", "version": 2}
    factory = client.app[PWA_DATABASE].factory
    row = await factory.run_read_async(get_branding)
    assert row["default_locale"] == "en"
    events = await factory.run_read_async(
        lambda c: c.execute(
            "SELECT after_json FROM audit_events WHERE action='branding.updated'"
        ).fetchall()
    )
    assert len(events) == 1
    assert json.loads(events[0]["after_json"])["profile_id"] == "tlf-prep-clubs"
    response = await client.get("/student/api/v1/branding/manifest.webmanifest")
    manifest = await response.json()
    assert manifest["name"] == "TLF Prep Clubs — Student"
    assert manifest["id"] == manifest["scope"] == "/student/"
    assert all(
        icon["src"].startswith("/student/brands/tlf-prep-clubs/v1/")
        for icon in manifest["icons"]
    )


@pytest.mark.parametrize(
    "body",
    [
        {"profileId": "bad", "version": 1},
        {"profileId": "vmsh", "version": True},
        {"profileId": "vmsh", "version": 0},
        {"profileId": "vmsh", "version": 1, "css": "x"},
    ],
)
async def test_invalid_selection_rejected(brand_client, body):
    response = await brand_client.put(
        "/staff/api/v1/branding", json=body, headers={"X-Test-Role": "admin"}
    )
    assert response.status == 422


def test_locale_and_manifest_defaults():
    assert locale_from_cookies({}, "en") == "en"
    assert locale_from_cookies({"vmsh-locale": "ru"}, "en") == "ru"
    assert brand_manifest("vmsh", "family")["lang"] == "ru"
    assert brand_manifest("tlf-prep-clubs", "family")["lang"] == "en"


def test_migration_preserves_existing_choices_and_rolls_back():
    import sqlite3
    from pathlib import Path

    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE auth_accounts (locale TEXT NOT NULL DEFAULT 'ru'); INSERT INTO auth_accounts VALUES ('en');"
    )
    connection.executescript(Path("migrations/0101.pwa_branding.sql").read_text())
    assert connection.execute(
        "SELECT locale, locale_explicit FROM auth_accounts"
    ).fetchone() == ("en", 1)
    connection.execute("INSERT INTO auth_accounts DEFAULT VALUES")
    assert connection.execute(
        "SELECT locale_explicit FROM auth_accounts ORDER BY rowid DESC"
    ).fetchone() == (0,)
    connection.executescript(
        Path("migrations/0101.pwa_branding.rollback.sql").read_text()
    )
    assert connection.execute(
        "SELECT locale FROM auth_accounts ORDER BY rowid LIMIT 1"
    ).fetchone() == ("en",)
    connection.close()
