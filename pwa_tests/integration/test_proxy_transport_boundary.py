"""Real aiohttp transport proof for the Phase-1 proxy boundary."""

from __future__ import annotations

import ipaddress
import socket
import tempfile
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import MappingProxyType

import aiohttp
import pytest
from aiohttp import WSServerHandshakeError, web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import (
    PWA_AUTH_STATE,
    PwaAuthState,
    pwa_auth_request_security_middleware,
    request_boundary,
    validate_request_boundary,
)
from helpers.pwa.auth_config import AuthRuntimeConfig
from models.pwa.auth import AuthAudience


PUBLIC_ORIGIN = "https://pwa.example.org"
FORWARDED = 'for="203.0.113.42";proto=https;host="pwa.example.org"'


@pytest.fixture
def unix_socket_dir() -> Iterator[Path]:
    # Darwin's sockaddr_un path is short; pytest's standard temp path can
    # exceed it before the filename is appended.
    with tempfile.TemporaryDirectory(prefix="pwa-proxy-", dir="/tmp") as directory:
        yield Path(directory)


def _auth_config(
    *,
    origins: frozenset[str] | None = None,
    tcp: bool = False,
    unix_sockets: tuple[str, ...] = (),
    hops: int = 1,
) -> AuthRuntimeConfig:
    return AuthRuntimeConfig(
        origins_by_audience=MappingProxyType(
            {
                audience: origins or frozenset({PUBLIC_ORIGIN})
                for audience in AuthAudience
            }
        ),
        trusted_proxy_networks=((ipaddress.ip_network("127.0.0.1/32"),) if tcp else ()),
        trusted_proxy_hops=hops,
        access_ttl_seconds=900,
        secure_cookies=False,
        signing_keys=("s" * 32,),
        refresh_pepper=b"r" * 32,
        throttle_pepper=b"t" * 32,
        trusted_proxy_unix_socket_paths=unix_sockets,
        test_only_defaults=True,
    )


@web.middleware
async def _render_security_failure(request: web.Request, handler):
    try:
        return await handler(request)
    except PwaApiError as error:
        return web.json_response(
            {"code": error.code},
            status=error.status,
            headers=error.headers,
        )


def _application(config: AuthRuntimeConfig) -> web.Application:
    app = web.Application(
        middlewares=[_render_security_failure, pwa_auth_request_security_middleware]
    )
    app[PWA_AUTH_STATE] = PwaAuthState(config)

    async def probe(request: web.Request) -> web.Response:
        boundary = request_boundary(request)
        return web.json_response(
            {
                "origin": boundary.external_origin,
                "client": boundary.client_address,
                "hops": boundary.proxy_hops,
            }
        )

    async def websocket_probe(request: web.Request) -> web.WebSocketResponse:
        validate_request_boundary(
            request,
            audience=AuthAudience.STUDENT,
            expects_json=False,
            require_browser_source=True,
        )
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        await websocket.close()
        return websocket

    app.router.add_get("/student/api/v1/health", probe)
    app.router.add_get("/student/ws", websocket_probe)
    return app


@asynccontextmanager
async def _tcp_server(
    config_factory,
) -> AsyncIterator[tuple[str, aiohttp.ClientSession]]:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(128)
    server_socket.setblocking(False)
    host, port = server_socket.getsockname()
    app = _application(config_factory(host, port))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.SockSite(runner, server_socket)
    await site.start()
    async with aiohttp.ClientSession() as session:
        try:
            yield f"http://{host}:{port}", session
        finally:
            await runner.cleanup()


@asynccontextmanager
async def _unix_server(
    socket_path: Path,
    config: AuthRuntimeConfig,
) -> AsyncIterator[tuple[str, aiohttp.ClientSession]]:
    app = _application(config)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.UnixSite(runner, str(socket_path))
    await site.start()
    connector = aiohttp.UnixConnector(path=str(socket_path))
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            yield "http://localhost", session
        finally:
            await runner.cleanup()


@pytest.mark.asyncio
async def test_direct_tcp_request_uses_only_its_real_target_and_peer():
    def direct_config(host: str, port: int) -> AuthRuntimeConfig:
        return _auth_config(
            origins=frozenset({f"http://{host}:{port}"}),
            hops=0,
        )

    async with _tcp_server(direct_config) as (base_url, session):
        response = await session.get(f"{base_url}/student/api/v1/health")
        status = response.status
        payload = await response.json()

    assert status == 200
    assert payload == {
        "origin": base_url,
        "client": "127.0.0.1",
        "hops": 0,
    }


@pytest.mark.asyncio
async def test_exact_loopback_tcp_proxy_replaces_external_request_facts():
    async with _tcp_server(lambda _host, _port: _auth_config(tcp=True)) as (
        base_url,
        session,
    ):
        response = await session.get(
            f"{base_url}/student/api/v1/health",
            headers={"Forwarded": FORWARDED},
        )
        status = response.status
        payload = await response.json()

    assert status == 200
    assert payload == {
        "origin": PUBLIC_ORIGIN,
        "client": "203.0.113.42",
        "hops": 1,
    }


@pytest.mark.asyncio
async def test_unix_proxy_requires_the_exact_server_socket_path(
    unix_socket_dir: Path,
):
    socket_path = unix_socket_dir / "backend.sock"
    config = _auth_config(unix_sockets=(str(socket_path),))

    async with _unix_server(socket_path, config) as (base_url, session):
        response = await session.get(
            f"{base_url}/student/api/v1/health",
            headers={"Forwarded": FORWARDED},
        )
        status = response.status
        payload = await response.json()

    assert status == 200
    assert payload == {
        "origin": PUBLIC_ORIGIN,
        "client": "203.0.113.42",
        "hops": 1,
    }


@pytest.mark.asyncio
async def test_other_unix_socket_is_not_trusted_as_a_local_process(
    unix_socket_dir: Path,
):
    actual_socket = unix_socket_dir / "actual.sock"
    configured_socket = unix_socket_dir / "configured.sock"
    config = _auth_config(unix_sockets=(str(configured_socket),))

    async with _unix_server(actual_socket, config) as (base_url, session):
        response = await session.get(
            f"{base_url}/student/api/v1/health",
            headers={"Forwarded": FORWARDED},
        )
        status = response.status
        payload = await response.json()

    assert status == 403
    assert payload["code"] == "untrusted_forwarding_peer"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("forwarded", "expected_status", "expected_code"),
    [
        (
            'for="203.0.113.42";proto=http;host="pwa.example.org"',
            403,
            "request_origin_not_allowed",
        ),
        (
            'for="203.0.113.42";proto=https;host="attacker.example"',
            403,
            "request_origin_not_allowed",
        ),
        (
            f"{FORWARDED}, for=127.0.0.2",
            403,
            "unexpected_proxy_chain_length",
        ),
    ],
)
async def test_proxy_cannot_select_external_proto_host_or_chain_length(
    unix_socket_dir: Path,
    forwarded: str,
    expected_status: int,
    expected_code: str,
):
    socket_path = unix_socket_dir / "backend.sock"
    config = _auth_config(unix_sockets=(str(socket_path),))

    async with _unix_server(socket_path, config) as (base_url, session):
        response = await session.get(
            f"{base_url}/student/api/v1/health",
            headers={"Forwarded": forwarded},
        )
        status = response.status
        payload = await response.json()

    assert status == expected_status
    assert payload["code"] == expected_code


@pytest.mark.asyncio
async def test_proxy_websocket_requires_exact_public_origin_before_upgrade(
    unix_socket_dir: Path,
):
    socket_path = unix_socket_dir / "backend.sock"
    config = _auth_config(unix_sockets=(str(socket_path),))

    async with _unix_server(socket_path, config) as (base_url, session):
        with pytest.raises(WSServerHandshakeError) as missing:
            await session.ws_connect(
                f"{base_url}/student/ws",
                headers={"Forwarded": FORWARDED},
            )
        with pytest.raises(WSServerHandshakeError) as cross_origin:
            await session.ws_connect(
                f"{base_url}/student/ws",
                origin="https://attacker.example",
                headers={"Forwarded": FORWARDED},
            )
        websocket = await session.ws_connect(
            f"{base_url}/student/ws",
            origin=PUBLIC_ORIGIN,
            headers={"Forwarded": FORWARDED},
        )
        await websocket.close()

    assert missing.value.status == 403
    assert cross_origin.value.status == 403
