"""Admin HTTP boundary for versioned classroom layouts."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.classroom_layouts import (
    ClassroomLayoutConflict,
    ClassroomLayoutNotFound,
    InvalidClassroomLayout,
    confirm_layout,
    materialize_layout,
    read_effective_layout,
    replace_draft_layout,
)


classroom_layout_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="classroom_layout_unavailable",
            message="Схема аудиторий временно недоступна",
        )
    return state.factory


def _admin_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
        or not principal.has_capability(Capability.CLASSROOM_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Управлять схемой аудиторий может только администратор",
        )
    return principal.linked_user_id


def _public_id(request: web.Request, field: str) -> str:
    value = request.match_info[field]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="classroom_layout_not_found",
            message="Схема аудиторий не найдена",
        )
    return value


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
            message="Проверьте поля схемы аудиторий",
        )
    return payload


def _expected_version(request: web.Request, layout_public_id: str) -> int:
    values = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите схему перед сохранением",
        )
    if match.group(1) != layout_public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Схема уже изменилась. Обновите страницу.",
        )
    return int(match.group(2))


def _serialize(result: dict[str, object]) -> dict[str, object]:
    event = result["event"]
    return {
        "event": {
            "publicId": event["public_id"],
            "name": event["name"],
            "startsAt": event["starts_at"],
            "endsAt": event["ends_at"],
            "status": event["status"],
            "version": event["version"],
        },
        "state": result["state"],
        "publicId": result["layout_public_id"],
        "version": result["version"],
        "groups": [
            {
                "groupLessonPublicId": group["group_lesson_public_id"],
                "coursePublicId": group["course_public_id"],
                "courseName": group["course_name"],
                "groupPublicId": group["group_public_id"],
                "groupName": group["group_name"],
                "shortCode": group["short_code"],
                "colorKey": group["color_key"],
                "lessonNumber": group["lesson_number"],
                "inPersonCount": group["in_person_count"],
                "assignedCount": 0,
            }
            for group in result["groups"]
        ],
        "rooms": [
            {
                "classroomPublicId": room["classroom_public_id"],
                "classroomName": room["classroom_name"],
                "classroomStatus": room["classroom_status"],
                "groupLessonPublicId": room["group_lesson_public_id"],
                "coursePublicId": room["course_public_id"],
                "groupPublicId": room["group_public_id"],
                "groupName": room["group_name"],
                "sourceLayoutPublicId": room["source_layout_public_id"],
            }
            for room in result["rooms"]
        ],
        "conflicts": [
            {
                "classroomPublicId": conflict["classroom_public_id"],
                "classroomName": conflict["classroom_name"],
            }
            for conflict in result["conflicts"]
        ],
    }


def _response(request: web.Request, result: dict[str, object]) -> web.Response:
    response = web.json_response(
        {
            "schemaVersion": 1,
            "layout": _serialize(result),
            "requestId": request["request_id"],
        }
    )
    if result["layout_public_id"] is not None:
        response.headers["ETag"] = (
            f'"{result["layout_public_id"]}:v{result["version"]}"'
        )
    return response


def _raise_layout_error(error: Exception) -> None:
    if isinstance(error, ClassroomLayoutNotFound):
        raise PwaApiError(
            status=404,
            code="classroom_layout_not_found",
            message="Схема аудиторий не найдена",
        ) from error
    if isinstance(error, ClassroomLayoutConflict):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Схема уже изменилась. Обновите страницу.",
        ) from error
    if isinstance(error, InvalidClassroomLayout):
        raise PwaApiError(
            status=422,
            code="invalid_classroom_layout",
            message="Проверьте распределение аудиторий по группам",
        ) from error
    raise error


@classroom_layout_routes.get(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-layout"
)
async def get_classroom_layout(request: web.Request) -> web.Response:
    _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    try:
        result = await _factory(request).run_read_async(
            lambda connection: read_effective_layout(connection, event_public_id)
        )
    except (
        ClassroomLayoutNotFound,
        ClassroomLayoutConflict,
        InvalidClassroomLayout,
    ) as error:
        _raise_layout_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


@classroom_layout_routes.post(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-layout/materialize"
)
async def post_materialize_classroom_layout(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    payload = await _json(request)
    if set(payload) != {"schemaVersion"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля схемы аудиторий",
        )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: materialize_layout(
                connection,
                event_public_id=event_public_id,
                layout_public_id=f"classroom-layout.{uuid.uuid4().hex}",
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except (
        ClassroomLayoutNotFound,
        ClassroomLayoutConflict,
        InvalidClassroomLayout,
    ) as error:
        _raise_layout_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


def _parse_mappings(payload: dict[str, object]) -> list[tuple[str, str]]:
    if set(payload) != {"schemaVersion", "mappings"} or not isinstance(
        payload["mappings"], list
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте список аудиторий",
        )
    if len(payload["mappings"]) > 500:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Слишком много аудиторий",
        )
    mappings = []
    for item in payload["mappings"]:
        if not isinstance(item, dict) or set(item) != {
            "classroomPublicId",
            "groupLessonPublicId",
        }:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Проверьте список аудиторий",
            )
        classroom_public_id = item["classroomPublicId"]
        group_lesson_public_id = item["groupLessonPublicId"]
        if (
            not isinstance(classroom_public_id, str)
            or _PUBLIC_ID.fullmatch(classroom_public_id) is None
            or not isinstance(group_lesson_public_id, str)
            or _PUBLIC_ID.fullmatch(group_lesson_public_id) is None
        ):
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Проверьте список аудиторий",
            )
        mappings.append((classroom_public_id, group_lesson_public_id))
    return mappings


@classroom_layout_routes.put(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-layout/"
    "{layout_public_id}/rooms"
)
async def put_classroom_layout_rooms(request: web.Request) -> web.Response:
    _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    layout_public_id = _public_id(request, "layout_public_id")
    expected_version = _expected_version(request, layout_public_id)
    mappings = _parse_mappings(await _json(request))
    try:
        result = await _factory(request).run_write_async(
            lambda connection: replace_draft_layout(
                connection,
                event_public_id=event_public_id,
                layout_public_id=layout_public_id,
                expected_version=expected_version,
                mappings=mappings,
                now=_now(),
            )
        )
    except (
        ClassroomLayoutNotFound,
        ClassroomLayoutConflict,
        InvalidClassroomLayout,
    ) as error:
        _raise_layout_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


@classroom_layout_routes.post(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-layout/"
    "{layout_public_id}/confirm"
)
async def post_confirm_classroom_layout(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    layout_public_id = _public_id(request, "layout_public_id")
    expected_version = _expected_version(request, layout_public_id)
    payload = await _json(request)
    if set(payload) != {"schemaVersion"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля схемы аудиторий",
        )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: confirm_layout(
                connection,
                event_public_id=event_public_id,
                layout_public_id=layout_public_id,
                expected_version=expected_version,
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except (
        ClassroomLayoutNotFound,
        ClassroomLayoutConflict,
        InvalidClassroomLayout,
    ) as error:
        _raise_layout_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


__all__ = ["classroom_layout_routes"]
