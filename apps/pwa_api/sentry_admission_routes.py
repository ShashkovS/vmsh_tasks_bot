"""Content-free frontend admission; 2026-10-11 Sentry quota decision."""

import json
import re

from aiohttp import web

from apps.pwa_api.middleware import validate_request_boundary
from helpers.prometheus_metrics import CLIENT_SENTRY_ADMISSIONS
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.sentry_budget import LIMITS, admit_frontend_event
from models.pwa.auth import AuthAudience


sentry_admission_routes = web.RouteTableDef()
_SIGNATURE = re.compile(r"^[0-9a-f]{8}$")


@sentry_admission_routes.post("/{audience:student|family|staff}/api/v1/observability/sentry-admission")
async def admit_sentry_event(request: web.Request) -> web.Response:
    # Pre-login crashes need this public route; it exposes no auth/domain data.
    validate_request_boundary(
        request, audience=AuthAudience(request.match_info["audience"]),
        expects_json=True, require_browser_source=True,
    )
    try:
        body = bytearray()
        async for chunk in request.content.iter_chunked(1025):
            body.extend(chunk)
            if len(body) > 1024:
                raise ValueError
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != {"lane", "signature"}:
            raise ValueError
        lane, signature = payload["lane"], payload["signature"]
        if (
            not isinstance(lane, str) or lane not in LIMITS
            or not isinstance(signature, str) or _SIGNATURE.fullmatch(signature) is None
        ):
            raise ValueError
    except (ValueError, TypeError):
        return web.json_response({"allowed": False}, headers={"Cache-Control": "no-store"})

    database = request.app.get(PWA_DATABASE)
    outcome = "unavailable"
    if database is not None and database.factory is not None:
        try:
            outcome = await admit_frontend_event(database.factory, lane=lane, signature=signature)
        except Exception:
            # Never turn admission failure into a fresh Sentry event/log loop.
            pass
    CLIENT_SENTRY_ADMISSIONS.labels(lane=lane, outcome=outcome).inc()
    return web.json_response(
        {"allowed": outcome == "admitted"}, headers={"Cache-Control": "no-store"},
    )
