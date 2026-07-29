"""Authenticated Student/Admin HTTP endpoints for oral-admission windows."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.oral_windows import group_lesson_scope, list_windows
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.oral_windows import (
    OralWindowClosed,
    OralWindowConflict,
    OralWindowInvalid,
    OralWindowNotFound,
    create_window,
    public_window,
    student_join_details,
    student_windows,
    update_window,
)


oral_window_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_FIELDS = frozenset(
    {
        "schemaVersion",
        "sequenceNumber",
        "opensAt",
        "closesAt",
        "joinLabel",
        "joinUrl",
        "joinCode",
        "status",
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="oral_windows_unavailable",
            message="Устный приём временно недоступен",
        )
    return state.factory


def _public_id(request: web.Request, field: str) -> str:
    value = request.match_info[field]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="oral_window_not_found",
            message="Окно устного приёма не найдено",
        )
    return value


def _student_account_id(request: web.Request) -> int:
    authenticated = authenticated_session(request)
    principal = authenticated.principal
    if principal.audience is not AuthAudience.STUDENT or not principal.has_capability(
        Capability.COURSE_READ
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для просмотра устного приёма",
        )
    return authenticated.current.session.account_id


def _admin_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
        or not principal.has_capability(Capability.ORAL_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Настраивать устный приём может только администратор",
        )
    return principal.linked_user_id


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время устного приёма",
            details={"field": field},
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время устного приёма",
            details={"field": field},
        ) from error
    if parsed.tzinfo is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Укажите часовой пояс времени",
            details={"field": field},
        )
    return parsed.astimezone(UTC)


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
    if (
        not isinstance(payload, dict)
        or set(payload) != _FIELDS
        or payload.get("schemaVersion") != 1
        or isinstance(payload.get("schemaVersion"), bool)
        or not isinstance(payload.get("sequenceNumber"), int)
        or isinstance(payload.get("sequenceNumber"), bool)
        or not all(
            isinstance(payload.get(field), str)
            for field in ("joinLabel", "joinUrl", "status")
        )
        or (
            payload.get("joinCode") is not None
            and not isinstance(payload.get("joinCode"), str)
        )
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля устного приёма",
        )
    return payload


def _student_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "windowId": item["public_id"],
        "sequenceNumber": item["sequence_number"],
        "opensAt": item["opens_at"],
        "closesAt": item["closes_at"],
        "joinLabel": item["join_label"],
        "state": item["state"],
        "joinAvailable": item["join_available"],
        "version": item["version"],
    }


def _admin_payload(item: dict[str, object], now: datetime) -> dict[str, object]:
    return {
        **_student_payload(public_window(item, now)),
        "joinUrl": item["join_url"],
        "joinCode": item["join_code"],
        "status": item["status"],
    }


def _translate(error: Exception) -> PwaApiError:
    if isinstance(error, OralWindowNotFound):
        return PwaApiError(
            status=404,
            code="oral_window_not_found",
            message="Окно устного приёма не найдено",
        )
    if isinstance(error, OralWindowClosed):
        return PwaApiError(
            status=409,
            code="oral_window_closed",
            message="Сейчас это окно устного приёма закрыто",
        )
    if isinstance(error, OralWindowConflict):
        return PwaApiError(
            status=409,
            code="oral_window_conflict",
            message="Окно устного приёма уже изменилось",
        )
    return PwaApiError(
        status=422,
        code="invalid_oral_window",
        message="Проверьте настройки устного приёма",
    )


@oral_window_routes.get(
    "/student/api/v1/courses/{course_public_id}/lessons/"
    "{group_lesson_public_id}/oral-windows"
)
async def list_student_oral_windows(request: web.Request) -> web.Response:
    now = _now()
    try:
        items = await _factory(request).run_read_async(
            lambda connection: student_windows(
                connection,
                account_id=_student_account_id(request),
                course_public_id=_public_id(request, "course_public_id"),
                group_lesson_public_id=_public_id(request, "group_lesson_public_id"),
                now=now,
            )
        )
    except OralWindowNotFound as error:
        raise _translate(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_student_payload(item) for item in items],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@oral_window_routes.get(
    "/student/api/v1/courses/{course_public_id}/lessons/"
    "{group_lesson_public_id}/oral-windows/{window_public_id}/join"
)
async def get_student_oral_join(request: web.Request) -> web.Response:
    try:
        item = await _factory(request).run_read_async(
            lambda connection: student_join_details(
                connection,
                account_id=_student_account_id(request),
                course_public_id=_public_id(request, "course_public_id"),
                group_lesson_public_id=_public_id(request, "group_lesson_public_id"),
                window_public_id=_public_id(request, "window_public_id"),
                now=_now(),
            )
        )
    except (OralWindowClosed, OralWindowNotFound) as error:
        raise _translate(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "join": {
                "windowId": item["public_id"],
                "joinLabel": item["join_label"],
                "joinUrl": item["join_url"],
                "joinCode": item["join_code"],
                "closesAt": item["closes_at"],
            },
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@oral_window_routes.get(
    "/staff/api/v1/group-lessons/{group_lesson_public_id}/oral-windows"
)
async def list_staff_oral_windows(request: web.Request) -> web.Response:
    _admin_user_id(request)
    scope = await _factory(request).run_read_async(
        lambda connection: group_lesson_scope(
            connection,
            group_lesson_public_id=_public_id(request, "group_lesson_public_id"),
        )
    )
    if scope is None:
        raise _translate(OralWindowNotFound)
    now = _now()
    items = await _factory(request).run_read_async(
        lambda connection: list_windows(
            connection,
            group_lesson_id=int(scope["group_lesson_id"]),
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_admin_payload(item, now) for item in items],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@oral_window_routes.post(
    "/staff/api/v1/group-lessons/{group_lesson_public_id}/oral-windows"
)
async def create_staff_oral_window(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    payload = await _json(request)
    now = _now()
    try:
        item = await _factory(request).run_write_async(
            lambda connection: create_window(
                connection,
                group_lesson_public_id=_public_id(request, "group_lesson_public_id"),
                actor_user_id=actor_user_id,
                now=now,
                sequence_number=int(payload["sequenceNumber"]),
                opens_at=_timestamp(payload["opensAt"], "opensAt"),
                closes_at=_timestamp(payload["closesAt"], "closesAt"),
                join_label=str(payload["joinLabel"]),
                join_url=str(payload["joinUrl"]),
                join_code=(
                    None if payload["joinCode"] is None else str(payload["joinCode"])
                ),
                status=str(payload["status"]),
            )
        )
    except (OralWindowConflict, OralWindowInvalid, OralWindowNotFound) as error:
        raise _translate(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "window": _admin_payload(item, now),
            "requestId": request["request_id"],
        },
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@oral_window_routes.put("/staff/api/v1/oral-windows/{window_public_id}")
async def update_staff_oral_window(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _public_id(request, "window_public_id")
    match_values = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(match_values[0]) if len(match_values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите данные перед сохранением",
        )
    if match.group(1) != public_id:
        raise _translate(OralWindowConflict)
    payload = await _json(request)
    now = _now()
    try:
        item = await _factory(request).run_write_async(
            lambda connection: update_window(
                connection,
                public_id=public_id,
                expected_version=int(match.group(2)),
                actor_user_id=actor_user_id,
                now=now,
                sequence_number=int(payload["sequenceNumber"]),
                opens_at=_timestamp(payload["opensAt"], "opensAt"),
                closes_at=_timestamp(payload["closesAt"], "closesAt"),
                join_label=str(payload["joinLabel"]),
                join_url=str(payload["joinUrl"]),
                join_code=(
                    None if payload["joinCode"] is None else str(payload["joinCode"])
                ),
                status=str(payload["status"]),
            )
        )
    except (OralWindowConflict, OralWindowInvalid, OralWindowNotFound) as error:
        raise _translate(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "window": _admin_payload(item, now),
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["oral_window_routes"]
