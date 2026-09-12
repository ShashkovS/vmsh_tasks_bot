"""Authenticated Student and Family notification endpoints."""

from __future__ import annotations

import json
import re
import logging
from collections.abc import Awaitable, Callable
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
from models.pwa.family_digest import (
    FamilyDigestLessonNotActive,
    FamilyDigestLessonNotFound,
    preview_family_digest,
    send_family_digest,
)


notification_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)
FamilyDigestInvalidator = Callable[[tuple[str, ...]], Awaitable[None]]
PWA_FAMILY_DIGEST_INVALIDATOR = web.AppKey(
    "pwa_family_digest_invalidator", FamilyDigestInvalidator
)
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


def _admin_identity(request: web.Request) -> tuple[int, str]:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
        or not principal.has_capability(Capability.BROADCAST_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Отправить итог семье может только администратор",
        )
    return principal.linked_user_id, principal.account_public_id


def _group_lesson_public_id(request: web.Request) -> str:
    value = request.match_info["group_lesson_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="group_lesson_not_found",
            message="Занятие не найдено",
        )
    return value


def _digest_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "groupLessonId": item["groupLessonId"],
        "courseId": item["courseId"],
        "courseName": item["courseName"],
        "groupId": item["groupId"],
        "groupName": item["groupName"],
        "lessonNumber": item["lessonNumber"],
        "studentCount": item["studentCount"],
        "familyCount": item["familyCount"],
        "alreadySentFamilyCount": item["alreadySentFamilyCount"],
        "pendingFamilyCount": item["pendingFamilyCount"],
        "unlinkedStudents": item["unlinkedStudents"],
    }


def _family_digest_error(error: Exception) -> PwaApiError:
    if isinstance(error, FamilyDigestLessonNotFound):
        return PwaApiError(
            status=404,
            code="group_lesson_not_found",
            message="Занятие не найдено",
        )
    return PwaApiError(
        status=409,
        code="group_lesson_not_active",
        message="Итог можно отправить только для действующего занятия",
    )


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
            now=_now(),
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


@notification_routes.get(
    "/staff/api/v1/group-lessons/{group_lesson_public_id}/family-digest"
)
async def _get_family_digest(request: web.Request) -> web.Response:
    _admin_identity(request)
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    group_lesson_public_id = _group_lesson_public_id(request)
    try:
        item = await _factory(request).run_read_async(
            lambda connection: preview_family_digest(
                connection,
                group_lesson_public_id=group_lesson_public_id,
            )
        )
    except (FamilyDigestLessonNotFound, FamilyDigestLessonNotActive) as error:
        raise _family_digest_error(error) from error
    item.pop("families")
    return web.json_response(
        {
            "schemaVersion": 1,
            "digest": _digest_payload(item),
            "requestId": request["request_id"],
        }
    )


@notification_routes.post(
    "/staff/api/v1/group-lessons/{group_lesson_public_id}/family-digest"
)
async def _post_family_digest(request: web.Request) -> web.Response:
    actor_user_id, actor_account_public_id = _admin_identity(request)
    group_lesson_public_id = _group_lesson_public_id(request)
    body = await _json(request)
    if set(body) != {"schemaVersion"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте запрос отправки",
        )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: send_family_digest(
                connection,
                group_lesson_public_id=group_lesson_public_id,
                actor_user_id=actor_user_id,
                actor_account_public_id=actor_account_public_id,
                request_id=request["request_id"],
                now=_now(),
            )
        )
    except (FamilyDigestLessonNotFound, FamilyDigestLessonNotActive) as error:
        raise _family_digest_error(error) from error

    account_ids = result.pop("createdAccountPublicIds")
    if account_ids:
        invalidator = request.app.get(PWA_FAMILY_DIGEST_INVALIDATOR)
        if invalidator is not None:
            try:
                await invalidator(account_ids)
            except Exception:
                # SQLite is authoritative; a transient refetch hint must not
                # invite an admin to repeat an already committed notification.
                logger.warning("Family digest invalidation failed", exc_info=True)
    return web.json_response(
        {
            "schemaVersion": 1,
            "digest": _digest_payload(result["digest"]),
            "createdFamilyCount": result["createdFamilyCount"],
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


__all__ = ["PWA_FAMILY_DIGEST_INVALIDATOR", "notification_routes"]
