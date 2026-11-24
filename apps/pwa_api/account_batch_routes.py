"""Admin preview/apply endpoints for the three v1 account batches."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import auth_service, authenticated_session
from db_methods.pwa.account_batches import (
    account_logins,
    available_student_logins,
    course_for_code,
    enrollment_for_student_course,
    family_emails,
    groups_for_course,
    insert_course_enrollment,
    insert_course_enrollment_created_event,
    insert_family_emails,
    insert_family_link,
    insert_imported_group_access,
    insert_provisioned_account,
    insert_student_user,
    student_has_course_enrollment,
    student_for_login,
    student_tokens,
    sync_first_course_to_legacy_user,
)
from db_methods.pwa.admin_accounts import insert_account_event
from db_methods.pwa.audit import insert_audit_event
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.account_batches import (
    InvalidAccountBatchRow,
    choose_active_group,
    choose_available_login,
    normalize_course_enrollment_batch_row,
    normalize_family_batch_row,
    normalize_student_batch_row,
)
from models.pwa.auth import (
    AuthAudience,
    normalize_login,
    normalize_student_login,
    normalize_telegram_token,
)


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
            message="Пакетные операции может выполнять только администратор",
        )
    return principal


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="account_import_unavailable",
            message="Пакетные операции временно недоступны",
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


async def _enrollment_payload(
    request: web.Request, *, apply: bool
) -> dict[str, object]:
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
        expected.add("previewHash")
    if (
        not isinstance(payload, dict)
        or set(payload) != expected
        or payload.get("schemaVersion") != 1
        or not isinstance(payload.get("rows"), list)
        or not 1 <= len(payload["rows"]) <= _MAX_ROWS
        or (
            apply
            and (
                not isinstance(payload.get("previewHash"), str)
                or len(payload["previewHash"]) != 64
            )
        )
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте таблицу"
        )
    return payload


def _preview_hash(rows: list[object], resolution: list[object]) -> str:
    encoded = json.dumps(
        {"rows": rows, "resolution": resolution},
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


def _resolve_enrollment_batch(
    connection: sqlite3.Connection, source_rows: list[object]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for number, source in enumerate(source_rows, start=1):
        try:
            normalized = normalize_course_enrollment_batch_row(source)
            student = student_for_login(
                connection, login_normalized=str(normalized["login_normalized"])
            )
            if student is None:
                raise InvalidAccountBatchRow("student_login_not_found")
            course = course_for_code(
                connection, course_code=str(normalized["course_code"])
            )
            if course is None:
                raise InvalidAccountBatchRow("course_not_found")
            if course["status"] == "archived":
                raise InvalidAccountBatchRow("course_archived")
            natural_key = (int(student["user_id"]), int(course["id"]))
            if natural_key in seen:
                raise InvalidAccountBatchRow("duplicate_enrollment_row")
            seen.add(natural_key)
            if (
                enrollment_for_student_course(
                    connection,
                    student_user_id=natural_key[0],
                    course_id=natural_key[1],
                )
                is not None
            ):
                raise InvalidAccountBatchRow("enrollment_exists")
            groups = groups_for_course(connection, course_id=natural_key[1])
            active_group = choose_active_group(
                groups, normalized["allowed_group_codes"]
            )
            allowed_codes = set(normalized["allowed_group_codes"])
            allowed_groups = [
                group
                for group in groups
                if str(group["short_code"]).casefold() in allowed_codes
            ]
            if any(group["status"] == "archived" for group in allowed_groups):
                raise InvalidAccountBatchRow("group_archived")
        except InvalidAccountBatchRow as error:
            result.append({"rowNumber": number, "state": "invalid", "code": str(error)})
            continue
        result.append(
            {
                "rowNumber": number,
                "state": "ready",
                "code": None,
                "login": normalized["login_normalized"],
                "studentUserId": student["user_id"],
                "courseId": course["id"],
                "coursePublicId": course["public_id"],
                "courseCode": course["code"],
                "activeGroupId": active_group["group_id"],
                "activeGroupPublicId": active_group["public_id"],
                "activeGroupCode": active_group["short_code"],
                "allowedGroupIds": [group["group_id"] for group in allowed_groups],
                "allowedGroupPublicIds": [
                    group["public_id"] for group in allowed_groups
                ],
                "allowedGroupCodes": [group["short_code"] for group in allowed_groups],
            }
        )
    return result


def _enrollment_resolution_hash(
    source_rows: list[object], rows: list[dict[str, object]]
) -> str:
    resolution: list[object] = []
    for row in rows:
        if row["state"] == "invalid":
            resolution.append({"state": "invalid", "code": row["code"]})
        else:
            resolution.append(
                {
                    "state": "ready",
                    "studentUserId": row["studentUserId"],
                    "coursePublicId": row["coursePublicId"],
                    "activeGroupPublicId": row["activeGroupPublicId"],
                    "allowedGroupPublicIds": row["allowedGroupPublicIds"],
                }
            )
    return _preview_hash(source_rows, resolution)


def _enrollment_preview_response(
    request: web.Request,
    *,
    source_rows: list[object],
    rows: list[dict[str, object]],
) -> web.Response:
    ready = sum(row["state"] == "ready" for row in rows)
    public_rows = []
    for row in rows:
        if row["state"] == "invalid":
            public_rows.append(
                {
                    "rowNumber": row["rowNumber"],
                    "state": "invalid",
                    "code": row["code"],
                }
            )
        else:
            public_rows.append(
                {
                    "rowNumber": row["rowNumber"],
                    "state": "ready",
                    "login": row["login"],
                    "courseCode": row["courseCode"],
                    "activeGroupCode": row["activeGroupCode"],
                    "allowedGroupCodes": row["allowedGroupCodes"],
                    "code": None,
                }
            )
    return web.json_response(
        {
            "schemaVersion": 1,
            "previewHash": _enrollment_resolution_hash(source_rows, rows),
            "counts": {
                "total": len(rows),
                "ready": ready,
                "invalid": len(rows) - ready,
            },
            "rows": public_rows,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


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
                normalize=normalize_student_login,
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


@account_batch_routes.post("/staff/api/v1/imports/course-enrollments/preview")
async def preview_course_enrollments(request: web.Request) -> web.Response:
    _admin(request)
    payload = await _enrollment_payload(request, apply=False)
    source_rows = payload["rows"]
    rows = await _factory(request).run_read_async(
        lambda connection: _resolve_enrollment_batch(connection, source_rows)
    )
    return _enrollment_preview_response(
        request,
        source_rows=source_rows,
        rows=rows,
    )


@account_batch_routes.post("/staff/api/v1/imports/family-accounts/preview")
async def preview_family_accounts(request: web.Request) -> web.Response:
    _admin(request)
    payload = await _payload(request, apply=False)
    source_rows = payload["rows"]
    used_logins, used_emails, student_logins = await _factory(request).run_read_async(
        lambda connection: (
            account_logins(connection, audience="family"),
            family_emails(connection),
            available_student_logins(connection),
        )
    )
    rows: list[dict[str, object]] = []
    resolved_logins: list[str | None] = []
    for number, source in enumerate(source_rows, start=1):
        try:
            normalized = normalize_family_batch_row(source)
            duplicate_code = _family_duplicate_code(
                login_normalized=str(normalized["login_normalized"]),
                emails=tuple(str(email).casefold() for email in normalized["emails"]),
                used_logins=used_logins,
                used_emails=used_emails,
            )
            if duplicate_code is not None:
                raise InvalidAccountBatchRow(duplicate_code)
            missing = [
                login
                for login in normalized["child_logins"]
                if login not in student_logins
            ]
            if missing:
                raise InvalidAccountBatchRow("child_login_not_found")
            login = str(normalized["login"])
            used_logins.add(str(normalized["login_normalized"]))
            used_emails.update(
                str(email).casefold() for email in normalized["emails"]
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
        row["loginAdjusted"] = False
        rows.append(row)
        resolved_logins.append(login)
    return _preview_response(
        request,
        rows=rows,
        source_rows=source_rows,
        resolved_logins=resolved_logins,
    )


def _family_duplicate_code(
    *,
    login_normalized: str,
    emails: tuple[str, ...],
    used_logins: set[str],
    used_emails: set[str],
) -> str | None:
    duplicate_login = login_normalized in used_logins
    duplicate_email = bool(set(emails) & used_emails)
    if duplicate_login and duplicate_email:
        return "family_login_email_duplicate"
    if duplicate_login:
        return "family_login_duplicate"
    if duplicate_email:
        return "family_email_duplicate"
    return None


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
) -> list[tuple[dict[str, object] | None, str | None, str | None]]:
    result: list[tuple[dict[str, object] | None, str | None, str | None]] = []
    for source in rows:
        try:
            row = normalize(source)
        except InvalidAccountBatchRow as error:
            result.append((None, None, str(error)))
            continue
        digest = await asyncio.to_thread(
            auth_service(request).credential_hasher.hash, str(row["password"])
        )
        result.append((row, digest, None))
    return result


def _row_integrity_code(error: sqlite3.IntegrityError) -> str:
    """Project expected row-local SQLite conflicts to safe diagnostics."""

    message = str(error)
    if "users.token" in message:
        return "student_token_conflict"
    if "family_account_emails" in message:
        return "invalid_emails"
    if "auth_accounts" in message:
        return "account_conflict"
    return "row_conflict"


def _rollback_row(connection: sqlite3.Connection) -> None:
    connection.execute("ROLLBACK TO SAVEPOINT account_batch_row")
    connection.execute("RELEASE SAVEPOINT account_batch_row")


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


def _enrollment_batch_audit(
    connection: sqlite3.Connection,
    *,
    request: web.Request,
    principal,
    created: int,
    skipped: int,
    now: str,
) -> None:
    insert_audit_event(
        connection,
        actor_user_id=principal.linked_user_id,
        actor_account_public_id=principal.account_public_id,
        audience="staff",
        action="course_enrollments.batch_created",
        object_type="course_enrollment_batch",
        object_id=request["request_id"],
        request_id=request["request_id"],
        before_json=None,
        after_json=json.dumps(
            {"created": created, "skipped": skipped}, separators=(",", ":")
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
        for number, ((row, digest, invalid_code), resolved_login) in enumerate(
            zip(prepared, resolved_logins, strict=True), start=1
        ):
            if row is None or digest is None or resolved_login is None:
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": invalid_code or "invalid_row",
                    }
                )
                continue
            resolved_normalized = normalize_student_login(str(resolved_login))
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
            connection.execute("SAVEPOINT account_batch_row")
            try:
                user_id, user_public_id = insert_student_user(
                    connection,
                    surname=str(row["surname"]),
                    name=str(row["name"]),
                    patronymic=str(row["patronymic"]),
                    token=str(row["password"]),
                    grade=row["grade"],
                    birth_date=row["birth_date"],
                )
                account_id, account_public_id = insert_provisioned_account(
                    connection,
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
                        {"actorUserId": principal.linked_user_id},
                        separators=(",", ":"),
                    ),
                )
            except sqlite3.IntegrityError as error:
                _rollback_row(connection)
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": _row_integrity_code(error),
                    }
                )
                continue
            connection.execute("RELEASE SAVEPOINT account_batch_row")
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


@account_batch_routes.post("/staff/api/v1/imports/course-enrollments/apply")
async def apply_course_enrollments(request: web.Request) -> web.Response:
    principal = _admin(request)
    payload = await _enrollment_payload(request, apply=True)
    source_rows = payload["rows"]
    now = _now()

    def write(connection: sqlite3.Connection) -> dict[str, object]:
        resolved = _resolve_enrollment_batch(connection, source_rows)
        expected_hash = _enrollment_resolution_hash(source_rows, resolved)
        if not hmac.compare_digest(str(payload["previewHash"]), expected_hash):
            return {"state": "preview_changed"}
        result: list[dict[str, object]] = []
        for row in resolved:
            number = int(row["rowNumber"])
            if row["state"] == "invalid":
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": row["code"],
                    }
                )
                continue
            student_user_id = int(row["studentUserId"])
            first_course = not student_has_course_enrollment(
                connection, student_user_id=student_user_id
            )
            enrollment_id, enrollment_public_id = insert_course_enrollment(
                connection,
                student_user_id=student_user_id,
                course_id=int(row["courseId"]),
                active_group_id=str(row["activeGroupId"]),
                actor_user_id=int(principal.linked_user_id),
                now=now,
            )
            allowed_group_ids = tuple(str(value) for value in row["allowedGroupIds"])
            insert_imported_group_access(
                connection,
                enrollment_id=enrollment_id,
                course_id=int(row["courseId"]),
                group_ids=allowed_group_ids,
                actor_user_id=int(principal.linked_user_id),
                now=now,
            )
            insert_course_enrollment_created_event(
                connection,
                enrollment_id=enrollment_id,
                course_id=int(row["courseId"]),
                active_group_id=str(row["activeGroupId"]),
                actor_user_id=int(principal.linked_user_id),
                request_id=f"{request['request_id']}.row-{number}",
                now=now,
            )
            if first_course:
                # The first course remains visible to the parallel legacy bot;
                # later courses cannot be represented by its single group field.
                sync_first_course_to_legacy_user(
                    connection,
                    student_user_id=student_user_id,
                    active_group_id=str(row["activeGroupId"]),
                    allowed_group_ids=allowed_group_ids,
                )
            result.append(
                {
                    "rowNumber": number,
                    "state": "created",
                    "login": row["login"],
                    "courseCode": row["courseCode"],
                    "activeGroupCode": row["activeGroupCode"],
                    "allowedGroupCodes": row["allowedGroupCodes"],
                    "enrollmentId": enrollment_public_id,
                }
            )
        _enrollment_batch_audit(
            connection,
            request=request,
            principal=principal,
            created=sum(row["state"] == "created" for row in result),
            skipped=sum(row["state"] != "created" for row in result),
            now=now,
        )
        return {"state": "ok", "rows": result}

    try:
        outcome = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="enrollment_conflict",
            message="Данные изменились. Обновите предпросмотр.",
        ) from error
    if outcome["state"] == "preview_changed":
        raise PwaApiError(
            status=409,
            code="preview_changed",
            message="Состав курса или групп изменился. Обновите предпросмотр.",
        )
    return _apply_response(request, outcome["rows"])


@account_batch_routes.post("/staff/api/v1/imports/family-accounts/apply")
async def apply_family_accounts(request: web.Request) -> web.Response:
    principal = _admin(request)
    payload = await _payload(request, apply=True)
    source_rows, resolved_logins = _validated_apply(payload)
    prepared = await _hash_rows(request, source_rows, normalize_family_batch_row)
    now = _now()

    def write(connection: sqlite3.Connection) -> list[dict[str, object]]:
        used_logins = account_logins(connection, audience="family")
        used_emails = family_emails(connection)
        result: list[dict[str, object]] = []
        for number, ((row, digest, invalid_code), resolved_login) in enumerate(
            zip(prepared, resolved_logins, strict=True), start=1
        ):
            if row is None or digest is None:
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": invalid_code or "invalid_row",
                    }
                )
                continue
            duplicate_code = _family_duplicate_code(
                login_normalized=str(row["login_normalized"]),
                emails=tuple(str(email).casefold() for email in row["emails"]),
                used_logins=used_logins,
                used_emails=used_emails,
            )
            if duplicate_code is not None:
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": duplicate_code,
                    }
                )
                continue
            students = [
                student_for_login(connection, login_normalized=str(login))
                for login in row["child_logins"]
            ]
            if any(student is None for student in students):
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": "child_login_not_found",
                    }
                )
                continue
            if (
                resolved_login is None
                or resolved_login != row["login"]
                or normalize_login(str(resolved_login)) != row["login_normalized"]
            ):
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": "account_conflict",
                    }
                )
                continue
            connection.execute("SAVEPOINT account_batch_row")
            try:
                account_id, account_public_id = insert_provisioned_account(
                    connection,
                    audience="family",
                    username=resolved_login,
                    username_normalized=str(row["login_normalized"]),
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
            except sqlite3.IntegrityError as error:
                _rollback_row(connection)
                result.append(
                    {
                        "rowNumber": number,
                        "state": "skipped",
                        "code": _row_integrity_code(error),
                    }
                )
                continue
            connection.execute("RELEASE SAVEPOINT account_batch_row")
            used_logins.add(str(row["login_normalized"]))
            used_emails.update(str(email).casefold() for email in row["emails"])
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
