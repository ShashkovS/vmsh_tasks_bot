"""Admin-only Student course enrollment and group-access API."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.admin_enrollments import (
    find_enrollment,
    grant_group_access,
    insert_group_event,
    insert_mode_event,
    insert_status_event,
    list_active_group_access,
    list_course_groups,
    list_family_links,
    list_owner_accounts,
    list_students,
    revoke_group_access,
    update_enrollment,
)
from db_methods.pwa.family_enrollment import (
    mark_working_classroom_plans_stale,
    sync_legacy_single_course_user,
)
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.classroom_assignment import classroom_strength
from helpers.pwa.permissions import AuthorizationPrincipal, Capability
from models.pwa.admin_enrollment import (
    InvalidAdminEnrollmentChange,
    plan_admin_enrollment_change,
)
from models.pwa.auth import AuthAudience


admin_enrollment_routes = web.RouteTableDef()
EnrollmentInvalidator = Callable[
    [tuple[str, ...], tuple[str, ...], str], Awaitable[None]
]
PWA_ENROLLMENT_INVALIDATOR = web.AppKey(
    "pwa_enrollment_invalidator", EnrollmentInvalidator
)
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_UPDATE_FIELDS = {
    "schemaVersion",
    "activeGroupId",
    "allowedGroupIds",
    "attendanceMode",
    "status",
}
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="student_enrollments_unavailable",
            message="Список участников временно недоступен",
        )
    return state.factory


def _staff_principal(
    request: web.Request, capability: Capability
) -> AuthorizationPrincipal:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.has_capability(capability)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для работы со списком участников",
        )
    return principal


def _path_public_id(request: web.Request) -> str:
    value = request.match_info["enrollment_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="enrollment_not_found",
            message="Запись на курс не найдена",
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
            message="Запись уже изменилась. Обновите список.",
        )
    return int(match.group(2))


async def _update_payload(request: web.Request) -> dict[str, object]:
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
            message="Проверьте группы и режим школьника",
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != _UPDATE_FIELDS
        or payload.get("schemaVersion") != 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте группы и режим школьника",
        )
    active_group_id = payload["activeGroupId"]
    allowed_group_ids = payload["allowedGroupIds"]
    if (
        not isinstance(active_group_id, str)
        or _PUBLIC_ID.fullmatch(active_group_id) is None
        or not isinstance(allowed_group_ids, list)
        or not allowed_group_ids
        or len(allowed_group_ids) > 100
        or any(
            not isinstance(group_id, str) or _PUBLIC_ID.fullmatch(group_id) is None
            for group_id in allowed_group_ids
        )
        or len(set(allowed_group_ids)) != len(allowed_group_ids)
        or payload["attendanceMode"] not in {"online", "in_person"}
        or payload["status"] not in {"active", "paused", "archived"}
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте группы и режим школьника",
        )
    return payload


def _group_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "groupId": row["group_public_id"],
        "code": row["short_code"],
        "name": row["public_name"],
        "status": row["status"],
        "colorKey": row["color_key"] or "neutral",
        "sortOrder": row["sort_order"],
    }


def _enrollment_payload(
    row: dict[str, object], *, access_rows: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "enrollmentId": row["enrollment_public_id"],
        "course": {
            "courseId": row["course_public_id"],
            "code": row["course_code"],
            "name": row["course_name"],
            "subjectCode": row["subject_code"],
        },
        "activeGroupId": row["active_group_public_id"],
        "allowedGroups": [_group_payload(access) for access in access_rows],
        "attendanceMode": row["attendance_mode"],
        "status": row["enrollment_status"],
        "version": row["enrollment_version"],
    }


def _directory(
    connection: sqlite3.Connection,
    *,
    staff_scopes: tuple[tuple[str, str | None], ...] | None,
    include_private_accounts: bool,
) -> list[dict[str, object]]:
    rows = list_students(connection, staff_scopes=staff_scopes)
    enrollment_ids = tuple(
        int(row["enrollment_id"]) for row in rows if row["enrollment_id"] is not None
    )
    student_user_ids = tuple(sorted({int(row["student_user_id"]) for row in rows}))
    access_by_enrollment: dict[int, list[dict[str, object]]] = {}
    for access in list_active_group_access(connection, enrollment_ids):
        access_by_enrollment.setdefault(int(access["enrollment_id"]), []).append(access)
    families_by_student: dict[int, list[dict[str, object]]] = {}
    family_rows = (
        list_family_links(connection, student_user_ids)
        if include_private_accounts
        else []
    )
    for family in family_rows:
        families_by_student.setdefault(int(family["student_user_id"]), []).append(
            family
        )

    students: dict[int, dict[str, object]] = {}
    for row in rows:
        student_user_id = int(row["student_user_id"])
        student = students.get(student_user_id)
        if student is None:
            student = {
                "studentId": row["student_public_id"],
                "surname": row["surname"],
                "name": row["name"],
                "middleName": row["middlename"],
                "grade": row["grade"],
                "birthday": row["birthday"],
                "strength": classroom_strength(row["simple_prob"], row["compl_prob"]),
                "webAccount": (
                    None
                    if not include_private_accounts or row["account_public_id"] is None
                    else {
                        "accountId": row["account_public_id"],
                        "username": row["username"],
                        "status": row["account_status"],
                        "credentialVersion": row["account_credential_version"],
                    }
                ),
                "familyAccounts": [
                    {
                        "accountId": family["account_public_id"],
                        "displayName": family["display_name"],
                        "status": family["status"],
                        "credentialVersion": family["credential_version"],
                        "relationshipLabel": family["relationship_label"],
                        "isPrimary": bool(family["is_primary"]),
                    }
                    for family in families_by_student.get(student_user_id, [])
                ],
                "enrollments": [],
            }
            students[student_user_id] = student
        if row["enrollment_id"] is not None:
            student["enrollments"].append(
                _enrollment_payload(
                    row,
                    access_rows=access_by_enrollment.get(int(row["enrollment_id"]), []),
                )
            )
    return list(students.values())


@admin_enrollment_routes.get("/staff/api/v1/student-enrollments")
async def get_student_enrollments(request: web.Request) -> web.Response:
    principal = _staff_principal(request, Capability.STUDENT_READ)
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    staff_scopes = None
    if not principal.is_global_admin:
        staff_scopes = tuple(
            (scope.course_public_id, scope.group_public_id)
            for scope in principal.staff_scope_grants
        )
    students = await _factory(request).run_read_async(
        lambda connection: _directory(
            connection,
            staff_scopes=staff_scopes,
            include_private_accounts=principal.is_global_admin,
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "students": students,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@admin_enrollment_routes.put("/staff/api/v1/course-enrollments/{enrollment_public_id}")
async def put_student_enrollment(request: web.Request) -> web.Response:
    principal = _staff_principal(request, Capability.STUDENT_ACTIVE_GROUP_WRITE)
    assert principal.linked_user_id is not None
    actor_user_id = principal.linked_user_id
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    public_id = _path_public_id(request)
    expected_version = _expected_version(request, public_id)
    payload = await _update_payload(request)
    now = _now()

    def write(connection: sqlite3.Connection):
        current = find_enrollment(connection, public_id=public_id)
        if current is None:
            return {"state": "not_found"}
        if int(current["enrollment_version"]) != expected_version:
            return {"state": "conflict"}
        course_groups = list_course_groups(
            connection, course_id=int(current["course_id"])
        )
        groups_by_public_id = {
            str(group["public_id"]): group for group in course_groups
        }
        requested_public_ids = set(payload["allowedGroupIds"])
        if payload[
            "activeGroupId"
        ] not in groups_by_public_id or not requested_public_ids.issubset(
            groups_by_public_id
        ):
            return {"state": "unknown_group"}
        active_group = groups_by_public_id[str(payload["activeGroupId"])]
        if active_group["status"] == "archived":
            return {"state": "archived_group"}

        requested_internal_ids = {
            str(groups_by_public_id[group_public_id]["group_id"])
            for group_public_id in requested_public_ids
        }
        current_access_rows = list_active_group_access(
            connection, (int(current["enrollment_id"]),)
        )
        current_access = {str(row["group_id"]) for row in current_access_rows}
        current_access_public_ids = {
            str(row["group_public_id"]) for row in current_access_rows
        }
        if not principal.is_global_admin:
            course_public_id = str(current["course_public_id"])
            current_group_public_id = str(current["active_group_public_id"])
            target_group_public_id = str(payload["activeGroupId"])
            if (
                not principal.has_staff_group_access(
                    course_public_id=course_public_id,
                    group_public_id=current_group_public_id,
                )
                or not principal.has_staff_group_access(
                    course_public_id=course_public_id,
                    group_public_id=target_group_public_id,
                )
                or target_group_public_id not in current_access_public_ids
                or requested_public_ids != current_access_public_ids
                or payload["attendanceMode"] != current["attendance_mode"]
                or payload["status"] != current["enrollment_status"]
            ):
                return {"state": "forbidden"}
        try:
            plan = plan_admin_enrollment_change(
                current_active_group_id=str(current["active_group_id"]),
                current_attendance_mode=str(current["attendance_mode"]),
                current_status=str(current["enrollment_status"]),
                current_allowed_group_ids=current_access,
                active_group_id=str(active_group["group_id"]),
                attendance_mode=str(payload["attendanceMode"]),
                status=str(payload["status"]),
                allowed_group_ids=requested_internal_ids,
            )
        except InvalidAdminEnrollmentChange:
            return {"state": "invalid"}
        if not plan.changed:
            return {
                "state": "ok",
                "row": current,
                "owners": list_owner_accounts(
                    connection, student_user_id=int(current["student_user_id"])
                ),
                "changed": False,
            }
        if not update_enrollment(
            connection,
            enrollment_id=int(current["enrollment_id"]),
            expected_version=expected_version,
            active_group_id=plan.active_group_id,
            attendance_mode=str(payload["attendanceMode"]),
            status=str(payload["status"]),
            actor_user_id=actor_user_id,
            now=now,
        ):
            return {"state": "conflict"}
        for group_id in sorted(plan.revoke_group_ids):
            revoke_group_access(
                connection,
                enrollment_id=int(current["enrollment_id"]),
                group_id=group_id,
                actor_user_id=actor_user_id,
                now=now,
            )
        for group_id in sorted(plan.grant_group_ids):
            grant_group_access(
                connection,
                enrollment_id=int(current["enrollment_id"]),
                course_id=int(current["course_id"]),
                group_id=group_id,
                actor_user_id=actor_user_id,
                now=now,
            )
        if plan.group_changed:
            insert_group_event(
                connection,
                public_id=f"course-enrollment-event.{uuid.uuid4().hex}",
                enrollment_id=int(current["enrollment_id"]),
                course_id=int(current["course_id"]),
                previous_group_id=str(current["active_group_id"]),
                new_group_id=plan.active_group_id,
                actor_user_id=actor_user_id,
                request_id=f"{request['request_id']}.group",
                now=now,
            )
        if plan.mode_changed:
            insert_mode_event(
                connection,
                public_id=f"course-enrollment-event.{uuid.uuid4().hex}",
                enrollment_id=int(current["enrollment_id"]),
                course_id=int(current["course_id"]),
                previous_mode=str(current["attendance_mode"]),
                new_mode=str(payload["attendanceMode"]),
                actor_user_id=actor_user_id,
                request_id=f"{request['request_id']}.mode",
                now=now,
            )
        if plan.status_changed:
            insert_status_event(
                connection,
                public_id=f"course-enrollment-event.{uuid.uuid4().hex}",
                enrollment_id=int(current["enrollment_id"]),
                course_id=int(current["course_id"]),
                previous_status=str(current["enrollment_status"]),
                new_status=str(payload["status"]),
                actor_user_id=actor_user_id,
                request_id=f"{request['request_id']}.status",
                now=now,
            )
        mark_working_classroom_plans_stale(
            connection, course_id=int(current["course_id"]), now=now
        )
        if plan.group_changed or plan.mode_changed:
            sync_legacy_single_course_user(
                connection,
                student_user_id=int(current["student_user_id"]),
                active_group_id=plan.active_group_id,
                attendance_mode=str(payload["attendanceMode"]),
                group_changed=plan.group_changed,
                mode_changed=plan.mode_changed,
                now=now,
            )
        updated = find_enrollment(connection, public_id=public_id)
        assert updated is not None
        return {
            "state": "ok",
            "row": updated,
            "owners": list_owner_accounts(
                connection, student_user_id=int(current["student_user_id"])
            ),
            "changed": True,
        }

    try:
        result = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="enrollment_conflict",
            message="Не удалось применить изменение. Обновите список.",
        ) from error
    if result["state"] == "not_found":
        raise PwaApiError(
            status=404,
            code="enrollment_not_found",
            message="Запись на курс не найдена",
        )
    if result["state"] == "forbidden":
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Преподаватель может менять только активную группу в своём доступе",
        )
    if result["state"] == "conflict":
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Запись уже изменилась. Обновите список.",
        )
    if result["state"] == "unknown_group":
        raise PwaApiError(
            status=422,
            code="group_not_in_course",
            message="Одна из выбранных групп не относится к этому курсу",
        )
    if result["state"] == "archived_group":
        raise PwaApiError(
            status=422,
            code="active_group_archived",
            message="Архивную группу нельзя сделать активной",
        )
    if result["state"] == "invalid":
        raise PwaApiError(
            status=422,
            code="invalid_enrollment",
            message="Активная группа должна входить в список доступных",
        )

    row = result["row"]
    access_rows = await _factory(request).run_read_async(
        lambda connection: list_active_group_access(
            connection, (int(row["enrollment_id"]),)
        )
    )
    if result["changed"]:
        student_accounts = tuple(
            str(owner["public_id"])
            for owner in result["owners"]
            if owner["audience"] == AuthAudience.STUDENT.value
        )
        family_accounts = tuple(
            str(owner["public_id"])
            for owner in result["owners"]
            if owner["audience"] == AuthAudience.FAMILY.value
        )
        invalidator = request.app.get(PWA_ENROLLMENT_INVALIDATOR)
        if invalidator is not None:
            try:
                await invalidator(
                    student_accounts,
                    family_accounts,
                    "staff-enrollment-updated",
                )
            except Exception:
                # SQLite is authoritative; a fan-out failure must not turn a
                # committed admin change into a browser retry and duplicate audit.
                logger.warning(
                    "Enrollment invalidation failed after commit", exc_info=True
                )
    version = int(row["enrollment_version"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "enrollment": _enrollment_payload(row, access_rows=access_rows),
            "requestId": request["request_id"],
        },
        headers={
            "ETag": f'"{public_id}:v{version}"',
            "Cache-Control": "no-store",
        },
    )


__all__ = [
    "PWA_ENROLLMENT_INVALIDATOR",
    "admin_enrollment_routes",
]
