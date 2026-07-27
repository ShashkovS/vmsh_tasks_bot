import asyncio
import json

import pytest
from aiohttp import ClientPayloadError, web

from apps import pwa_app
from helpers.config import config
from helpers.nats_brocker import InProcessBroker
from helpers.object_storage import LocalObjectStorage
from main import create_app


class HermeticPwaAdapter:
    """Inject one broker owned exclusively by this aiohttp test application."""

    def __init__(self, broker):
        self.broker = broker

    def configure(self, app):
        pwa_app.configure(app, broker=self.broker)


@pytest.fixture()
async def client(aiohttp_client):
    broker = InProcessBroker("vmshpwa_e2e_pytest")
    app = create_app([HermeticPwaAdapter(broker)], runtime_config=config)
    return await aiohttp_client(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("audience", ["student", "family", "staff"])
async def test_runtime_isolated_from_legacy_credentials(client, audience):
    response = await client.get(f"/{audience}/api/v1/runtime")
    assert response.status == 200
    payload = await response.json()
    assert payload["audience"] == audience
    assert payload["appBase"] == f"/{audience}"
    assert payload["apiBase"] == f"/{audience}/api/v1"
    assert payload["websocketPath"] == f"/{audience}/ws"
    assert payload["features"]["telegram"] is False
    assert payload["features"]["google"] is False
    assert payload["features"]["prototype"] is True
    assert payload["instance"] == config.pwa_instance
    assert response.headers["X-Request-ID"] == payload["requestId"]


@pytest.mark.asyncio
async def test_request_id_is_validated_and_error_is_structured(client):
    accepted = await client.get(
        "/student/api/v1/health", headers={"X-Request-ID": "browser.42"}
    )
    assert accepted.headers["X-Request-ID"] == "browser.42"

    rejected = await client.get(
        "/student/api/v1/missing",
        headers={"X-Request-ID": "invalid id with spaces"},
    )
    payload = await rejected.json()
    assert rejected.status == 404
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["requestId"] != "invalid id with spaces"


@pytest.mark.asyncio
async def test_pwa_middleware_does_not_rewrite_legacy_routes(client):
    response = await client.get("/missing", headers={"X-Request-ID": "browser.42"})
    assert response.status == 404
    assert response.content_type != "application/json"
    assert "X-Request-ID" not in response.headers


@pytest.mark.asyncio
async def test_exact_audience_api_root_keeps_json_error_contract(client):
    response = await client.get("/staff/api", headers={"X-Request-ID": "api.root"})

    assert response.status == 404
    assert response.content_type == "application/json"
    assert response.headers["X-Request-ID"] == "api.root"
    assert response.headers["Cache-Control"] == "no-store"
    assert (await response.json())["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_pwa_api_has_baseline_security_headers(client):
    response = await client.get("/family/api/v1/health")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_rebuilt_http_error_preserves_protocol_headers(client):
    response = await client.post("/student/api/v1/health")

    assert response.status == 405
    assert response.content_type == "application/json"
    assert response.headers["Allow"] == "GET,HEAD"
    assert response.headers["Cache-Control"] == "no-store"
    assert (await response.json())["error"]["code"] == "method_not_allowed"


@pytest.mark.asyncio
async def test_stable_domain_error_keeps_details_and_retry_header(aiohttp_client):
    async def conflict(_request):
        raise pwa_app.PwaApiError(
            status=409,
            code="version_conflict",
            message="Данные изменились",
            details={"expectedVersion": 7, "actualVersion": 8},
            headers={"Retry-After": "1"},
        )

    broker = InProcessBroker("vmshpwa_domain_error_test")
    app = create_app([HermeticPwaAdapter(broker)], runtime_config=config)
    app.router.add_get("/student/api/v1/conflict", conflict)
    local_client = await aiohttp_client(app)

    response = await local_client.get("/student/api/v1/conflict")
    payload = await response.json()
    assert response.status == 409
    assert response.headers["Retry-After"] == "1"
    assert response.headers["Cache-Control"] == "no-store"
    assert payload["error"] == {
        "code": "version_conflict",
        "message": "Данные изменились",
        "requestId": response.headers["X-Request-ID"],
        "details": {"expectedVersion": 7, "actualVersion": 8},
    }


@pytest.mark.asyncio
async def test_prepared_stream_gets_pwa_headers_before_first_chunk(aiohttp_client):
    async def stream(request):
        response = web.StreamResponse(headers={"Content-Type": "text/plain"})
        await response.prepare(request)
        await response.write(b"first chunk")
        await response.write_eof()
        return response

    broker = InProcessBroker("vmshpwa_prepared_stream_test")
    app = create_app([HermeticPwaAdapter(broker)], runtime_config=config)
    app.router.add_get("/student/api/v1/stream", stream)
    local_client = await aiohttp_client(app)

    response = await local_client.get(
        "/student/api/v1/stream",
        headers={"X-Request-ID": "stream.prepared"},
    )

    assert response.status == 200
    assert response.headers["X-Request-ID"] == "stream.prepared"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert await response.text() == "first chunk"


@pytest.mark.asyncio
async def test_prepared_stream_exception_is_not_rebuilt_as_json(
    aiohttp_client, monkeypatch
):
    async def broken_stream(request):
        response = web.StreamResponse(headers={"Content-Type": "text/plain"})
        await response.prepare(request)
        await response.write(b"partial")
        raise RuntimeError("synthetic failure after prepare")

    def unexpected_json_response(*_args, **_kwargs):
        raise AssertionError("prepared response must not be rebuilt as JSON")

    broker = InProcessBroker("vmshpwa_broken_stream_test")
    app = create_app([HermeticPwaAdapter(broker)], runtime_config=config)
    app.router.add_get("/family/api/v1/broken-stream", broken_stream)
    local_client = await aiohttp_client(app)
    monkeypatch.setattr(pwa_app.web, "json_response", unexpected_json_response)

    response = await local_client.get(
        "/family/api/v1/broken-stream",
        headers={"X-Request-ID": "stream.failed"},
    )

    assert response.status == 200
    assert response.content_type == "text/plain"
    assert response.headers["X-Request-ID"] == "stream.failed"
    assert response.headers["Cache-Control"] == "no-store"
    with pytest.raises(ClientPayloadError):
        await response.read()


@pytest.mark.asyncio
async def test_websocket_handshake_heartbeat_and_invalidation(client):
    websocket = await client.ws_connect("/student/ws")
    connected = await websocket.receive_json()
    assert connected["type"] == "connected"
    assert connected["audience"] == "student"

    await websocket.send_json({"type": "ping"})
    assert (await websocket.receive_json())["type"] == "pong"

    await client.app[pwa_app.PWA_BROKER].publish(
        "pwa_invalidate", {"resources": ["lesson:42"], "reason": "test"}
    )
    invalidation = await websocket.receive_json()
    assert invalidation["type"] == "invalidate"
    assert invalidation["resources"] == ["lesson:42"]
    assert invalidation["cursor"] >= 1
    await websocket.close()


@pytest.mark.asyncio
async def test_websocket_reconnect_always_requires_authoritative_resync(client):
    websocket = await client.ws_connect("/student/ws?cursor=0")
    event = await websocket.receive_json()
    assert event["type"] == "resync-required"
    assert event["reason"] == "reconnect-full-refetch-required"
    await websocket.close()


@pytest.mark.asyncio
async def test_websocket_invalid_json_uses_recoverable_wire_error(client):
    websocket = await client.ws_connect(
        "/student/ws", headers={"X-Request-ID": "ws.invalid-json"}
    )
    assert (await websocket.receive_json())["type"] == "connected"

    await websocket.send_str("not-json")
    event = await websocket.receive_json()

    assert event == {
        "type": "error",
        "cursor": 0,
        "serverTime": event["serverTime"],
        "code": "invalid_json",
        "message": "Сообщение WebSocket должно быть корректным JSON",
        "requestId": "ws.invalid-json",
    }
    await websocket.send_json({"type": "ping"})
    assert (await websocket.receive_json())["type"] == "pong"
    await websocket.close()


@pytest.mark.asyncio
async def test_websocket_decoder_recursion_failure_is_recoverable(client, monkeypatch):
    websocket = await client.ws_connect(
        "/student/ws", headers={"X-Request-ID": "ws.recursion"}
    )
    assert (await websocket.receive_json())["type"] == "connected"
    original_loads = pwa_app.json.loads

    def fail_at_decoder_boundary(_payload):
        raise RecursionError("synthetic deeply nested JSON")

    monkeypatch.setattr(pwa_app.json, "loads", fail_at_decoder_boundary)
    await websocket.send_str("{}")
    message = await websocket.receive()
    monkeypatch.setattr(pwa_app.json, "loads", original_loads)
    event = original_loads(message.data)

    assert event["type"] == "error"
    assert event["code"] == "invalid_json"
    assert event["requestId"] == "ws.recursion"
    await websocket.send_json({"type": "ping"})
    assert (await websocket.receive_json())["type"] == "pong"
    await websocket.close()


@pytest.mark.asyncio
async def test_websocket_post_upgrade_failure_never_reenters_http_middleware(
    monkeypatch,
):
    class FailingHandshakeWebSocket:
        def __init__(self):
            self.closed = False
            self.headers = {}

        async def prepare(self, _request):
            return None

        async def send_json(self, _payload):
            raise ConnectionResetError("synthetic disconnect after upgrade")

        async def close(self, *, code, message):
            assert code == pwa_app.WSCloseCode.INTERNAL_ERROR
            assert message == b"Realtime transport failure"
            self.closed = True

    class Request:
        match_info = {"audience": "student"}
        query = {}

        def __init__(self):
            self.app = {pwa_app.PWA_STATE: pwa_app._create_pwa_state()}

        def __getitem__(self, key):
            assert key == "request_id"
            return "ws.post-upgrade"

    websocket = FailingHandshakeWebSocket()
    monkeypatch.setattr(pwa_app.web, "WebSocketResponse", lambda **_kwargs: websocket)
    request = Request()

    response = await pwa_app.realtime(request)

    assert response is websocket
    assert websocket.closed is True
    assert request.app[pwa_app.PWA_STATE]["websockets"]["student"] == set()


@pytest.mark.asyncio
async def test_invalidation_can_be_scoped_to_one_audience(client):
    student = await client.ws_connect("/student/ws")
    staff = await client.ws_connect("/staff/ws")
    assert (await student.receive_json())["type"] == "connected"
    assert (await staff.receive_json())["type"] == "connected"

    await client.app[pwa_app.PWA_BROKER].publish(
        "pwa_invalidate",
        {
            "resources": ["review-queue"],
            "reason": "submission-updated",
            "audience": "staff",
        },
    )
    staff_event = await staff.receive_json()
    assert staff_event["type"] == "invalidate"
    assert staff_event["audience"] == "staff"
    assert staff_event["cursor"] == 1

    await student.send_json({"type": "ping"})
    student_pong = await student.receive_json()
    assert student_pong["type"] == "pong"
    assert student_pong["cursor"] == 0

    await client.app[pwa_app.PWA_BROKER].publish(
        "pwa_invalidate",
        {"resources": ["lesson:42"], "reason": "lesson-published"},
    )
    assert (await student.receive_json())["cursor"] == 1
    assert (await staff.receive_json())["cursor"] == 2
    await student.close()
    await staff.close()


@pytest.mark.asyncio
async def test_concurrent_invalidations_are_ordered_per_socket(client):
    class BackpressuredSocket:
        closed = False

        def __init__(self):
            self.first_send_started = asyncio.Event()
            self.release_first_send = asyncio.Event()
            self.in_send = False
            self.messages = []

        async def send_json(self, event):
            assert self.in_send is False, "concurrent writes reached one websocket"
            self.in_send = True
            try:
                if event["cursor"] == 1:
                    self.first_send_started.set()
                    await self.release_first_send.wait()
                self.messages.append(event)
            finally:
                self.in_send = False

    socket = BackpressuredSocket()
    client.app[pwa_app.PWA_STATE]["websockets"]["student"].add(socket)

    first = asyncio.create_task(
        pwa_app._broadcast(
            client.app, ["lesson:41"], "lesson-published", audience="student"
        )
    )
    await socket.first_send_started.wait()
    second = asyncio.create_task(
        pwa_app._broadcast(
            client.app, ["lesson:42"], "lesson-published", audience="student"
        )
    )
    await asyncio.sleep(0)
    assert socket.messages == []

    socket.release_first_send.set()
    await asyncio.gather(first, second)

    assert [event["cursor"] for event in socket.messages] == [1, 2]
    assert [event["resources"] for event in socket.messages] == [
        ["lesson:41"],
        ["lesson:42"],
    ]
    client.app[pwa_app.PWA_STATE]["websockets"]["student"].remove(socket)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"resources": []},
        {"resources": ["x"] * 129},
        {"resources": ["line\nbreak"]},
        {"resources": ["valid"], "reason": "INVALID REASON"},
        {"resources": ["valid"], "audience": "student\nforged-log"},
    ],
)
async def test_invalid_invalidation_payload_is_ignored_without_cursor_change(
    client, payload
):
    websocket = await client.ws_connect("/student/ws")
    assert (await websocket.receive_json())["cursor"] == 0

    await client.app[pwa_app.PWA_BROKER].publish("pwa_invalidate", payload)
    await websocket.send_json({"type": "ping"})
    pong = await websocket.receive_json()
    assert pong["type"] == "pong"
    assert pong["cursor"] == 0
    await websocket.close()


@pytest.mark.asyncio
async def test_local_object_storage_rejects_path_escape(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    await storage.put("submissions/photo.webp", b"image", "image/webp")
    assert await storage.get("submissions/photo.webp") == b"image"
    with pytest.raises(ValueError):
        await storage.put("../secret", b"nope", "text/plain")
    await storage.delete("submissions/photo.webp")


def test_seed_contract_is_json_serializable():
    seed = {"version": 1, "instance": config.pwa_instance, "fixture": "prototype-week"}
    assert json.loads(json.dumps(seed)) == seed
