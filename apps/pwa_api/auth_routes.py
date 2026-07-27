"""Versioned HTTP authentication routes for Student, Family and Staff."""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from email.utils import format_datetime

from aiohttp import web

from apps.pwa_api.auth_service import AuthenticatedSession, IssuedSession, SUPPORT_EMAIL
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import (
    auth_service,
    authenticated_session,
    optional_authenticated_session,
    request_boundary,
)
from apps.pwa_api.realtime_control import realtime_session_controller
from db_methods.pwa.auth import AuthSessionRecord
from helpers.pwa.auth_config import COOKIE_POLICY, AudienceCookiePolicy
from models.pwa.auth import AuthAudience


AUTH_BODY_LIMIT_BYTES = 16 * 1024
_SESSION_PUBLIC_ID = re.compile(r"[0-9a-f]{32}\Z")
auth_routes = web.RouteTableDef()


def _audience(request: web.Request) -> AuthAudience:
    return AuthAudience(request.match_info["audience"])


def _request_id(request: web.Request) -> str:
    return request["request_id"]


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Authentication timestamp must be timezone-aware")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _display_name(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part.strip())


def _session_payload(
    session: AuthSessionRecord,
    *,
    current_session_public_id: str,
) -> dict[str, object]:
    return {
        "sessionId": session.public_id,
        "audience": session.audience.value,
        "isCurrent": session.public_id == current_session_public_id,
        "deviceLabel": session.device_label,
        "userAgentFamily": session.user_agent_family,
        "createdAt": _iso(session.created_at),
        "lastSeenAt": _iso(session.last_seen_at),
        "expiresAt": _iso(session.expires_at),
    }


def _principal_payload(authenticated: AuthenticatedSession) -> dict[str, object]:
    current = authenticated.current
    principal = authenticated.principal
    common: dict[str, object] = {
        "accountId": principal.account_public_id,
        "audience": principal.audience.value,
        "displayName": current.display_name,
        "sessionVersion": principal.session_version,
        "credentialVersion": principal.credential_version,
    }
    if principal.audience is AuthAudience.STUDENT:
        if (
            current.linked_user_public_id is None
        ):  # pragma: no cover - service invariant
            raise RuntimeError("Student principal has no public user ID")
        common["userId"] = current.linked_user_public_id
    elif principal.audience is AuthAudience.FAMILY:
        common["linkedChildren"] = [
            {
                "studentId": child.student_public_id,
                "displayName": _display_name(child.name, child.surname),
                "relationshipLabel": child.relationship_label,
                "isPrimary": child.is_primary,
            }
            for child in authenticated.family_children
        ]
    else:
        if (
            current.linked_user_public_id is None
        ):  # pragma: no cover - service invariant
            raise RuntimeError("Staff principal has no public user ID")
        common.update(
            {
                "userId": current.linked_user_public_id,
                "role": principal.role.value,
                "capabilities": list(principal.capability_names),
                "scopes": [
                    {
                        "courseId": scope.course_public_id,
                        "groupId": scope.group_public_id,
                        "role": scope.role.value,
                        "validFrom": _iso(scope.valid_from),
                        "validTo": (
                            None if scope.valid_to is None else _iso(scope.valid_to)
                        ),
                        "version": scope.version,
                    }
                    for scope in authenticated.staff_scopes
                ],
            }
        )
    return common


def _auth_context_payload(
    authenticated: AuthenticatedSession,
    *,
    access_expires_at: datetime,
) -> dict[str, object]:
    current = authenticated.current.session
    return {
        "principal": _principal_payload(authenticated),
        "currentSession": _session_payload(
            current,
            current_session_public_id=current.public_id,
        ),
        "policy": {
            "accessExpiresAt": _iso(access_expires_at),
            "sessionExpiresAt": _iso(current.expires_at),
            "supportEmail": SUPPORT_EMAIL,
        },
    }


async def _json_object(request: web.Request) -> dict[str, object]:
    if (
        request.content_length is not None
        and request.content_length > AUTH_BODY_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Запрос слишком большой",
        )
    try:
        raw_body = await request.read()
    except web.HTTPRequestEntityTooLarge as error:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Запрос слишком большой",
        ) from error
    if len(raw_body) > AUTH_BODY_LIMIT_BYTES:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Запрос слишком большой",
        )
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PwaApiError(
            status=400,
            code="invalid_json",
            message="Тело запроса должно быть корректным JSON",
        ) from error
    if not isinstance(payload, dict):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
        )
    return payload


def _required_string(
    payload: dict[str, object],
    field: str,
    *,
    maximum_length: int,
    trim: bool,
) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
            details={"fields": [field]},
        )
    normalized = value.strip() if trim else value
    if not normalized or len(normalized) > maximum_length:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
            details={"fields": [field]},
        )
    return normalized


async def _login_payload(
    request: web.Request,
    audience: AuthAudience,
) -> tuple[str, str, str | None]:
    payload = await _json_object(request)
    credential_field = (
        "telegramToken" if audience is AuthAudience.STUDENT else "password"
    )
    allowed = {"username", credential_field, "deviceLabel"}
    if not set(payload).issubset(allowed):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
        )
    username = _required_string(
        payload,
        "username",
        maximum_length=128,
        trim=True,
    )
    credential = _required_string(
        payload,
        credential_field,
        maximum_length=512,
        trim=False,
    )
    device_label: str | None = None
    if "deviceLabel" in payload:
        device_label = _required_string(
            payload,
            "deviceLabel",
            maximum_length=120,
            trim=True,
        )
    return username, credential, device_label


async def _require_empty_object(request: web.Request) -> None:
    if await _json_object(request) != {}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть пустым JSON-объектом",
        )


def _cookie_expiry(value: datetime) -> str:
    return format_datetime(value.astimezone(UTC), usegmt=True)


def _max_age(value: datetime) -> int:
    return max(
        0,
        math.ceil((value.astimezone(UTC) - datetime.now(UTC)).total_seconds()),
    )


def _set_cookie(
    response: web.StreamResponse,
    *,
    name: str,
    value: str,
    policy: AudienceCookiePolicy,
    secure: bool,
    expires_at: datetime,
) -> None:
    response.set_cookie(
        name,
        value,
        path=policy.path,
        secure=secure,
        httponly=policy.http_only,
        samesite=policy.same_site,
        max_age=_max_age(expires_at),
        expires=_cookie_expiry(expires_at),
    )


def _set_session_cookies_for_request(
    request: web.Request,
    response: web.StreamResponse,
    issued: IssuedSession,
) -> None:
    audience = issued.authenticated.principal.audience
    policy = COOKIE_POLICY[audience]
    secure = auth_service(request).runtime_config.secure_cookies
    _set_cookie(
        response,
        name=policy.access_name,
        value=issued.access_cookie_value,
        policy=policy,
        secure=secure,
        expires_at=issued.access_expires_at,
    )
    _set_cookie(
        response,
        name=policy.refresh_name,
        value=issued.refresh_cookie_value,
        policy=policy,
        secure=secure,
        expires_at=issued.authenticated.current.session.expires_at,
    )


def _clear_session_cookies(request: web.Request, response: web.StreamResponse) -> None:
    audience = _audience(request)
    policy = COOKIE_POLICY[audience]
    secure = auth_service(request).runtime_config.secure_cookies
    for name in (policy.access_name, policy.refresh_name):
        response.set_cookie(
            name,
            "",
            path=policy.path,
            secure=secure,
            httponly=policy.http_only,
            samesite=policy.same_site,
            max_age=0,
            expires="Thu, 01 Jan 1970 00:00:00 GMT",
        )


@auth_routes.post("/{audience:student|family|staff}/api/v1/auth/login")
async def login(request: web.Request) -> web.Response:
    audience = _audience(request)
    username, credential, device_label = await _login_payload(request, audience)
    issued = await auth_service(request).login(
        audience=audience,
        username=username,
        credential=credential,
        request_id=_request_id(request),
        client_address=request_boundary(request).client_address,
        device_label=device_label,
        raw_user_agent=request.headers.get("User-Agent"),
    )
    response = web.json_response(
        _auth_context_payload(
            issued.authenticated,
            access_expires_at=issued.access_expires_at,
        )
    )
    _set_session_cookies_for_request(request, response, issued)
    return response


@auth_routes.post("/{audience:student|family|staff}/api/v1/auth/refresh")
async def refresh(request: web.Request) -> web.Response:
    await _require_empty_object(request)
    audience = _audience(request)
    policy = COOKIE_POLICY[audience]
    issued = await auth_service(request).refresh(
        audience=audience,
        refresh_cookie_value=request.cookies.get(policy.refresh_name),
        request_id=_request_id(request),
        client_address=request_boundary(request).client_address,
    )
    response = web.json_response(
        _auth_context_payload(
            issued.authenticated,
            access_expires_at=issued.access_expires_at,
        )
    )
    _set_session_cookies_for_request(request, response, issued)
    return response


@auth_routes.post("/{audience:student|family|staff}/api/v1/auth/logout")
async def logout(request: web.Request) -> web.Response:
    await _require_empty_object(request)
    audience = _audience(request)
    policy = COOKIE_POLICY[audience]
    service = auth_service(request)
    authenticated = optional_authenticated_session(request)
    if authenticated is not None:
        revoked = await service.revoke_session(
            authenticated,
            session_public_id=authenticated.current.session.public_id,
            request_id=_request_id(request),
            client_address=request_boundary(request).client_address,
        )
        controller = realtime_session_controller(request)
        if revoked and controller is not None:
            await controller.close_session(
                audience=authenticated.principal.audience.value,
                session_public_id=authenticated.current.session.public_id,
            )
    # Keep the refresh-authenticated path for expired/missing access cookies.
    # If a mismatched but valid refresh cookie is presented alongside access,
    # revoke both lineages instead of treating either credential as optional.
    refresh_revoked = await service.logout_by_refresh(
        audience=audience,
        refresh_cookie_value=request.cookies.get(policy.refresh_name),
        request_id=_request_id(request),
        client_address=request_boundary(request).client_address,
    )
    controller = realtime_session_controller(request)
    if refresh_revoked is not None and controller is not None:
        # Repository returns this target only after the current or consumed
        # refresh secret proves ownership. Malformed/foreign cookies never
        # become a cross-worker close command.
        await controller.close_session(
            audience=refresh_revoked.audience.value,
            session_public_id=refresh_revoked.session_public_id,
        )
    response = web.Response(status=204)
    _clear_session_cookies(request, response)
    return response


@auth_routes.get("/{audience:student|family|staff}/api/v1/auth/me")
async def me(request: web.Request) -> web.Response:
    authenticated = authenticated_session(request)
    if (
        authenticated.access_expires_at is None
    ):  # pragma: no cover - middleware invariant
        raise RuntimeError("Access-authenticated session has no cookie expiry")
    return web.json_response(
        _auth_context_payload(
            authenticated,
            access_expires_at=authenticated.access_expires_at,
        )
    )


@auth_routes.get("/{audience:student|family|staff}/api/v1/auth/sessions")
async def sessions(request: web.Request) -> web.Response:
    authenticated = authenticated_session(request)
    current_session_id = authenticated.current.session.public_id
    active_sessions = await auth_service(request).list_active_sessions(authenticated)
    return web.json_response(
        {
            "audience": authenticated.principal.audience.value,
            "sessions": [
                _session_payload(
                    session,
                    current_session_public_id=current_session_id,
                )
                for session in active_sessions
            ],
        }
    )


@auth_routes.delete(
    "/{audience:student|family|staff}/api/v1/auth/sessions/{session_public_id}"
)
async def revoke_session(request: web.Request) -> web.Response:
    session_public_id = request.match_info["session_public_id"]
    if _SESSION_PUBLIC_ID.fullmatch(session_public_id) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Некорректный идентификатор сеанса",
        )
    authenticated = authenticated_session(request)
    revoked = await auth_service(request).revoke_session(
        authenticated,
        session_public_id=session_public_id,
        request_id=_request_id(request),
        client_address=request_boundary(request).client_address,
    )
    controller = realtime_session_controller(request)
    if revoked and controller is not None:
        await controller.close_session(
            audience=authenticated.principal.audience.value,
            session_public_id=session_public_id,
        )
    response = web.Response(status=204)
    if session_public_id == authenticated.current.session.public_id:
        _clear_session_cookies(request, response)
    return response


@auth_routes.post("/{audience:student|family|staff}/api/v1/auth/logout-all")
async def logout_all(request: web.Request) -> web.Response:
    await _require_empty_object(request)
    authenticated = authenticated_session(request)
    revoked_count = await auth_service(request).logout_all(
        authenticated,
        request_id=_request_id(request),
        client_address=request_boundary(request).client_address,
    )
    controller = realtime_session_controller(request)
    if revoked_count and controller is not None:
        await controller.close_account(
            audience=authenticated.principal.audience.value,
            account_public_id=authenticated.principal.account_public_id,
        )
    response = web.Response(status=204)
    _clear_session_cookies(request, response)
    return response


__all__ = ["AUTH_BODY_LIMIT_BYTES", "auth_routes"]
