"""Admin-only lifecycle actions for existing Student and Family accounts."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import (
    auth_service,
    authenticated_session,
)
from apps.pwa_api.realtime_control import realtime_session_controller
from db_methods.pwa.admin_accounts import (
    find_account,
    insert_status_event,
    revoke_sessions,
    update_status,
)
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.admin_accounts import (
    InvalidManagedAccountChange,
    ManagedAccountStatus,
    prepare_replacement_credential,
    validate_status_change,
)
from models.pwa.auth import AuthAudience


admin_account_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="accounts_unavailable",
            message="Управление аккаунтами временно недоступно",
        )
    return state.factory


def _admin(request: web.Request):
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Управлять аккаунтами может только администратор",
        )
    return principal


def _account_public_id(request: web.Request) -> str:
    value = request.match_info["account_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="account_not_found",
            message="Аккаунт не найден",
        )
    return value


def _expected_version(request: web.Request, public_id: str) -> int:
    values = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите список перед сохранением",
        )
    if match.group(1) != public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аккаунт уже изменился. Обновите список.",
        )
    return int(match.group(2))


async def _json_object(
    request: web.Request, expected_fields: set[str]
) -> dict[str, object]:
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
            message="Проверьте введённые данные",
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != expected_fields | {"schemaVersion"}
        or payload.get("schemaVersion") != 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте введённые данные",
        )
    return payload


def _account_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "accountId": row["public_id"],
        "audience": row["audience"],
        "status": row["status"],
        "credentialVersion": row["credential_version"],
    }


def _response(request: web.Request, row: dict[str, object]) -> web.Response:
    version = int(row["credential_version"])
    public_id = str(row["public_id"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "account": _account_payload(row),
            "requestId": request["request_id"],
        },
        headers={
            "Cache-Control": "no-store",
            "ETag": f'"{public_id}:v{version}"',
        },
    )


async def _close_account_sockets(request: web.Request, row: dict[str, object]) -> None:
    controller = realtime_session_controller(request)
    if controller is not None:
        await controller.close_account(
            audience=str(row["audience"]),
            account_public_id=str(row["public_id"]),
        )


@admin_account_routes.patch("/staff/api/v1/accounts/{account_public_id}/status")
async def patch_account_status(request: web.Request) -> web.Response:
    principal = _admin(request)
    public_id = _account_public_id(request)
    expected_version = _expected_version(request, public_id)
    payload = await _json_object(request, {"status"})
    try:
        requested = ManagedAccountStatus(payload["status"])
    except (ValueError, TypeError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Выберите допустимое состояние аккаунта",
        ) from error
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        current = find_account(connection, public_id=public_id)
        if current is None:
            return {"state": "not_found"}
        if int(current["credential_version"]) != expected_version:
            return {"state": "conflict"}
        try:
            changed = validate_status_change(
                current=ManagedAccountStatus(str(current["status"])),
                requested=requested,
                has_credential=current["credential_hash"] is not None,
            )
        except InvalidManagedAccountChange:
            return {"state": "missing_credential"}
        if not changed:
            return {"state": "ok", "row": current, "changed": False}
        updated = update_status(
            connection,
            account_id=int(current["id"]),
            expected_version=expected_version,
            status=requested.value,
            now=now,
        )
        if updated is None:
            return {"state": "conflict"}
        revoke_sessions(
            connection,
            account_id=int(current["id"]),
            now=now,
            reason="account_status_changed",
        )
        insert_status_event(
            connection,
            account_id=int(current["id"]),
            request_id=request["request_id"],
            occurred_at=now,
            metadata_json=json.dumps(
                {
                    "actorUserId": principal.linked_user_id,
                    "beforeStatus": current["status"],
                    "afterStatus": requested.value,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return {"state": "ok", "row": updated, "changed": True}

    result = await _factory(request).run_write_async(write)
    if result["state"] == "not_found":
        raise PwaApiError(
            status=404, code="account_not_found", message="Аккаунт не найден"
        )
    if result["state"] == "conflict":
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аккаунт уже изменился. Обновите список.",
        )
    if result["state"] == "missing_credential":
        raise PwaApiError(
            status=422,
            code="account_credential_missing",
            message="Сначала задайте данные для входа",
        )
    row = result["row"]
    if result["changed"]:
        await _close_account_sockets(request, row)
    return _response(request, row)


@admin_account_routes.post("/staff/api/v1/accounts/{account_public_id}/credential")
async def replace_account_credential(request: web.Request) -> web.Response:
    _admin(request)
    public_id = _account_public_id(request)
    expected_version = _expected_version(request, public_id)
    payload = await _json_object(request, {"credential"})
    raw_credential = payload["credential"]
    if not isinstance(raw_credential, str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Введите новые данные для входа",
        )
    account = await _factory(request).run_read_async(
        lambda connection: find_account(connection, public_id=public_id)
    )
    if account is None:
        raise PwaApiError(
            status=404, code="account_not_found", message="Аккаунт не найден"
        )
    if int(account["credential_version"]) != expected_version:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аккаунт уже изменился. Обновите список.",
        )
    audience = AuthAudience(str(account["audience"]))
    try:
        credential = prepare_replacement_credential(audience, raw_credential)
    except InvalidManagedAccountChange as error:
        message = (
            "Telegram-токен должен быть непустым и не похожим на тестовый"
            if audience is AuthAudience.STUDENT
            else "Пароль должен содержать от 8 до 256 символов"
        )
        raise PwaApiError(status=422, code=str(error), message=message) from error

    service = auth_service(request)
    credential_hash = await asyncio.to_thread(
        service.credential_hasher.hash, credential
    )
    try:
        if audience is AuthAudience.STUDENT:
            result = await service.repository.change_student_telegram_credential(
                account_id=int(account["id"]),
                expected_credential_version=expected_version,
                normalized_telegram_token=credential,
                replacement_credential_hash=credential_hash,
                request_id=request["request_id"],
            )
        else:
            result = await service.repository.change_credential(
                account_id=int(account["id"]),
                expected_credential_version=expected_version,
                replacement_credential_hash=credential_hash,
                request_id=request["request_id"],
            )
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="credential_conflict",
            message="Эти данные для входа уже используются",
        ) from error
    if not result.changed:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Аккаунт уже изменился. Обновите список.",
        )
    updated = await _factory(request).run_read_async(
        lambda connection: find_account(connection, public_id=public_id)
    )
    if updated is None:  # pragma: no cover - immutable account identity
        raise RuntimeError("Updated account disappeared")
    await _close_account_sockets(request, updated)
    return _response(request, updated)


__all__ = ["admin_account_routes"]
