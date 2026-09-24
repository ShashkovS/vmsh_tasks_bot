import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from aiohttp import WSCloseCode

from apps.pwa_api.websocket_sessions import (
    SessionRevalidationStatus,
    WebSocketSessionAlreadyClosedError,
    WebSocketSessionIdentity,
    WebSocketSessionRegistry,
)


class FakeWebSocket:
    def __init__(
        self,
        *,
        operation_delay: float = 0,
        send_error: Exception | None = None,
        close_error: Exception | None = None,
        close_changes_state: bool = True,
        activity: "ActivityProbe | None" = None,
    ) -> None:
        self.closed = False
        self.operation_delay = operation_delay
        self.send_error = send_error
        self.close_error = close_error
        self.close_changes_state = close_changes_state
        self.activity = activity
        self.messages: list[Any] = []
        self.close_calls: list[tuple[int, bytes]] = []
        self._active_operations = 0
        self.max_active_operations = 0

    async def send_json(self, data: Any) -> None:
        await self._operate(lambda: self._send(data))

    async def close(self, *, code: int, message: bytes) -> bool:
        await self._operate(lambda: self._close(code, message))
        return self.closed

    async def _operate(self, operation: Callable[[], Awaitable[None]]) -> None:
        self._active_operations += 1
        self.max_active_operations = max(
            self.max_active_operations, self._active_operations
        )
        if self.activity is not None:
            self.activity.enter()
        try:
            if self.operation_delay:
                await asyncio.sleep(self.operation_delay)
            await operation()
        finally:
            if self.activity is not None:
                self.activity.exit()
            self._active_operations -= 1

    async def _send(self, data: Any) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.messages.append(data)

    async def _close(self, code: int, message: bytes) -> None:
        self.close_calls.append((code, message))
        if self.close_error is not None:
            raise self.close_error
        if self.close_changes_state:
            self.closed = True


class ActivityProbe:
    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0

    def enter(self) -> None:
        self.active += 1
        self.maximum = max(self.maximum, self.active)

    def exit(self) -> None:
        self.active -= 1


class GatedSendWebSocket(FakeWebSocket):
    def __init__(self) -> None:
        super().__init__()
        self.send_started = asyncio.Event()
        self.release_send = asyncio.Event()

    async def send_json(self, data: Any) -> None:
        self.send_started.set()
        await self.release_send.wait()
        await super().send_json(data)


async def register(
    registry: WebSocketSessionRegistry,
    socket: FakeWebSocket,
    *,
    audience: str = "student",
    account: str = "account-1",
    session: str = "session-1",
) -> WebSocketSessionIdentity:
    return await registry.register(
        socket,
        audience=audience,
        account_public_id=account,
        session_public_id=session,
    )


async def test_registration_is_idempotent_only_for_the_same_identity() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()

    identity = await register(registry, socket)
    assert await register(registry, socket) == identity
    assert await registry.connection_count() == 1

    with pytest.raises(ValueError, match="another identity"):
        await register(registry, socket, session="session-2")

    with pytest.raises(ValueError, match="unknown PWA audience"):
        await register(registry, FakeWebSocket(), audience="unknown")

    closed = FakeWebSocket()
    closed.closed = True
    with pytest.raises(ValueError, match="closed websocket"):
        await register(registry, closed)


async def test_one_session_cannot_be_registered_for_two_accounts() -> None:
    registry = WebSocketSessionRegistry()
    await register(registry, FakeWebSocket(), account="account-1")

    with pytest.raises(ValueError, match="another account"):
        await register(registry, FakeWebSocket(), account="account-2")


async def test_close_before_registration_leaves_a_session_tombstone() -> None:
    registry = WebSocketSessionRegistry()

    report = await registry.close_session(
        audience="student",
        session_public_id="session-closed-before-register",
    )

    assert report.selected == 0
    with pytest.raises(WebSocketSessionAlreadyClosedError):
        await register(
            registry,
            FakeWebSocket(),
            session="session-closed-before-register",
        )


async def test_pending_handshake_is_not_routable_until_initial_frame() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()
    await registry.register_pending(
        socket,
        audience="student",
        account_public_id="account-1",
        session_public_id="session-pending",
    )

    before = await registry.send_to_audience(
        audience="student",
        payload={"type": "invalidate", "cursor": 1},
    )

    async def active(
        _identity: WebSocketSessionIdentity,
    ) -> SessionRevalidationStatus:
        return SessionRevalidationStatus.VALID

    validated = await registry.revalidate_pending(
        socket,
        revalidate=active,
    )
    status = await registry.activate_with_initial(
        socket,
        payload={"type": "connected", "cursor": 1},
    )
    after = await registry.send_to_audience(
        audience="student",
        payload={"type": "invalidate", "cursor": 2},
    )

    assert before.selected == 0
    assert validated is SessionRevalidationStatus.VALID
    assert status is SessionRevalidationStatus.VALID
    assert after.succeeded == 1
    assert socket.messages == [
        {"type": "connected", "cursor": 1},
        {"type": "invalidate", "cursor": 2},
    ]


async def test_peer_disconnect_before_initial_frame_is_not_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket(send_error=ConnectionResetError("peer closed"))
    await registry.register_pending(
        socket,
        audience="student",
        account_public_id="account-1",
        session_public_id="session-peer-closed",
    )

    async def active(
        _identity: WebSocketSessionIdentity,
    ) -> SessionRevalidationStatus:
        return SessionRevalidationStatus.VALID

    assert (
        await registry.revalidate_pending(socket, revalidate=active)
        is SessionRevalidationStatus.VALID
    )
    with caplog.at_level("WARNING", logger="apps.pwa_api.websocket_sessions"):
        status = await registry.activate_with_initial(
            socket,
            payload={"type": "connected", "cursor": 1},
        )

    assert status is SessionRevalidationStatus.CORRUPT
    assert "Failed to send" not in caplog.text
    assert socket.closed
    assert await registry.connection_count() == 0


async def test_close_session_is_scoped_by_audience_and_keeps_other_sessions() -> None:
    registry = WebSocketSessionRegistry()
    student_first = FakeWebSocket()
    student_second = FakeWebSocket()
    family_same_session_id = FakeWebSocket()
    other_session = FakeWebSocket()
    await register(registry, student_first)
    await register(registry, student_second)
    await register(
        registry,
        family_same_session_id,
        audience="family",
        account="family-account",
    )
    await register(registry, other_session, session="session-2")

    report = await registry.close_session(
        audience="student", session_public_id="session-1"
    )

    assert report.selected == report.succeeded == 2
    assert report.failed == 0
    assert student_first.closed and student_second.closed
    assert not family_same_session_id.closed
    assert not other_session.closed
    assert await registry.connection_count() == 2


async def test_close_account_ends_all_of_its_sessions_only() -> None:
    registry = WebSocketSessionRegistry()
    first = FakeWebSocket()
    second = FakeWebSocket()
    another_account = FakeWebSocket()
    await register(registry, first, session="session-1")
    await register(registry, second, session="session-2")
    await register(
        registry,
        another_account,
        account="account-2",
        session="session-3",
    )

    report = await registry.close_account(
        audience="student", account_public_id="account-1"
    )

    assert report == type(report)(selected=2, succeeded=2, failed=0)
    assert first.closed and second.closed
    assert not another_account.closed
    assert await registry.connection_count() == 1


async def test_closed_sockets_are_pruned_and_unregister_is_repeatable() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()
    await register(registry, socket)
    socket.closed = True

    assert await registry.prune_closed() == 1
    assert await registry.prune_closed() == 0
    assert not await registry.unregister(socket)
    assert await registry.connection_count() == 0


async def test_failed_close_stays_tracked_until_transport_reports_closed() -> None:
    registry = WebSocketSessionRegistry(operation_timeout_seconds=0.01)
    socket = FakeWebSocket(close_changes_state=False)
    await register(registry, socket)

    report = await registry.close_session(
        audience="student", session_public_id="session-1"
    )

    assert report.failed == 1
    assert await registry.connection_count() == 1
    socket.closed = True
    assert await registry.prune_closed() == 1


async def test_hung_close_is_bounded_and_remains_available_for_retry() -> None:
    registry = WebSocketSessionRegistry(operation_timeout_seconds=0.01)
    socket = FakeWebSocket(operation_delay=1, close_changes_state=False)
    await register(registry, socket)

    report = await asyncio.wait_for(
        registry.close_session(audience="student", session_public_id="session-1"),
        timeout=0.1,
    )

    assert report.failed == 1
    assert await registry.connection_count() == 1


async def test_send_failure_attempts_close_and_removes_closed_socket() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket(send_error=RuntimeError("transport broke"))
    await register(registry, socket)

    report = await registry.send_to_session(
        audience="student",
        session_public_id="session-1",
        payload={"type": "invalidate"},
    )

    assert report.failed == 1
    assert socket.close_calls == [(WSCloseCode.GOING_AWAY, b"Realtime delivery failed")]
    assert await registry.connection_count() == 0


async def test_fanout_is_bounded_and_operations_on_one_socket_are_serialized() -> None:
    probe = ActivityProbe()
    registry = WebSocketSessionRegistry(max_concurrency=2)
    sockets = [FakeWebSocket(operation_delay=0.01, activity=probe) for _ in range(6)]
    for index, socket in enumerate(sockets):
        await register(registry, socket, session=f"session-{index}")

    report = await registry.send_to_account(
        audience="student",
        account_public_id="account-1",
        payload={"type": "public-state-changed"},
    )

    assert report.succeeded == len(sockets)
    assert probe.maximum == 2

    one_socket = sockets[0]
    await asyncio.gather(
        registry.send_to_session(
            audience="student",
            session_public_id="session-0",
            payload={"sequence": 1},
        ),
        registry.send_to_session(
            audience="student",
            session_public_id="session-0",
            payload={"sequence": 2},
        ),
    )
    assert one_socket.max_active_operations == 1


async def test_concurrent_close_does_not_close_the_same_socket_twice() -> None:
    registry = WebSocketSessionRegistry(max_concurrency=2)
    socket = FakeWebSocket(operation_delay=0.01)
    await register(registry, socket)

    await asyncio.gather(
        registry.close_session(audience="student", session_public_id="session-1"),
        registry.close_session(audience="student", session_public_id="session-1"),
    )

    assert len(socket.close_calls) == 1


async def test_handler_send_and_session_close_share_one_transport_lock() -> None:
    registry = WebSocketSessionRegistry(max_concurrency=2)
    socket = FakeWebSocket(operation_delay=0.01)
    await register(registry, socket)

    sent, closed = await asyncio.gather(
        registry.send_to_connection(socket, payload={"type": "connected"}),
        registry.close_session(
            audience="student",
            session_public_id="session-1",
        ),
    )

    assert sent.selected == 1
    assert closed.selected == 1
    assert socket.max_active_operations == 1
    assert socket.closed
    assert await registry.connection_count() == 0


async def test_send_waiting_for_capacity_is_suppressed_after_close_wins() -> None:
    registry = WebSocketSessionRegistry(max_concurrency=1)
    blocker = GatedSendWebSocket()
    target = FakeWebSocket()
    await register(registry, blocker, session="blocking-session")
    await register(registry, target, session="target-session")

    blocking_send = asyncio.create_task(
        registry.send_to_session(
            audience="student",
            session_public_id="blocking-session",
            payload={"type": "blocker"},
        )
    )
    await asyncio.wait_for(blocker.send_started.wait(), timeout=1)

    queued_send = asyncio.create_task(
        registry.send_to_session(
            audience="student",
            session_public_id="target-session",
            payload={"type": "must-not-arrive"},
        )
    )
    await asyncio.sleep(0)
    close = asyncio.create_task(
        registry.close_session(
            audience="student",
            session_public_id="target-session",
        )
    )
    # close_session marks the record non-routable before it queues for the
    # occupied transport slot. The already-selected send must recheck this.
    await asyncio.sleep(0)
    blocker.release_send.set()

    await asyncio.gather(blocking_send, queued_send, close)

    assert target.messages == []
    assert target.closed is True


async def test_registry_transmits_payload_without_cursor_interpretation() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()
    await register(registry, socket)
    payload = {"type": "resync-required", "cursor": -999, "custom": "opaque"}

    await registry.send_to_session(
        audience="student",
        session_public_id="session-1",
        payload=payload,
    )

    assert socket.messages == [payload]
    assert socket.messages[0] is not payload


async def test_revalidation_checks_each_session_once_and_closes_invalid() -> None:
    registry = WebSocketSessionRegistry()
    valid_first = FakeWebSocket()
    valid_second = FakeWebSocket()
    revoked = FakeWebSocket()
    expired = FakeWebSocket()
    corrupt = FakeWebSocket()
    await register(registry, valid_first, session="valid")
    await register(registry, valid_second, session="valid")
    await register(registry, revoked, session="revoked")
    await register(registry, expired, session="expired")
    await register(registry, corrupt, session="corrupt")
    calls: list[str] = []
    statuses = {
        "valid": SessionRevalidationStatus.VALID,
        "revoked": SessionRevalidationStatus.REVOKED,
        "expired": SessionRevalidationStatus.EXPIRED,
        "corrupt": SessionRevalidationStatus.CORRUPT,
    }

    async def revalidate(
        identity: WebSocketSessionIdentity,
    ) -> SessionRevalidationStatus:
        calls.append(identity.session_public_id)
        return statuses[identity.session_public_id]

    report = await registry.run_revalidation_once(revalidate)

    assert sorted(calls) == sorted(statuses)
    assert report.selected == report.succeeded == 3
    assert not valid_first.closed and not valid_second.closed
    assert revoked.close_calls[-1][1] == b"Session revoked"
    assert expired.close_calls[-1][1] == b"Session expired"
    assert corrupt.close_calls[-1][1] == b"Session unavailable"
    assert await registry.connection_count() == 2


@pytest.mark.parametrize(
    "revalidator",
    [
        pytest.param(lambda _identity: _return_invalid_status(), id="bad-status"),
        pytest.param(lambda _identity: _raise_revalidation_error(), id="error"),
    ],
)
async def test_invalid_or_failed_revalidation_fails_closed(
    revalidator: Callable[[WebSocketSessionIdentity], Awaitable[Any]],
) -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()
    await register(registry, socket)

    report = await registry.run_revalidation_once(revalidator)

    assert report.succeeded == 1
    assert socket.close_calls[-1][1] == b"Session unavailable"


async def test_warning_logs_do_not_include_callback_or_transport_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sentinel = "account-secret-179/session-secret-179"
    registry = WebSocketSessionRegistry()
    callback_socket = FakeWebSocket()
    send_socket = FakeWebSocket(send_error=RuntimeError(sentinel))
    close_socket = FakeWebSocket(
        close_error=RuntimeError(sentinel), close_changes_state=False
    )
    await register(registry, callback_socket, session="callback-session")
    await register(registry, send_socket, session="send-session")
    await register(registry, close_socket, session="close-session")

    async def leaking_revalidator(
        identity: WebSocketSessionIdentity,
    ) -> SessionRevalidationStatus:
        if identity.session_public_id == "callback-session":
            raise RuntimeError(sentinel)
        return SessionRevalidationStatus.VALID

    with caplog.at_level("WARNING", logger="apps.pwa_api.websocket_sessions"):
        await registry.run_revalidation_once(leaking_revalidator)
        await registry.send_to_session(
            audience="student",
            session_public_id="send-session",
            payload={"type": "test"},
        )
        await registry.close_session(
            audience="student", session_public_id="close-session"
        )

    assert sentinel not in caplog.text
    assert "RuntimeError" not in caplog.text
    assert "authoritative revalidation failed" in caplog.text
    assert "Failed to send" in caplog.text
    assert "Failed to close" in caplog.text


async def _return_invalid_status() -> str:
    return "unexpected"


async def _raise_revalidation_error() -> SessionRevalidationStatus:
    raise RuntimeError("authoritative storage failed")


async def test_periodic_revalidation_runs_and_can_be_stopped() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()
    await register(registry, socket)
    checked = asyncio.Event()

    async def revalidate(
        _identity: WebSocketSessionIdentity,
    ) -> SessionRevalidationStatus:
        checked.set()
        return SessionRevalidationStatus.VALID

    task = registry.start_revalidation(revalidate, interval_seconds=0.01)
    await asyncio.wait_for(checked.wait(), timeout=0.2)
    await registry.stop_revalidation()

    assert task.done()
    assert not socket.closed


async def test_shutdown_stops_checker_closes_all_and_rejects_registration() -> None:
    registry = WebSocketSessionRegistry()
    first = FakeWebSocket()
    second = FakeWebSocket()
    await register(registry, first)
    await register(
        registry,
        second,
        audience="staff",
        account="staff-account",
        session="staff-session",
    )

    async def always_valid(
        _identity: WebSocketSessionIdentity,
    ) -> SessionRevalidationStatus:
        return SessionRevalidationStatus.VALID

    registry.start_revalidation(always_valid, interval_seconds=10)
    report = await registry.shutdown()

    assert report.succeeded == 2
    assert first.close_calls[-1] == (
        WSCloseCode.GOING_AWAY,
        b"Server shutdown",
    )
    assert await registry.connection_count() == 0
    with pytest.raises(RuntimeError, match="shut down"):
        await register(registry, FakeWebSocket())


def test_configuration_and_close_message_validation() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        WebSocketSessionRegistry(max_concurrency=0)
    with pytest.raises(ValueError, match="operation_timeout"):
        WebSocketSessionRegistry(operation_timeout_seconds=0)
    with pytest.raises(ValueError, match="revalidation_timeout"):
        WebSocketSessionRegistry(revalidation_timeout_seconds=0)


async def test_too_long_close_message_is_rejected_before_transport_use() -> None:
    registry = WebSocketSessionRegistry()
    socket = FakeWebSocket()
    await register(registry, socket)

    with pytest.raises(ValueError, match="at most 123 bytes"):
        await registry.close_session(
            audience="student",
            session_public_id="session-1",
            message=b"x" * 124,
        )
    assert not socket.close_calls
