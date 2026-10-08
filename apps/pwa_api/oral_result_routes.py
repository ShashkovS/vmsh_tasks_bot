"""Staff HTTP adapter for online oral marks stored in legacy results."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from apps.pwa_api.review_routes import PWA_REVIEW_COMPLETION_INVALIDATOR
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.oral_results import (
    OralResultConflict,
    OralResultInvalid,
    OralResultNotFound,
    record_round,
    roster,
)


oral_result_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_FIELDS = frozenset(
    {"schemaVersion", "studentId", "idempotencyKey", "marks", "reactionId"}
)
_MARK_FIELDS = frozenset({"problemId", "outcome"})


def _now() -> datetime:
    return datetime.now(UTC)


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="oral_results_unavailable",
            message="Внесение устных результатов временно недоступно",
        )
    return state.factory


def _public_id(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные устной сдачи",
            details={"field": field},
        )
    return value


def _staff_principal(request: web.Request):
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.has_capability(Capability.ORAL_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для внесения устных результатов",
        )
    return principal


def _authorize_lesson(principal, lesson: dict[str, object]) -> None:
    if not principal.has_staff_group_access(
        course_public_id=str(lesson["course_public_id"]),
        group_public_id=str(lesson["group_public_id"]),
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Нет доступа к этой группе",
        )


async def _json(request: web.Request) -> dict[str, object]:
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
        or set(payload) != _FIELDS
        or payload.get("schemaVersion") != 1
        or not isinstance(payload.get("marks"), list)
        or not 1 <= len(payload["marks"]) <= 50
        or (
            payload.get("reactionId") is not None
            and (
                not isinstance(payload.get("reactionId"), int)
                or isinstance(payload.get("reactionId"), bool)
            )
        )
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные устной сдачи",
        )
    for mark in payload["marks"]:
        if (
            not isinstance(mark, dict)
            or set(mark) != _MARK_FIELDS
            or mark.get("outcome") not in {"accepted", "rejected"}
        ):
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Проверьте отметки устных задач",
            )
        _public_id(mark.get("problemId"), field="problemId")
    _public_id(payload.get("studentId"), field="studentId")
    _public_id(payload.get("idempotencyKey"), field="idempotencyKey")
    return payload


def _translate(error: Exception) -> PwaApiError:
    if isinstance(error, OralResultNotFound):
        return PwaApiError(
            status=404,
            code="oral_result_context_not_found",
            message="Школьник или занятие не найдены",
        )
    if isinstance(error, OralResultConflict):
        return PwaApiError(
            status=409,
            code="oral_result_idempotency_conflict",
            message="Эта операция уже использована с другими данными",
        )
    return PwaApiError(
        status=422,
        code="invalid_oral_result",
        message="Проверьте школьника, задачи и отметки",
    )


@oral_result_routes.get(
    "/staff/api/v1/group-lessons/{group_lesson_public_id}/oral-roster"
)
async def get_oral_roster(request: web.Request) -> web.Response:
    principal = _staff_principal(request)
    group_lesson_public_id = _public_id(
        request.match_info["group_lesson_public_id"],
        field="groupLessonId",
    )
    try:
        data = await _factory(request).run_read_async(
            lambda connection: roster(
                connection,
                group_lesson_public_id=group_lesson_public_id,
            )
        )
    except OralResultNotFound as error:
        raise _translate(error) from error
    _authorize_lesson(principal, data["lesson"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "groupLessonId": group_lesson_public_id,
            "students": [
                {
                    "studentId": student["public_id"],
                    "displayName": student["display_name"],
                }
                for student in data["students"]
            ],
            "problems": [
                {
                    "problemId": problem["public_id"],
                    "displayNumber": problem["display_number"],
                    "title": problem["title"],
                }
                for problem in data["problems"]
            ],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@oral_result_routes.post(
    "/staff/api/v1/group-lessons/{group_lesson_public_id}/oral-results"
)
async def post_oral_result(request: web.Request) -> web.Response:
    principal = _staff_principal(request)
    group_lesson_public_id = _public_id(
        request.match_info["group_lesson_public_id"],
        field="groupLessonId",
    )
    try:
        context = await _factory(request).run_read_async(
            lambda connection: roster(
                connection,
                group_lesson_public_id=group_lesson_public_id,
            )
        )
    except OralResultNotFound as error:
        raise _translate(error) from error
    _authorize_lesson(principal, context["lesson"])
    payload = await _json(request)
    marks = tuple(
        (str(mark["problemId"]), str(mark["outcome"])) for mark in payload["marks"]
    )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: record_round(
                connection,
                group_lesson_public_id=group_lesson_public_id,
                student_public_id=str(payload["studentId"]),
                teacher_user_id=int(principal.linked_user_id),
                idempotency_key=str(payload["idempotencyKey"]),
                marks=marks,
                reaction_id=(
                    None
                    if payload["reactionId"] is None
                    else int(payload["reactionId"])
                ),
                now=_now(),
            )
        )
    except (OralResultConflict, OralResultInvalid, OralResultNotFound) as error:
        raise _translate(error) from error

    invalidator = request.app.get(PWA_REVIEW_COMPLETION_INVALIDATOR)
    if invalidator is not None and not result["replayed"]:
        try:
            await invalidator(
                (str(result["student_account_public_id"]),),
                (),
                tuple(str(problem_id) for problem_id in result["marks"]),
                "oral-result-recorded",
            )
        except Exception:
            logger.warning(
                "Oral-result invalidation failed after commit: key=%s",
                payload["idempotencyKey"],
                exc_info=True,
            )
    return web.json_response(
        {
            "schemaVersion": 1,
            "idempotencyKey": payload["idempotencyKey"],
            "replayed": result["replayed"],
            "marks": payload["marks"],
            "reactionId": result["reaction_id"],
            "requestId": request["request_id"],
        },
        status=200 if result["replayed"] else 201,
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["oral_result_routes"]
