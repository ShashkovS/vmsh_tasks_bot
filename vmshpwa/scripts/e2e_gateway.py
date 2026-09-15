"""Serve all production PWA bundles behind one test-only origin.

The real deployment routes a public landing page plus three applications and their API/WebSocket paths on
one host.  Vite's preview server cannot model that boundary by itself, so this
small aiohttp gateway is deliberately part of the Playwright harness only.  It
fails closed unless it is started with the isolated ``pwa-e2e`` profile.

See ``vmshpwa/dev/development-plan/04-phase-0-baseline.md`` and
``vmshpwa/e2e/runtime-isolation.spec.ts``.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import ipaddress
import json
import os
import re
import uuid
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, DummyCookieJar, WSMsgType, web
from multidict import CIMultiDict, CIMultiDictProxy

AUDIENCES = ("student", "family", "staff")
PWA_AUDIENCES = ("student", "family")
BUNDLES = ("landing", *AUDIENCES)
HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
STATIC_SUFFIXES = frozenset(
    {
        ".avif",
        ".css",
        ".csv",
        ".eot",
        ".gif",
        ".html",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".map",
        ".mjs",
        ".otf",
        ".pdf",
        ".png",
        ".svg",
        ".ttf",
        ".txt",
        ".wasm",
        ".webmanifest",
        ".webp",
        ".woff",
        ".woff2",
        ".xml",
        ".zip",
    }
)
GENERATION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

DIST_ROOTS = web.AppKey("e2e_gateway_dist_roots", dict)
API_ORIGIN = web.AppKey("e2e_gateway_api_origin", str)
HTTP_CLIENT = web.AppKey("e2e_gateway_http_client", ClientSession)
CONTROL_TOKEN = web.AppKey("e2e_gateway_control_token", str)
GATEWAY_CLIENT_MAX_SIZE = 64 * 1024 * 1024


class UnsafeStaticPath(ValueError):
    """Raised when an input could escape its audience's immutable dist root."""


def _require_loopback(value: str, *, label: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a literal loopback address") from exc
    if not address.is_loopback:
        raise ValueError(f"{label} must be a loopback address")
    return value


def _validate_api_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("API origin must be a plain loopback HTTP origin")
    _require_loopback(parsed.hostname, label="API origin host")
    if parsed.port is None:
        raise ValueError("API origin must include an explicit port")
    return value.rstrip("/")


def _load_dist_roots(workspace: Path) -> dict[str, Path]:
    workspace = workspace.resolve(strict=True)
    roots: dict[str, Path] = {}
    for audience in BUNDLES:
        audience_root = workspace / "apps" / audience
        dist_root = audience_root / "dist"
        if audience_root.is_symlink() or dist_root.is_symlink():
            raise UnsafeStaticPath(f"{audience} dist root must not be a symlink")
        expected_parent = audience_root.resolve(strict=True)
        root = dist_root.resolve(strict=True)
        if not root.is_relative_to(workspace):
            raise UnsafeStaticPath(f"{audience} dist root escapes the workspace")
        if root.parent != expected_parent:
            raise UnsafeStaticPath(f"{audience} dist root changed ownership")
        index = root / "index.html"
        if not index.is_file():
            raise FileNotFoundError(f"Missing production bundle: {index}")
        roots[audience] = root
    return roots


def resolve_static_file(root: Path, relative_path: str) -> Path | None:
    """Resolve one built asset without accepting traversal or escaping symlinks."""

    if "\x00" in relative_path or "\\" in relative_path:
        raise UnsafeStaticPath("Invalid static path")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise UnsafeStaticPath("Static path traversal is forbidden")

    try:
        candidate = (root / Path(*relative.parts)).resolve(strict=True)
    except FileNotFoundError:
        return None
    canonical_root = root.resolve(strict=True)
    if not candidate.is_relative_to(canonical_root):
        raise UnsafeStaticPath("Static symlink escapes its audience dist root")
    return candidate if candidate.is_file() else None


def _connection_header_names(headers: CIMultiDictProxy[str]) -> set[str]:
    names: set[str] = set()
    for value in headers.getall("Connection", []):
        names.update(part.strip().lower() for part in value.split(",") if part.strip())
    return names


def _forward_headers(
    headers: CIMultiDictProxy[str],
    *,
    request_headers: bool,
    force_no_store: bool = True,
) -> CIMultiDict[str]:
    blocked = HOP_BY_HOP_HEADERS | _connection_header_names(headers)
    if request_headers:
        blocked = blocked | {
            "content-length",
            "host",
            "sec-websocket-extensions",
            "sec-websocket-key",
            "sec-websocket-protocol",
            "sec-websocket-version",
        }
    elif force_no_store:
        # Every API response is private and authoritative.  Do not let an
        # accidental upstream cache header weaken the E2E production boundary.
        blocked = blocked | {"cache-control", "expires", "pragma"}
    forwarded = CIMultiDict(
        (name, value) for name, value in headers.items() if name.lower() not in blocked
    )
    if not request_headers and force_no_store:
        forwarded["Cache-Control"] = "no-store"
        forwarded["Pragma"] = "no-cache"
    return forwarded


def _forward_request_headers(request: web.Request) -> CIMultiDict[str]:
    """Sanitize request headers while preserving the browser-facing Host."""

    forwarded = _forward_headers(request.headers, request_headers=True)
    incoming_host = request.headers.get("Host")
    if incoming_host is not None:
        # aiohttp would otherwise synthesize Host from API_ORIGIN.  Phase-1
        # target-origin checks must see the same authority the browser used.
        forwarded["Host"] = incoming_host
    return forwarded


def _upstream_url(request: web.Request) -> str:
    return f"{request.app[API_ORIGIN]}{request.rel_url.raw_path_qs}"


async def _proxy_http(request: web.Request) -> web.StreamResponse:
    return await _proxy_upstream(request, force_no_store=True)


async def _proxy_content_asset(request: web.Request) -> web.StreamResponse:
    return await _proxy_upstream(request, force_no_store=False)


async def _proxy_upstream(
    request: web.Request, *, force_no_store: bool
) -> web.StreamResponse:
    override = _runtime_override(request)
    if override is not None:
        return override

    headers = _forward_request_headers(request)
    body = request.content.iter_any() if request.can_read_body else None
    session = request.app[HTTP_CLIENT]
    try:
        upstream = await session.request(
            request.method,
            _upstream_url(request),
            headers=headers,
            data=body,
            allow_redirects=False,
        )
    except OSError as exc:
        raise web.HTTPBadGateway(text="Isolated PWA API is unavailable") from exc

    try:
        response = web.StreamResponse(
            status=upstream.status,
            reason=upstream.reason,
            headers=_forward_headers(
                upstream.headers,
                request_headers=False,
                force_no_store=force_no_store,
            ),
        )
        try:
            await response.prepare(request)
        except ConnectionResetError:
            # Playwright's real offline mode deliberately drops the browser
            # transport before the upstream response arrives.  That is a
            # normal downstream cancellation, not a gateway failure.
            return response
        async for chunk in upstream.content.iter_any():
            try:
                await response.write(chunk)
            except ConnectionResetError:
                return response
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass
        return response
    finally:
        upstream.release()


def _runtime_override(request: web.Request) -> web.Response | None:
    """Return a deliberately incompatible runtime only for recovery E2E."""

    audience = request.match_info.get("audience")
    if audience not in AUDIENCES or request.path != f"/{audience}/api/v1/runtime":
        return None
    if request.cookies.get(f"vmsh-e2e-runtime-mode-{audience}") != "incompatible":
        return None
    request_id = request.headers.get("X-Request-ID", "")
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        request_id = uuid.uuid4().hex
    other_audience = "family" if audience == "student" else "student"
    return web.json_response(
        {
            "contractVersion": 1,
            "audience": other_audience,
            "appBase": f"/{other_audience}",
            "apiBase": f"/{other_audience}/api/v1",
            "websocketPath": f"/{other_audience}/ws",
            "instance": "e2e",
            "serverTime": "2026-07-27T12:00:00Z",
            "requestId": request_id,
            "features": {
                "telegram": False,
                "google": False,
                "nats": False,
                "prototype": True,
            },
        },
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Request-ID": request_id,
        },
    )


async def _relay_websocket(request: web.Request) -> web.WebSocketResponse:
    incoming_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        incoming_request_id
        if REQUEST_ID_PATTERN.fullmatch(incoming_request_id)
        else uuid.uuid4().hex
    )
    headers = _forward_request_headers(request)
    headers["X-Request-ID"] = request_id
    protocols = tuple(
        item.strip()
        for item in request.headers.get("Sec-WebSocket-Protocol", "").split(",")
        if item.strip()
    )
    upstream_url = _upstream_url(request).replace("http://", "ws://", 1)
    try:
        upstream = await request.app[HTTP_CLIENT].ws_connect(
            upstream_url,
            headers=headers,
            protocols=protocols,
            autoping=True,
        )
    except Exception as exc:
        raise web.HTTPBadGateway(text="Isolated PWA WebSocket is unavailable") from exc

    downstream: web.WebSocketResponse | None = None
    downstream_prepared = False
    try:
        downstream_protocols = (upstream.protocol,) if upstream.protocol else ()
        downstream = web.WebSocketResponse(
            protocols=downstream_protocols, autoping=True
        )
        downstream.headers["X-Request-ID"] = request_id
        try:
            await downstream.prepare(request)
        except AssertionError as error:
            if request.transport is None:
                raise asyncio.CancelledError from error
            raise
        downstream_prepared = True

        async def downstream_to_upstream() -> None:
            assert downstream is not None
            async for message in downstream:
                if message.type == WSMsgType.TEXT:
                    await upstream.send_str(message.data)
                elif message.type == WSMsgType.BINARY:
                    await upstream.send_bytes(message.data)
                elif message.type == WSMsgType.ERROR:
                    raise downstream.exception() or RuntimeError(
                        "downstream websocket failed"
                    )

        async def upstream_to_downstream() -> None:
            assert downstream is not None
            async for message in upstream:
                if message.type == WSMsgType.TEXT:
                    await downstream.send_str(message.data)
                elif message.type == WSMsgType.BINARY:
                    await downstream.send_bytes(message.data)
                elif message.type == WSMsgType.ERROR:
                    raise upstream.exception() or RuntimeError(
                        "upstream websocket failed"
                    )

        tasks = {
            asyncio.create_task(downstream_to_upstream()),
            asyncio.create_task(upstream_to_downstream()),
        }
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # The upstream must also close when the browser disconnects before its
        # downstream upgrade completes; otherwise repeated aborted E2E probes
        # leak sockets and make later runtime checks misleading.
        await upstream.close()
        if downstream is not None and downstream_prepared:
            await downstream.close()
    assert downstream is not None
    return downstream


async def _transport(request: web.Request) -> web.StreamResponse:
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await _relay_websocket(request)
    return await _proxy_http(request)


def _is_history_navigation(request: web.Request, relative_path: str) -> bool:
    if request.method not in {"GET", "HEAD"}:
        return False
    if relative_path == "api" or relative_path.startswith("api/"):
        return False
    if relative_path == "ws" or relative_path.startswith("ws/"):
        return False
    if PurePosixPath(relative_path).suffix.lower() in STATIC_SUFFIXES:
        return False
    return (
        request.headers.get("Sec-Fetch-Mode", "").lower() == "navigate"
        or "text/html" in request.headers.get("Accept", "").lower()
    )


def _static_headers(relative_path: str, audience: str) -> dict[str, str]:
    headers = {
        "Cache-Control": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    if relative_path.startswith("assets/"):
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    if relative_path == "sw.js":
        headers["Cache-Control"] = "no-store"
        headers["Service-Worker-Allowed"] = f"/{audience}/"
    return headers


async def _service_worker(
    request: web.Request, audience: str, source: Path
) -> web.Response:
    generation = request.cookies.get(f"vmsh-e2e-sw-generation-{audience}", "baseline")
    if not GENERATION_PATTERN.fullmatch(generation):
        generation = "baseline"
    # This probe exists only in the loopback gateway response. It proves which
    # byte-distinct worker controls the page after the real Workbox
    # SKIP_WAITING flow; scriptURL itself stays constant across revisions.
    probe = (
        f"\n// vmsh-e2e-generation:{generation}\n"
        "self.addEventListener('message',(event)=>{"
        "if(event.data?.type==='VMSH_E2E_PROBE_GENERATION')"
        f"event.source?.postMessage({{type:'VMSH_E2E_GENERATION',generation:{json.dumps(generation)},nonce:event.data.nonce}})"
        "});\n"
    )
    body = source.read_bytes() + probe.encode()
    return web.Response(
        body=body,
        content_type="text/javascript",
        headers=_static_headers("sw.js", audience),
    )


async def _serve_application(request: web.Request) -> web.StreamResponse:
    audience = request.match_info["audience"]
    relative_path = request.match_info.get("tail", "")
    if relative_path == "":
        relative_path = "index.html"

    root = request.app[DIST_ROOTS][audience]
    try:
        source = resolve_static_file(root, relative_path)
    except UnsafeStaticPath as exc:
        raise web.HTTPNotFound(text="Static resource not found") from exc

    if source is None:
        if not _is_history_navigation(request, relative_path):
            raise web.HTTPNotFound(text="Static resource not found")
        source = resolve_static_file(root, "index.html")
        assert source is not None
        relative_path = "index.html"

    if relative_path == "sw.js" and audience in PWA_AUDIENCES:
        return await _service_worker(request, audience, source)
    return web.FileResponse(source, headers=_static_headers(relative_path, audience))


def _landing_headers(relative_path: str) -> dict[str, str]:
    headers = {"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    if relative_path.startswith("assets/"):
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return headers


async def _serve_landing(request: web.Request) -> web.StreamResponse:
    relative_path = request.match_info.get("tail", "") or "index.html"
    root = request.app[DIST_ROOTS]["landing"]
    try:
        source = resolve_static_file(root, relative_path)
    except UnsafeStaticPath as exc:
        raise web.HTTPNotFound(text="Static resource not found") from exc
    if source is None:
        raise web.HTTPNotFound(text="Static resource not found")
    return web.FileResponse(source, headers=_landing_headers(relative_path))


async def _redirect_application_root(request: web.Request) -> web.Response:
    audience = request.match_info["audience"]
    raise web.HTTPPermanentRedirect(location=f"/{audience}/")


def _is_local_request(request: web.Request) -> bool:
    try:
        return (
            request.remote is not None
            and ipaddress.ip_address(request.remote).is_loopback
        )
    except ValueError:
        return False


async def _gateway_health(_request: web.Request) -> web.Response:
    return web.json_response(
        {"ok": True, "apps": list(AUDIENCES)},
        headers={"Cache-Control": "no-store"},
    )


async def _set_service_worker_generation(request: web.Request) -> web.Response:
    if not _is_local_request(request) or not hmac.compare_digest(
        request.headers.get("X-VMSH-E2E-Control", ""), request.app[CONTROL_TOKEN]
    ):
        raise web.HTTPForbidden(text="E2E control capability required")
    audience = request.match_info["audience"]
    try:
        payload = await request.json(loads=json.loads)
    except json.JSONDecodeError, UnicodeDecodeError:
        raise web.HTTPBadRequest(text="Expected a JSON generation payload") from None
    generation = payload.get("generation") if isinstance(payload, dict) else None
    if not isinstance(generation, str) or not GENERATION_PATTERN.fullmatch(generation):
        raise web.HTTPBadRequest(text="Invalid service-worker generation")

    response = web.json_response(
        {"ok": True, "audience": audience, "generation": generation}
    )
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        f"vmsh-e2e-sw-generation-{audience}",
        generation,
        path=f"/{audience}/",
        httponly=True,
        samesite="Strict",
    )
    return response


async def _set_runtime_mode(request: web.Request) -> web.Response:
    if not _is_local_request(request) or not hmac.compare_digest(
        request.headers.get("X-VMSH-E2E-Control", ""), request.app[CONTROL_TOKEN]
    ):
        raise web.HTTPForbidden(text="E2E control capability required")
    audience = request.match_info["audience"]
    try:
        payload = await request.json(loads=json.loads)
    except json.JSONDecodeError, UnicodeDecodeError:
        raise web.HTTPBadRequest(text="Expected a JSON runtime-mode payload") from None
    mode = payload.get("mode") if isinstance(payload, dict) else None
    if mode not in {"valid", "incompatible"}:
        raise web.HTTPBadRequest(text="Invalid runtime mode")

    response = web.json_response({"ok": True, "audience": audience, "mode": mode})
    response.headers["Cache-Control"] = "no-store"
    cookie_name = f"vmsh-e2e-runtime-mode-{audience}"
    if mode == "valid":
        response.del_cookie(cookie_name, path=f"/{audience}/")
    else:
        response.set_cookie(
            cookie_name,
            mode,
            path=f"/{audience}/",
            httponly=True,
            samesite="Strict",
        )
    return response


async def _client_session_context(app: web.Application):
    session = ClientSession(
        auto_decompress=False,
        # The gateway is shared by Playwright browser contexts.  Browser
        # cookies are forwarded per request; retaining them here would cross
        # the very audience/session boundary this harness exists to test.
        cookie_jar=DummyCookieJar(),
        timeout=ClientTimeout(total=30),
    )
    app[HTTP_CLIENT] = session
    yield
    await session.close()


def create_gateway(
    workspace: Path,
    *,
    api_origin: str,
    control_token: str,
) -> web.Application:
    if not control_token:
        raise ValueError("A non-empty E2E control token is required")
    # Match production nginx; endpoint-specific aiohttp readers retain their
    # narrower limits (the Phase-2 asset body is 25 MiB plus multipart framing).
    app = web.Application(client_max_size=GATEWAY_CLIENT_MAX_SIZE)
    app[DIST_ROOTS] = _load_dist_roots(workspace)
    app[API_ORIGIN] = _validate_api_origin(api_origin)
    app[CONTROL_TOKEN] = control_token
    app.cleanup_ctx.append(_client_session_context)

    app.router.add_get("/__e2e__/health", _gateway_health)
    app.router.add_post(
        "/__e2e__/service-worker-generation/{audience:student|family}",
        _set_service_worker_generation,
    )
    app.router.add_get("/", _serve_landing)
    app.router.add_get("/landing/{tail:.*}", _serve_landing)
    app.router.add_post(
        "/__e2e__/runtime-mode/{audience:student|family}",
        _set_runtime_mode,
    )
    # Transport routes precede the SPA wildcard.  A missing API or malformed WS
    # path must never receive index.html from history fallback.
    app.router.add_route("*", "/{audience:student|family|staff}/api", _proxy_http)
    app.router.add_route(
        "*", "/{audience:student|family|staff}/api/{tail:.*}", _proxy_http
    )
    app.router.add_get(
        "/pwa-content-assets/{asset_id:[a-z0-9][a-z0-9._:-]{0,127}}",
        _proxy_content_asset,
    )
    app.router.add_route("*", "/{audience:student|family|staff}/ws", _transport)
    app.router.add_get("/{audience:student|family|staff}", _redirect_application_root)
    app.router.add_get("/{audience:student|family|staff}/{tail:.*}", _serve_application)
    return app


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5380)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--api-origin", default="http://127.0.0.1:8380")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = _parse_args(argv)
    if os.environ.get("VMSH_RUNTIME_PROFILE") != "pwa-e2e":
        raise SystemExit("The E2E gateway requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    _require_loopback(args.host, label="Gateway bind host")
    control_token = os.environ.get("VMSH_E2E_GATEWAY_CONTROL_TOKEN", "")
    application = create_gateway(
        args.workspace,
        api_origin=args.api_origin,
        control_token=control_token,
    )
    web.run_app(application, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
