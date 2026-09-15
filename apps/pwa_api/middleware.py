"""aiohttp request-security and authentication boundary for audience APIs.

The pure proxy/origin policy lives in :mod:`helpers.pwa.request_security`;
this module only adapts trusted aiohttp transport facts and attaches the
server-authoritative principal to the current request.  See ADR 0003 and
Phase 1 in ``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass

from aiohttp import web
from helpers.pwa.request_trace import trace_stage
from aiohttp.web_urldispatcher import SystemRoute

from apps.pwa_api.auth_service import (
    AuthenticatedSession,
    AuthFailureCode,
    AuthServiceError,
    PwaAuthService,
)
from apps.pwa_api.errors import PwaApiError
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from helpers.pwa.request_security import RequestBoundary, evaluate_request_security
from models.pwa.auth import AuthAudience


_AUDIENCE_API_PATH = re.compile(
    r"^/(?P<audience>student|family|staff)/api/v1(?:/(?P<resource>.*))?/?$"
)
_PUBLIC_ROUTES = frozenset(
    {
        ("GET", "health"),
        ("HEAD", "health"),
        ("GET", "runtime"),
        ("HEAD", "runtime"),
        ("POST", "auth/login"),
        ("POST", "auth/refresh"),
        ("POST", "auth/logout"),
    }
)
_AUTH_JSON_MUTATIONS = frozenset(
    {
        "auth/login",
        "auth/refresh",
        "auth/logout",
        "auth/logout-all",
    }
)


@dataclass(slots=True)
class PwaAuthState:
    """Composition-time auth configuration plus startup-created service."""

    runtime_config: AuthRuntimeConfig
    service: PwaAuthService | None = None


PWA_AUTH_STATE = web.AppKey("pwa_auth_state", PwaAuthState)
PWA_REQUEST_BOUNDARY = web.AppKey("pwa_request_boundary", RequestBoundary)
PWA_AUTHENTICATED_SESSION = web.AppKey(
    "pwa_authenticated_session",
    AuthenticatedSession,
)


def _api_match(request: web.Request) -> re.Match[str] | None:
    return _AUDIENCE_API_PATH.fullmatch(request.path)


def _resource(match: re.Match[str]) -> str:
    return (match.group("resource") or "").rstrip("/")


def _transport_peer(request: web.Request) -> tuple[str | None, str | None]:
    """Return mutually exclusive TCP peer or exact bound AF_UNIX path."""

    transport = request.transport
    if transport is None:
        return None, None
    transport_socket = transport.get_extra_info("socket")
    if (
        transport_socket is not None
        and getattr(transport_socket, "family", None) == socket.AF_UNIX
    ):
        sockname = transport.get_extra_info("sockname")
        if isinstance(sockname, (str, bytes)):
            return None, os.fsdecode(sockname)
        return None, None
    peer = transport.get_extra_info("peername")
    if isinstance(peer, tuple) and peer:
        return str(peer[0]), None
    return None, None


def _request_id(request: web.Request) -> str:
    # The outer PWA error middleware establishes this before this middleware
    # runs. Missing state is a composition error and must not mint a second ID.
    return request["request_id"]


def _auth_error(error: AuthServiceError) -> PwaApiError:
    if error.code is AuthFailureCode.RATE_LIMITED:
        retry_after = max(1, error.retry_after_seconds or 1)
        return PwaApiError(
            status=429,
            code=error.code.value,
            message="Слишком много попыток. Попробуйте позже.",
            headers={"Retry-After": str(retry_after)},
        )
    if error.code in {
        AuthFailureCode.INVALID_CREDENTIALS,
        AuthFailureCode.ACCOUNT_UNAVAILABLE,
    }:
        # Account state and credential failures intentionally use the same
        # copy; the stable code is for client state, never user enumeration.
        return PwaApiError(
            status=401,
            code=error.code.value,
            message="Не удалось войти. Проверьте логин и данные для входа.",
        )
    return PwaApiError(
        status=401,
        code=error.code.value,
        message="Сеанс завершён. Войдите снова.",
    )


def auth_service(request: web.Request) -> PwaAuthService:
    state = request.app.get(PWA_AUTH_STATE)
    service = None if state is None else state.service
    if service is None:
        raise PwaApiError(
            status=503,
            code="authentication_unavailable",
            message="Вход временно недоступен",
        )
    return service


def authenticated_session(request: web.Request) -> AuthenticatedSession:
    try:
        return request[PWA_AUTHENTICATED_SESSION]
    except KeyError as error:
        raise PwaApiError(
            status=401,
            code=AuthFailureCode.AUTHENTICATION_REQUIRED.value,
            message="Для продолжения войдите в кабинет.",
        ) from error


def optional_authenticated_session(
    request: web.Request,
) -> AuthenticatedSession | None:
    return request.get(PWA_AUTHENTICATED_SESSION)


def request_boundary(request: web.Request) -> RequestBoundary:
    try:
        return request[PWA_REQUEST_BOUNDARY]
    except KeyError as error:  # pragma: no cover - route/middleware invariant
        raise RuntimeError(
            "PWA auth route has no validated request boundary"
        ) from error


def validate_request_boundary(
    request: web.Request,
    *,
    audience: AuthAudience,
    expects_json: bool,
    require_browser_source: bool = False,
) -> RequestBoundary:
    """Apply the common target/proxy/origin policy to one aiohttp request."""

    state = request.app.get(PWA_AUTH_STATE)
    if state is None:
        raise PwaApiError(
            status=503,
            code="authentication_unavailable",
            message="Вход временно недоступен",
        )
    peer_address, peer_unix_socket_path = _transport_peer(request)
    decision = evaluate_request_security(
        audience=audience,
        method=request.method,
        headers=request.headers.items(),
        peer_address=peer_address,
        peer_unix_socket_path=peer_unix_socket_path,
        transport_scheme=request.scheme,
        request_host=request.host,
        config=state.runtime_config,
        expects_json=expects_json,
        require_browser_source=require_browser_source,
    )
    if decision.failure is not None:
        raise PwaApiError(
            status=decision.failure.http_status,
            code=decision.failure.code,
            message="Запрос отклонён политикой безопасности.",
        )
    assert decision.boundary is not None
    request[PWA_REQUEST_BOUNDARY] = decision.boundary
    return decision.boundary


async def authenticate_access_cookie(
    request: web.Request,
    *,
    audience: AuthAudience,
    required: bool,
) -> AuthenticatedSession | None:
    """Revalidate the audience access cookie and attach verified identity."""

    policy = COOKIE_POLICY[audience]
    try:
        with trace_stage("auth"):
            authenticated = await auth_service(request).authenticate_access(
                audience=audience,
                access_cookie_value=request.cookies.get(policy.access_name),
                request_id=_request_id(request),
                client_address=request_boundary(request).client_address,
            )
    except AuthServiceError as error:
        raise _auth_error(error) from error
    if authenticated is not None:
        request[PWA_AUTHENTICATED_SESSION] = authenticated
    elif required:
        raise PwaApiError(
            status=401,
            code=AuthFailureCode.AUTHENTICATION_REQUIRED.value,
            message="Для продолжения войдите в кабинет.",
        )
    return authenticated


@web.middleware
async def pwa_auth_request_security_middleware(request: web.Request, handler):
    """Apply exact target/origin checks to every versioned audience API."""

    match = _api_match(request)
    if match is None:
        return await handler(request)
    audience = AuthAudience(match.group("audience"))
    resource = _resource(match)
    expects_json = request.method.upper() == "POST" and resource in _AUTH_JSON_MUTATIONS
    validate_request_boundary(
        request,
        audience=audience,
        expects_json=expects_json,
    )
    return await handler(request)


@web.middleware
async def pwa_authentication_middleware(request: web.Request, handler):
    """Revalidate access cookies under a small explicit public allowlist."""

    match = _api_match(request)
    if match is None:
        return await handler(request)
    resource = _resource(match)
    # Preserve aiohttp's 404/405 contract for routes which do not exist. Every
    # newly registered audience API route, however, becomes private without an
    # opt-in decorator. This is the Phase-1 public allowlist boundary.
    if isinstance(request.match_info.route, SystemRoute):
        return await handler(request)
    route_key = (request.method.upper(), resource)
    is_public = route_key in _PUBLIC_ROUTES
    is_optional_logout = route_key == ("POST", "auth/logout")

    if route_key in {
        ("GET", "health"),
        ("HEAD", "health"),
        ("GET", "runtime"),
        ("HEAD", "runtime"),
    }:
        return await handler(request)

    audience = AuthAudience(match.group("audience"))
    try:
        if not is_public or is_optional_logout:
            await authenticate_access_cookie(
                request,
                audience=audience,
                required=not is_public,
            )
        return await handler(request)
    except AuthServiceError as error:
        # Route-level operations such as refresh can fail after the access
        # middleware has run; keep the same stable secret-free mapping.
        raise _auth_error(error) from error


__all__ = [
    "PWA_AUTHENTICATED_SESSION",
    "PWA_AUTH_STATE",
    "PWA_REQUEST_BOUNDARY",
    "PwaAuthState",
    "auth_service",
    "authenticate_access_cookie",
    "authenticated_session",
    "optional_authenticated_session",
    "pwa_auth_request_security_middleware",
    "pwa_authentication_middleware",
    "request_boundary",
    "validate_request_boundary",
]
