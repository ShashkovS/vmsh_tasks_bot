from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import WSMsgType, web
from multidict import CIMultiDict, CIMultiDictProxy

import vmshpwa.scripts.e2e_gateway as e2e_gateway
from vmshpwa.scripts.e2e_gateway import (
    AUDIENCES,
    UnsafeStaticPath,
    create_gateway,
    main,
    resolve_static_file,
)


def _production_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "vmshpwa"
    for audience in AUDIENCES:
        dist = workspace / "apps" / audience / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text(
            f"<!doctype html><main data-product='{audience}'>{audience}</main>",
            encoding="utf-8",
        )
        (dist / "assets" / "app.js").write_text("export {}", encoding="utf-8")
        if audience != "staff":
            (dist / "sw.js").write_text(
                "self.addEventListener('fetch',()=>{})", encoding="utf-8"
            )
            (dist / "manifest.webmanifest").write_text(
                json.dumps({"id": f"/{audience}/"}),
                encoding="utf-8",
            )
    return workspace


@pytest.fixture
async def upstream(aiohttp_server):
    application = web.Application()

    async def api(request: web.Request) -> web.Response:
        body = await request.read()
        payload = {
            "method": request.method,
            "path": request.path,
            "query": request.query_string,
            "body": body.decode(),
            "requestId": request.headers.get("X-Request-ID"),
        }
        if request.path.endswith("/host"):
            payload["host"] = request.headers.get("Host")
        response = web.json_response(
            payload, status=418 if request.path.endswith("missing") else 200
        )
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["X-Upstream"] = "yes"
        return response

    async def websocket(request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        payload = {
            "type": "connected",
            "requestId": request.headers.get("X-Request-ID"),
        }
        if request.query.get("includeHost") == "1":
            payload["host"] = request.headers.get("Host")
        await socket.send_json(payload)
        async for message in socket:
            if message.type == WSMsgType.TEXT:
                await socket.send_str(f"echo:{message.data}")
        return socket

    application.router.add_route("*", "/{audience}/api", api)
    application.router.add_route("*", "/{audience}/api/{tail:.*}", api)
    application.router.add_get("/pwa-content-assets/{asset_id}", api)
    application.router.add_get("/{audience}/ws", websocket)
    return await aiohttp_server(application)


@pytest.fixture
async def gateway_client(tmp_path, upstream, aiohttp_client):
    application = create_gateway(
        _production_workspace(tmp_path),
        api_origin=str(upstream.make_url("/")).rstrip("/"),
        control_token="unit-test-capability",
    )
    return await aiohttp_client(application)


async def test_gateway_serves_three_bundles_and_only_navigation_fallback(
    gateway_client,
):
    for audience in AUDIENCES:
        shell = await gateway_client.get(f"/{audience}/")
        assert shell.status == 200
        assert f"data-product='{audience}'" in await shell.text()
        assert shell.headers["Cache-Control"] == "no-cache"

        deep_link = await gateway_client.get(
            f"/{audience}/deep/route",
            headers={"Accept": "text/html"},
        )
        assert deep_link.status == 200
        assert f"data-product='{audience}'" in await deep_link.text()

        missing_asset = await gateway_client.get(
            f"/{audience}/assets/missing.js",
            headers={"Accept": "text/html"},
        )
        assert missing_asset.status == 404
        assert "data-product" not in await missing_asset.text()

        for static_path in (
            "not-built.js",
            "missing-document.html",
            "missing-print.pdf",
            "robots.txt",
        ):
            missing_root_asset = await gateway_client.get(
                f"/{audience}/{static_path}", headers={"Accept": "text/html"}
            )
            assert missing_root_asset.status == 404
            assert "data-product" not in await missing_root_asset.text()

        malformed_websocket = await gateway_client.get(
            f"/{audience}/ws/extra",
            headers={"Accept": "text/html"},
        )
        assert malformed_websocket.status == 404
        assert "data-product" not in await malformed_websocket.text()

    unknown = await gateway_client.get("/unknown/deep", headers={"Accept": "text/html"})
    assert unknown.status == 404
    non_navigation = await gateway_client.post("/student/deep/route")
    assert non_navigation.status == 405


async def test_gateway_proxies_api_before_fallback_and_forces_no_store(gateway_client):
    response = await gateway_client.post(
        "/student/api/v1/missing?lesson=41",
        data=b"payload",
        headers={
            "Accept": "text/html",
            "Content-Type": "application/octet-stream",
            "X-Request-ID": "gateway.unit.41",
        },
    )

    assert response.status == 418
    assert response.content_type == "application/json"
    assert response.headers["X-Upstream"] == "yes"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert await response.json() == {
        "method": "POST",
        "path": "/student/api/v1/missing",
        "query": "lesson=41",
        "body": "payload",
        "requestId": "gateway.unit.41",
    }

    api_root = await gateway_client.get("/family/api")
    assert api_root.status == 200
    assert (await api_root.json())["path"] == "/family/api"


async def test_gateway_proxies_exact_content_asset_and_preserves_immutable_cache(
    gateway_client,
):
    assert (
        gateway_client.server.app._client_max_size
        == e2e_gateway.GATEWAY_CLIENT_MAX_SIZE
        == 64 * 1024 * 1024
    )
    response = await gateway_client.get("/pwa-content-assets/asset-content-41")

    assert response.status == 200
    assert response.headers["Cache-Control"] == "public, max-age=86400"
    assert (await response.json())["path"] == (
        "/pwa-content-assets/asset-content-41"
    )
    malformed = await gateway_client.get(
        "/pwa-content-assets/asset-content-41/extra",
        headers={"Accept": "text/html"},
    )
    assert malformed.status == 404


async def test_gateway_relays_websocket_frames_and_request_id(gateway_client):
    socket = await gateway_client.ws_connect(
        "/staff/ws",
        headers={"X-Request-ID": "gateway.websocket.17"},
    )
    connected = await socket.receive_json()
    assert connected == {
        "type": "connected",
        "requestId": "gateway.websocket.17",
    }
    await socket.send_str("ping")
    assert (await socket.receive()).data == "echo:ping"
    await socket.close()


async def test_gateway_preserves_browser_host_for_http_and_websocket(gateway_client):
    browser_host = "pwa.test.invalid:5380"

    response = await gateway_client.get(
        "/student/api/v1/host", headers={"Host": browser_host}
    )
    assert response.status == 200
    assert (await response.json())["host"] == browser_host

    socket = await gateway_client.ws_connect(
        "/staff/ws?includeHost=1", headers={"Host": browser_host}
    )
    assert (await socket.receive_json())["host"] == browser_host
    await socket.close()


async def test_gateway_releases_upstream_when_offline_browser_drops_response(
    monkeypatch,
):
    class UpstreamContent:
        async def iter_any(self):
            yield b"never forwarded"

    class UpstreamResponse:
        status = 201
        reason = "Created"
        headers = CIMultiDictProxy(CIMultiDict())
        content = UpstreamContent()
        released = False

        def release(self) -> None:
            self.released = True

    upstream = UpstreamResponse()

    class HttpClient:
        async def request(self, *_args, **_kwargs):
            return upstream

    class AbortedDownstream:
        def __init__(self, *_args, **_kwargs):
            pass

        async def prepare(self, _request) -> None:
            raise ConnectionResetError("browser switched offline")

    monkeypatch.setattr(e2e_gateway.web, "StreamResponse", AbortedDownstream)
    request = SimpleNamespace(
        app={
            e2e_gateway.API_ORIGIN: "http://127.0.0.1:8380",
            e2e_gateway.HTTP_CLIENT: HttpClient(),
        },
        headers=CIMultiDictProxy(CIMultiDict()),
        rel_url=SimpleNamespace(raw_path_qs="/student/api/v1/problems/p/test-attempts"),
        match_info={},
        method="POST",
        can_read_body=False,
    )

    response = await e2e_gateway._proxy_upstream(request, force_no_store=True)

    assert isinstance(response, AbortedDownstream)
    assert upstream.released is True


async def test_gateway_closes_upstream_when_downstream_upgrade_aborts(monkeypatch):
    class UpstreamSocket:
        protocol = None
        closed = False

        async def close(self) -> None:
            self.closed = True

    upstream = UpstreamSocket()

    class HttpClient:
        async def ws_connect(self, *_args, **_kwargs):
            return upstream

    class AbortedDownstream:
        close_called = False

        def __init__(self, *_args, **_kwargs):
            self.headers: dict[str, str] = {}

        async def prepare(self, _request) -> None:
            raise ConnectionResetError("browser left before the upgrade")

        async def close(self) -> None:
            type(self).close_called = True

    monkeypatch.setattr(e2e_gateway.web, "WebSocketResponse", AbortedDownstream)
    request = SimpleNamespace(
        app={
            e2e_gateway.API_ORIGIN: "http://127.0.0.1:8380",
            e2e_gateway.HTTP_CLIENT: HttpClient(),
        },
        headers=CIMultiDictProxy(CIMultiDict()),
        rel_url=SimpleNamespace(raw_path_qs="/student/ws"),
    )

    with pytest.raises(ConnectionResetError, match="browser left"):
        await e2e_gateway._relay_websocket(request)

    assert upstream.closed is True
    assert AbortedDownstream.close_called is False


async def test_gateway_service_worker_control_is_local_capability_gated(gateway_client):
    baseline = await gateway_client.get("/student/sw.js")
    baseline_body = await baseline.text()
    assert "vmsh-e2e-generation:baseline" in baseline_body
    assert "VMSH_E2E_PROBE_GENERATION" in baseline_body
    assert baseline.headers["Cache-Control"] == "no-store"
    assert baseline.headers["Service-Worker-Allowed"] == "/student/"

    denied = await gateway_client.post(
        "/__e2e__/service-worker-generation/student",
        json={"generation": "rev-2"},
    )
    assert denied.status == 403
    invalid = await gateway_client.post(
        "/__e2e__/service-worker-generation/student",
        json={"generation": "../../escape"},
        headers={"X-VMSH-E2E-Control": "unit-test-capability"},
    )
    assert invalid.status == 400

    changed = await gateway_client.post(
        "/__e2e__/service-worker-generation/student",
        json={"generation": "rev-2"},
        headers={"X-VMSH-E2E-Control": "unit-test-capability"},
    )
    assert changed.status == 200
    assert await changed.json() == {
        "ok": True,
        "audience": "student",
        "generation": "rev-2",
    }
    cookie = changed.headers["Set-Cookie"].split(";", 1)[0]
    updated = await gateway_client.get("/student/sw.js", headers={"Cookie": cookie})
    updated_body = await updated.text()
    assert "vmsh-e2e-generation:rev-2" in updated_body
    assert 'generation:"rev-2"' in updated_body
    assert updated_body != baseline_body


async def test_gateway_runtime_override_is_capability_gated_and_audience_scoped(
    gateway_client,
):
    denied = await gateway_client.post(
        "/__e2e__/runtime-mode/student", json={"mode": "incompatible"}
    )
    assert denied.status == 403

    changed = await gateway_client.post(
        "/__e2e__/runtime-mode/student",
        json={"mode": "incompatible"},
        headers={"X-VMSH-E2E-Control": "unit-test-capability"},
    )
    assert changed.status == 200
    cookie = changed.headers["Set-Cookie"].split(";", 1)[0]

    overridden = await gateway_client.get(
        "/student/api/v1/runtime",
        headers={"Cookie": cookie, "X-Request-ID": "runtime.recovery.unit"},
    )
    assert overridden.status == 200
    assert overridden.headers["Cache-Control"] == "no-store"
    assert overridden.headers["X-Request-ID"] == "runtime.recovery.unit"
    assert (await overridden.json())["audience"] == "family"

    unaffected = await gateway_client.get(
        "/family/api/v1/runtime", headers={"Cookie": cookie}
    )
    assert unaffected.status == 200
    assert (await unaffected.json())["path"] == "/family/api/v1/runtime"


async def test_gateway_health_is_small_and_non_cacheable(gateway_client):
    response = await gateway_client.get("/__e2e__/health")
    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert await response.json() == {"ok": True, "apps": list(AUDIENCES)}


def test_static_resolver_rejects_traversal_and_escaping_symlinks(tmp_path):
    root = tmp_path / "dist"
    root.mkdir()
    (root / "index.html").write_text("safe", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (root / "escape.txt").symlink_to(outside)

    assert resolve_static_file(root, "index.html") == (root / "index.html").resolve()
    assert resolve_static_file(root, "missing.js") is None
    with pytest.raises(UnsafeStaticPath, match="traversal"):
        resolve_static_file(root, "../secret.txt")
    with pytest.raises(UnsafeStaticPath, match="symlink"):
        resolve_static_file(root, "escape.txt")
    with pytest.raises(UnsafeStaticPath, match="Invalid"):
        resolve_static_file(root, "folder\\secret.txt")


def test_gateway_rejects_non_loopback_upstream(tmp_path):
    workspace = _production_workspace(tmp_path)
    with pytest.raises(ValueError, match="loopback"):
        create_gateway(
            workspace,
            api_origin="https://example.com:443",
            control_token="unit-test-capability",
        )


def test_gateway_rejects_cross_audience_dist_root_symlink(tmp_path):
    workspace = _production_workspace(tmp_path)
    family_dist = workspace / "apps" / "family" / "dist"
    shutil.rmtree(family_dist)
    family_dist.symlink_to(
        workspace / "apps" / "student" / "dist", target_is_directory=True
    )

    with pytest.raises(UnsafeStaticPath, match="must not be a symlink"):
        create_gateway(
            workspace,
            api_origin="http://127.0.0.1:8380",
            control_token="unit-test-capability",
        )


def test_gateway_cli_requires_e2e_profile(monkeypatch):
    monkeypatch.delenv("VMSH_RUNTIME_PROFILE", raising=False)
    with pytest.raises(SystemExit, match="VMSH_RUNTIME_PROFILE=pwa-e2e"):
        main([])


@pytest.mark.parametrize("audience", AUDIENCES)
def test_vite_dev_and_preview_proxies_preserve_browser_host(audience):
    repository_root = Path(__file__).resolve().parents[1]
    source = (
        repository_root / "vmshpwa" / "apps" / audience / "vite.config.ts"
    ).read_text(encoding="utf-8")

    api_proxy = f"'/{audience}/api': {{ target: apiOrigin, changeOrigin: false }}"
    websocket_proxy = (
        f"'/{audience}/ws': {{ target: apiOrigin, changeOrigin: false, ws: true }}"
    )
    assert source.count(api_proxy) == 2
    assert source.count(websocket_proxy) == 2
    assert "changeOrigin: true" not in source
