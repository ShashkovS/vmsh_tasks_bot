"""Staff adapter for vmshpwa/docs/live-marking.md; no Telegram startup imports."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.oral_result_routes import _factory, _staff_principal
from db_methods.pwa import live_marking as db
from models.pwa import live_marking as domain

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)
_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_MESSAGES = {
    "not_found": (404, "Школьник, занятие или аудитория не найдены"),
    "forbidden": (403, "Нет доступа к этому приёму"),
    "conflict": (409, "Данные уже изменились. Сравните с актуальным состоянием"),
    "plan_unavailable": (409, "Нужен актуальный подтверждённый план аудиторий"),
    "admin_draft": (
        409,
        "Администратор редактирует распределение. Сначала завершите этот план",
    ),
    "session_finished": (409, "Сессия завершена. Начните новую для исправлений"),
    "invalid": (422, "Проверьте данные изменения"),
}


def _id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise domain.LiveMarkingError("invalid")
    return value


def _context(value):
    if not isinstance(value, dict) or set(value) - {
        "mode",
        "contextId",
        "roomId",
        "lessonId",
        "studentId",
    }:
        raise domain.LiveMarkingError("invalid")
    if value.get("mode") not in ("zoom", "school"):
        raise domain.LiveMarkingError("invalid")
    _id(value.get("contextId"))
    if value["mode"] == "school":
        _id(value.get("roomId"))
    for key in ("roomId", "lessonId", "studentId"):
        if key in value:
            _id(value[key])
    return value


def _integer(value):
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise domain.LiveMarkingError("invalid")


def _command(payload):
    if not isinstance(payload, dict):
        raise domain.LiveMarkingError("invalid")
    kind = payload.get("kind")
    fields = {
        "mark": {"studentId", "problemId", "expectedVersion", "value"},
        "attendance": {"studentId", "expectedVersion", "value"},
        "transfer": {"studentId", "enrollmentVersion", "planId"},
        "reaction": {"studentId", "expectedVersion", "reactions"},
        "praise": {"studentId", "expectedVersion"},
        "undo": {"targetOperationId"},
    }
    if (
        kind not in fields
        or set(payload) != {"kind", "operationId", "context"} | fields[kind]
    ):
        raise domain.LiveMarkingError("invalid")
    _id(payload["operationId"])
    _context(payload["context"])
    for key in ("studentId", "problemId", "planId", "targetOperationId"):
        if key in payload:
            _id(payload[key])
    for key in ("expectedVersion", "enrollmentVersion"):
        if key in payload:
            _integer(payload[key])
    if kind in ("mark", "reaction", "praise"):
        _id(payload["context"].get("lessonId"))
    if kind == "mark" and payload["value"] not in ("plus", "minus"):
        raise domain.LiveMarkingError("invalid")
    if kind == "attendance" and payload["value"] not in (
        "unmarked",
        "present",
        "absent",
    ):
        raise domain.LiveMarkingError("invalid")
    if kind == "reaction":
        rs = payload["reactions"]
        if (
            not isinstance(rs, list)
            or len(rs) > 5
            or any(type(r) is not int or r not in (300, 301, 303, 304, 305) for r in rs)
            or len(set(rs)) != len(rs)
        ):
            raise domain.LiveMarkingError("invalid")
    if (
        payload["context"].get("studentId")
        and payload.get("studentId")
        and payload["context"]["studentId"] != payload["studentId"]
    ):
        raise domain.LiveMarkingError("invalid")
    return payload


async def _payload(request):
    if request.content_type != "application/json":
        raise domain.LiveMarkingError("invalid")
    try:
        value = await request.json()
    except ValueError, UnicodeDecodeError:
        raise domain.LiveMarkingError("invalid") from None
    if not isinstance(value, dict):
        raise domain.LiveMarkingError("invalid")
    return value


async def _run(request, fn, *, write=False):
    try:
        factory = _factory(request)
        result = await (
            factory.run_write_async(fn) if write else factory.run_read_async(fn)
        )
    except domain.LiveMarkingError as error:
        status, message = _MESSAGES[error.code]
        raise PwaApiError(
            status=status, code=f"live_marking_{error.code}", message=message
        ) from error
    return web.json_response(
        dict(schemaVersion=1, **result, requestId=request["request_id"]),
        headers={"Cache-Control": "no-store"},
    )


def _checked(fn):
    # Parsing and service failures use the same public error contract.
    async def wrapped(request):
        try:
            return await fn(request)
        except domain.LiveMarkingError as error:
            status, message = _MESSAGES[error.code]
            raise PwaApiError(
                status=status, code=f"live_marking_{error.code}", message=message
            ) from error

    return wrapped


@routes.get("/staff/api/v1/live-marking/catalog")
@_checked
async def get_catalog(request):
    principal = _staff_principal(request)
    return await _run(request, lambda c: domain.catalog(c, principal))


@routes.get("/staff/api/v1/live-marking/directory")
@_checked
async def get_directory(request):
    principal = _staff_principal(request)
    course_id = _id(request.query.get("courseId"))
    return await _run(request, lambda c: domain.directory(c, principal, course_id))


@routes.get("/staff/api/v1/live-marking/{resource:board|cells|history}")
@_checked
async def get_board(request):
    principal = _staff_principal(request)
    query = dict(request.query)
    after = query.pop("after", None)
    scope = query.pop("scope", None)
    spec = _context(query)
    resource = request.match_info["resource"]
    if resource != "history":
        _id(spec.get("lessonId"))
    if resource == "cells":
        if after is not None:
            if not after.isdecimal() or len(after) > 16:
                raise domain.LiveMarkingError("invalid")
            after = int(after)
        if scope is not None and not re.fullmatch("[0-9a-f]{64}", scope):
            raise domain.LiveMarkingError("invalid")
        return await _run(
            request, lambda c: domain.read_cells(c, principal, spec, after, scope)
        )
    fn = {"board": domain.board, "history": domain.operation_history}[resource]
    return await _run(request, lambda c: fn(c, principal, spec))


@routes.get("/staff/api/v1/live-marking/sessions/{session_id}/visits")
@_checked
async def get_visits(request):
    principal = _staff_principal(request)
    session_id = _id(request.match_info["session_id"])
    return await _run(
        request, lambda c: domain.session_visits(c, principal, session_id)
    )


@routes.post("/staff/api/v1/live-marking/sessions")
@_checked
async def post_session(request):
    principal = _staff_principal(request)
    payload = await _payload(request)
    if set(payload) != {"courseId", "sessionId"}:
        raise domain.LiveMarkingError("invalid")
    _id(payload["courseId"])
    _id(payload["sessionId"])
    response = await _run(
        request,
        lambda c: domain.session_start(
            c, principal, payload["courseId"], payload["sessionId"], _now()
        ),
        write=True,
    )
    await _session_changed(request, principal, json.loads(response.body)["sessionId"])
    return response


@routes.post("/staff/api/v1/live-marking/sessions/{session_id}/finish")
@_checked
async def post_finish(request):
    principal = _staff_principal(request)
    session_id = _id(request.match_info["session_id"])
    response = await _run(
        request,
        lambda c: domain.session_finish(c, principal, session_id, _now()),
        write=True,
    )
    await _session_changed(request, principal, session_id)
    return response


@routes.post("/staff/api/v1/live-marking/visits")
@_checked
async def post_visit(request):
    principal = _staff_principal(request)
    spec = _context(await _payload(request))
    _id(spec.get("lessonId"))
    _id(spec.get("studentId"))
    response = await _run(
        request, lambda c: domain.visit_student(c, principal, spec, _now()), write=True
    )
    await _session_changed(request, principal, spec["contextId"])
    return response


async def _session_changed(request, principal, session_id):
    # Personal session state follows the teacher across devices.
    try:
        from apps.pwa_app import PWA_BROKER, NATS_PWA_INVALIDATE

        await request.app[PWA_BROKER].publish(
            NATS_PWA_INVALIDATE,
            dict(
                resources=[
                    "live-catalog",
                    f"live-board/{session_id}",
                    f"live-visits/{session_id}",
                ],
                reason="live-session-changed",
                audience="staff",
                accountId=principal.account_public_id,
            ),
        )
    except Exception:
        logger.warning("Live session invalidation failed after commit", exc_info=True)


def _now():
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


@routes.post("/staff/api/v1/live-marking/operations")
@_checked
async def post_operation(request):
    principal = _staff_principal(request)
    command = _command(await _payload(request))
    response = await _run(
        request, lambda c: domain.execute(c, principal, command, _now()), write=True
    )
    # HTTP success remains success if transient fan-out fails. The existing WS
    # invalidation protocol carries resource IDs only, never student data.
    try:
        from apps.pwa_app import PWA_BROKER, NATS_PWA_INVALIDATE

        payload = json.loads(response.body)
        if payload["replayed"]:
            return response
        context_id = command["context"]["contextId"]
        lesson_id = payload["state"].get("lessonId") or command["context"].get(
            "lessonId"
        )
        kind = command["kind"]
        resources = [
            f"live-cells/{lesson_id}",
            f"live-history/{context_id}",
            f"live-visits/{context_id}",
        ]
        if kind in ("attendance", "transfer", "reaction", "praise", "undo"):
            resources.extend([f"live-board/{context_id}"])
        if kind in ("transfer", "undo"):
            resources.append("live-directory")
        await request.app[PWA_BROKER].publish(
            NATS_PWA_INVALIDATE,
            dict(resources=resources, reason="live-marking-changed", audience="staff"),
        )
        # All affected student/family reads refetch authoritative projections.
        student_id = payload["state"].get("studentId")
        if student_id:
            accounts = await _factory(request).run_read_async(
                lambda c: db.owner_accounts(c, student_id)
            )
            for owner in accounts:
                await request.app[PWA_BROKER].publish(
                    NATS_PWA_INVALIDATE,
                    dict(
                        resources=[
                            "live-results",
                            "notification-events",
                            "classroom-assignment",
                            "course-enrollments",
                        ],
                        reason="live-marking-changed",
                        audience=owner["audience"],
                        accountId=owner["public_id"],
                    ),
                )
    except Exception:
        logger.warning("Live-marking invalidation failed after commit", exc_info=True)
    return response


@routes.get("/staff/api/v1/live-marking/condition")
@_checked
async def get_condition(request):
    principal = _staff_principal(request)
    query = dict(request.query)
    problem_id = _id(query.pop("problemId", None))
    spec = _context(query)
    _id(spec.get("lessonId"))
    return await _run(
        request, lambda c: domain.condition(c, principal, spec, problem_id)
    )
