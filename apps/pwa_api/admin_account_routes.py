"""Admin-only lifecycle actions for existing Student and Family accounts."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import uuid
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
    find_family_account_by_username,
    find_student,
    find_student_account_by_username,
    insert_account_event,
    insert_family_account,
    insert_student_account,
    insert_status_event,
    revoke_family_link,
    revoke_sessions,
    save_family_link,
    update_status,
)
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.admin_accounts import (
    InvalidManagedAccountChange,
    ManagedAccountStatus,
    prepare_family_identity,
    prepare_family_link_identity,
    prepare_replacement_credential,
    prepare_student_identity,
    validate_status_change,
)
from models.pwa.auth import AuthAudience, normalize_telegram_token


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


def _path_public_id(request: web.Request, name: str) -> str:
    value = request.match_info[name]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="account_not_found",
            message="Школьник или аккаунт не найдены",
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


def _response(
    request: web.Request, row: dict[str, object], *, status: int = 200
) -> web.Response:
    version = int(row["credential_version"])
    public_id = str(row["public_id"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "account": _account_payload(row),
            "requestId": request["request_id"],
        },
        status=status,
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


def _family_link_payload(
    *,
    account: dict[str, object],
    student_public_id: str,
    relationship_label: str,
    is_primary: bool,
) -> dict[str, object]:
    return {
        "account": {
            "accountId": account["public_id"],
            "username": account["username"],
            "displayName": account["display_name"],
            "status": account["status"],
            "credentialVersion": account["credential_version"],
        },
        "link": {
            "studentId": student_public_id,
            "relationshipLabel": relationship_label,
            "isPrimary": is_primary,
        },
    }


def _family_link_response(
    request: web.Request,
    *,
    account: dict[str, object],
    student_public_id: str,
    relationship_label: str,
    is_primary: bool,
    status: int = 200,
) -> web.Response:
    return web.json_response(
        {
            "schemaVersion": 1,
            **_family_link_payload(
                account=account,
                student_public_id=student_public_id,
                relationship_label=relationship_label,
                is_primary=is_primary,
            ),
            "requestId": request["request_id"],
        },
        status=status,
        headers={"Cache-Control": "no-store"},
    )


@admin_account_routes.post("/staff/api/v1/students/{student_public_id}/student-account")
async def create_student_account(request: web.Request) -> web.Response:
    principal = _admin(request)
    student_public_id = _path_public_id(request, "student_public_id")
    payload = await _json_object(request, {"username"})
    if not isinstance(payload["username"], str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Введите логин школьника",
        )

    student = await _factory(request).run_read_async(
        lambda connection: find_student(connection, public_id=student_public_id)
    )
    if student is None:
        raise PwaApiError(
            status=404, code="student_not_found", message="Школьник не найден"
        )
    try:
        username, normalized_username, credential = prepare_student_identity(
            username=str(payload["username"]),
            telegram_token=str(student["token"] or ""),
            chat_id=student["chat_id"],
        )
    except InvalidManagedAccountChange as error:
        message = (
            "Сначала задайте школьнику безопасный Telegram-токен"
            if str(error) == "unsafe_student_credential"
            else "Проверьте логин школьника"
        )
        raise PwaApiError(status=422, code=str(error), message=message) from error

    credential_hash = await asyncio.to_thread(
        auth_service(request).credential_hasher.hash, credential
    )
    now = _now()
    display_name = " ".join(
        part
        for part in (
            str(student["name"] or "").strip(),
            str(student["surname"] or "").strip(),
        )
        if part
    )

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        current_student = find_student(connection, public_id=student_public_id)
        if current_student is None:
            return {"state": "student_not_found"}
        if normalize_telegram_token(str(current_student["token"] or "")) != credential:
            return {"state": "credential_changed"}
        if (
            find_student_account_by_username(
                connection, username_normalized=normalized_username
            )
            is not None
        ):
            return {"state": "username_conflict"}
        account = insert_student_account(
            connection,
            public_id=f"student-account.{uuid.uuid4().hex}",
            username=username,
            username_normalized=normalized_username,
            display_name=display_name,
            credential_hash=credential_hash,
            student_user_id=int(current_student["id"]),
            now=now,
        )
        insert_account_event(
            connection,
            account_id=int(account["id"]),
            event_type="student.account_created",
            request_id=request["request_id"],
            occurred_at=now,
            metadata_json=json.dumps(
                {
                    "actorUserId": principal.linked_user_id,
                    "studentPublicId": student_public_id,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return {"state": "ok", "account": account}

    try:
        result = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="student_account_conflict",
            message="Web-вход уже создан или такой логин занят",
        ) from error
    if result["state"] == "student_not_found":
        raise PwaApiError(
            status=404, code="student_not_found", message="Школьник не найден"
        )
    if result["state"] == "credential_changed":
        raise PwaApiError(
            status=409,
            code="student_credential_changed",
            message="Telegram-токен изменился. Повторите создание входа.",
        )
    if result["state"] == "username_conflict":
        raise PwaApiError(
            status=409,
            code="student_username_conflict",
            message="Такой логин школьника уже используется",
        )
    return _response(request, result["account"], status=201)


@admin_account_routes.post("/staff/api/v1/students/{student_public_id}/family-accounts")
async def create_family_account(request: web.Request) -> web.Response:
    principal = _admin(request)
    student_public_id = _path_public_id(request, "student_public_id")
    payload = await _json_object(
        request,
        {"username", "displayName", "password", "relationshipLabel", "isPrimary"},
    )
    if not all(
        isinstance(payload[field], str)
        for field in ("username", "displayName", "password", "relationshipLabel")
    ) or not isinstance(payload["isPrimary"], bool):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные семейного аккаунта",
        )
    try:
        username, normalized_username, display_name, relationship_label = (
            prepare_family_identity(
                username=str(payload["username"]),
                display_name=str(payload["displayName"]),
                relationship_label=str(payload["relationshipLabel"]),
            )
        )
        password = prepare_replacement_credential(
            AuthAudience.FAMILY, str(payload["password"])
        )
    except InvalidManagedAccountChange as error:
        raise PwaApiError(
            status=422,
            code=str(error),
            message="Проверьте логин, имя, роль и пароль семейного аккаунта",
        ) from error

    service = auth_service(request)
    credential_hash = await asyncio.to_thread(service.credential_hasher.hash, password)
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        student = find_student(connection, public_id=student_public_id)
        if student is None:
            return {"state": "student_not_found"}
        if (
            find_family_account_by_username(
                connection, username_normalized=normalized_username
            )
            is not None
        ):
            return {"state": "username_conflict"}
        account = insert_family_account(
            connection,
            public_id=f"family-account.{uuid.uuid4().hex}",
            username=username,
            username_normalized=normalized_username,
            display_name=display_name,
            credential_hash=credential_hash,
            now=now,
        )
        save_family_link(
            connection,
            family_account_id=int(account["id"]),
            student_user_id=int(student["id"]),
            relationship_label=relationship_label,
            is_primary=bool(payload["isPrimary"]),
            now=now,
        )
        insert_account_event(
            connection,
            account_id=int(account["id"]),
            event_type="family.account_created",
            request_id=request["request_id"],
            occurred_at=now,
            metadata_json=json.dumps(
                {
                    "actorUserId": principal.linked_user_id,
                    "studentPublicId": student_public_id,
                    "relationshipLabel": relationship_label,
                    "isPrimary": bool(payload["isPrimary"]),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return {"state": "ok", "account": account}

    try:
        result = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="family_username_conflict",
            message="Такой семейный логин уже используется",
        ) from error
    if result["state"] == "student_not_found":
        raise PwaApiError(
            status=404, code="student_not_found", message="Школьник не найден"
        )
    if result["state"] == "username_conflict":
        raise PwaApiError(
            status=409,
            code="family_username_conflict",
            message="Такой семейный логин уже используется",
        )
    return _family_link_response(
        request,
        account=result["account"],
        student_public_id=student_public_id,
        relationship_label=relationship_label,
        is_primary=bool(payload["isPrimary"]),
        status=201,
    )


@admin_account_routes.post("/staff/api/v1/students/{student_public_id}/family-links")
async def link_family_account(request: web.Request) -> web.Response:
    principal = _admin(request)
    student_public_id = _path_public_id(request, "student_public_id")
    payload = await _json_object(
        request, {"familyUsername", "relationshipLabel", "isPrimary"}
    )
    if (
        not isinstance(payload["familyUsername"], str)
        or not isinstance(payload["relationshipLabel"], str)
        or not isinstance(payload["isPrimary"], bool)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные семейной связи",
        )
    try:
        _, normalized_username, relationship_label = prepare_family_link_identity(
            username=str(payload["familyUsername"]),
            relationship_label=str(payload["relationshipLabel"]),
        )
    except InvalidManagedAccountChange as error:
        raise PwaApiError(
            status=422,
            code=str(error),
            message="Проверьте логин и роль семейного аккаунта",
        ) from error
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        student = find_student(connection, public_id=student_public_id)
        if student is None:
            return {"state": "student_not_found"}
        account = find_family_account_by_username(
            connection, username_normalized=normalized_username
        )
        if account is None:
            return {"state": "account_not_found"}
        save_family_link(
            connection,
            family_account_id=int(account["id"]),
            student_user_id=int(student["id"]),
            relationship_label=relationship_label,
            is_primary=bool(payload["isPrimary"]),
            now=now,
        )
        insert_account_event(
            connection,
            account_id=int(account["id"]),
            event_type="family.student_linked",
            request_id=request["request_id"],
            occurred_at=now,
            metadata_json=json.dumps(
                {
                    "actorUserId": principal.linked_user_id,
                    "studentPublicId": student_public_id,
                    "relationshipLabel": relationship_label,
                    "isPrimary": bool(payload["isPrimary"]),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return {"state": "ok", "account": account}

    result = await _factory(request).run_write_async(write)
    if result["state"] == "student_not_found":
        raise PwaApiError(
            status=404, code="student_not_found", message="Школьник не найден"
        )
    if result["state"] == "account_not_found":
        raise PwaApiError(
            status=404,
            code="family_account_not_found",
            message="Семейный аккаунт не найден",
        )
    return _family_link_response(
        request,
        account=result["account"],
        student_public_id=student_public_id,
        relationship_label=relationship_label,
        is_primary=bool(payload["isPrimary"]),
    )


@admin_account_routes.delete(
    "/staff/api/v1/students/{student_public_id}/family-links/{family_account_public_id}"
)
async def unlink_family_account(request: web.Request) -> web.Response:
    principal = _admin(request)
    student_public_id = _path_public_id(request, "student_public_id")
    family_account_public_id = _path_public_id(request, "family_account_public_id")
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        student = find_student(connection, public_id=student_public_id)
        account = find_account(connection, public_id=family_account_public_id)
        if student is None or account is None or account["audience"] != "family":
            return {"state": "not_found"}
        if not revoke_family_link(
            connection,
            family_account_id=int(account["id"]),
            student_user_id=int(student["id"]),
            now=now,
        ):
            return {"state": "not_found"}
        insert_account_event(
            connection,
            account_id=int(account["id"]),
            event_type="family.student_unlinked",
            request_id=request["request_id"],
            occurred_at=now,
            metadata_json=json.dumps(
                {
                    "actorUserId": principal.linked_user_id,
                    "studentPublicId": student_public_id,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        return {"state": "ok", "account": account}

    result = await _factory(request).run_write_async(write)
    if result["state"] == "not_found":
        raise PwaApiError(
            status=404,
            code="family_link_not_found",
            message="Связь семейного аккаунта со школьником не найдена",
        )
    await _close_account_sockets(request, result["account"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "studentId": student_public_id,
            "accountId": family_account_public_id,
            "revoked": True,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
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
