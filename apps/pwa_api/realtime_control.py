"""Cross-worker control plane for authenticated PWA WebSocket sessions.

Core NATS is transient fan-out, not authority.  Every worker first closes the
matching process-local sockets and publishes a small, strictly validated
control event.  If publication fails, the local close still succeeds and the
bounded authoritative revalidation loop closes sockets in other workers.

See ``vmshpwa/dev/development-plan/05-phase-1-auth.md`` and
``vmshpwa/docs/realtime-offline-and-notifications.md``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from aiohttp import web

from helpers.nats_brocker import JsonBroker

from .websocket_sessions import (
    WebSocketOperationReport,
    WebSocketSessionRegistry,
)

logger = logging.getLogger(__name__)

NATS_PWA_SESSION_CONTROL = "pwa_session_control"
REALTIME_CONTROL_VERSION = 1
_AUDIENCES = frozenset({"student", "family", "staff"})
_SESSION_PUBLIC_ID = re.compile(r"[0-9a-f]{32}\Z")
_ACCOUNT_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")
_CONTROL_KEYS = frozenset({"version", "type", "audience", "scope", "targetId"})


class RealtimeControlScope(StrEnum):
    SESSION = "session"
    ACCOUNT = "account"


@dataclass(frozen=True, slots=True)
class RealtimeControlEvent:
    """One validated cross-worker close command."""

    audience: str
    scope: RealtimeControlScope
    target_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "version": REALTIME_CONTROL_VERSION,
            "type": "auth.close",
            "audience": self.audience,
            "scope": self.scope.value,
            "targetId": self.target_id,
        }


@dataclass(frozen=True, slots=True)
class RealtimeControlReport:
    """Local close outcome plus best-effort broker publication state."""

    local: WebSocketOperationReport
    published: bool


def parse_realtime_control_event(payload: Any) -> RealtimeControlEvent | None:
    """Reject malformed, over-broad or extension-bearing broker commands."""

    if not isinstance(payload, Mapping) or set(payload) != _CONTROL_KEYS:
        return None
    version = payload.get("version")
    if type(version) is not int or version != REALTIME_CONTROL_VERSION:
        return None
    event_type = payload.get("type")
    if not isinstance(event_type, str) or event_type != "auth.close":
        return None
    audience = payload.get("audience")
    if not isinstance(audience, str) or audience not in _AUDIENCES:
        return None
    raw_scope = payload.get("scope")
    if not isinstance(raw_scope, str):
        return None
    try:
        scope = RealtimeControlScope(raw_scope)
    except TypeError, ValueError:
        return None
    target_id = payload.get("targetId")
    if not isinstance(target_id, str):
        return None
    pattern = (
        _SESSION_PUBLIC_ID
        if scope is RealtimeControlScope.SESSION
        else _ACCOUNT_PUBLIC_ID
    )
    if pattern.fullmatch(target_id) is None:
        return None
    return RealtimeControlEvent(
        audience=audience,
        scope=scope,
        target_id=target_id,
    )


class RealtimeSessionController:
    """Coordinate local registry operations with transient worker fan-out."""

    def __init__(
        self,
        registry: WebSocketSessionRegistry,
        broker: JsonBroker,
    ) -> None:
        self.registry = registry
        self.broker = broker

    async def close_session(
        self,
        *,
        audience: str,
        session_public_id: str,
    ) -> RealtimeControlReport:
        event = _validated_event(
            audience=audience,
            scope=RealtimeControlScope.SESSION,
            target_id=session_public_id,
        )
        local = await self._apply(event)
        return RealtimeControlReport(local=local, published=await self._publish(event))

    async def close_account(
        self,
        *,
        audience: str,
        account_public_id: str,
    ) -> RealtimeControlReport:
        event = _validated_event(
            audience=audience,
            scope=RealtimeControlScope.ACCOUNT,
            target_id=account_public_id,
        )
        local = await self._apply(event)
        return RealtimeControlReport(local=local, published=await self._publish(event))

    async def handle_broker_payload(self, payload: Any) -> None:
        """Apply only an exact versioned payload; never republish it."""

        event = parse_realtime_control_event(payload)
        if event is None:
            logger.warning("Ignoring invalid PWA realtime control event")
            return
        await self._apply(event)

    async def _apply(
        self,
        event: RealtimeControlEvent,
    ) -> WebSocketOperationReport:
        if event.scope is RealtimeControlScope.SESSION:
            return await self.registry.close_session(
                audience=event.audience,
                session_public_id=event.target_id,
            )
        return await self.registry.close_account(
            audience=event.audience,
            account_public_id=event.target_id,
        )

    async def _publish(self, event: RealtimeControlEvent) -> bool:
        try:
            await self.broker.publish(NATS_PWA_SESSION_CONTROL, event.to_payload())
        except asyncio.CancelledError:
            raise
        except Exception:
            # Deliberately omit identifiers, exception text and traceback.  The
            # authoritative revalidation loop is the bounded cross-worker fallback.
            logger.warning(
                "PWA realtime control publication failed; "
                "authoritative revalidation remains active"
            )
            return False
        return True


def _validated_event(
    *,
    audience: str,
    scope: RealtimeControlScope,
    target_id: str,
) -> RealtimeControlEvent:
    candidate = RealtimeControlEvent(
        audience=audience,
        scope=scope,
        target_id=target_id,
    )
    validated = parse_realtime_control_event(candidate.to_payload())
    if validated is None:
        raise ValueError("Invalid realtime control target")
    return validated


PWA_REALTIME_SESSION_CONTROLLER = web.AppKey(
    "pwa_realtime_session_controller",
    RealtimeSessionController,
)


def realtime_session_controller(
    request: web.Request,
) -> RealtimeSessionController | None:
    """Return the optional app-owned controller for auth route close hooks."""

    return request.app.get(PWA_REALTIME_SESSION_CONTROLLER)


__all__ = [
    "NATS_PWA_SESSION_CONTROL",
    "PWA_REALTIME_SESSION_CONTROLLER",
    "REALTIME_CONTROL_VERSION",
    "RealtimeControlEvent",
    "RealtimeControlReport",
    "RealtimeControlScope",
    "RealtimeSessionController",
    "parse_realtime_control_event",
    "realtime_session_controller",
]
