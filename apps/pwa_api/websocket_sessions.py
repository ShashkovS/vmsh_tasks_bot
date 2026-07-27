"""Authenticated WebSocket connection lifecycle for the PWA audiences.

This module deliberately owns only process-local connection routing.  SQLite
remains authoritative for session state and application data, while reconnect
always requires an API refetch.  In particular, this registry does not retain
or interpret a client cursor as durable event history.

See ``adr/0003-pwa-authentication-cryptography-and-sessions.md`` and
``vmshpwa/docs/realtime-offline-and-notifications.md``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from aiohttp import WSCloseCode

logger = logging.getLogger(__name__)

DEFAULT_AUDIENCES = frozenset({"student", "family", "staff"})
DEFAULT_OPERATION_TIMEOUT_SECONDS = 5.0
DEFAULT_REVALIDATION_TIMEOUT_SECONDS = 5.0
DEFAULT_REVALIDATION_INTERVAL_SECONDS = 60.0
DEFAULT_MAX_CONCURRENCY = 32
MAX_CLOSE_MESSAGE_BYTES = 123


class WebSocketLike(Protocol):
    """The aiohttp WebSocket surface used by the registry."""

    @property
    def closed(self) -> bool: ...

    async def send_json(self, data: Any) -> None: ...

    async def close(self, *, code: int, message: bytes) -> bool: ...


@dataclass(frozen=True, slots=True)
class WebSocketSessionIdentity:
    """Server-authenticated identity attached to one or more sockets."""

    audience: str
    account_public_id: str
    session_public_id: str


class SessionRevalidationStatus(StrEnum):
    """Authoritative result returned by the injected session repository."""

    VALID = "valid"
    REVOKED = "revoked"
    EXPIRED = "expired"
    CORRUPT = "corrupt"


SessionRevalidator = Callable[
    [WebSocketSessionIdentity], Awaitable[SessionRevalidationStatus]
]


@dataclass(frozen=True, slots=True)
class WebSocketOperationReport:
    """Aggregate result without exposing account or session identifiers."""

    selected: int
    succeeded: int
    failed: int


@dataclass(slots=True)
class _RegisteredConnection:
    socket: WebSocketLike
    identity: WebSocketSessionIdentity
    io_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    state_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    routable: bool = True
    authoritatively_validated: bool = True
    closing: bool = False


class WebSocketSessionAlreadyClosedError(RuntimeError):
    """A close command won the race with handshake registration."""


class WebSocketSessionRegistry:
    """Track and operate on authenticated sockets in one aiohttp worker.

    Callers must authenticate the handshake and check its exact browser Origin
    before ``register``.  A registration is process-local: logout/revoke should
    publish an owner-scoped control signal to every worker and invoke the
    matching close method there.  Long-lived sockets are additionally guarded
    by ``start_revalidation``.

    Send and close operations are bounded by both a concurrency limit and a
    per-operation timeout.  Per-socket serialization prevents a close racing a
    write.  A socket that fails to close remains tracked for shutdown or the
    next revalidation pass; closed sockets are removed eagerly.
    """

    def __init__(
        self,
        *,
        audiences: frozenset[str] = DEFAULT_AUDIENCES,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        operation_timeout_seconds: float = DEFAULT_OPERATION_TIMEOUT_SECONDS,
        revalidation_timeout_seconds: float = (DEFAULT_REVALIDATION_TIMEOUT_SECONDS),
    ) -> None:
        if not audiences or any(not audience for audience in audiences):
            raise ValueError("audiences must contain non-empty values")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if operation_timeout_seconds <= 0:
            raise ValueError("operation_timeout_seconds must be positive")
        if revalidation_timeout_seconds <= 0:
            raise ValueError("revalidation_timeout_seconds must be positive")

        self._audiences = audiences
        self._operation_timeout_seconds = operation_timeout_seconds
        self._revalidation_timeout_seconds = revalidation_timeout_seconds
        self._io_semaphore = asyncio.Semaphore(max_concurrency)
        self._revalidation_semaphore = asyncio.Semaphore(max_concurrency)
        self._registry_lock = asyncio.Lock()
        self._records: dict[int, _RegisteredConnection] = {}
        self._by_audience: dict[str, set[int]] = {
            audience: set() for audience in audiences
        }
        self._by_account: dict[tuple[str, str], set[int]] = {}
        self._by_session: dict[tuple[str, str], set[int]] = {}
        # Session identifiers are random and never reused.  Retaining a
        # process-local tombstone makes a close command linearizable with a
        # handshake that authenticated before the command but has not yet
        # registered.  SQLite revalidation remains the cross-worker authority.
        self._closed_sessions: set[tuple[str, str]] = set()
        self._revalidation_task: asyncio.Task[None] | None = None
        self._revalidation_stop = asyncio.Event()
        self._is_shutdown = False

    async def register(
        self,
        socket: WebSocketLike,
        *,
        audience: str,
        account_public_id: str,
        session_public_id: str,
    ) -> WebSocketSessionIdentity:
        """Attach an authenticated socket and make it immediately routable.

        Protocol adapters should use :meth:`register_pending` followed by
        :meth:`activate_with_initial` so no fan-out can precede their initial
        ``connected``/``resync-required`` frame.  Immediate registration stays
        available for already-established transports and focused registry use.
        """

        return await self._register(
            socket,
            audience=audience,
            account_public_id=account_public_id,
            session_public_id=session_public_id,
            routable=True,
        )

    async def register_pending(
        self,
        socket: WebSocketLike,
        *,
        audience: str,
        account_public_id: str,
        session_public_id: str,
    ) -> WebSocketSessionIdentity:
        """Register a handshake without exposing it to application fan-out."""

        return await self._register(
            socket,
            audience=audience,
            account_public_id=account_public_id,
            session_public_id=session_public_id,
            routable=False,
        )

    async def _register(
        self,
        socket: WebSocketLike,
        *,
        audience: str,
        account_public_id: str,
        session_public_id: str,
        routable: bool,
    ) -> WebSocketSessionIdentity:
        """Attach one socket while serializing against session tombstones."""

        identity = WebSocketSessionIdentity(
            audience=self._validate_audience(audience),
            account_public_id=self._validate_public_id(
                account_public_id, label="account_public_id"
            ),
            session_public_id=self._validate_public_id(
                session_public_id, label="session_public_id"
            ),
        )
        if self._socket_is_closed(socket):
            raise ValueError("cannot register a closed websocket")

        connection_id = id(socket)
        async with self._registry_lock:
            if self._is_shutdown:
                raise RuntimeError("websocket registry is shut down")

            existing = self._records.get(connection_id)
            if existing is not None:
                if existing.socket is not socket or existing.identity != identity:
                    raise ValueError(
                        "websocket is already registered with another identity"
                    )
                return identity

            session_key = (identity.audience, identity.session_public_id)
            if session_key in self._closed_sessions:
                raise WebSocketSessionAlreadyClosedError(
                    "websocket session was closed before registration"
                )
            for registered_id in self._by_session.get(session_key, ()):
                registered = self._records[registered_id]
                if registered.identity.account_public_id != identity.account_public_id:
                    raise ValueError(
                        "session is already registered for another account"
                    )

            self._records[connection_id] = _RegisteredConnection(
                socket=socket,
                identity=identity,
                routable=routable,
                authoritatively_validated=routable,
            )
            self._by_audience.setdefault(identity.audience, set()).add(connection_id)
            self._by_account.setdefault(
                (identity.audience, identity.account_public_id), set()
            ).add(connection_id)
            self._by_session.setdefault(session_key, set()).add(connection_id)
        return identity

    async def revalidate_pending(
        self,
        socket: WebSocketLike,
        *,
        revalidate: SessionRevalidator,
    ) -> SessionRevalidationStatus:
        """Check one registered handshake against current server authority."""

        record = await self._record_for_socket(socket, routable_only=False)
        if record is None:
            return SessionRevalidationStatus.REVOKED
        status = await self._revalidate_one(record.identity, revalidate)
        if status is not SessionRevalidationStatus.VALID:
            await self._close_one(
                record,
                code=WSCloseCode.POLICY_VIOLATION,
                message=self._revalidation_close_message(status),
            )
            return status

        async with record.state_lock:
            session_key = (
                record.identity.audience,
                record.identity.session_public_id,
            )
            async with self._registry_lock:
                current = self._records.get(id(record.socket))
                if (
                    current is not record
                    or record.closing
                    or session_key in self._closed_sessions
                    or self._socket_is_closed(record.socket)
                ):
                    return SessionRevalidationStatus.REVOKED
                record.authoritatively_validated = True
        return SessionRevalidationStatus.VALID

    async def activate_with_initial(
        self,
        socket: WebSocketLike,
        *,
        payload: Mapping[str, object],
    ) -> SessionRevalidationStatus:
        """Send the initial frame and activate one validated handshake.

        The record is deliberately absent from normal fan-out until the
        initial frame succeeds.  ``state_lock`` linearizes activation with a
        matching close operation; a close that wins first prevents the frame.
        Callers must also hold their audience cursor/broadcast lock while
        constructing ``payload`` and awaiting this method.  Authoritative DB
        work is intentionally completed by :meth:`revalidate_pending` before
        taking that audience-wide lock.
        """

        record = await self._record_for_socket(socket, routable_only=False)
        if record is None:
            return SessionRevalidationStatus.REVOKED

        event = dict(payload)
        send_failed = False
        async with record.state_lock:
            session_key = (
                record.identity.audience,
                record.identity.session_public_id,
            )
            async with self._registry_lock:
                current = self._records.get(id(record.socket))
                blocked = (
                    current is not record
                    or record.closing
                    or not record.authoritatively_validated
                    or session_key in self._closed_sessions
                    or self._socket_is_closed(record.socket)
                )
            if blocked:
                return SessionRevalidationStatus.REVOKED
            try:
                async with self._io_semaphore:
                    async with record.io_lock:
                        async with asyncio.timeout(self._operation_timeout_seconds):
                            await record.socket.send_json(event)
            except asyncio.CancelledError:
                raise
            except ConnectionResetError:
                # A browser can close the page after the HTTP upgrade but
                # before the first frame reaches the transport.  This is a
                # normal peer disconnect (especially during navigation), not
                # an application/realtime failure worth a warning.
                logger.debug(
                    "PWA WebSocket peer disconnected before the initial event"
                )
                send_failed = True
            except Exception:
                logger.warning(
                    "Failed to send an authenticated PWA WebSocket initial event"
                )
                send_failed = True
            if not send_failed:
                async with self._registry_lock:
                    current = self._records.get(id(record.socket))
                    if current is record and not record.closing:
                        record.routable = True
                        return SessionRevalidationStatus.VALID

        await self._close_one(
            record,
            code=WSCloseCode.GOING_AWAY,
            message=b"Realtime delivery failed",
        )
        return SessionRevalidationStatus.CORRUPT

    async def unregister(self, socket: WebSocketLike) -> bool:
        """Remove a socket from routing; safe to call repeatedly in ``finally``."""

        async with self._registry_lock:
            record = self._records.get(id(socket))
            if record is None or record.socket is not socket:
                return False
            self._remove_locked(id(socket), record)
            return True

    async def prune_closed(self) -> int:
        """Drop transports that aiohttp already reports as closed."""

        async with self._registry_lock:
            closed_ids = [
                connection_id
                for connection_id, record in self._records.items()
                if self._socket_is_closed(record.socket)
            ]
            for connection_id in closed_ids:
                self._remove_locked(connection_id, self._records[connection_id])
            return len(closed_ids)

    async def connection_count(self) -> int:
        """Return the current process-local count after pruning closed sockets."""

        await self.prune_closed()
        async with self._registry_lock:
            return len(self._records)

    async def close_session(
        self,
        *,
        audience: str,
        session_public_id: str,
        code: int = WSCloseCode.POLICY_VIOLATION,
        message: bytes = b"Session ended",
    ) -> WebSocketOperationReport:
        """Close every socket for one audience session in this worker."""

        audience = self._validate_audience(audience)
        session_public_id = self._validate_public_id(
            session_public_id, label="session_public_id"
        )
        message = self._validated_close_message(message)
        session_key = (audience, session_public_id)
        async with self._registry_lock:
            # Mark first: a concurrent pre-registration handshake must observe
            # the command even when there is no socket to close yet.
            self._closed_sessions.add(session_key)
            records = [
                self._records[connection_id]
                for connection_id in self._by_session.get(session_key, set()).copy()
                if connection_id in self._records
            ]
        return await self._close_records(records, code=code, message=message)

    async def close_account(
        self,
        *,
        audience: str,
        account_public_id: str,
        code: int = WSCloseCode.POLICY_VIOLATION,
        message: bytes = b"Account sessions ended",
    ) -> WebSocketOperationReport:
        """Close all sockets for one account (the logout-all operation)."""

        audience = self._validate_audience(audience)
        account_public_id = self._validate_public_id(
            account_public_id, label="account_public_id"
        )
        records = await self._snapshot(self._by_account, (audience, account_public_id))
        return await self._close_records(records, code=code, message=message)

    async def close_all(
        self,
        *,
        code: int = WSCloseCode.GOING_AWAY,
        message: bytes = b"Server shutdown",
    ) -> WebSocketOperationReport:
        """Close all sockets tracked by this process."""

        records = await self._snapshot_all()
        return await self._close_records(records, code=code, message=message)

    async def send_to_session(
        self,
        *,
        audience: str,
        session_public_id: str,
        payload: Mapping[str, object],
    ) -> WebSocketOperationReport:
        """Send an opaque event to every socket of one authenticated session."""

        audience = self._validate_audience(audience)
        session_public_id = self._validate_public_id(
            session_public_id, label="session_public_id"
        )
        records = await self._snapshot(self._by_session, (audience, session_public_id))
        return await self._send_records(records, payload)

    async def send_to_connection(
        self,
        socket: WebSocketLike,
        *,
        payload: Mapping[str, object],
    ) -> WebSocketOperationReport:
        """Serialize one handler response with fan-out and close operations."""

        record = await self._record_for_socket(socket)
        return await self._send_records([] if record is None else [record], payload)

    async def close_connection(
        self,
        socket: WebSocketLike,
        *,
        code: int = WSCloseCode.GOING_AWAY,
        message: bytes = b"Realtime connection ended",
    ) -> WebSocketOperationReport:
        """Close one registered transport under its shared per-socket lock."""

        record = await self._record_for_socket(socket, routable_only=False)
        return await self._close_records(
            [] if record is None else [record],
            code=code,
            message=message,
        )

    async def send_to_account(
        self,
        *,
        audience: str,
        account_public_id: str,
        payload: Mapping[str, object],
    ) -> WebSocketOperationReport:
        """Send an opaque event to all sessions of one authenticated account."""

        audience = self._validate_audience(audience)
        account_public_id = self._validate_public_id(
            account_public_id, label="account_public_id"
        )
        records = await self._snapshot(self._by_account, (audience, account_public_id))
        return await self._send_records(records, payload)

    async def send_to_audience(
        self,
        *,
        audience: str,
        payload: Mapping[str, object],
    ) -> WebSocketOperationReport:
        """Send an opaque public/audience event without weakening owner scope."""

        audience = self._validate_audience(audience)
        records = await self._snapshot(self._by_audience, audience)
        return await self._send_records(records, payload)

    async def run_revalidation_once(
        self, revalidate: SessionRevalidator
    ) -> WebSocketOperationReport:
        """Revalidate every distinct session once and close invalid sessions.

        The callback must read authoritative server state; neither the original
        handshake nor anything supplied by a WebSocket client is sufficient.
        Callback errors fail closed without logging identity values.
        """

        identities = await self._snapshot_session_identities()

        async def validate_one(
            identity: WebSocketSessionIdentity,
        ) -> tuple[WebSocketSessionIdentity, SessionRevalidationStatus]:
            try:
                async with self._revalidation_semaphore:
                    async with asyncio.timeout(self._revalidation_timeout_seconds):
                        status = await revalidate(identity)
                if not isinstance(status, SessionRevalidationStatus):
                    logger.warning(
                        "PWA WebSocket revalidator returned an invalid status"
                    )
                    return identity, SessionRevalidationStatus.CORRUPT
                return identity, status
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning(
                    "PWA WebSocket authoritative revalidation failed; "
                    "closing the affected session"
                )
                return identity, SessionRevalidationStatus.CORRUPT

        results = await asyncio.gather(
            *(validate_one(identity) for identity in identities)
        )
        invalid = [
            result
            for result in results
            if result[1] is not SessionRevalidationStatus.VALID
        ]
        reports = await asyncio.gather(
            *(
                self.close_session(
                    audience=identity.audience,
                    session_public_id=identity.session_public_id,
                    code=WSCloseCode.POLICY_VIOLATION,
                    message=self._revalidation_close_message(status),
                )
                for identity, status in invalid
            )
        )
        await self.prune_closed()
        return self._combine_reports(reports)

    def start_revalidation(
        self,
        revalidate: SessionRevalidator,
        *,
        interval_seconds: float = DEFAULT_REVALIDATION_INTERVAL_SECONDS,
    ) -> asyncio.Task[None]:
        """Start the periodic authoritative-session check for this worker."""

        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self._is_shutdown:
            raise RuntimeError("websocket registry is shut down")
        if self._revalidation_task is not None and not self._revalidation_task.done():
            raise RuntimeError("websocket revalidation is already running")

        self._revalidation_stop = asyncio.Event()
        self._revalidation_task = asyncio.create_task(
            self._revalidation_loop(revalidate, interval_seconds),
            name="pwa-websocket-session-revalidation",
        )
        return self._revalidation_task

    async def stop_revalidation(self) -> None:
        """Stop the periodic checker without closing otherwise valid sockets."""

        task = self._revalidation_task
        if task is None:
            return
        self._revalidation_stop.set()
        try:
            await task
        finally:
            if self._revalidation_task is task:
                self._revalidation_task = None

    async def shutdown(self) -> WebSocketOperationReport:
        """Stop checks, reject new registrations and close tracked sockets."""

        async with self._registry_lock:
            self._is_shutdown = True
        await self.stop_revalidation()
        return await self.close_all()

    async def _revalidation_loop(
        self, revalidate: SessionRevalidator, interval_seconds: float
    ) -> None:
        while True:
            try:
                async with asyncio.timeout(interval_seconds):
                    await self._revalidation_stop.wait()
                return
            except TimeoutError:
                await self.run_revalidation_once(revalidate)

    async def _snapshot(
        self,
        index: dict[Any, set[int]],
        key: Any,
    ) -> list[_RegisteredConnection]:
        await self.prune_closed()
        async with self._registry_lock:
            return [
                self._records[connection_id]
                for connection_id in index.get(key, set()).copy()
                if connection_id in self._records
            ]

    async def _snapshot_all(self) -> list[_RegisteredConnection]:
        await self.prune_closed()
        async with self._registry_lock:
            return list(self._records.values())

    async def _record_for_socket(
        self,
        socket: WebSocketLike,
        *,
        routable_only: bool = True,
    ) -> _RegisteredConnection | None:
        await self.prune_closed()
        async with self._registry_lock:
            record = self._records.get(id(socket))
            if record is None or record.socket is not socket:
                return None
            if routable_only and (not record.routable or record.closing):
                return None
            return record

    async def _snapshot_session_identities(
        self,
    ) -> list[WebSocketSessionIdentity]:
        await self.prune_closed()
        async with self._registry_lock:
            identities: dict[tuple[str, str], WebSocketSessionIdentity] = {}
            for record in self._records.values():
                identities[
                    (
                        record.identity.audience,
                        record.identity.session_public_id,
                    )
                ] = record.identity
            return list(identities.values())

    async def _send_records(
        self,
        records: list[_RegisteredConnection],
        payload: Mapping[str, object],
    ) -> WebSocketOperationReport:
        # Copy the top-level mapping so a caller cannot mutate it differently
        # between concurrently scheduled sends. Cursor semantics remain wholly
        # outside this registry; see the realtime contract referenced above.
        event = dict(payload)
        results = await asyncio.gather(
            *(
                self._send_one(record, event)
                for record in records
                if record.routable and not record.closing
            )
        )
        return self._report(results)

    async def _send_one(
        self,
        record: _RegisteredConnection,
        payload: Mapping[str, object],
    ) -> bool:
        if self._socket_is_closed(record.socket):
            await self.unregister(record.socket)
            return False
        try:
            async with self._io_semaphore:
                async with record.io_lock:
                    # ``_send_records`` may have selected this record just
                    # before logout/revoke marked it closing.  Recheck after
                    # acquiring the serialization lock so a close that won
                    # while this send was queued cannot be followed by one
                    # last application event.  See Phase 1 race-hardening
                    # proof in pwa_tests/reports/phase1-auth-race-hardening.md.
                    if record.closing:
                        return False
                    if self._socket_is_closed(record.socket):
                        await self.unregister(record.socket)
                        return False
                    async with asyncio.timeout(self._operation_timeout_seconds):
                        await record.socket.send_json(payload)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Failed to send an authenticated PWA WebSocket event")
            await self._close_one(
                record,
                code=WSCloseCode.GOING_AWAY,
                message=b"Realtime delivery failed",
            )
            return False

    async def _close_records(
        self,
        records: list[_RegisteredConnection],
        *,
        code: int,
        message: bytes,
    ) -> WebSocketOperationReport:
        message = self._validated_close_message(message)
        results = await asyncio.gather(
            *(self._close_one(record, code=code, message=message) for record in records)
        )
        return self._report(results)

    async def _close_one(
        self,
        record: _RegisteredConnection,
        *,
        code: int,
        message: bytes,
    ) -> bool:
        async with record.state_lock:
            record.closing = True
            record.routable = False
            record.authoritatively_validated = False
        if self._socket_is_closed(record.socket):
            await self.unregister(record.socket)
            return True
        try:
            async with self._io_semaphore:
                async with record.io_lock:
                    if self._socket_is_closed(record.socket):
                        await self.unregister(record.socket)
                        return True
                    async with asyncio.timeout(self._operation_timeout_seconds):
                        await record.socket.close(code=code, message=message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Failed to close an authenticated PWA WebSocket")

        if self._socket_is_closed(record.socket):
            await self.unregister(record.socket)
            return True
        return False

    def _remove_locked(self, connection_id: int, record: _RegisteredConnection) -> None:
        self._records.pop(connection_id, None)
        identity = record.identity
        self._remove_from_index(self._by_audience, identity.audience, connection_id)
        self._remove_from_index(
            self._by_account,
            (identity.audience, identity.account_public_id),
            connection_id,
        )
        self._remove_from_index(
            self._by_session,
            (identity.audience, identity.session_public_id),
            connection_id,
        )

    @staticmethod
    def _remove_from_index(
        index: dict[Any, set[int]], key: Any, connection_id: int
    ) -> None:
        values = index.get(key)
        if values is None:
            return
        values.discard(connection_id)
        if not values:
            index.pop(key, None)

    def _validate_audience(self, audience: str) -> str:
        if audience not in self._audiences:
            raise ValueError(f"unknown PWA audience: {audience!r}")
        return audience

    @staticmethod
    def _validate_public_id(value: str, *, label: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value:
            raise ValueError(f"{label} must be a non-empty normalized string")
        return value

    @staticmethod
    def _validated_close_message(message: bytes) -> bytes:
        if not isinstance(message, bytes):
            raise TypeError("WebSocket close message must be bytes")
        if len(message) > MAX_CLOSE_MESSAGE_BYTES:
            raise ValueError("WebSocket close message must be at most 123 bytes")
        return message

    @staticmethod
    def _socket_is_closed(socket: WebSocketLike) -> bool:
        try:
            return bool(socket.closed)
        except Exception:
            # A transport whose state cannot be inspected is not safe to use.
            return True

    @staticmethod
    def _report(results: list[bool]) -> WebSocketOperationReport:
        succeeded = sum(results)
        return WebSocketOperationReport(
            selected=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
        )

    @staticmethod
    def _combine_reports(
        reports: list[WebSocketOperationReport],
    ) -> WebSocketOperationReport:
        return WebSocketOperationReport(
            selected=sum(report.selected for report in reports),
            succeeded=sum(report.succeeded for report in reports),
            failed=sum(report.failed for report in reports),
        )

    async def _revalidate_one(
        self,
        identity: WebSocketSessionIdentity,
        revalidate: SessionRevalidator,
    ) -> SessionRevalidationStatus:
        try:
            async with self._revalidation_semaphore:
                async with asyncio.timeout(self._revalidation_timeout_seconds):
                    status = await revalidate(identity)
            if isinstance(status, SessionRevalidationStatus):
                return status
            logger.warning("PWA WebSocket revalidator returned an invalid status")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "PWA WebSocket authoritative revalidation failed; "
                "closing the affected session"
            )
        return SessionRevalidationStatus.CORRUPT

    @staticmethod
    def _revalidation_close_message(status: SessionRevalidationStatus) -> bytes:
        if status is SessionRevalidationStatus.REVOKED:
            return b"Session revoked"
        if status is SessionRevalidationStatus.EXPIRED:
            return b"Session expired"
        return b"Session unavailable"
