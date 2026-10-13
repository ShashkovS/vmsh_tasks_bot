"""Admin-only course/group Telegram binding endpoints."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.audit import insert_audit_event
from db_methods.pwa.telegram_bindings import (
    TelegramBindingDuplicate,
    TelegramBindingNotFound,
    TelegramBindingVersionConflict,
    get_binding,
    list_binding_owners,
    list_bindings,
    set_binding_status,
)
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from helpers.pwa.telegram_bindings import TelegramBindingVerificationError
from models.pwa.auth import AuthAudience
from models.pwa.telegram_bindings import (
    InvalidTelegramBinding,
    TelegramBindingOwnerNotFound,
    create_binding,
    edit_binding,
)


telegram_binding_routes = web.RouteTableDef()
TelegramBindingVerifier = Callable[[int, int | None, str], Awaitable[dict[str, object]]]
PWA_TELEGRAM_BINDING_VERIFIER = web.AppKey(
    "pwa_telegram_binding_verifier", TelegramBindingVerifier
)
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


def _actor_account_id(request: web.Request) -> str:
    return authenticated_session(request).principal.account_public_id


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


def _audit_values(item: dict[str, object]) -> dict[str, object]:
    """Keep destinations visible to admins without ever journaling bot credentials."""

    payload = _payload(item)
    return {
        "ownerType": payload["ownerType"],
        "ownerId": payload["ownerId"],
        "purpose": payload["purpose"],
        "chatId": payload["chatId"],
        "messageThreadId": payload["messageThreadId"],
        "titleCached": payload["titleCached"],
        "status": payload["status"],
        "verifiedAt": payload["verifiedAt"],
        "version": payload["version"],
    }


def _append_audit(
    connection: sqlite3.Connection,
    request: web.Request,
    *,
    actor_user_id: int,
    actor_account_id: str,
    action: str,
    public_id: str,
    before: dict[str, object] | None,
    after: dict[str, object],
    now: str,
) -> None:
    insert_audit_event(
        connection,
        actor_user_id=actor_user_id,
        actor_account_public_id=actor_account_id,
        audience="staff",
        action=action,
        object_type="telegram_binding",
        object_id=public_id,
        request_id=request["request_id"],
        before_json=(
            None
            if before is None
            else json.dumps(_audit_values(before), ensure_ascii=False)
        ),
        after_json=json.dumps(_audit_values(after), ensure_ascii=False),
        occurred_at=now,
    )


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
        raise PwaApiError(status=422, code="validation_error", message="Проверьте курс")
    items = await _factory(request).run_read_async(
        lambda connection: list_bindings(connection, course_public_id=course_public_id)
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_payload(item) for item in items],
            "requestId": request["request_id"],
        }
    )


@telegram_binding_routes.get("/staff/api/v1/telegram-binding-owners")
async def get_telegram_binding_owners(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Параметры не поддерживаются"
        )
    rows = await _factory(request).run_read_async(list_binding_owners)
    courses: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        course_public_id = str(row["course_public_id"])
        course = by_id.get(course_public_id)
        if course is None:
            course = {
                "courseId": course_public_id,
                "courseName": row["course_name"],
                "status": row["course_status"],
                "groups": [],
            }
            by_id[course_public_id] = course
            courses.append(course)
        if row["group_public_id"] is not None:
            course["groups"].append(
                {
                    "groupId": row["group_public_id"],
                    "groupName": row["group_name"],
                    "status": row["group_status"],
                }
            )
    return web.json_response(
        {
            "schemaVersion": 1,
            "courses": courses,
            "requestId": request["request_id"],
        }
    )


@telegram_binding_routes.post("/staff/api/v1/telegram-bindings")
async def post_telegram_binding(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    payload = await _json(request, _FIELDS)
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        item = create_binding(
            connection,
            owner_type=payload["ownerType"],
            owner_public_id=payload["ownerId"],
            purpose=payload["purpose"],
            chat_id=payload["chatId"],
            message_thread_id=payload["messageThreadId"],
            title_cached=payload["titleCached"],
            actor_user_id=actor_user_id,
            now=now,
        )
        _append_audit(
            connection,
            request,
            actor_user_id=actor_user_id,
            actor_account_id=actor_account_id,
            action="telegram_binding.created",
            public_id=str(item["public_id"]),
            before=None,
            after=item,
            now=now,
        )
        return item

    try:
        item = await _factory(request).run_write_async(write)
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
    actor_account_id = _actor_account_id(request)
    public_id = _public_id(request)
    expected_version = _expected_version(request, public_id)
    payload = await _json(request, _FIELDS)
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        before = get_binding(connection, public_id)
        item = edit_binding(
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
            now=now,
        )
        assert before is not None
        _append_audit(
            connection,
            request,
            actor_user_id=actor_user_id,
            actor_account_id=actor_account_id,
            action="telegram_binding.updated",
            public_id=public_id,
            before=before,
            after=item,
            now=now,
        )
        return item

    try:
        item = await _factory(request).run_write_async(write)
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
    actor_account_id = _actor_account_id(request)
    public_id = _public_id(request)
    expected_version = _expected_version(request, public_id)
    await _json(request, frozenset({"schemaVersion"}))
    now = _now()

    def change(connection: sqlite3.Connection) -> dict[str, object]:
        current = get_binding(connection, public_id)
        if current is None:
            raise TelegramBindingNotFound
        item = set_binding_status(
            connection,
            public_id=public_id,
            expected_version=expected_version,
            status=status,
            verified_at=current["verified_at"] if status == "disabled" else None,
            title_cached=None,
            actor_user_id=actor_user_id,
            now=now,
        )
        _append_audit(
            connection,
            request,
            actor_user_id=actor_user_id,
            actor_account_id=actor_account_id,
            action=(
                "telegram_binding.disabled"
                if status == "disabled"
                else "telegram_binding.draft_restored"
            ),
            public_id=public_id,
            before=current,
            after=item,
            now=now,
        )
        return item

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


@telegram_binding_routes.post(
    "/staff/api/v1/telegram-bindings/{binding_public_id}/verify"
)
async def verify_telegram_binding_route(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    public_id = _public_id(request)
    expected_version = _expected_version(request, public_id)
    await _json(request, frozenset({"schemaVersion"}))
    verifier = request.app.get(PWA_TELEGRAM_BINDING_VERIFIER)
    if verifier is None:
        raise PwaApiError(
            status=503,
            code="telegram_not_configured",
            message="Telegram не настроен для этого запуска",
        )
    current = await _factory(request).run_read_async(
        lambda connection: get_binding(connection, public_id)
    )
    if current is None:
        raise PwaApiError(
            status=404,
            code="telegram_binding_not_found",
            message="Привязка Telegram не найдена",
        )
    if current["version"] != expected_version:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Привязка уже изменилась. Обновите страницу.",
        )
    try:
        verified = await verifier(
            int(current["chat_id"]),
            (
                None
                if current["message_thread_id"] is None
                else int(current["message_thread_id"])
            ),
            str(current["purpose"]),
        )
    except TelegramBindingVerificationError as error:
        raise PwaApiError(
            status=503 if error.retryable else 409,
            code=error.reason,
            message=(
                "Telegram временно недоступен"
                if error.retryable
                else "Бот не может использовать этот канал или группу"
            ),
        ) from error
    verified_title = verified.get("title")
    if (
        verified.get("chat_id") != current["chat_id"]
        or not isinstance(verified_title, str)
        or not verified_title.strip()
    ):
        raise PwaApiError(
            status=409,
            code="telegram_verification_mismatch",
            message="Telegram вернул другой канал или некорректное название",
        )
    now = _now()

    def save_verified(connection: sqlite3.Connection) -> dict[str, object]:
        # Telegram verification happens outside SQLite. Re-read and apply the
        # optimistic version inside one transaction so a concurrent edit cannot
        # be journaled as verified with stale destination data.
        before = get_binding(connection, public_id)
        if before is None:
            raise TelegramBindingNotFound
        item = set_binding_status(
            connection,
            public_id=public_id,
            expected_version=expected_version,
            status="verified",
            verified_at=now,
            title_cached=verified_title.strip()[:200],
            actor_user_id=actor_user_id,
            now=now,
        )
        _append_audit(
            connection,
            request,
            actor_user_id=actor_user_id,
            actor_account_id=actor_account_id,
            action="telegram_binding.verified",
            public_id=public_id,
            before=before,
            after=item,
            now=now,
        )
        return item

    try:
        item = await _factory(request).run_write_async(save_verified)
    except (TelegramBindingNotFound, TelegramBindingVersionConflict) as error:
        _raise_write_error(error)
        raise AssertionError("unreachable")
    return _response(request, item)


__all__ = [
    "PWA_TELEGRAM_BINDING_VERIFIER",
    "TelegramBindingVerifier",
    "telegram_binding_routes",
]
