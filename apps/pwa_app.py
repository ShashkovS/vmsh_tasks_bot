# -*- coding: utf-8 -*-
import json
import logging
import re
import uuid
from datetime import UTC, datetime

from aiohttp import WSMsgType, web

from helpers.config import DEBUG, config, logger
from helpers.nats_brocker import vmsh_nats

__all__ = ["pwa_routes"]

AUDIENCES = ("student", "family", "staff")
NATS_PWA_INVALIDATE = "pwa_invalidate"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
PWA_STATE = web.AppKey("pwa_state", dict)

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


@web.middleware
async def pwa_error_middleware(request: web.Request, handler):
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
    response.headers["X-Request-ID"] = request_id
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
    return web.json_response(
        {
            "audience": audience,
            "appBase": app_base,
            "apiBase": f"{app_base}/api/v1",
            "websocketPath": f"{app_base}/ws",
            "instance": config.pwa_instance or config.config_name,
            "serverTime": _now(),
            "requestId": _request_id(request),
            "features": {
                "telegram": bool(config.telegram_bot_token),
                "google": bool(config.google_cred_json),
                "nats": vmsh_nats.nats_is_working,
                "prototype": config.pwa_prototype,
            },
        }
    )


@pwa_routes.post("/api/pwa/health")
async def legacy_health(_request: web.Request):
    return web.json_response({"ok": True})


async def _broadcast(app: web.Application, resources: list[str], reason: str):
    state = app[PWA_STATE]
    state["cursor"] += 1
    event = {
        "type": "invalidate",
        "cursor": state["cursor"],
        "serverTime": _now(),
        "resources": resources,
        "reason": reason,
    }
    stale = []
    for connections in state["websockets"].values():
        for websocket in connections.copy():
            if websocket.closed:
                stale.append((connections, websocket))
            else:
                await websocket.send_json(event)
    for connections, websocket in stale:
        connections.discard(websocket)


@pwa_routes.get("/{audience:student|family|staff}/ws")
async def realtime(request: web.Request):
    audience = _audience(request)
    try:
        requested_cursor = max(0, int(request.query.get("cursor", "0")))
    except ValueError as exc:
        raise web.HTTPBadRequest(text="cursor must be a non-negative integer") from exc

    websocket = web.WebSocketResponse(heartbeat=25, max_msg_size=64 * 1024)
    websocket.headers["X-Request-ID"] = _request_id(request)
    await websocket.prepare(request)
    state = request.app[PWA_STATE]
    state["websockets"][audience].add(websocket)

    current_cursor = state["cursor"]
    if requested_cursor > current_cursor:
        await websocket.send_json(
            {
                "type": "resync-required",
                "cursor": current_cursor,
                "serverTime": _now(),
                "reason": "client-cursor-is-ahead",
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
                if payload.get("type") == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "cursor": state["cursor"],
                            "serverTime": _now(),
                        }
                    )
            elif message.type == WSMsgType.ERROR:
                logger.warning("PWA websocket error: %s", websocket.exception())
    finally:
        state["websockets"][audience].discard(websocket)
    return websocket


async def on_startup(app: web.Application):
    logger.info(
        "PWA app startup: instance=%s", config.pwa_instance or config.config_name
    )
    await vmsh_nats.setup(config.nats_server)

    async def handle_invalidation(payload):
        resources = [str(item) for item in payload.get("resources", []) if item]
        if resources:
            await _broadcast(app, resources, str(payload.get("reason") or "nats"))

    await vmsh_nats.subscribe(NATS_PWA_INVALIDATE, handle_invalidation)


async def on_shutdown(_app: web.Application):
    await vmsh_nats.disconnect()
    logger.info("PWA app shutdown")


def configue(app: web.Application):
    app.middlewares.append(pwa_error_middleware)
    app[PWA_STATE] = {
        "cursor": 0,
        "websockets": {audience: set() for audience in AUDIENCES},
    }
    app.add_routes(pwa_routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)
    standalone_app = web.Application()
    configue(standalone_app)
    web.run_app(standalone_app)
