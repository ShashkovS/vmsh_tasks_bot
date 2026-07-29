"""Authenticated Student and Family notification endpoints."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.notifications import (
    InvalidNotificationPreference,
    NotificationCourseNotFound,
    NotificationNotFound,
    acknowledge_event,
    read_events,
    read_course_preferences,
    read_preferences,
    update_preference,
    update_course_preference,
)


notification_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="notifications_unavailable",
            message="Уведомления временно недоступны",
        )
    return state.factory


def _identity(request: web.Request) -> tuple[int, int, AuthAudience]:
    authenticated = authenticated_session(request)
    principal = authenticated.principal
    if principal.audience not in {
        AuthAudience.STUDENT,
        AuthAudience.FAMILY,
    } or not principal.has_capability(Capability.NOTIFICATION_MANAGE):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для управления уведомлениями",
        )
    return (
        authenticated.current.session.account_id,
        authenticated.current.session.id,
        principal.audience,
    )


async def _json(request: web.Request) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть JSON",
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
            message="Проверьте настройки уведомлений",
        )
    return payload


def _preference_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "category": item["category"],
        "inAppEnabled": bool(item["in_app_enabled"]),
        "pushEnabled": bool(item["push_enabled"]),
        "soundEnabled": bool(item["sound_enabled"]),
        "quietStartsLocal": item["quiet_starts_local"],
        "quietEndsLocal": item["quiet_ends_local"],
        "timezone": item["timezone"],
        "updatedAt": item["updated_at"],
    }


def _course_preference_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "category": item["category"],
        "pushEnabled": bool(item["push_enabled"]),
        "inherited": bool(item["inherited"]),
        "updatedAt": item["updated_at"],
    }


def _student_account_id(request: web.Request) -> int:
    account_id, _session_id, audience = _identity(request)
    if audience is not AuthAudience.STUDENT:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Настройки курса доступны только школьнику",
        )
    return account_id


def _course_public_id(request: web.Request) -> str:
    value = request.match_info["course_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="course_not_found",
            message="Курс не найден",
        )
    return value


async def _get_events(request: web.Request) -> web.Response:
    account_id, _session_id, _audience = _identity(request)
    try:
        limit = int(request.query.get("limit", "50"))
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметр limit"
        ) from error
    unread_value = request.query.get("unreadOnly", "false")
    if limit < 1 or limit > 100 or unread_value not in {"true", "false"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка уведомлений",
        )
    items = await _factory(request).run_read_async(
        lambda connection: read_events(
            connection,
            account_id=account_id,
            limit=limit,
            unread_only=unread_value == "true",
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [
                {
                    "eventId": item["public_id"],
                    "category": item["category"],
                    "route": item["route"],
                    "payload": item["payload"],
                    "occurredAt": item["occurred_at"],
                    "deliverAfter": item["deliver_after"],
                    "readAt": item["read_at"],
                }
                for item in items
            ],
            "requestId": request["request_id"],
        }
    )


async def _get_preferences(request: web.Request) -> web.Response:
    account_id, _session_id, _audience = _identity(request)
    items = await _factory(request).run_read_async(
        lambda connection: read_preferences(connection, account_id)
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_preference_payload(item) for item in items],
            "requestId": request["request_id"],
        }
    )


async def _put_preferences(request: web.Request) -> web.Response:
    account_id, _session_id, _audience = _identity(request)
    payload = await _json(request)
    expected_fields = {
        "schemaVersion",
        "category",
        "inAppEnabled",
        "pushEnabled",
        "soundEnabled",
        "quietStartsLocal",
        "quietEndsLocal",
        "timezone",
    }
    if (
        set(payload) != expected_fields
        or not all(
            isinstance(payload[field], bool)
            for field in ("inAppEnabled", "pushEnabled", "soundEnabled")
        )
        or not all(
            isinstance(payload[field], str)
            for field in ("category", "quietStartsLocal", "quietEndsLocal", "timezone")
        )
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте настройки уведомлений",
        )
    try:
        item = await _factory(request).run_write_async(
            lambda connection: update_preference(
                connection,
                account_id=account_id,
                category=str(payload["category"]),
                in_app_enabled=bool(payload["inAppEnabled"]),
                push_enabled=bool(payload["pushEnabled"]),
                sound_enabled=bool(payload["soundEnabled"]),
                quiet_starts_local=str(payload["quietStartsLocal"]),
                quiet_ends_local=str(payload["quietEndsLocal"]),
                timezone=str(payload["timezone"]),
                now=_now(),
            )
        )
    except InvalidNotificationPreference as error:
        raise PwaApiError(
            status=422,
            code="invalid_notification_preference",
            message="Проверьте настройки уведомлений",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "preference": _preference_payload(item),
            "requestId": request["request_id"],
        }
    )


async def _get_course_preferences(request: web.Request) -> web.Response:
    account_id = _student_account_id(request)
    course_public_id = _course_public_id(request)
    try:
        course, items = await _factory(request).run_read_async(
            lambda connection: read_course_preferences(
                connection,
                account_id=account_id,
                course_public_id=course_public_id,
            )
        )
    except NotificationCourseNotFound as error:
        raise PwaApiError(
            status=404,
            code="course_not_found",
            message="Курс не найден",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "courseId": course["public_id"],
            "items": [_course_preference_payload(item) for item in items],
            "requestId": request["request_id"],
        }
    )


async def _put_course_preference(request: web.Request) -> web.Response:
    account_id = _student_account_id(request)
    course_public_id = _course_public_id(request)
    payload = await _json(request)
    if (
        set(payload) != {"schemaVersion", "category", "pushEnabled"}
        or not isinstance(payload["category"], str)
        or (
            payload["pushEnabled"] is not None
            and not isinstance(payload["pushEnabled"], bool)
        )
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте настройку курса",
        )
    try:
        item = await _factory(request).run_write_async(
            lambda connection: update_course_preference(
                connection,
                account_id=account_id,
                course_public_id=course_public_id,
                category=str(payload["category"]),
                push_enabled=payload["pushEnabled"],
                now=_now(),
            )
        )
    except NotificationCourseNotFound as error:
        raise PwaApiError(
            status=404,
            code="course_not_found",
            message="Курс не найден",
        ) from error
    except InvalidNotificationPreference as error:
        raise PwaApiError(
            status=422,
            code="invalid_notification_preference",
            message="Проверьте настройку курса",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "courseId": course_public_id,
            "preference": _course_preference_payload(item),
            "requestId": request["request_id"],
        }
    )


async def _post_read(request: web.Request) -> web.Response:
    account_id, session_id, _audience = _identity(request)
    event_public_id = request.match_info["event_public_id"]
    if _PUBLIC_ID.fullmatch(event_public_id) is None:
        raise PwaApiError(
            status=404,
            code="notification_not_found",
            message="Уведомление не найдено",
        )
    payload = await _json(request)
    if set(payload) != {"schemaVersion"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте запрос",
        )
    try:
        item = await _factory(request).run_write_async(
            lambda connection: acknowledge_event(
                connection,
                account_id=account_id,
                event_public_id=event_public_id,
                session_id=session_id,
                now=_now(),
            )
        )
    except NotificationNotFound as error:
        raise PwaApiError(
            status=404,
            code="notification_not_found",
            message="Уведомление не найдено",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "eventId": item["public_id"],
            "readAt": item["read_at"],
            "requestId": request["request_id"],
        }
    )


for audience in ("student", "family"):
    notification_routes.get(f"/{audience}/api/v1/notification-events")(_get_events)
    notification_routes.get(f"/{audience}/api/v1/notifications/preferences")(
        _get_preferences
    )
    notification_routes.put(f"/{audience}/api/v1/notifications/preferences")(
        _put_preferences
    )
    notification_routes.post(
        f"/{audience}/api/v1/notification-events/{{event_public_id}}/read"
    )(_post_read)

notification_routes.get(
    "/student/api/v1/courses/{course_public_id}/notifications/preferences"
)(_get_course_preferences)
notification_routes.put(
    "/student/api/v1/courses/{course_public_id}/notifications/preferences"
)(_put_course_preference)


__all__ = ["notification_routes"]
