from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from aiohttp import web
from nats.errors import ConnectionClosedError

from apps import pwa_app
from helpers.config import Config
from helpers.nats_brocker import (
    BrokerDeliveryError,
    BrokerStateError,
    InProcessBroker,
    JsonPayloadError,
    NATS,
    NatsBroker,
    SubjectError,
    decode_json_payload,
    encode_json_payload,
)
from main import RUNTIME_CONFIG


@pytest.mark.parametrize(
    "payload",
    [
        {1: "non-string-key"},
        {"tuple": (1, 2)},
        {"when": datetime(2026, 7, 27)},
        {"number": float("nan")},
        {"number": float("inf")},
        {"number": 2**64},
    ],
)
def test_json_payload_boundary_rejects_values_real_nats_cannot_preserve(payload):
    with pytest.raises(JsonPayloadError):
        encode_json_payload(payload)


def test_json_payload_boundary_rejects_invalid_wire_bytes():
    with pytest.raises(JsonPayloadError, match="not valid JSON"):
        decode_json_payload(b"not-json")


@pytest.mark.parametrize(
    "prefix, topic",
    [
        ("vmshpwa_agent.*", "invalidate"),
        ("vmshpwa agent", "invalidate"),
        ("vmshpwa_agent", ">"),
        ("vmshpwa_agent", "invalid topic"),
    ],
)
@pytest.mark.asyncio
async def test_subject_wildcards_and_scope_escape_are_rejected(prefix, topic):
    if prefix != "vmshpwa_agent":
        with pytest.raises(SubjectError):
            InProcessBroker(prefix)
        return

    broker = InProcessBroker(prefix)
    await broker.setup()
    with pytest.raises(SubjectError):
        await broker.publish(topic, {"ok": True})


@pytest.mark.asyncio
async def test_in_process_prefixes_are_isolated_and_payload_is_cloned():
    agent = InProcessBroker("vmshpwa_agent_test")
    human = InProcessBroker("vmshpwa_human_test")
    await agent.setup()
    await human.setup()
    agent_received = []
    human_received = []

    async def receive_agent(payload):
        agent_received.append(payload)

    async def receive_human(payload):
        human_received.append(payload)

    await agent.subscribe("pwa_invalidate", receive_agent)
    await human.subscribe("pwa_invalidate", receive_human)

    payload = {"resources": ["lesson:42"], "reason": "synthetic"}
    await agent.publish("pwa_invalidate", payload)

    assert agent_received == [payload]
    assert agent_received[0] is not payload
    assert human_received == []


@pytest.mark.asyncio
async def test_in_process_fanout_starts_subscribers_concurrently():
    broker = InProcessBroker("vmshpwa_agent_concurrency")
    await broker.setup()
    both_started = asyncio.Event()
    release = asyncio.Event()
    started = 0

    async def subscriber(_payload):
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await release.wait()

    await broker.subscribe("pwa_invalidate", subscriber)
    await broker.subscribe("pwa_invalidate", subscriber)
    publishing = asyncio.create_task(
        broker.publish("pwa_invalidate", {"resources": ["lesson:42"]})
    )

    await asyncio.wait_for(both_started.wait(), timeout=1)
    release.set()
    await publishing
    assert started == 2


@pytest.mark.asyncio
async def test_each_in_process_subscriber_receives_its_own_decoded_value():
    broker = InProcessBroker("vmshpwa_agent_payload_isolation")
    await broker.setup()
    received = []

    async def subscriber(payload):
        received.append(payload)

    await broker.subscribe("pwa_invalidate", subscriber)
    await broker.subscribe("pwa_invalidate", subscriber)
    await broker.publish("pwa_invalidate", {"resources": ["lesson:42"]})

    assert received[0] == received[1]
    assert received[0] is not received[1]
    assert received[0]["resources"] is not received[1]["resources"]


@pytest.mark.asyncio
async def test_failing_subscriber_does_not_cancel_other_fanout_targets():
    broker = InProcessBroker("vmshpwa_agent_failures")
    await broker.setup()
    completed = []

    async def failing(_payload):
        raise RuntimeError("synthetic subscriber failure")

    async def succeeding(_payload):
        await asyncio.sleep(0)
        completed.append(True)

    await broker.subscribe("pwa_invalidate", failing)
    await broker.subscribe("pwa_invalidate", succeeding)

    with pytest.raises(BrokerDeliveryError) as captured:
        await broker.publish("pwa_invalidate", {"resources": ["lesson:42"]})
    assert completed == [True]
    assert isinstance(captured.value.errors[0], RuntimeError)


@pytest.mark.asyncio
async def test_in_process_setup_and_disconnect_are_idempotent():
    broker = InProcessBroker("vmshpwa_agent_lifecycle")
    await broker.setup()
    await broker.setup()
    await broker.disconnect()
    await broker.disconnect()

    with pytest.raises(BrokerStateError):
        await broker.publish("pwa_invalidate", {"ok": True})

    await broker.setup()
    assert broker.active
    await broker.disconnect()


@pytest.mark.asyncio
async def test_subscribe_rejects_sync_callback_before_first_publish():
    broker = InProcessBroker("vmshpwa_agent_callback")
    await broker.setup()

    with pytest.raises(TypeError, match="async def"):
        await broker.subscribe("pwa_invalidate", [].append)


class FakeNatsClient:
    def __init__(
        self,
        *,
        closed: bool = False,
        drain_error=None,
        close_error=None,
    ):
        self.is_closed = closed
        self.is_draining = False
        self.is_connected = not closed
        self.drain_error = drain_error
        self.close_error = close_error
        self.drain_calls = 0
        self.close_calls = 0
        self.flush_calls = 0

    async def drain(self):
        self.drain_calls += 1
        self.is_draining = True
        if self.drain_error is not None:
            raise self.drain_error
        self.is_closed = True

    async def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        self.is_connected = False
        self.is_draining = False
        self.is_closed = True

    async def flush(self, *, timeout):
        assert timeout == 1.0
        self.flush_calls += 1


@pytest.mark.asyncio
async def test_nats_broker_connect_and_disconnect_are_idempotent():
    client = FakeNatsClient()
    connect_calls = []

    async def connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return client

    broker = NatsBroker("vmshpwa_agent_nats_lifecycle", connect=connect)
    await broker.setup("nats://127.0.0.1:4222")
    await broker.setup("nats://127.0.0.1:4222")
    assert broker.active
    assert len(connect_calls) == 1

    await broker.disconnect()
    await broker.disconnect()
    assert client.drain_calls == 1
    assert not broker.active


@pytest.mark.asyncio
async def test_nats_broker_treats_unexpected_closed_client_as_inactive():
    client = FakeNatsClient()

    async def connect(*_args, **_kwargs):
        return client

    broker = NatsBroker("vmshpwa_agent_nats_closed", connect=connect)
    await broker.setup("nats://127.0.0.1:4222")
    client.is_closed = True
    client.is_connected = False

    assert not broker.active
    with pytest.raises(BrokerStateError, match="not connected"):
        await broker.publish("probe", {"ok": True})
    await broker.disconnect()
    assert client.drain_calls == 0


@pytest.mark.asyncio
async def test_nats_broker_treats_reconnecting_client_as_temporarily_unavailable():
    client = FakeNatsClient()

    async def connect(*_args, **_kwargs):
        return client

    broker = NatsBroker("vmshpwa_agent_nats_reconnect", connect=connect)
    await broker.setup("nats://127.0.0.1:4222")
    client.is_connected = False

    assert not broker.active
    with pytest.raises(BrokerStateError, match="not connected"):
        await broker.publish("probe", {"ok": True})

    await broker.disconnect()
    assert client.drain_calls == 0
    assert client.close_calls == 1
    assert broker._client is None


@pytest.mark.asyncio
async def test_pwa_startup_releases_broker_if_subscription_fails():
    class FailingSubscriptionBroker(InProcessBroker):
        async def subscribe(self, topic, callback):
            await super().subscribe(topic, callback)
            raise RuntimeError("synthetic subscription failure")

    broker = FailingSubscriptionBroker("vmshpwa_agent_failed_startup")
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e", config_name="vmshpwa_agent_failed_startup"
    )
    pwa_app.configure(app, broker=broker)

    with pytest.raises(RuntimeError, match="subscription failure"):
        await pwa_app.on_startup(app)
    assert not broker.active


@pytest.mark.asyncio
async def test_pwa_startup_releases_broker_if_setup_partially_fails():
    class PartiallyFailingSetupBroker(InProcessBroker):
        async def setup(self, server_url=None):
            await super().setup(server_url)
            raise RuntimeError("synthetic setup failure")

    broker = PartiallyFailingSetupBroker("vmshpwa_agent_failed_setup")
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e", config_name="vmshpwa_agent_failed_setup"
    )
    pwa_app.configure(app, broker=broker)

    with pytest.raises(RuntimeError, match="setup failure"):
        await pwa_app.on_startup(app)
    assert not broker.active


@pytest.mark.asyncio
async def test_disconnect_absorbs_connection_closed_race_and_stays_idempotent():
    client = FakeNatsClient(drain_error=ConnectionClosedError())

    async def connect(*_args, **_kwargs):
        return client

    broker = NatsBroker("vmshpwa_agent_nats_close_race", connect=connect)
    await broker.setup("nats://127.0.0.1:4222")
    await broker.disconnect()
    await broker.disconnect()
    assert client.drain_calls == 1
    assert client.close_calls == 1


@pytest.mark.asyncio
async def test_disconnect_keeps_client_reference_when_drain_and_close_both_fail():
    client = FakeNatsClient(
        drain_error=RuntimeError("synthetic drain failure"),
        close_error=RuntimeError("synthetic close failure"),
    )

    async def connect(*_args, **_kwargs):
        return client

    broker = NatsBroker("vmshpwa_agent_nats_double_failure", connect=connect)
    await broker.setup("nats://127.0.0.1:4222")

    with pytest.raises(BaseExceptionGroup) as captured:
        await broker.disconnect()
    assert len(captured.value.exceptions) == 2
    assert broker._client is client


@pytest.mark.asyncio
async def test_nats_ready_flushes_subscription_registration():
    client = FakeNatsClient()

    async def connect(*_args, **_kwargs):
        return client

    broker = NatsBroker("vmshpwa_agent_nats_ready", connect=connect)
    await broker.setup("nats://127.0.0.1:4222")
    await broker.ready()
    assert client.flush_calls == 1
    await broker.disconnect()


@pytest.mark.asyncio
async def test_legacy_disconnect_is_idempotent_after_unexpected_close():
    broker = NATS("legacy_test")
    client = FakeNatsClient(closed=True)
    broker.nc = client

    assert not broker.nats_is_working
    await broker.disconnect()
    await broker.disconnect()
    assert client.drain_calls == 0


@pytest.mark.asyncio
async def test_legacy_disconnect_forces_close_while_reconnecting():
    broker = NATS("legacy_reconnecting")
    client = FakeNatsClient()
    client.is_connected = False
    broker.nc = client

    await broker.disconnect()

    assert client.drain_calls == 0
    assert client.close_calls == 1
    assert broker.nc is None


@pytest.mark.asyncio
async def test_legacy_disconnect_retains_client_after_double_failure():
    broker = NATS("legacy_double_failure")
    client = FakeNatsClient(
        drain_error=RuntimeError("synthetic legacy drain failure"),
        close_error=RuntimeError("synthetic legacy close failure"),
    )
    broker.nc = client

    with pytest.raises(BaseExceptionGroup) as captured:
        await broker.disconnect()

    assert len(captured.value.exceptions) == 2
    assert broker.nc is client


@pytest.mark.asyncio
async def test_each_pwa_application_owns_and_disconnects_only_its_broker():
    first_broker = InProcessBroker("vmshpwa_agent_app_one")
    second_broker = InProcessBroker("vmshpwa_agent_app_two")
    first = web.Application()
    second = web.Application()
    first[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e", config_name="vmshpwa_agent_app_one"
    )
    second[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e", config_name="vmshpwa_agent_app_two"
    )
    pwa_app.configure(first, broker=first_broker)
    pwa_app.configure(second, broker=second_broker)
    first.freeze()
    second.freeze()
    await first.startup()
    await second.startup()

    await first.shutdown()
    assert not first_broker.active
    assert second_broker.active
    await second_broker.publish(
        pwa_app.NATS_PWA_INVALIDATE,
        {"resources": ["lesson:42"], "reason": "still-alive"},
    )

    await first.cleanup()
    await second.shutdown()
    await second.cleanup()
    assert not second_broker.active


@pytest.mark.asyncio
async def test_pwa_shutdown_closes_all_tracked_websockets_before_broker():
    class RecordingWebSocket:
        def __init__(self):
            self.closed = False
            self.close_args = None

        async def close(self, **kwargs):
            self.close_args = kwargs
            self.closed = True

    broker = InProcessBroker("vmshpwa_agent_shutdown")
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e", config_name="vmshpwa_agent_shutdown"
    )
    pwa_app.configure(app, broker=broker)
    await broker.setup()
    student = RecordingWebSocket()
    staff = RecordingWebSocket()
    app[pwa_app.PWA_STATE]["websockets"]["student"].add(student)
    app[pwa_app.PWA_STATE]["websockets"]["staff"].add(staff)

    await pwa_app.on_shutdown(app)

    assert student.closed and staff.closed
    assert student.close_args["code"] == pwa_app.WSCloseCode.GOING_AWAY
    assert staff.close_args["message"] == b"Server shutdown"
    assert not broker.active
    assert all(not sockets for sockets in app[pwa_app.PWA_STATE]["websockets"].values())


@pytest.mark.asyncio
async def test_slow_websocket_is_bounded_and_removed(monkeypatch):
    class SlowWebSocket:
        closed = False

        def __init__(self):
            self.close_calls = 0

        async def send_json(self, _event):
            await asyncio.Event().wait()

        async def close(self, **_kwargs):
            self.close_calls += 1
            self.closed = True

    monkeypatch.setattr(pwa_app, "WEBSOCKET_SEND_TIMEOUT_SECONDS", 0.01)
    app = web.Application()
    app[pwa_app.PWA_STATE] = {
        "cursors": {audience: 0 for audience in pwa_app.AUDIENCES},
        "websockets": {audience: set() for audience in pwa_app.AUDIENCES},
    }
    websocket = SlowWebSocket()
    app[pwa_app.PWA_STATE]["websockets"]["student"].add(websocket)

    await asyncio.wait_for(
        pwa_app._broadcast(app, ["lesson:42"], "lesson-published", "student"),
        timeout=0.2,
    )

    assert websocket not in app[pwa_app.PWA_STATE]["websockets"]["student"]
    assert websocket.close_calls == 1


@pytest.mark.asyncio
async def test_failed_websocket_close_remains_tracked_for_shutdown_retry(monkeypatch):
    class UnclosableWebSocket:
        closed = False

        async def send_json(self, _event):
            raise RuntimeError("synthetic send failure")

        async def close(self, **_kwargs):
            raise RuntimeError("synthetic close failure")

    monkeypatch.setattr(pwa_app, "WEBSOCKET_CLOSE_TIMEOUT_SECONDS", 0.01)
    app = web.Application()
    app[pwa_app.PWA_STATE] = {
        "cursors": {audience: 0 for audience in pwa_app.AUDIENCES},
        "websockets": {audience: set() for audience in pwa_app.AUDIENCES},
    }
    websocket = UnclosableWebSocket()
    connections = app[pwa_app.PWA_STATE]["websockets"]["student"]
    connections.add(websocket)

    await pwa_app._broadcast(app, ["lesson:42"], "lesson-published", "student")

    assert websocket in connections
