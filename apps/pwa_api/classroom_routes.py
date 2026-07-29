"""Admin-only HTTP endpoints for the small global classroom catalog."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.classrooms import (
    ClassroomNameConflict,
    ClassroomNotFound,
    ClassroomVersionConflict,
    create_classroom,
    find_classroom_by_normalized_name,
    list_classrooms,
    rename_classroom,
    set_classroom_status,
)
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.classrooms import (
    InvalidClassroomName,
    normalize_classroom_search,
    prepare_classroom_name,
)


classroom_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_LIST_QUERY_FIELDS = frozenset({"search", "status"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="classroom_catalog_unavailable",
            message="Каталог аудиторий временно недоступен",
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
            message="Управлять аудиториями может только администратор",
        )
    return principal.linked_user_id


def _classroom_public_id(request: web.Request) -> str:
    public_id = request.match_info["classroom_public_id"]
    if _PUBLIC_ID.fullmatch(public_id) is None:
        raise PwaApiError(
            status=404,
            code="classroom_not_found",
            message="Аудитория не найдена",
        )
    return public_id


async def _json(request: web.Request, fields: frozenset[str]) -> dict[str, object]:
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
        or set(payload) != fields
        or payload.get("schemaVersion") != 1
        or isinstance(payload.get("schemaVersion"), bool)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля аудитории",
            details={"required": sorted(fields)},
        )
    return payload


def _expected_version(request: web.Request, public_id: str) -> int:
    values = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите данные перед сохранением",
        )
    if match.group(1) != public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аудитория уже изменилась. Обновите страницу.",
        )
    return int(match.group(2))


def _response(item: dict[str, object], *, status: int = 200) -> web.Response:
    payload = {
        "schemaVersion": 1,
        "classroom": {
            "publicId": item["public_id"],
            "name": item["name"],
            "status": item["status"],
            "createdAt": item["created_at"],
            "updatedAt": item["updated_at"],
            "version": item["version"],
        },
    }
    response = web.json_response(payload, status=status)
    response.headers["ETag"] = f'"{item["public_id"]}:v{item["version"]}"'
    return response


async def _raise_name_conflict(request: web.Request, normalized_name: str) -> None:
    existing = await _factory(request).run_read_async(
        lambda connection: find_classroom_by_normalized_name(
            connection, normalized_name
        )
    )
    raise PwaApiError(
        status=409,
        code="classroom_name_conflict",
        message="Аудитория с таким названием уже есть",
        details={
            "existingPublicId": None if existing is None else existing["public_id"]
        },
    )


@classroom_routes.get("/staff/api/v1/classrooms")
async def get_classrooms(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if set(request.query) - _LIST_QUERY_FIELDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры поиска",
        )
    status_value = request.query.get("status", "active")
    if status_value not in {"active", "archived", "all"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный статус аудитории",
            details={"field": "status"},
        )
    search = request.query.get("search", "")
    if len(search) > 200:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Поисковый запрос слишком длинный",
            details={"field": "search"},
        )
    rows = await _factory(request).run_read_async(
        lambda connection: list_classrooms(
            connection,
            status=None if status_value == "all" else status_value,
            normalized_search=normalize_classroom_search(search),
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [
                {
                    "publicId": row["public_id"],
                    "name": row["name"],
                    "status": row["status"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                    "version": row["version"],
                }
                for row in rows
            ],
        }
    )


@classroom_routes.post("/staff/api/v1/classrooms")
async def post_classroom(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    payload = await _json(request, frozenset({"schemaVersion", "name"}))
    try:
        name, normalized_name = prepare_classroom_name(payload["name"])
    except InvalidClassroomName as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Введите название аудитории",
            details={"field": "name"},
        ) from error
    now = _now()
    try:
        item = await _factory(request).run_write_async(
            lambda connection: create_classroom(
                connection,
                public_id=f"classroom.{uuid.uuid4().hex}",
                event_public_id=f"classroom-event.{uuid.uuid4().hex}",
                name=name,
                normalized_name=normalized_name,
                actor_user_id=actor_user_id,
                request_id=request["request_id"],
                now=now,
            )
        )
    except ClassroomNameConflict:
        await _raise_name_conflict(request, normalized_name)
        raise AssertionError("unreachable")
    return _response(item, status=201)


@classroom_routes.patch("/staff/api/v1/classrooms/{classroom_public_id}")
async def patch_classroom(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _classroom_public_id(request)
    expected_version = _expected_version(request, public_id)
    payload = await _json(request, frozenset({"schemaVersion", "name"}))
    try:
        name, normalized_name = prepare_classroom_name(payload["name"])
    except InvalidClassroomName as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Введите название аудитории",
            details={"field": "name"},
        ) from error
    try:
        item = await _factory(request).run_write_async(
            lambda connection: rename_classroom(
                connection,
                public_id=public_id,
                expected_version=expected_version,
                event_public_id=f"classroom-event.{uuid.uuid4().hex}",
                name=name,
                normalized_name=normalized_name,
                actor_user_id=actor_user_id,
                request_id=request["request_id"],
                now=_now(),
            )
        )
    except ClassroomNameConflict:
        await _raise_name_conflict(request, normalized_name)
        raise AssertionError("unreachable")
    except ClassroomNotFound as error:
        raise PwaApiError(
            status=404,
            code="classroom_not_found",
            message="Аудитория не найдена",
        ) from error
    except ClassroomVersionConflict as error:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аудитория уже изменилась. Обновите страницу.",
        ) from error
    return _response(item)


async def _change_status(request: web.Request, status: str) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _classroom_public_id(request)
    expected_version = _expected_version(request, public_id)
    await _json(request, frozenset({"schemaVersion"}))
    try:
        item = await _factory(request).run_write_async(
            lambda connection: set_classroom_status(
                connection,
                public_id=public_id,
                expected_version=expected_version,
                event_public_id=f"classroom-event.{uuid.uuid4().hex}",
                status=status,
                actor_user_id=actor_user_id,
                request_id=request["request_id"],
                now=_now(),
            )
        )
    except ClassroomNotFound as error:
        raise PwaApiError(
            status=404,
            code="classroom_not_found",
            message="Аудитория не найдена",
        ) from error
    except ClassroomVersionConflict as error:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аудитория уже изменилась. Обновите страницу.",
        ) from error
    return _response(item)


@classroom_routes.post("/staff/api/v1/classrooms/{classroom_public_id}/archive")
async def archive_classroom(request: web.Request) -> web.Response:
    return await _change_status(request, "archived")


@classroom_routes.post("/staff/api/v1/classrooms/{classroom_public_id}/restore")
async def restore_classroom(request: web.Request) -> web.Response:
    return await _change_status(request, "active")


__all__ = ["classroom_routes"]
