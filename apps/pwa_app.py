# -*- coding: utf-8 -*-
import asyncio
import json
import re
import uuid
from datetime import UTC, datetime

from aiohttp import WSCloseCode, WSMsgType, web

from helpers.config import logger
from helpers.nats_brocker import InProcessBroker, JsonBroker, NatsBroker

__all__ = ["pwa_routes"]

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
PWA_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}

pwa_routes = web.RouteTableDef()


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
    # Importing the AppKey lazily avoids a module-import cycle while still making
    # app-factory runtime_config authoritative over import-time legacy config.
    # See vmshpwa/docs/phase-0-live-integration-harness.md.
    from main import RUNTIME_CONFIG

    return app[RUNTIME_CONFIG]


def _is_pwa_transport_path(path: str) -> bool:
    return any(
        path == f"/{audience}/ws" or path.startswith(f"/{audience}/api/")
        for audience in AUDIENCES
    )


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
    except web.HTTPException as exc:
        response = web.json_response(
            {
                "error": {
                    "code": exc.reason.lower().replace(" ", "_"),
                    "message": exc.text,
                    "requestId": request_id,
                }
            },
            status=exc.status,
        )
    except Exception:
        logger.exception("Unhandled PWA API exception, request_id=%s", request_id)
        response = web.json_response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "Внутренняя ошибка сервера",
                    "requestId": request_id,
                }
            },
            status=500,
        )
    if not response.prepared:
        response.headers["X-Request-ID"] = request_id
        for name, value in PWA_SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
    return response


@pwa_routes.get("/{audience:student|family|staff}/api/v1/health")
async def health(request: web.Request):
    return web.json_response(
        {"ok": True, "audience": _audience(request), "requestId": _request_id(request)}
    )


@pwa_routes.get("/{audience:student|family|staff}/api/v1/runtime")
async def runtime(request: web.Request):
    audience = _audience(request)
    app_base = f"/{audience}"
    runtime_config = _runtime_config(request.app)
    broker = request.app[PWA_BROKER]
    return web.json_response(
        {
            "audience": audience,
            "appBase": app_base,
            "apiBase": f"{app_base}/api/v1",
            "websocketPath": f"{app_base}/ws",
            "instance": runtime_config.pwa_instance or runtime_config.config_name,
            "serverTime": _now(),
            "requestId": _request_id(request),
            "features": {
                "telegram": bool(runtime_config.telegram_bot_token),
                "google": bool(runtime_config.google_cred_json),
                "nats": broker.nats_is_working,
                "prototype": runtime_config.pwa_prototype,
            },
        }
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

    state = app[PWA_STATE]
    target_audiences = (audience,) if audience is not None else AUDIENCES
    deliveries = []
    for target_audience in target_audiences:
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
        deliveries.extend(
            _send_invalidation(connections, websocket, event)
            for websocket in connections.copy()
        )
    await asyncio.gather(
        *deliveries,
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
    websocket.headers["X-Request-ID"] = _request_id(request)
    await websocket.prepare(request)
    state = request.app[PWA_STATE]
    state["websockets"][audience].add(websocket)

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

    try:
        async for message in websocket:
            if message.type == WSMsgType.TEXT:
                try:
                    payload = json.loads(message.data)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {
                            "error": {
                                "code": "invalid_json",
                                "requestId": _request_id(request),
                            }
                        }
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
    if broker is None:
        if runtime_config.nats_server:
            broker = NatsBroker(runtime_config.config_name)
        else:
            broker = InProcessBroker(runtime_config.config_name)
    app.middlewares.append(pwa_error_middleware)
    app[PWA_BROKER] = broker
    app[PWA_STATE] = {
        "cursors": {audience: 0 for audience in AUDIENCES},
        "websockets": {audience: set() for audience in AUDIENCES},
    }
    app.add_routes(pwa_routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


# Compatibility alias for older launchers; new code uses the correctly named API.
configue = configure


if __name__ == "__main__":
    raise SystemExit(
        "Use the explicit PWA runtime entry point; this module is an adapter"
    )
