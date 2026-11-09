"""Authenticated Student and Family Web Push subscription endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.push_subscriptions import (
    InvalidPushSubscription,
    register_subscription,
    unregister_subscription,
)


push_subscription_routes = web.RouteTableDef()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity(request: web.Request) -> tuple[int, int]:
    authenticated = authenticated_session(request)
    principal = authenticated.principal
    if principal.audience not in {
        AuthAudience.STUDENT,
        AuthAudience.FAMILY,
    } or not principal.has_capability(Capability.NOTIFICATION_MANAGE):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для управления push-уведомлениями",
        )
    return (
        authenticated.current.session.account_id,
        authenticated.current.session.id,
    )


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="push_unavailable",
            message="Push-уведомления временно недоступны",
        )
    return state.factory


async def _json(request: web.Request) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        payload = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть корректным JSON-объектом",
        ) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные push-подписки",
        )
    return payload


async def _get_config(request: web.Request) -> web.Response:
    _identity(request)
    public_key = request.app[RUNTIME_CONFIG].pwa_vapid_public_key
    return web.json_response(
        {
            "schemaVersion": 1,
            "enabled": bool(public_key),
            "applicationServerKey": public_key or None,
            "requestId": request["request_id"],
        }
    )


async def _post_subscription(request: web.Request) -> web.Response:
    account_id, session_id = _identity(request)
    if not request.app[RUNTIME_CONFIG].pwa_vapid_public_key:
        raise PwaApiError(
            status=503,
            code="push_not_configured",
            message="Push-уведомления пока не настроены",
        )
    payload = await _json(request)
    if set(payload) != {"schemaVersion", "endpoint", "expirationTime", "keys"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные push-подписки",
        )
    keys = payload["keys"]
    if (
        not isinstance(payload["endpoint"], str)
        or (
            payload["expirationTime"] is not None
            and (
                not isinstance(payload["expirationTime"], int)
                or isinstance(payload["expirationTime"], bool)
            )
        )
        or not isinstance(keys, dict)
        or set(keys) != {"p256dh", "auth"}
        or not all(isinstance(keys[key], str) for key in ("p256dh", "auth"))
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные push-подписки",
        )
    try:
        public_id = await _factory(request).run_write_async(
            lambda connection: register_subscription(
                connection,
                account_id=account_id,
                session_id=session_id,
                endpoint=str(payload["endpoint"]),
                p256dh=str(keys["p256dh"]),
                auth_secret=str(keys["auth"]),
                expiration_time=payload["expirationTime"],
                user_agent=request.headers.get("User-Agent"),
                now=_now(),
            )
        )
    except InvalidPushSubscription as error:
        raise PwaApiError(
            status=422,
            code="invalid_push_subscription",
            message="Браузер вернул некорректную push-подписку",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "subscriptionId": public_id,
            "requestId": request["request_id"],
        }
    )


async def _delete_subscription(request: web.Request) -> web.Response:
    account_id, _session_id = _identity(request)
    payload = await _json(request)
    if set(payload) != {"schemaVersion", "endpoint"} or not isinstance(
        payload["endpoint"], str
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные push-подписки",
        )
    try:
        deleted = await _factory(request).run_write_async(
            lambda connection: unregister_subscription(
                connection,
                account_id=account_id,
                endpoint=str(payload["endpoint"]),
            )
        )
    except InvalidPushSubscription as error:
        raise PwaApiError(
            status=422,
            code="invalid_push_subscription",
            message="Браузер вернул некорректную push-подписку",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "deleted": deleted,
            "requestId": request["request_id"],
        }
    )


for audience in ("student", "family"):
    base = f"/{audience}/api/v1/push-subscriptions"
    push_subscription_routes.get(f"{base}/config")(_get_config)
    push_subscription_routes.post(base)(_post_subscription)
    push_subscription_routes.delete(base)(_delete_subscription)


__all__ = ["push_subscription_routes"]
