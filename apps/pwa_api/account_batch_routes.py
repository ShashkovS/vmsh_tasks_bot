"""Admin preview/apply endpoints for the two v1 account batches."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import auth_service, authenticated_session
from db_methods.pwa.account_batches import (
    account_logins,
    available_student_logins,
    insert_family_emails,
    insert_family_link,
    insert_provisioned_account,
    insert_student_user,
    student_for_login,
    student_tokens,
)
from db_methods.pwa.admin_accounts import insert_account_event
from db_methods.pwa.audit import insert_audit_event
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.account_batches import (
    InvalidAccountBatchRow,
    choose_available_login,
    normalize_family_batch_row,
    normalize_student_batch_row,
)
from models.pwa.auth import AuthAudience, normalize_login, normalize_telegram_token


account_batch_routes = web.RouteTableDef()
_MAX_ROWS = 2_000


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


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
            message="Пакетно создавать аккаунты может только администратор",
        )
    return principal


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="account_import_unavailable",
            message="Пакетное создание аккаунтов временно недоступно",
        )
    return state.factory


async def _payload(request: web.Request, *, apply: bool) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        payload = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте таблицу"
        ) from error
    expected = {"schemaVersion", "rows"}
    if apply:
        expected |= {"previewHash", "resolvedLogins"}
    if (
        not isinstance(payload, dict)
        or set(payload) != expected
        or payload.get("schemaVersion") != 1
        or not isinstance(payload.get("rows"), list)
        or not 1 <= len(payload["rows"]) <= _MAX_ROWS
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте таблицу"
        )
    if apply and (
        not isinstance(payload["previewHash"], str)
        or not isinstance(payload["resolvedLogins"], list)
        or len(payload["resolvedLogins"]) != len(payload["rows"])
        or any(
            value is not None and not isinstance(value, str)
            for value in payload["resolvedLogins"]
        )
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Сначала обновите предпросмотр"
        )
    return payload


def _preview_hash(rows: list[object], resolved_logins: list[str | None]) -> str:
    encoded = json.dumps(
        {"rows": rows, "resolvedLogins": resolved_logins},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _suffixes() -> list[int]:
    return secrets.SystemRandom().sample(range(100), 100)


def _preview_response(
    request: web.Request,
    *,
    rows: list[dict[str, object]],
    source_rows: list[object],
    resolved_logins: list[str | None],
) -> web.Response:
    ready = sum(row["state"] == "ready" for row in rows)
    return web.json_response(
        {
            "schemaVersion": 1,
            "previewHash": _preview_hash(source_rows, resolved_logins),
            "counts": {
                "total": len(rows),
                "ready": ready,
                "invalid": len(rows) - ready,
            },
            "rows": rows,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


def _preview_row(
    *, row_number: int, state: str, resolved_login: str | None, code: str | None
) -> dict[str, object]:
    return {
        "rowNumber": row_number,
        "state": state,
        "resolvedLogin": resolved_login,
        "loginAdjusted": state == "ready" and resolved_login is not None,
        "code": code,
    }


@account_batch_routes.post("/staff/api/v1/imports/student-accounts/preview")
async def preview_student_accounts(request: web.Request) -> web.Response:
    _admin(request)
    payload = await _payload(request, apply=False)
    source_rows = payload["rows"]
    used, used_tokens = await _factory(request).run_read_async(
        lambda connection: (
            account_logins(connection, audience="student"),
            {normalize_telegram_token(token) for token in student_tokens(connection)},
        )
    )
    rows: list[dict[str, object]] = []
    resolved_logins: list[str | None] = []
    for number, source in enumerate(source_rows, start=1):
        try:
            normalized = normalize_student_batch_row(source)
            token = str(normalized["password"])
            if token in used_tokens:
                raise InvalidAccountBatchRow("student_token_conflict")
            login, _, adjusted = choose_available_login(
                str(normalized["login"]),
                str(normalized["login_normalized"]),
                used,
                _suffixes(),
            )
            used_tokens.add(token)
        except InvalidAccountBatchRow as error:
            rows.append(
                _preview_row(
                    row_number=number,
                    state="invalid",
                    resolved_login=None,
                    code=str(error),
                )
            )
            resolved_logins.append(None)
            continue
        row = _preview_row(
            row_number=number, state="ready", resolved_login=login, code=None
        )
        row["loginAdjusted"] = adjusted
        rows.append(row)
        resolved_logins.append(login)
    return _preview_response(
        request,
        rows=rows,
        source_rows=source_rows,
        resolved_logins=resolved_logins,
    )


@account_batch_routes.post("/staff/api/v1/imports/family-accounts/preview")
async def preview_family_accounts(request: web.Request) -> web.Response:
    _admin(request)
    payload = await _payload(request, apply=False)
    source_rows = payload["rows"]
    used, student_logins = await _factory(request).run_read_async(
        lambda connection: (
            account_logins(connection, audience="family"),
            available_student_logins(connection),
        )
    )
    rows: list[dict[str, object]] = []
    resolved_logins: list[str | None] = []
    for number, source in enumerate(source_rows, start=1):
        try:
            normalized = normalize_family_batch_row(source)
            missing = [
                login
                for login in normalized["child_logins"]
                if login not in student_logins
            ]
            if missing:
                raise InvalidAccountBatchRow("child_login_not_found")
            login, _, adjusted = choose_available_login(
                str(normalized["login"]),
                str(normalized["login_normalized"]),
                used,
                _suffixes(),
            )
        except InvalidAccountBatchRow as error:
            rows.append(
                _preview_row(
                    row_number=number,
                    state="invalid",
                    resolved_login=None,
                    code=str(error),
                )
            )
            resolved_logins.append(None)
            continue
        row = _preview_row(
            row_number=number, state="ready", resolved_login=login, code=None
        )
        row["loginAdjusted"] = adjusted
        rows.append(row)
        resolved_logins.append(login)
    return _preview_response(
        request,
        rows=rows,
        source_rows=source_rows,
        resolved_logins=resolved_logins,
    )


def _validated_apply(
    payload: dict[str, object],
) -> tuple[list[object], list[str | None]]:
    rows = payload["rows"]
    resolved = payload["resolvedLogins"]
    expected = _preview_hash(rows, resolved)
    if not hmac.compare_digest(str(payload["previewHash"]), expected):
        raise PwaApiError(
            status=409,
            code="preview_changed",
            message="Таблица изменилась. Обновите предпросмотр.",
        )
    return rows, resolved


async def _hash_rows(
    request: web.Request,
    rows: list[object],
    normalize,
) -> list[tuple[dict[str, object] | None, str | None]]:
    result: list[tuple[dict[str, object] | None, str | None]] = []
    for source in rows:
        try:
            row = normalize(source)
        except InvalidAccountBatchRow:
            result.append((None, None))
            continue
        digest = await asyncio.to_thread(
            auth_service(request).credential_hasher.hash, str(row["password"])
        )
        result.append((row, digest))
    return result


def _batch_audit(
    connection: sqlite3.Connection,
    *,
    request: web.Request,
    principal,
    audience: str,
    created: int,
    skipped: int,
    now: str,
) -> None:
    insert_audit_event(
        connection,
        public_id=f"audit.{uuid.uuid4().hex}",
        actor_user_id=principal.linked_user_id,
        actor_account_public_id=principal.account_public_id,
        audience="staff",
        action=f"{audience}.accounts_batch_created",
        object_type="account_batch",
        object_id=request["request_id"],
        request_id=request["request_id"],
        before_json=None,
        after_json=json.dumps(
            {"audience": audience, "created": created, "skipped": skipped},
            separators=(",", ":"),
        ),
        occurred_at=now,
    )


def _apply_response(
    request: web.Request, rows: list[dict[str, object]]
) -> web.Response:
    created = sum(row["state"] == "created" for row in rows)
    return web.json_response(
        {
            "schemaVersion": 1,
            "counts": {
                "total": len(rows),
                "created": created,
                "skipped": len(rows) - created,
            },
            "rows": rows,
            "requestId": request["request_id"],
        },
        status=201 if created else 200,
        headers={"Cache-Control": "no-store"},
    )


@account_batch_routes.post("/staff/api/v1/imports/student-accounts/apply")
async def apply_student_accounts(request: web.Request) -> web.Response:
    principal = _admin(request)
    payload = await _payload(request, apply=True)
    source_rows, resolved_logins = _validated_apply(payload)
    prepared = await _hash_rows(request, source_rows, normalize_student_batch_row)
    now = _now()

    def write(connection: sqlite3.Connection) -> list[dict[str, object]]:
        used = account_logins(connection, audience="student")
        used_tokens = {
            normalize_telegram_token(token) for token in student_tokens(connection)
        }
        result: list[dict[str, object]] = []
        for number, ((row, digest), resolved_login) in enumerate(
            zip(prepared, resolved_logins, strict=True), start=1
        ):
            if row is None or digest is None or resolved_login is None:
                result.append(
                    {"rowNumber": number, "state": "skipped", "code": "invalid_row"}
                )
                continue
            resolved_normalized = normalize_login(str(resolved_login))
            original = str(row["login"])
            allowed_suffix = (
                len(resolved_login) == min(len(original), 97) + 3
                and resolved_login.startswith(original[:97] + "-")
                and resolved_login[-2:].isdigit()
            )
            if (
                not resolved_normalized
                or resolved_normalized in used
                or str(row["password"]) in used_tokens
                or (resolved_login != original and not allowed_suffix)
                or (
                    resolved_login != original
                    and str(row["login_normalized"]) not in used
                )
            ):
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": "account_conflict",
                    }
                )
                continue
            user_public_id = f"user.{uuid.uuid4().hex}"
            user_id = insert_student_user(
                connection,
                public_id=user_public_id,
                surname=str(row["surname"]),
                name=str(row["name"]),
                patronymic=str(row["patronymic"]),
                token=str(row["password"]),
                grade=row["grade"],
                birth_date=row["birth_date"],
            )
            account_public_id = f"student-account.{uuid.uuid4().hex}"
            account_id = insert_provisioned_account(
                connection,
                public_id=account_public_id,
                audience="student",
                username=resolved_login,
                username_normalized=resolved_normalized,
                display_name=" ".join(
                    part for part in (str(row["name"]), str(row["surname"])) if part
                ),
                credential_kind="telegram_token",
                credential_hash=digest,
                credential_plaintext=str(row["password"]),
                linked_user_id=user_id,
                now=now,
            )
            insert_account_event(
                connection,
                account_id=account_id,
                event_type="student.account_batch_created",
                request_id=request["request_id"],
                occurred_at=now,
                metadata_json=json.dumps(
                    {"actorUserId": principal.linked_user_id}, separators=(",", ":")
                ),
            )
            used.add(resolved_normalized)
            used_tokens.add(str(row["password"]))
            result.append(
                {
                    "rowNumber": number,
                    "state": "created",
                    "login": resolved_login,
                    "userId": user_public_id,
                    "accountId": account_public_id,
                }
            )
        _batch_audit(
            connection,
            request=request,
            principal=principal,
            audience="student",
            created=sum(row["state"] == "created" for row in result),
            skipped=sum(row["state"] != "created" for row in result),
            now=now,
        )
        return result

    try:
        rows = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="account_conflict",
            message="Данные изменились. Обновите предпросмотр.",
        ) from error
    return _apply_response(request, rows)


@account_batch_routes.post("/staff/api/v1/imports/family-accounts/apply")
async def apply_family_accounts(request: web.Request) -> web.Response:
    principal = _admin(request)
    payload = await _payload(request, apply=True)
    source_rows, resolved_logins = _validated_apply(payload)
    prepared = await _hash_rows(request, source_rows, normalize_family_batch_row)
    now = _now()

    def write(connection: sqlite3.Connection) -> list[dict[str, object]]:
        used = account_logins(connection, audience="family")
        result: list[dict[str, object]] = []
        for number, ((row, digest), resolved_login) in enumerate(
            zip(prepared, resolved_logins, strict=True), start=1
        ):
            if row is None or digest is None or resolved_login is None:
                result.append(
                    {"rowNumber": number, "state": "skipped", "code": "invalid_row"}
                )
                continue
            resolved_normalized = normalize_login(str(resolved_login))
            original = str(row["login"])
            allowed_suffix = (
                len(resolved_login) == min(len(original), 97) + 3
                and resolved_login.startswith(original[:97] + "-")
                and resolved_login[-2:].isdigit()
            )
            students = [
                student_for_login(connection, login_normalized=str(login))
                for login in row["child_logins"]
            ]
            if (
                not resolved_normalized
                or resolved_normalized in used
                or any(student is None for student in students)
                or (resolved_login != original and not allowed_suffix)
                or (
                    resolved_login != original
                    and str(row["login_normalized"]) not in used
                )
            ):
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": "account_conflict",
                    }
                )
                continue
            account_public_id = f"family-account.{uuid.uuid4().hex}"
            account_id = insert_provisioned_account(
                connection,
                public_id=account_public_id,
                audience="family",
                username=resolved_login,
                username_normalized=resolved_normalized,
                display_name=str(row["name"]),
                credential_kind="password",
                credential_hash=digest,
                credential_plaintext=str(row["password"]),
                linked_user_id=None,
                now=now,
            )
            insert_family_emails(
                connection,
                family_account_id=account_id,
                emails=row["emails"],
                now=now,
            )
            for student in students:
                insert_family_link(
                    connection,
                    family_account_id=account_id,
                    student_user_id=int(student["user_id"]),
                    now=now,
                )
            insert_account_event(
                connection,
                account_id=account_id,
                event_type="family.account_batch_created",
                request_id=request["request_id"],
                occurred_at=now,
                metadata_json=json.dumps(
                    {
                        "actorUserId": principal.linked_user_id,
                        "childCount": len(students),
                    },
                    separators=(",", ":"),
                ),
            )
            used.add(resolved_normalized)
            result.append(
                {
                    "rowNumber": number,
                    "state": "created",
                    "login": resolved_login,
                    "accountId": account_public_id,
                    "childCount": len(students),
                }
            )
        _batch_audit(
            connection,
            request=request,
            principal=principal,
            audience="family",
            created=sum(row["state"] == "created" for row in result),
            skipped=sum(row["state"] != "created" for row in result),
            now=now,
        )
        return result

    try:
        rows = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="account_conflict",
            message="Данные изменились. Обновите предпросмотр.",
        ) from error
    return _apply_response(request, rows)


__all__ = ["account_batch_routes"]
