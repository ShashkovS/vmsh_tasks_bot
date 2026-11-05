"""Strict cross-worker control tests for authenticated PWA sockets."""

from __future__ import annotations

from typing import Any

import pytest

from apps.pwa_api.realtime_control import (
    NATS_PWA_SESSION_CONTROL,
    RealtimeControlScope,
    RealtimeSessionController,
    parse_realtime_control_event,
)
from apps.pwa_api.websocket_sessions import WebSocketSessionRegistry
from helpers.nats_brocker import InProcessBroker


SESSION_A = "a" * 32
SESSION_B = "b" * 32
ACCOUNT_A = "account-student-a"
ACCOUNT_B = "account-student-b"


class FakeSocket:
    def __init__(self) -> None:
        self.closed = False
        self.messages: list[Any] = []
        self.close_calls: list[tuple[int, bytes]] = []

    async def send_json(self, data: Any) -> None:
        self.messages.append(data)

    async def close(self, *, code: int, message: bytes) -> bool:
        self.close_calls.append((code, message))
        self.closed = True
        return True


class FailingPublishBroker(InProcessBroker):
    async def publish(self, topic: str, payload: Any) -> None:
        del topic, payload
        raise RuntimeError("sensitive-target-a/transport-details")


async def _register(
    registry: WebSocketSessionRegistry,
    socket: FakeSocket,
    *,
    session: str = SESSION_A,
    account: str = ACCOUNT_A,
) -> None:
    await registry.register(
        socket,
        audience="student",
        account_public_id=account,
        session_public_id=session,
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {
            "version": 2,
            "type": "auth.close",
            "audience": "student",
            "scope": "session",
            "targetId": SESSION_A,
        },
        {
            "version": True,
            "type": "auth.close",
            "audience": "student",
            "scope": "session",
            "targetId": SESSION_A,
        },
        {
            "version": 1,
            "type": "auth.close",
            "audience": "unknown",
            "scope": "session",
            "targetId": SESSION_A,
        },
        {
            "version": 1,
            "type": "auth.close",
            "audience": "student",
            "scope": "session",
            "targetId": "not-a-session",
        },
        {
            "version": 1,
            "type": "auth.close",
            "audience": "student",
            "scope": "account",
            "targetId": "Account With Spaces",
        },
        {
            "version": 1,
            "type": "auth.close",
            "audience": "student",
            "scope": "session",
            "targetId": SESSION_A,
            "unexpected": True,
        },
    ],
)
def test_control_payload_is_exact_and_versioned(payload: Any) -> None:
    assert parse_realtime_control_event(payload) is None


def test_valid_session_and_account_payloads_are_typed() -> None:
    session = parse_realtime_control_event(
        {
            "version": 1,
            "type": "auth.close",
            "audience": "student",
            "scope": "session",
            "targetId": SESSION_A,
        }
    )
    account = parse_realtime_control_event(
        {
            "version": 1,
            "type": "auth.close",
            "audience": "staff",
            "scope": "account",
            "targetId": "account-staff-1",
        }
    )

    assert session is not None and session.scope is RealtimeControlScope.SESSION
    assert account is not None and account.scope is RealtimeControlScope.ACCOUNT


async def test_cross_worker_session_control_closes_every_tab_only_for_target() -> None:
    broker = InProcessBroker("realtime_control_cross_worker")
    await broker.setup()
    first_registry = WebSocketSessionRegistry()
    second_registry = WebSocketSessionRegistry()
    first = RealtimeSessionController(first_registry, broker)
    second = RealtimeSessionController(second_registry, broker)
    await broker.subscribe(NATS_PWA_SESSION_CONTROL, first.handle_broker_payload)
    await broker.subscribe(NATS_PWA_SESSION_CONTROL, second.handle_broker_payload)

    local_tab = FakeSocket()
    remote_tab_one = FakeSocket()
    remote_tab_two = FakeSocket()
    other_session = FakeSocket()
    await _register(first_registry, local_tab)
    await _register(second_registry, remote_tab_one)
    await _register(second_registry, remote_tab_two)
    await _register(second_registry, other_session, session=SESSION_B)

    report = await first.close_session(
        audience="student",
        session_public_id=SESSION_A,
    )

    assert report.local.selected == report.local.succeeded == 1
    assert report.published is True
    assert local_tab.closed and remote_tab_one.closed and remote_tab_two.closed
    assert not other_session.closed
    await first_registry.shutdown()
    await second_registry.shutdown()
    await broker.disconnect()


async def test_cross_worker_account_control_closes_all_sessions() -> None:
    broker = InProcessBroker("realtime_control_account")
    await broker.setup()
    registry = WebSocketSessionRegistry()
    controller = RealtimeSessionController(registry, broker)
    await broker.subscribe(NATS_PWA_SESSION_CONTROL, controller.handle_broker_payload)
    first = FakeSocket()
    second = FakeSocket()
    another_account = FakeSocket()
    await _register(registry, first, session=SESSION_A)
    await _register(registry, second, session=SESSION_B)
    await _register(
        registry,
        another_account,
        session="c" * 32,
        account=ACCOUNT_B,
    )

    report = await controller.close_account(
        audience="student",
        account_public_id=ACCOUNT_A,
    )

    assert report.local.selected == report.local.succeeded == 2
    assert report.published is True
    assert first.closed and second.closed
    assert not another_account.closed
    await registry.shutdown()
    await broker.disconnect()


async def test_publish_failure_keeps_local_close_and_logs_no_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    broker = FailingPublishBroker("realtime_control_failure")
    await broker.setup()
    registry = WebSocketSessionRegistry()
    socket = FakeSocket()
    await _register(registry, socket)
    controller = RealtimeSessionController(registry, broker)

    with caplog.at_level("WARNING", logger="apps.pwa_api.realtime_control"):
        report = await controller.close_session(
            audience="student",
            session_public_id=SESSION_A,
        )

    assert report.local.succeeded == 1
    assert report.published is False
    assert socket.closed
    assert "sensitive-target" not in caplog.text
    assert "RuntimeError" not in caplog.text
    assert "authoritative revalidation remains active" in caplog.text
    await registry.shutdown()
    await broker.disconnect()


async def test_invalid_broker_event_never_closes_a_socket(
    caplog: pytest.LogCaptureFixture,
) -> None:
    broker = InProcessBroker("realtime_control_invalid")
    registry = WebSocketSessionRegistry()
    socket = FakeSocket()
    await _register(registry, socket)
    controller = RealtimeSessionController(registry, broker)

    with caplog.at_level("WARNING", logger="apps.pwa_api.realtime_control"):
        await controller.handle_broker_payload(
            {
                "version": 1,
                "type": "auth.close",
                "audience": "student",
                "scope": "session",
                "targetId": SESSION_A,
                "overbroad": "all",
            }
        )

    assert not socket.closed
    assert await registry.connection_count() == 1
    assert SESSION_A not in caplog.text
    await registry.shutdown()
