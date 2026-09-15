"""Public release smoke contract without contacting a real deployment."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from aiohttp import web

from vmshpwa.scripts import production_http_smoke


ROOT = Path(__file__).resolve().parents[1]
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; script-src 'self'"
    ),
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=()",
}


def _runtime(audience: str, request_id: str, *, prototype: bool = False):
    return {
        "contractVersion": 1,
        "audience": audience,
        "appBase": f"/{audience}",
        "apiBase": f"/{audience}/api/v1",
        "websocketPath": f"/{audience}/ws",
        "instance": "production-2026",
        "serverTime": datetime.now(UTC).isoformat(),
        "requestId": request_id,
        "features": {
            "telegram": False,
            "google": False,
            "nats": True,
            "prototype": prototype,
        },
    }


def _release_app(
    *,
    prototype: bool = False,
    redirect_health: bool = False,
    html_cache_control: str = "no-cache",
) -> web.Application:
    app = web.Application()

    @web.middleware
    async def public_headers(request: web.Request, handler):
        response = await handler(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.middlewares.append(public_headers)

    async def health(request: web.Request) -> web.Response:
        if redirect_health and request.match_info["audience"] == "student":
            raise web.HTTPFound("/student/")
        audience = request.match_info["audience"]
        request_id = request.headers["X-Request-ID"]
        return web.json_response(
            {"ok": True, "audience": audience, "requestId": request_id},
            headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
        )

    async def runtime(request: web.Request) -> web.Response:
        audience = request.match_info["audience"]
        request_id = request.headers["X-Request-ID"]
        return web.json_response(
            _runtime(audience, request_id, prototype=prototype),
            headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
        )

    async def missing_api(request: web.Request) -> web.Response:
        request_id = request.headers["X-Request-ID"]
        return web.json_response(
            {"error": {"code": "not_found", "requestId": request_id}},
            status=404,
            headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
        )

    async def manifest(request: web.Request) -> web.Response:
        audience = request.match_info["audience"]
        root = f"/{audience}/"
        return web.json_response(
            {
                "id": root,
                "start_url": root,
                "scope": root,
                "display": "standalone",
                "icons": [
                    {
                        "src": f"/{audience}/icon.svg",
                        "sizes": "any",
                        "type": "image/svg+xml",
                    }
                ],
            },
            content_type="application/manifest+json",
        )

    async def icon(_request: web.Request) -> web.Response:
        return web.Response(body=b"<svg/>", content_type="image/svg+xml")

    async def worker(request: web.Request) -> web.Response:
        audience = request.match_info["audience"]
        return web.Response(
            body=b"self.addEventListener('install', () => {});",
            content_type="text/javascript",
            headers={
                "Cache-Control": "no-store",
                "Service-Worker-Allowed": f"/{audience}/",
            },
        )

    async def static(request: web.Request) -> web.Response:
        audience = request.match_info["audience"]
        manifest_link = (
            f'<link rel="manifest" href="/{audience}/manifest.webmanifest">'
            if audience in production_http_smoke.PWA_AUDIENCES
            else ""
        )
        return web.Response(
            text=f'<!doctype html>{manifest_link}<div id="root"></div>',
            content_type="text/html",
            headers={"Cache-Control": html_cache_control},
        )

    async def landing(_request: web.Request) -> web.Response:
        return web.Response(
            text=(
                '<!doctype html><title>ВМШ 179</title>'
                '<a href="/student/">Student</a>'
                '<a href="/family/">Family</a>'
            ),
            content_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    app.router.add_get("/{audience:student|family|staff}/api/v1/health", health)
    app.router.add_get("/{audience:student|family|staff}/api/v1/runtime", runtime)
    app.router.add_get("/{audience:student|family|staff}/api/v1/{tail:.*}", missing_api)
    app.router.add_get("/{audience:student|family}/manifest.webmanifest", manifest)
    app.router.add_get("/{audience:student|family}/icon.svg", icon)
    app.router.add_get("/{audience:student|family}/sw.js", worker)
    app.router.add_get("/{audience:student|family|staff}/{tail:.*}", static)
    app.router.add_get("/", landing)
    return app


@pytest.mark.parametrize(
    "value",
    [
        "http://pwa.example.org",
        "https://PWA.example.org",
        "https://pwa.example.org:443",
        "https://user@pwa.example.org",
        "https://pwa.example.org/student",
        "https://127.0.0.1",
        "pwa.example.org",
        "",
    ],
)
def test_public_origin_rejects_ambiguous_or_non_production_targets(value):
    with pytest.raises(ValueError, match="exact https"):
        production_http_smoke.validate_public_origin(value)


def test_public_origin_accepts_only_exact_https_fqdn():
    assert (
        production_http_smoke.validate_public_origin("https://pwa.example.org/")
        == "https://pwa.example.org"
    )


@pytest.mark.asyncio
async def test_smoke_checks_all_audiences_static_manifests_icons_and_workers(
    aiohttp_server,
):
    server = await aiohttp_server(_release_app())

    passed = await production_http_smoke.check_deployed_release(
        str(server.make_url("")).rstrip("/"),
        "production-2026",
    )

    assert len(passed) == 19
    assert "public landing" in passed
    assert "student service worker" in passed
    assert "family manifest" in passed
    assert "staff SPA fallback" in passed


@pytest.mark.asyncio
async def test_smoke_fails_closed_when_prototype_reaches_public_runtime(aiohttp_server):
    server = await aiohttp_server(_release_app(prototype=True))

    with pytest.raises(production_http_smoke.ProductionSmokeFailure, match="prototype"):
        await production_http_smoke.check_deployed_release(
            str(server.make_url("")).rstrip("/"),
            "production-2026",
        )


@pytest.mark.asyncio
async def test_smoke_does_not_follow_a_misrouted_health_redirect(aiohttp_server):
    server = await aiohttp_server(_release_app(redirect_health=True))

    with pytest.raises(
        production_http_smoke.ProductionSmokeFailure,
        match="expected HTTP 200, got 302",
    ):
        await production_http_smoke.check_deployed_release(
            str(server.make_url("")).rstrip("/"),
            "production-2026",
        )


@pytest.mark.asyncio
async def test_smoke_rejects_a_stale_cacheable_application_shell(aiohttp_server):
    server = await aiohttp_server(_release_app(html_cache_control="max-age=3600"))

    with pytest.raises(
        production_http_smoke.ProductionSmokeFailure,
        match="SPA fallback: Cache-Control lacks no-cache",
    ):
        await production_http_smoke.check_deployed_release(
            str(server.make_url("")).rstrip("/"),
            "production-2026",
        )


@pytest.mark.asyncio
async def test_response_limit_stops_an_unexpectedly_large_public_body(aiohttp_server):
    app = web.Application()

    async def oversized(_request: web.Request) -> web.Response:
        return web.Response(body=b"x" * (production_http_smoke.MAX_RESPONSE_BYTES + 1))

    app.router.add_get("/large", oversized)
    server = await aiohttp_server(app)
    origin = str(server.make_url("")).rstrip("/")
    async with production_http_smoke.aiohttp.ClientSession() as session:
        with pytest.raises(
            production_http_smoke.ProductionSmokeFailure,
            match="response exceeds",
        ):
            await production_http_smoke._read_response(
                session,
                origin,
                "/large",
                label="large response",
            )


def test_cli_refuses_http_before_opening_a_session(monkeypatch, capsys):
    called = False

    async def unexpected_call(_origin: str, _expected_instance: str):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(
        production_http_smoke,
        "check_deployed_release",
        unexpected_call,
    )

    result = production_http_smoke.main(
        ["--origin", "http://pwa.example.org", "--expected-instance", "production"]
    )

    assert result == 1
    assert called is False
    assert capsys.readouterr().out.startswith("FAILED:")


def test_make_target_requires_explicit_public_identity():
    source = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: pwa-nginx-check pwa-production-http-smoke" in source
    assert 'test -n "$(PWA_PRODUCTION_ORIGIN)"' in source
    assert 'test -n "$(PWA_PRODUCTION_INSTANCE)"' in source
    assert "python -m vmshpwa.scripts.production_http_smoke" in source
