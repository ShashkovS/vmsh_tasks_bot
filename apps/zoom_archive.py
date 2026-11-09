"""Signed, lossless Zoom ingress. See docs/deploy/tlf-app/README.md."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from functools import partial

from aiohttp import web

from db_methods.pwa.connection import SqliteConcurrencyPolicy
from db_methods.pwa.zoom_archive import insert_receipt
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG

routes = web.RouteTableDef()


@routes.get("/health")
async def health(request):
    state = request.app[PWA_DATABASE]
    return web.json_response(
        {"status": "ready" if state.factory else "unavailable"},
        status=200 if state.factory else 503,
    )


@routes.post("/zoomevents")
async def receive(request):
    secret = request.app[RUNTIME_CONFIG].zoom_secret_token
    raw = await request.read()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError, UnicodeDecodeError:
        return web.json_response({"error": "invalid_json"}, status=400)
    timestamp = request.headers.get("x-zm-request-timestamp", "")
    signature = request.headers.get("x-zm-signature", "")
    # CRC is Zoom's separate public registration challenge. If signed, verify it too.
    challenge = payload.get("event") == "endpoint.url_validation"
    if not challenge or signature:
        try:
            valid_time = abs(time.time() - int(timestamp)) <= 300
        except ValueError:
            valid_time = False
        expected = (
            "v0="
            + hmac.new(
                secret.encode(),
                b"v0:" + timestamp.encode() + b":" + raw,
                hashlib.sha256,
            ).hexdigest()
        )
        if not valid_time or not hmac.compare_digest(signature, expected):
            return web.json_response({"error": "invalid_signature"}, status=401)
    if challenge:
        inner = payload.get("payload")
        token = inner.get("plainToken") if isinstance(inner, dict) else None
        if not isinstance(token, str) or not token or len(token) > 4096:
            return web.json_response({"error": "invalid_challenge"}, status=400)
        return web.json_response(
            {
                "plainToken": token,
                "encryptedToken": hmac.new(
                    secret.encode(), token.encode(), hashlib.sha256
                ).hexdigest(),
            }
        )
    inner = payload.get("payload")
    obj = inner.get("object") if isinstance(inner, dict) else None
    meeting = obj.get("id") if isinstance(obj, dict) else None
    event = payload.get("event")
    write = partial(
        insert_receipt,
        received_at=datetime.now(UTC).isoformat(),
        event_type=event if isinstance(event, str) else "unknown",
        meeting_id=str(meeting) if isinstance(meeting, (str, int)) else None,
        request_id=request.headers.get("x-zm-request-id"),
        request_timestamp=timestamp,
        raw_body=raw,
    )
    factory = request.app[PWA_DATABASE].factory
    try:
        async with asyncio.timeout(2):
            await factory.run_write_async(write)
    except Exception:
        # No payload/identity is logged. Zoom can retry; duplicate receipts are retained.
        return web.json_response(
            {"error": "archive_unavailable"}, status=503, headers={"Retry-After": "2"}
        )
    return web.json_response({"accepted": True})


async def archive_startup(app):
    if not app[RUNTIME_CONFIG].zoom_secret_token:
        raise RuntimeError("Zoom archive requires zoom_secret_token")
    app[PWA_DATABASE].factory.policy = SqliteConcurrencyPolicy(
        busy_timeout_ms=200,
        retry_delays_seconds=(0.02, 0.05),
    )


def configure(app):
    app.add_routes(routes)
    app.on_startup.append(archive_startup)


def create_app():
    # Same backend/lifecycle, dedicated adapter; no Telegram, Google or PWA routes.
    import sys
    from helpers.config import config
    from main import create_app as compose

    if config.runtime_profile != "pwa-production":
        raise RuntimeError("Zoom archive must use the production PWA config loader")
    return compose(
        (sys.modules[__name__],),
        runtime_config=config,
        analytics_enabled=False,
        client_max_size=8 * 1024 * 1024,
    )
