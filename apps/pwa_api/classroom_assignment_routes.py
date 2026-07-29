"""Admin HTTP endpoints for classroom student-assignment plans."""

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
from models.pwa.classroom_assignments import (
    ClassroomAssignmentConflict,
    ClassroomAssignmentNotFound,
    InvalidClassroomAssignment,
    confirm_assignment_plan,
    read_assignment_plan,
    recalculate_assignment_plan,
)


classroom_assignment_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="classroom_assignment_unavailable",
            message="Распределение школьников временно недоступно",
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
            message="Распределять школьников может только администратор",
        )
    return principal.linked_user_id


def _public_id(request: web.Request, field: str) -> str:
    value = request.match_info[field]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="classroom_assignment_not_found",
            message="План распределения не найден",
        )
    return value


async def _empty_json(request: web.Request) -> None:
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
    if payload != {"schemaVersion": 1}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля плана распределения",
        )


def _expected_version(request: web.Request, plan_public_id: str) -> int:
    values = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите план перед сохранением",
        )
    if match.group(1) != plan_public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="План уже изменился. Обновите страницу.",
        )
    return int(match.group(2))


def _working_plan_version(request: web.Request) -> tuple[str, int] | None:
    values = request.headers.getall("If-Match", [])
    if not values:
        return None
    match = _ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите план перед сохранением",
        )
    return match.group(1), int(match.group(2))


def _serialize(result: dict[str, object]) -> dict[str, object]:
    event = result["event"]
    plan = result["plan"]
    groups_by_id = {int(group["group_lesson_id"]): group for group in result["groups"]}
    return {
        "event": {
            "publicId": event["public_id"],
            "name": event["name"],
            "startsAt": event["starts_at"],
            "endsAt": event["ends_at"],
            "status": event["status"],
        },
        "plan": (
            None
            if plan is None
            else {
                "publicId": plan["public_id"],
                "state": plan["state"],
                "staleReason": plan["stale_reason"],
                "version": plan["version"],
                "updatedAt": plan["updated_at"],
                "confirmedAt": plan["confirmed_at"],
            }
        ),
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
            }
            for group in result["groups"]
        ],
        "rooms": [
            {
                "publicId": room["classroom_public_id"],
                "name": room["classroom_name"],
                "status": room["classroom_status"],
                "groupLessonPublicId": groups_by_id[int(room["group_lesson_id"])][
                    "group_lesson_public_id"
                ],
            }
            for room in result["rooms"]
        ],
        "students": [
            {
                "enrollmentPublicId": student["enrollment_public_id"],
                "studentPublicId": student["student_public_id"],
                "surname": student["surname"],
                "name": student["name"],
                "age": student["age_years"],
                "grade": student["grade"],
                "strength": student["strength"],
                "groupLessonPublicId": student["group_lesson_public_id"],
                "groupPublicId": groups_by_id[int(student["group_lesson_id"])][
                    "group_public_id"
                ],
                "classroomPublicId": student["classroom_public_id"],
                "classroomName": student["classroom_name"],
                "status": student["status"],
                "source": student["source"],
            }
            for student in result["students"]
        ],
    }


def _response(request: web.Request, result: dict[str, object]) -> web.Response:
    response = web.json_response(
        {
            "schemaVersion": 1,
            "assignmentPlan": _serialize(result),
            "requestId": request["request_id"],
        }
    )
    plan = result["plan"]
    if plan is not None:
        response.headers["ETag"] = f'"{plan["public_id"]}:v{plan["version"]}"'
    return response


def _raise_domain_error(error: Exception) -> None:
    if isinstance(error, ClassroomAssignmentNotFound):
        raise PwaApiError(
            status=404,
            code="classroom_assignment_not_found",
            message="План распределения не найден",
        ) from error
    if isinstance(error, ClassroomAssignmentConflict):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="План уже изменился. Обновите страницу.",
        ) from error
    if isinstance(error, InvalidClassroomAssignment):
        raise PwaApiError(
            status=422,
            code="invalid_classroom_assignment",
            message="Проверьте распределение школьников по аудиториям",
        ) from error
    raise error


@classroom_assignment_routes.get(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-assignment-plan"
)
async def get_classroom_assignment_plan(request: web.Request) -> web.Response:
    _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    try:
        result = await _factory(request).run_read_async(
            lambda connection: read_assignment_plan(connection, event_public_id)
        )
    except ClassroomAssignmentNotFound as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


@classroom_assignment_routes.post(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-assignment-plan/recalculate"
)
async def post_recalculate_classroom_assignment_plan(
    request: web.Request,
) -> web.Response:
    actor_user_id = _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    await _empty_json(request)
    working_plan = _working_plan_version(request)
    plan_public_id, expected_version = (
        (f"classroom-plan.{uuid.uuid4().hex}", None)
        if working_plan is None
        else working_plan
    )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: recalculate_assignment_plan(
                connection,
                event_public_id=event_public_id,
                plan_public_id=plan_public_id,
                expected_version=expected_version,
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except (
        ClassroomAssignmentNotFound,
        ClassroomAssignmentConflict,
        InvalidClassroomAssignment,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


@classroom_assignment_routes.post(
    "/staff/api/v1/in-person-events/{event_public_id}/classroom-assignment-plan/"
    "{plan_public_id}/confirm"
)
async def post_confirm_classroom_assignment_plan(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    event_public_id = _public_id(request, "event_public_id")
    plan_public_id = _public_id(request, "plan_public_id")
    expected_version = _expected_version(request, plan_public_id)
    await _empty_json(request)
    try:
        result = await _factory(request).run_write_async(
            lambda connection: confirm_assignment_plan(
                connection,
                event_public_id=event_public_id,
                plan_public_id=plan_public_id,
                expected_version=expected_version,
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except (
        ClassroomAssignmentNotFound,
        ClassroomAssignmentConflict,
        InvalidClassroomAssignment,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")
    return _response(request, result)


__all__ = ["classroom_assignment_routes"]
