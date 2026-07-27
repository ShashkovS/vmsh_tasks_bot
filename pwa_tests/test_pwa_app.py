import json

import pytest

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
async def test_pwa_api_has_baseline_security_headers(client):
    response = await client.get("/family/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


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
