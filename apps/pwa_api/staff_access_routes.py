"""Admin-only HTTP boundary for teacher course/group access."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import auth_service, authenticated_session
from db_methods.pwa.audit import insert_audit_event
from db_methods.pwa.staff_access import (
    find_scope_target,
    find_staff_member,
    insert_teacher,
    insert_teacher_scope,
    list_staff_members,
    list_teacher_scopes,
    promote_staff_member_to_admin,
    revoke_teacher_scope,
)
from helpers.consts import USER_TYPE
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience, normalize_login
from models.pwa.staff_access import InvalidTeacherScopes, teacher_scope_changes


staff_access_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_FIELDS = {"schemaVersion", "expectedScopes", "scopes"}
_CREATE_FIELDS = {
    "schemaVersion",
    "surname",
    "name",
    "middleName",
    "username",
    "password",
    "role",
}
_BATCH_FIELDS = {"schemaVersion", "rows", "scopes"}
_BATCH_ROW_FIELDS = {"surname", "name", "middleName", "username", "password"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="staff_access_unavailable",
            message="Доступы преподавателей временно недоступны",
        )
    return state.factory


def _admin_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Управлять доступами преподавателей может только администратор",
        )
    return principal.linked_user_id


def _actor_account_id(request: web.Request) -> str:
    return authenticated_session(request).principal.account_public_id


def _path_id(request: web.Request) -> str:
    value = request.match_info["staff_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404, code="staff_member_not_found", message="Сотрудник не найден"
        )
    return value


def _scope_input(
    value: object, *, with_version: bool
) -> tuple[str, str | None, int | None]:
    fields = (
        {"courseId", "groupId", "version"} if with_version else {"courseId", "groupId"}
    )
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError
    course_id = value["courseId"]
    group_id = value["groupId"]
    version = value.get("version")
    if (
        not isinstance(course_id, str)
        or _PUBLIC_ID.fullmatch(course_id) is None
        or (
            group_id is not None
            and (
                not isinstance(group_id, str) or _PUBLIC_ID.fullmatch(group_id) is None
            )
        )
        or (
            with_version
            and (
                not isinstance(version, int)
                or isinstance(version, bool)
                or version <= 0
            )
        )
    ):
        raise ValueError
    return course_id, group_id, version if with_version else None


async def _payload(
    request: web.Request,
) -> tuple[list[tuple[str, str | None, int]], list[tuple[str, str | None]]]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        body = json.loads(await request.read())
        if (
            not isinstance(body, dict)
            or set(body) != _FIELDS
            or body.get("schemaVersion") != 1
            or not isinstance(body["expectedScopes"], list)
            or not isinstance(body["scopes"], list)
            or len(body["expectedScopes"]) > 100
            or len(body["scopes"]) > 100
        ):
            raise ValueError
        expected = [
            _scope_input(item, with_version=True) for item in body["expectedScopes"]
        ]
        desired_raw = [
            _scope_input(item, with_version=False) for item in body["scopes"]
        ]
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранные курсы и группы",
        ) from error
    if len(expected) != len(
        {(course_id, group_id) for course_id, group_id, _ in expected}
    ):
        raise PwaApiError(
            status=422,
            code="duplicate_scope",
            message="Одна область доступа указана несколько раз",
        )
    return (
        [
            (course_id, group_id, int(version))
            for course_id, group_id, version in expected
        ],
        [(course_id, group_id) for course_id, group_id, _ in desired_raw],
    )


def _scope_payload(row: dict[str, object]) -> dict[str, object]:
    group_id = row["group_public_id"]
    return {
        "courseId": row["course_public_id"],
        "courseCode": row["course_code"],
        "courseName": row["course_name"],
        "courseStatus": row["course_status"],
        "groupId": group_id,
        "groupCode": row["group_code"] if group_id is not None else None,
        "groupName": row["group_name"] if group_id is not None else None,
        "groupStatus": row["group_status"] if group_id is not None else None,
        "version": row["version"],
    }


def _member_payload(
    row: dict[str, object], scopes: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "staffUserId": row["public_id"],
        "name": row["name"],
        "surname": row["surname"],
        "middleName": row["middlename"],
        "role": "admin" if int(row["type"]) == int(USER_TYPE.ADMIN) else "teacher",
        "account": None
        if row.get("account_public_id") is None
        else {
            "accountId": row["account_public_id"],
            "username": row["username"],
            "status": row["account_status"],
        },
        "scopes": [_scope_payload(scope) for scope in scopes],
    }


def _scope_summary(rows: list[dict[str, object]]) -> str:
    """Return a stable compact audit value without duplicating scope history."""
    values = [
        "/".join(
            part
            for part in (str(row["course_public_id"]), row["group_public_id"])
            if part is not None
        )
        for row in rows
    ]
    return ", ".join(sorted(values))


def _is_scope_integrity_conflict(error: sqlite3.IntegrityError) -> bool:
    return "UNIQUE constraint failed: staff_scopes" in str(error)


def _directory(connection) -> list[dict[str, object]]:
    members = list_staff_members(connection)
    scope_rows = list_teacher_scopes(
        connection,
        staff_user_ids=tuple(
            int(member["id"])
            for member in members
            if int(member["type"]) == int(USER_TYPE.TEACHER)
        ),
    )
    scopes_by_user: dict[int, list[dict[str, object]]] = {}
    for scope in scope_rows:
        scopes_by_user.setdefault(int(scope["staff_user_id"]), []).append(scope)
    return [
        _member_payload(member, scopes_by_user.get(int(member["id"]), []))
        for member in members
    ]


def _required_text(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    result = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    return result if 1 <= len(result) <= maximum else None


async def _batch_payload(
    request: web.Request,
) -> tuple[list[dict[str, str | None]], list[tuple[str, str | None]]]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        body = json.loads(await request.read())
        if (
            not isinstance(body, dict)
            or set(body) != _BATCH_FIELDS
            or body.get("schemaVersion") != 1
            or not isinstance(body["rows"], list)
            or not 1 <= len(body["rows"]) <= 500
            or not isinstance(body["scopes"], list)
            or not 1 <= len(body["scopes"]) <= 100
        ):
            raise ValueError
        desired_raw = [
            _scope_input(item, with_version=False) for item in body["scopes"]
        ]
        desired = [(course_id, group_id) for course_id, group_id, _ in desired_raw]
        teacher_scope_changes((), desired)
        rows: list[dict[str, str | None]] = []
        normalized_usernames: set[str] = set()
        for item in body["rows"]:
            if not isinstance(item, dict) or set(item) != _BATCH_ROW_FIELDS:
                raise ValueError
            surname = _required_text(item["surname"], maximum=100)
            name = _required_text(item["name"], maximum=100)
            username = _required_text(item["username"], maximum=100)
            middle_value = item["middleName"]
            middle_name = (
                None
                if middle_value is None
                else _required_text(middle_value, maximum=100)
            )
            password = item["password"]
            username_normalized = normalize_login(username or "")
            if (
                surname is None
                or name is None
                or username is None
                or (middle_value is not None and middle_name is None)
                or not username_normalized
                or username_normalized in normalized_usernames
                or not isinstance(password, str)
                or not 8 <= len(password) <= 256
                or not password.strip()
            ):
                raise ValueError
            normalized_usernames.add(username_normalized)
            rows.append(
                {
                    "surname": surname,
                    "name": name,
                    "middle_name": middle_name,
                    "username": username,
                    "username_normalized": username_normalized,
                    "password": password,
                }
            )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        InvalidTeacherScopes,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте таблицу преподавателей и выбранные доступы",
        ) from error
    return rows, desired


@staff_access_routes.post("/staff/api/v1/staff-members")
async def create_staff_member(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
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
            message="Проверьте данные преподавателя",
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != _CREATE_FIELDS
        or payload.get("schemaVersion") != 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные преподавателя",
        )
    surname = _required_text(payload["surname"], maximum=100)
    name = _required_text(payload["name"], maximum=100)
    username = _required_text(payload["username"], maximum=100)
    middle_value = payload["middleName"]
    middle_name = (
        None if middle_value is None else _required_text(middle_value, maximum=100)
    )
    password = payload["password"]
    role = payload["role"]
    normalized_username = normalize_login(username or "")
    if (
        surname is None
        or name is None
        or username is None
        or (middle_value is not None and middle_name is None)
        or not normalized_username
        or not isinstance(password, str)
        or not 8 <= len(password) <= 256
        or not password.strip()
        or role not in {"teacher", "admin"}
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные преподавателя",
        )

    credential_hash = await asyncio.to_thread(
        auth_service(request).credential_hasher.hash, password
    )
    now = _now()

    def write(connection):
        created = insert_teacher(
            connection,
            surname=surname,
            name=name,
            middle_name=middle_name,
            username=username,
            username_normalized=normalized_username,
            credential_hash=credential_hash,
            now=now,
            user_type=USER_TYPE.ADMIN if role == "admin" else USER_TYPE.TEACHER,
        )
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="staff.member_created",
            object_type="staff_member",
            object_id=str(created["public_id"]),
            request_id=request["request_id"],
            before_json=None,
            after_json=json.dumps(
                {"username": username, "role": role},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=now,
        )
        return find_staff_member(connection, public_id=str(created["public_id"]))

    try:
        member = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="staff_member_conflict",
            message="Такой логин преподавателя уже используется",
        ) from error
    assert member is not None
    return web.json_response(
        {
            "schemaVersion": 1,
            "member": _member_payload(member, []),
            "requestId": request["request_id"],
        },
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@staff_access_routes.patch("/staff/api/v1/staff-members/{staff_public_id}/role")
async def promote_staff_member(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    staff_public_id = _path_id(request)
    if request.query or request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте новую роль сотрудника"
        )
    try:
        body = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте новую роль сотрудника"
        ) from error
    if body != {"schemaVersion": 1, "role": "admin"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте новую роль сотрудника"
        )
    now = _now()

    def write(connection):
        member = find_staff_member(connection, public_id=staff_public_id)
        if member is None:
            return None
        if int(member["type"]) == int(USER_TYPE.TEACHER):
            promote_staff_member_to_admin(
                connection, staff_user_id=int(member["id"]), now=now
            )
            insert_audit_event(
                connection,
                actor_user_id=actor_user_id,
                actor_account_public_id=actor_account_id,
                audience="staff",
                action="staff.member_promoted",
                object_type="staff_member",
                object_id=staff_public_id,
                request_id=request["request_id"],
                before_json='{"role":"teacher"}',
                after_json='{"role":"admin"}',
                occurred_at=now,
            )
        updated = find_staff_member(connection, public_id=staff_public_id)
        assert updated is not None
        return _member_payload(updated, [])

    member = await _factory(request).run_write_async(write)
    if member is None:
        raise PwaApiError(
            status=404, code="staff_member_not_found", message="Сотрудник не найден"
        )
    return web.json_response(
        {"schemaVersion": 1, "member": member, "requestId": request["request_id"]},
        headers={"Cache-Control": "no-store"},
    )


@staff_access_routes.post("/staff/api/v1/staff-members/batch")
async def create_staff_member_batch(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    rows, desired_scopes = await _batch_payload(request)
    hasher = auth_service(request).credential_hasher
    credential_hashes = await asyncio.to_thread(
        lambda: [hasher.hash(str(row["password"])) for row in rows]
    )
    now = _now()
    request_id = request["request_id"]

    def write(connection):
        existing_usernames = {
            normalize_login(str(member["username"]))
            for member in list_staff_members(connection)
            if member.get("username") is not None
        }
        if any(str(row["username_normalized"]) in existing_usernames for row in rows):
            return "conflict"

        targets: list[dict[str, object]] = []
        for course_id, group_id in desired_scopes:
            target = find_scope_target(
                connection, course_public_id=course_id, group_public_id=group_id
            )
            if (
                target is None
                or target["course_status"] != "active"
                or (group_id is not None and target["group_status"] != "active")
            ):
                return "invalid_target"
            targets.append(target)

        for row, credential_hash in zip(rows, credential_hashes, strict=True):
            created = insert_teacher(
                connection,
                surname=str(row["surname"]),
                name=str(row["name"]),
                middle_name=row["middle_name"],
                username=str(row["username"]),
                username_normalized=str(row["username_normalized"]),
                credential_hash=credential_hash,
                now=now,
            )
            for target in targets:
                insert_teacher_scope(
                    connection,
                    staff_user_id=int(created["id"]),
                    course_id=int(target["course_id"]),
                    group_id=target.get("group_id"),
                    actor_user_id=actor_user_id,
                    now=now,
                )

        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="staff.member_batch_created",
            object_type="staff_member_batch",
            object_id=request_id,
            request_id=request_id,
            before_json=None,
            after_json=json.dumps(
                {"createdCount": len(rows), "scopeCount": len(desired_scopes)},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=now,
        )
        return "created"

    try:
        outcome = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="staff_member_batch_conflict",
            message="Один из логинов преподавателей уже используется",
        ) from error
    if outcome == "conflict":
        raise PwaApiError(
            status=409,
            code="staff_member_batch_conflict",
            message="Один из логинов преподавателей уже используется",
        )
    if outcome == "invalid_target":
        raise PwaApiError(
            status=409,
            code="staff_scope_target_changed",
            message="Курс или группа изменились. Обновите страницу и повторите загрузку",
        )
    return web.json_response(
        {
            "schemaVersion": 1,
            "counts": {"total": len(rows), "created": len(rows)},
            "requestId": request_id,
        },
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@staff_access_routes.get("/staff/api/v1/staff-access")
async def get_staff_access(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    members = await _factory(request).run_read_async(_directory)
    return web.json_response(
        {"schemaVersion": 1, "members": members, "requestId": request["request_id"]},
        headers={"Cache-Control": "no-store"},
    )


@staff_access_routes.put("/staff/api/v1/staff-members/{staff_public_id}/scopes")
async def replace_staff_scopes(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    staff_public_id = _path_id(request)
    expected, desired = await _payload(request)

    def write(connection):
        member = find_staff_member(connection, public_id=staff_public_id)
        if member is None:
            return "not_found", None
        if int(member["type"]) != int(USER_TYPE.TEACHER):
            return "admin", None
        current = list_teacher_scopes(connection, staff_user_ids=(int(member["id"]),))
        current_versions = {
            (str(row["course_public_id"]), row["group_public_id"], int(row["version"]))
            for row in current
        }
        if current_versions != set(expected):
            return "conflict", None
        try:
            additions, removals = teacher_scope_changes(
                (
                    (str(row["course_public_id"]), row["group_public_id"])
                    for row in current
                ),
                desired,
            )
        except InvalidTeacherScopes as error:
            return str(error), None

        targets: dict[tuple[str, str | None], dict[str, object]] = {}
        for course_id, group_id in additions:
            target = find_scope_target(
                connection, course_public_id=course_id, group_public_id=group_id
            )
            if (
                target is None
                or target["course_status"] != "active"
                or (group_id is not None and target["group_status"] != "active")
            ):
                return "invalid_target", None
            targets[(course_id, group_id)] = target

        now = _now()
        current_by_key = {
            (str(row["course_public_id"]), row["group_public_id"]): row
            for row in current
        }
        for key in removals:
            row = current_by_key[key]
            if not revoke_teacher_scope(
                connection,
                scope_id=int(row["id"]),
                expected_version=int(row["version"]),
                actor_user_id=actor_user_id,
                now=now,
            ):
                raise RuntimeError("Locked teacher scope changed inside transaction")
        for key in additions:
            target = targets[key]
            insert_teacher_scope(
                connection,
                staff_user_id=int(member["id"]),
                course_id=int(target["course_id"]),
                group_id=target.get("group_id"),
                actor_user_id=actor_user_id,
                now=now,
            )
        updated = list_teacher_scopes(connection, staff_user_ids=(int(member["id"]),))
        if additions or removals:
            insert_audit_event(
                connection,
                actor_user_id=actor_user_id,
                actor_account_public_id=actor_account_id,
                audience="staff",
                action="staff_scope.replaced",
                object_type="staff_scope",
                object_id=staff_public_id,
                request_id=request["request_id"],
                before_json=json.dumps(
                    {"scopeCount": len(current), "scopes": _scope_summary(current)},
                    ensure_ascii=False,
                ),
                after_json=json.dumps(
                    {
                        "scopeCount": len(updated),
                        "scopes": _scope_summary(updated),
                        "addedCount": len(additions),
                        "removedCount": len(removals),
                    },
                    ensure_ascii=False,
                ),
                occurred_at=now,
            )
        return "ok", _member_payload(member, updated)

    try:
        outcome, member = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_scope_integrity_conflict(error):
            raise
        raise PwaApiError(
            status=409,
            code="staff_scope_conflict",
            message="Доступы уже изменились. Обновите страницу.",
        ) from error
    if outcome == "not_found":
        raise PwaApiError(
            status=404, code="staff_member_not_found", message="Сотрудник не найден"
        )
    if outcome == "admin":
        raise PwaApiError(
            status=422,
            code="admin_scope_fixed",
            message="Администратор имеет доступ ко всем курсам",
        )
    if outcome == "conflict":
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Доступы уже изменились. Обновите страницу.",
        )
    if outcome in {"duplicate_scope", "redundant_group_scope", "invalid_target"}:
        raise PwaApiError(
            status=422, code=outcome, message="Проверьте выбранные курсы и группы"
        )
    assert member is not None
    return web.json_response(
        {"schemaVersion": 1, "member": member, "requestId": request["request_id"]},
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["staff_access_routes"]
