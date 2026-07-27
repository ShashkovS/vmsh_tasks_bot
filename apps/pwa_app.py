# -*- coding: utf-8 -*-
import asyncio
import json
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from aiohttp import WSCloseCode, WSMsgType, web

from helpers.config import logger
from helpers.nats_brocker import InProcessBroker, JsonBroker, NatsBroker
from helpers.pwa.api_contracts import (
    build_api_error_payload,
    build_realtime_error_payload,
    build_runtime_payload,
    validate_runtime_instance,
)
from helpers.pwa.app_keys import RUNTIME_CONFIG

__all__ = ["PwaApiError", "pwa_routes"]

AUDIENCES = ("student", "family", "staff")
NATS_PWA_INVALIDATE = "pwa_invalidate"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
INVALIDATION_RESOURCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,255}$")
INVALIDATION_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
MAX_INVALIDATION_RESOURCES = 128
WEBSOCKET_SEND_TIMEOUT_SECONDS = 2
WEBSOCKET_CLOSE_TIMEOUT_SECONDS = 5
PWA_STATE = web.AppKey("pwa_state", dict)
PWA_BROKER = web.AppKey("pwa_broker", JsonBroker)
PWA_RESPONSE_PREPARED = web.AppKey("pwa_response_prepared", bool)
PWA_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
PWA_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}
REBUILT_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "content-type",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "cache-control",
        "expires",
        "pragma",
        *(name.casefold() for name in PWA_SECURITY_HEADERS),
    }
)

pwa_routes = web.RouteTableDef()


class PwaApiError(Exception):
    """Stable domain-facing PWA error independent from aiohttp reason strings."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        if not 400 <= status <= 599:
            raise ValueError("PWA API error status must be between 400 and 599")
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}
        super().__init__(message)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _audience(request: web.Request) -> str:
    audience = request.match_info.get("audience", "")
    if audience not in AUDIENCES:
        raise web.HTTPNotFound(text="Unknown PWA audience")
    return audience


def _request_id(request: web.Request) -> str:
    return request["request_id"]


def _runtime_config(app: web.Application):
    return app[RUNTIME_CONFIG]


def _is_pwa_transport_path(path: str) -> bool:
    return any(
        path == f"/{audience}/ws"
        or path == f"/{audience}/api"
        or path.startswith(f"/{audience}/api/")
        for audience in AUDIENCES
    )


def _copy_rebuilt_response_headers(
    response: web.StreamResponse, headers: Mapping[str, str]
) -> None:
    """Preserve end-to-end exception headers while owning body/cache headers."""

    for name, value in headers.items():
        if name.casefold() not in REBUILT_RESPONSE_HEADERS:
            response.headers.add(name, value)


def _apply_pwa_response_headers(response: web.StreamResponse, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    for name, value in PWA_NO_STORE_HEADERS.items():
        response.headers[name] = value
    for name, value in PWA_SECURITY_HEADERS.items():
        response.headers[name] = value


async def on_pwa_response_prepare(
    request: web.Request, response: web.StreamResponse
) -> None:
    """Apply the PWA wire boundary immediately before headers are written."""

    if not _is_pwa_transport_path(request.path):
        return
    # At this point aiohttp has attached its payload writer. If the handler
    # later fails, middleware must not try to replace this response with JSON.
    # See vmshpwa/docs/runtime-isolation.md.
    request[PWA_RESPONSE_PREPARED] = True
    _apply_pwa_response_headers(response, _request_id(request))


def _create_pwa_state() -> dict[str, dict[str, object]]:
    """Create one internally consistent realtime state for an app instance."""

    return {
        "cursors": {audience: 0 for audience in AUDIENCES},
        "websockets": {audience: set() for audience in AUDIENCES},
        "broadcast_locks": {audience: asyncio.Lock() for audience in AUDIENCES},
    }


@web.middleware
async def pwa_error_middleware(request: web.Request, handler):
    if not _is_pwa_transport_path(request.path):
        return await handler(request)

    incoming_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        incoming_request_id
        if REQUEST_ID_PATTERN.fullmatch(incoming_request_id)
        else uuid.uuid4().hex
    )
    request["request_id"] = request_id
    try:
        response = await handler(request)
    except Exception as exc:
        if request.get(PWA_RESPONSE_PREPARED, False):
            logger.exception(
                "PWA handler failed after response preparation, request_id=%s",
                request_id,
            )
            raise
        if isinstance(exc, PwaApiError):
            response = web.json_response(
                build_api_error_payload(
                    code=exc.code,
                    message=exc.message,
                    request_id=request_id,
                    details=exc.details,
                ),
                status=exc.status,
            )
            _copy_rebuilt_response_headers(response, exc.headers)
        elif isinstance(exc, web.HTTPException):
            response = web.json_response(
                build_api_error_payload(
                    code=exc.reason.lower().replace(" ", "_"),
                    message=exc.text,
                    request_id=request_id,
                ),
                status=exc.status,
            )
            _copy_rebuilt_response_headers(response, exc.headers)
        else:
            logger.exception("Unhandled PWA API exception, request_id=%s", request_id)
            response = web.json_response(
                build_api_error_payload(
                    code="internal_error",
                    message="Внутренняя ошибка сервера",
                    request_id=request_id,
                ),
                status=500,
            )
    if not response.prepared:
        _apply_pwa_response_headers(response, request_id)
    return response


@pwa_routes.get("/{audience:student|family|staff}/api/v1/health")
async def health(request: web.Request):
    return web.json_response(
        {"ok": True, "audience": _audience(request), "requestId": _request_id(request)}
    )


@pwa_routes.get("/{audience:student|family|staff}/api/v1/runtime")
async def runtime(request: web.Request):
    audience = _audience(request)
    runtime_config = _runtime_config(request.app)
    broker = request.app[PWA_BROKER]
    return web.json_response(
        build_runtime_payload(
            audience=audience,
            instance=runtime_config.pwa_instance or runtime_config.config_name,
            server_time=_now(),
            request_id=_request_id(request),
            telegram=bool(runtime_config.telegram_bot_token),
            google=bool(runtime_config.google_cred_json),
            nats=broker.nats_is_working,
            prototype=runtime_config.pwa_prototype,
        )
    )


@pwa_routes.post("/api/pwa/health")
async def legacy_health(_request: web.Request):
    return web.json_response({"ok": True})


async def _close_websocket(
    websocket,
    *,
    code: WSCloseCode,
    message: bytes,
    context: str,
) -> bool:
    if websocket.closed:
        return True
    try:
        async with asyncio.timeout(WEBSOCKET_CLOSE_TIMEOUT_SECONDS):
            await websocket.close(code=code, message=message)
    except Exception:
        logger.warning(
            "Failed to close PWA websocket during %s", context, exc_info=True
        )
        return False
    return bool(websocket.closed)


async def _send_invalidation(connections: set, websocket, event: dict):
    if websocket.closed:
        connections.discard(websocket)
        return
    try:
        async with asyncio.timeout(WEBSOCKET_SEND_TIMEOUT_SECONDS):
            await websocket.send_json(event)
    except Exception:
        logger.warning("Failed to send PWA invalidation", exc_info=True)
        # Close before dropping tracking. If close also fails, shutdown retains a
        # bounded second chance instead of leaking an untracked handler/transport.
        # See vmshpwa/docs/phase-0-live-integration-harness.md.
        closed = await _close_websocket(
            websocket,
            code=WSCloseCode.GOING_AWAY,
            message=b"Invalidation delivery failed",
            context="failed invalidation delivery",
        )
        if closed:
            connections.discard(websocket)


async def _broadcast(
    app: web.Application,
    resources: list[str],
    reason: str,
    audience: str | None = None,
):
    if audience is not None and audience not in AUDIENCES:
        raise ValueError(f"Unknown PWA audience: {audience}")

    async def broadcast_to_audience(target_audience: str) -> None:
        state = app[PWA_STATE]
        # NATS happens to dispatch one subscription sequentially today, but
        # the broker interface and direct domain callers do not promise that.
        # Serialize cursor allocation and socket writes per audience while
        # allowing Student/Family/Staff fan-out to proceed independently.
        async with state["broadcast_locks"][target_audience]:
            state["cursors"][target_audience] += 1
            event = {
                "type": "invalidate",
                "cursor": state["cursors"][target_audience],
                "serverTime": _now(),
                "resources": resources,
                "reason": reason,
                "audience": target_audience,
            }
            connections = state["websockets"][target_audience]
            await asyncio.gather(
                *(
                    _send_invalidation(connections, websocket, event)
                    for websocket in connections.copy()
                )
            )

    target_audiences = (audience,) if audience is not None else AUDIENCES
    await asyncio.gather(
        *(
            broadcast_to_audience(target_audience)
            for target_audience in target_audiences
        )
    )


@pwa_routes.get("/{audience:student|family|staff}/ws")
async def realtime(request: web.Request):
    audience = _audience(request)
    cursor_value = request.query.get("cursor")
    if cursor_value is not None:
        try:
            requested_cursor = int(cursor_value)
        except ValueError as exc:
            raise web.HTTPBadRequest(
                text="cursor must be a non-negative integer"
            ) from exc
        if requested_cursor < 0:
            raise web.HTTPBadRequest(text="cursor must be a non-negative integer")

    websocket = web.WebSocketResponse(heartbeat=25, max_msg_size=64 * 1024)
    _apply_pwa_response_headers(websocket, _request_id(request))
    await websocket.prepare(request)
    state = request.app[PWA_STATE]
    state["websockets"][audience].add(websocket)

    try:
        # The first send belongs inside the same cleanup guard as the receive
        # loop: a client can vanish between upgrade and handshake delivery.
        current_cursor = state["cursors"][audience]
        if cursor_value is not None:
            await websocket.send_json(
                {
                    "type": "resync-required",
                    "cursor": current_cursor,
                    "serverTime": _now(),
                    "reason": "reconnect-full-refetch-required",
                }
            )
        else:
            await websocket.send_json(
                {
                    "type": "connected",
                    "cursor": current_cursor,
                    "serverTime": _now(),
                    "audience": audience,
                }
            )

        async for message in websocket:
            if message.type == WSMsgType.TEXT:
                try:
                    payload = json.loads(message.data)
                except json.JSONDecodeError, RecursionError:
                    # HTTP middleware can no longer replace the response after
                    # WebSocket upgrade. Keep protocol errors on the versioned
                    # realtime wire contract instead. See Phase 0 contracts.
                    await websocket.send_json(
                        build_realtime_error_payload(
                            cursor=state["cursors"][audience],
                            server_time=_now(),
                            code="invalid_json",
                            message="Сообщение WebSocket должно быть корректным JSON",
                            request_id=_request_id(request),
                        )
                    )
                    continue
                if isinstance(payload, dict) and payload.get("type") == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "cursor": state["cursors"][audience],
                            "serverTime": _now(),
                        }
                    )
            elif message.type == WSMsgType.ERROR:
                logger.warning("PWA websocket error: %s", websocket.exception())
    except Exception:
        # Once prepare() succeeds the HTTP error middleware cannot replace the
        # upgraded response. Contain transport/serialization failures here,
        # close with a bounded wait, and return the original WebSocket object.
        logger.warning(
            "PWA websocket failed after upgrade, request_id=%s",
            _request_id(request),
            exc_info=True,
        )
        await _close_websocket(
            websocket,
            code=WSCloseCode.INTERNAL_ERROR,
            message=b"Realtime transport failure",
            context="post-upgrade handler failure",
        )
    finally:
        state["websockets"][audience].discard(websocket)
    return websocket


async def on_startup(app: web.Application):
    runtime_config = _runtime_config(app)
    broker = app[PWA_BROKER]
    logger.info(
        "PWA app startup: instance=%s",
        runtime_config.pwa_instance or runtime_config.config_name,
    )

    async def handle_invalidation(payload):
        if not isinstance(payload, dict):
            logger.warning("Ignoring non-object PWA invalidation")
            return
        raw_resources = payload.get("resources")
        if (
            not isinstance(raw_resources, list)
            or not 1 <= len(raw_resources) <= MAX_INVALIDATION_RESOURCES
            or not all(
                isinstance(item, str) and INVALIDATION_RESOURCE_PATTERN.fullmatch(item)
                for item in raw_resources
            )
        ):
            logger.warning("Ignoring invalid PWA invalidation resources")
            return
        resources = list(dict.fromkeys(raw_resources))
        audience = payload.get("audience")
        if audience is not None and audience not in AUDIENCES:
            logger.warning("Ignoring invalid PWA invalidation audience")
            return
        reason = payload.get("reason", "nats")
        if not isinstance(reason, str) or not INVALIDATION_REASON_PATTERN.fullmatch(
            reason
        ):
            logger.warning("Ignoring invalid PWA invalidation reason")
            return
        await _broadcast(app, resources, reason, audience=audience)

    try:
        await broker.setup(runtime_config.nats_server)
        await broker.subscribe(NATS_PWA_INVALIDATE, handle_invalidation)
        await broker.ready()
    except BaseException as startup_error:
        # aiohttp does not promise to run an adapter's shutdown hook after that
        # adapter's startup callback fails. Setup itself may allocate a client
        # before raising, so the whole adapter startup belongs inside this guard.
        try:
            await broker.disconnect()
        except BaseException as cleanup_error:
            raise BaseExceptionGroup(
                "PWA broker startup and cleanup both failed",
                [startup_error, cleanup_error],
            ) from None
        raise


async def on_shutdown(app: web.Application):
    state = app[PWA_STATE]

    sockets = {
        websocket
        for connections in state["websockets"].values()
        for websocket in connections.copy()
    }
    await asyncio.gather(
        *(
            _close_websocket(
                websocket,
                code=WSCloseCode.GOING_AWAY,
                message=b"Server shutdown",
                context="shutdown",
            )
            for websocket in sockets
        )
    )
    for connections in state["websockets"].values():
        connections.clear()
    await app[PWA_BROKER].disconnect()
    logger.info("PWA app shutdown")


def configure(app: web.Application, *, broker: JsonBroker | None = None):
    runtime_config = _runtime_config(app)
    # Browser storage uses this server-owned value verbatim. Rejecting an
    # unsafe namespace during composition prevents a partially working process
    # whose frontend would fail closed only after the first request.
    validate_runtime_instance(runtime_config.pwa_instance or runtime_config.config_name)
    if broker is None:
        if runtime_config.nats_server:
            broker = NatsBroker(runtime_config.config_name)
        else:
            broker = InProcessBroker(runtime_config.config_name)
    app.middlewares.append(pwa_error_middleware)
    app.on_response_prepare.append(on_pwa_response_prepare)
    app[PWA_BROKER] = broker
    app[PWA_STATE] = _create_pwa_state()
    app.add_routes(pwa_routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


# Compatibility alias for older launchers; new code uses the correctly named API.
configue = configure


if __name__ == "__main__":
    raise SystemExit(
        "Use the explicit PWA runtime entry point; this module is an adapter"
    )
