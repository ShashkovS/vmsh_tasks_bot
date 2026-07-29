"""Admin-only course/group Telegram binding endpoints."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.telegram_bindings import (
    TelegramBindingDuplicate,
    TelegramBindingNotFound,
    TelegramBindingVersionConflict,
    get_binding,
    list_bindings,
    set_binding_status,
)
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.telegram_bindings import (
    InvalidTelegramBinding,
    TelegramBindingOwnerNotFound,
    create_binding,
    edit_binding,
)


telegram_binding_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_FIELDS = frozenset(
    {
        "schemaVersion",
        "ownerType",
        "ownerId",
        "purpose",
        "chatId",
        "messageThreadId",
        "titleCached",
    }
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="telegram_bindings_unavailable",
            message="Привязки Telegram временно недоступны",
        )
    return state.factory


def _admin_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
        or not principal.has_capability(Capability.TELEGRAM_BINDING_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Управлять привязками Telegram может только администратор",
        )
    return principal.linked_user_id


def _public_id(request: web.Request) -> str:
    value = request.match_info["binding_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="telegram_binding_not_found",
            message="Привязка Telegram не найдена",
        )
    return value


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
            message="Привязка уже изменилась. Обновите страницу.",
        )
    return int(match.group(2))


async def _json(request: web.Request, fields: frozenset[str]) -> dict[str, object]:
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
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or payload.get("schemaVersion") != 1
        or isinstance(payload.get("schemaVersion"), bool)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля привязки Telegram",
        )
    return payload


def _payload(item: dict[str, object]) -> dict[str, object]:
    course_public_id = (
        item["owner_course_public_id"]
        if item["owner_type"] == "course"
        else item["group_course_public_id"]
    )
    course_name = (
        item["owner_course_name"]
        if item["owner_type"] == "course"
        else item["group_course_name"]
    )
    return {
        "publicId": item["public_id"],
        "ownerType": item["owner_type"],
        "ownerId": (
            item["owner_course_public_id"]
            if item["owner_type"] == "course"
            else item["owner_group_public_id"]
        ),
        "ownerName": (
            item["owner_course_name"]
            if item["owner_type"] == "course"
            else item["owner_group_name"]
        ),
        "courseId": course_public_id,
        "courseName": course_name,
        "purpose": item["purpose"],
        "chatId": item["chat_id"],
        "messageThreadId": item["message_thread_id"],
        "titleCached": item["title_cached"],
        "status": item["status"],
        "verifiedAt": item["verified_at"],
        "createdAt": item["created_at"],
        "updatedAt": item["updated_at"],
        "version": item["version"],
    }


def _response(
    request: web.Request, item: dict[str, object], *, status: int = 200
) -> web.Response:
    response = web.json_response(
        {
            "schemaVersion": 1,
            "binding": _payload(item),
            "requestId": request["request_id"],
        },
        status=status,
    )
    response.headers["ETag"] = f'"{item["public_id"]}:v{item["version"]}"'
    return response


def _raise_write_error(error: Exception) -> None:
    if isinstance(error, InvalidTelegramBinding):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля привязки Telegram",
            details={"field": str(error)},
        ) from error
    if isinstance(error, TelegramBindingOwnerNotFound):
        raise PwaApiError(
            status=404,
            code="telegram_binding_owner_not_found",
            message="Курс или группа не найдены",
        ) from error
    if isinstance(error, TelegramBindingDuplicate):
        raise PwaApiError(
            status=409,
            code="telegram_binding_duplicate",
            message="Такая привязка Telegram уже существует",
        ) from error
    if isinstance(error, TelegramBindingNotFound):
        raise PwaApiError(
            status=404,
            code="telegram_binding_not_found",
            message="Привязка Telegram не найдена",
        ) from error
    if isinstance(error, TelegramBindingVersionConflict):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Привязка уже изменилась. Обновите страницу.",
        ) from error
    raise error


@telegram_binding_routes.get("/staff/api/v1/telegram-bindings")
async def get_telegram_bindings(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if set(request.query) - {"courseId"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    course_public_id = request.query.get("courseId")
    if course_public_id is not None and _PUBLIC_ID.fullmatch(course_public_id) is None:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте курс"
        )
    items = await _factory(request).run_read_async(
        lambda connection: list_bindings(
            connection, course_public_id=course_public_id
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_payload(item) for item in items],
            "requestId": request["request_id"],
        }
    )


@telegram_binding_routes.post("/staff/api/v1/telegram-bindings")
async def post_telegram_binding(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    payload = await _json(request, _FIELDS)
    try:
        item = await _factory(request).run_write_async(
            lambda connection: create_binding(
                connection,
                public_id=f"telegram-binding.{uuid.uuid4().hex}",
                owner_type=payload["ownerType"],
                owner_public_id=payload["ownerId"],
                purpose=payload["purpose"],
                chat_id=payload["chatId"],
                message_thread_id=payload["messageThreadId"],
                title_cached=payload["titleCached"],
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except (
        InvalidTelegramBinding,
        TelegramBindingOwnerNotFound,
        TelegramBindingDuplicate,
    ) as error:
        _raise_write_error(error)
        raise AssertionError("unreachable")
    return _response(request, item, status=201)


@telegram_binding_routes.put("/staff/api/v1/telegram-bindings/{binding_public_id}")
async def put_telegram_binding(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _public_id(request)
    expected_version = _expected_version(request, public_id)
    payload = await _json(request, _FIELDS)
    try:
        item = await _factory(request).run_write_async(
            lambda connection: edit_binding(
                connection,
                public_id=public_id,
                expected_version=expected_version,
                owner_type=payload["ownerType"],
                owner_public_id=payload["ownerId"],
                purpose=payload["purpose"],
                chat_id=payload["chatId"],
                message_thread_id=payload["messageThreadId"],
                title_cached=payload["titleCached"],
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except (
        InvalidTelegramBinding,
        TelegramBindingOwnerNotFound,
        TelegramBindingDuplicate,
        TelegramBindingNotFound,
        TelegramBindingVersionConflict,
    ) as error:
        _raise_write_error(error)
        raise AssertionError("unreachable")
    return _response(request, item)


async def _change_status(request: web.Request, status: str) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _public_id(request)
    expected_version = _expected_version(request, public_id)
    await _json(request, frozenset({"schemaVersion"}))

    def change(connection):
        current = get_binding(connection, public_id)
        if current is None:
            raise TelegramBindingNotFound
        return set_binding_status(
            connection,
            public_id=public_id,
            expected_version=expected_version,
            status=status,
            verified_at=current["verified_at"] if status == "disabled" else None,
            title_cached=None,
            actor_user_id=actor_user_id,
            now=_now(),
        )

    try:
        item = await _factory(request).run_write_async(change)
    except (TelegramBindingNotFound, TelegramBindingVersionConflict) as error:
        _raise_write_error(error)
        raise AssertionError("unreachable")
    return _response(request, item)


@telegram_binding_routes.post(
    "/staff/api/v1/telegram-bindings/{binding_public_id}/disable"
)
async def disable_telegram_binding(request: web.Request) -> web.Response:
    return await _change_status(request, "disabled")


@telegram_binding_routes.post(
    "/staff/api/v1/telegram-bindings/{binding_public_id}/restore-draft"
)
async def restore_telegram_binding_draft(request: web.Request) -> web.Response:
    return await _change_status(request, "draft")


__all__ = ["telegram_binding_routes"]
