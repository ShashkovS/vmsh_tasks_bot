"""Admin-only manual analytics operations; vmshpwa/docs/lesson-statistics.md."""

import asyncio
import re

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from apps.pwa_api.staff_statistics_routes import _factory
from models.pwa.auth import AuthAudience
from models.pwa.statistics_recalculation import (
    StatisticsRecalculation,
    RecalculationConflict,
)

statistics_recalculation_routes = web.RouteTableDef()
SERVICE = web.AppKey("statistics_recalculation", dict)
ID = re.compile(r"^[a-zA-Z0-9._:-]{1,128}$")


async def close_statistics_recalculation(app):
    service = app.get(SERVICE, {}).get("service")
    if service is not None:
        await asyncio.to_thread(service.close)


def service(request):
    holder = request.app[SERVICE]
    if "service" not in holder:
        holder["service"] = StatisticsRecalculation(_factory(request).database_path)
    return holder["service"]


def admin(request):
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or not principal.is_global_admin
        or principal.linked_user_id is None
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Пересчёт доступен только администратору",
        )
    return principal


async def course(request, value, principal):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise PwaApiError(status=422, code="validation_error", message="Выберите курс")
    if not principal.has_staff_course_access(value):
        raise PwaApiError(status=403, code="forbidden", message="Нет доступа к курсу")
    row = await _factory(request).run_read_async(
        lambda c: c.execute(
            "SELECT id FROM courses WHERE public_id=?",
            (value,),
        ).fetchone()
    )
    if row is None:
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    return int(row["id"])


@statistics_recalculation_routes.get("/staff/api/v1/statistics/recalculate")
async def get_recalculation(request):
    principal = admin(request)
    course_id = await course(request, request.query.get("courseId"), principal)
    result = await asyncio.to_thread(service(request).status, course_id)
    return web.json_response(result, headers={"Cache-Control": "no-store"})


@statistics_recalculation_routes.post("/staff/api/v1/statistics/recalculate")
async def start_recalculation(request):
    principal = admin(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    if (
        not isinstance(body, dict)
        or set(body) != {"courseId", "idempotencyKey"}
        or not isinstance(body.get("idempotencyKey"), str)
        or not ID.fullmatch(body["idempotencyKey"])
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректный запрос пересчёта"
        )
    course_id = await course(request, body["courseId"], principal)
    try:
        result = await asyncio.to_thread(
            service(request).start,
            course_id,
            principal.linked_user_id,
            body["idempotencyKey"],
        )
    except RecalculationConflict:
        raise PwaApiError(
            status=409,
            code="idempotency_conflict",
            message="Ключ запроса уже использован для другого курса",
        )
    return web.json_response(
        result,
        status=202 if result["busy"] else 200,
        headers={"Cache-Control": "no-store"},
    )
