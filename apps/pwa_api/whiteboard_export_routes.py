"""Staff-only public-safe worksheet export; docs/whiteboard-export.md."""

import logging
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.content_routes import _apply_figure_scales, read_local_content_asset
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa import whiteboard_export as db
from db_methods.pwa.lesson_statistics import course_facts
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.lesson_statistics import summarize_lessons

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def access(request):
    principal = authenticated_session(request).principal
    if principal.audience is not AuthAudience.STAFF or not principal.has_capability(
        Capability.COURSE_READ
    ):
        raise PwaApiError(
            status=403, code="forbidden", message="Нет доступа к материалам для разбора"
        )
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503, code="unavailable", message="Материалы временно недоступны"
        )
    return principal, state.factory


def allowed(principal, sheet):
    return principal.has_staff_group_access(
        course_public_id=sheet["courseId"], group_public_id=sheet["groupId"]
    )


@routes.get("/staff/api/v1/whiteboard-export")
async def catalog(request):
    principal, factory = access(request)
    sheets = await factory.run_read_async(db.published_sheets)
    return web.json_response(
        {"sheets": [db.sheet_metadata(s) for s in sheets if allowed(principal, s)]},
        headers={"Cache-Control": "no-store"},
    )


@routes.get("/staff/api/v1/whiteboard-export/{group_lesson:gl-[0-9]+}")
async def worksheet(request):
    principal, factory = access(request)
    if set(request.query) - {"statistics"} or request.query.get(
        "statistics", "1"
    ) not in ("0", "1"):
        raise PwaApiError(
            status=422, code="validation_error", message="Неверные параметры экспорта"
        )

    def read(connection):
        connection.execute("BEGIN")
        try:
            sheet = next(
                (
                    s
                    for s in db.published_sheets(connection)
                    if s["groupLessonId"] == request.match_info["group_lesson"]
                ),
                None,
            )
            if sheet is None:
                raise PwaApiError(
                    status=404,
                    code="not_found",
                    message="Опубликованные условия не найдены",
                )
            if not allowed(principal, sheet):
                raise PwaApiError(
                    status=403, code="forbidden", message="Нет доступа к этому уровню"
                )
            document, scales = db.sheet_document(connection, sheet)
            _apply_figure_scales(document, scales)
            for asset in db.document_assets(document):
                asset_id = asset["assetId"]
                asset["src"] = (
                    f"/staff/api/v1/whiteboard-export/{sheet['groupLessonId']}/assets/{asset_id}"
                )
            statistics = None
            statistics_error = False
            if request.query.get("statistics", "1") == "1":
                try:
                    lessons = summarize_lessons(
                        *course_facts(connection, sheet["course_id"]),
                        {sheet["groupId"]},
                    )
                    lesson = next(
                        (
                            entry
                            for entry in lessons
                            if entry["lessonNumber"] == sheet["lessonNumber"]
                        ),
                        None,
                    )
                    group = (
                        next(
                            (
                                g
                                for g in lesson["groups"]
                                if g["groupId"] == sheet["groupId"]
                            ),
                            None,
                        )
                        if lesson
                        else None
                    )
                    statistics = {
                        "participantCount": group["participantCount"] if group else 0,
                        "problems": group["problems"] if group else [],
                        "generatedAt": datetime.now(UTC).isoformat(),
                    }
                except Exception:
                    logger.exception(
                        "Whiteboard statistics unavailable for %s",
                        sheet["groupLessonId"],
                    )
                    statistics_error = True
            return {
                "sheet": db.sheet_metadata(sheet),
                "document": document,
                "statistics": statistics,
                "statisticsError": statistics_error,
            }
        finally:
            connection.execute("ROLLBACK")

    result = await factory.run_read_async(read)
    return web.json_response(result, headers={"Cache-Control": "no-store"})


@routes.get(
    "/staff/api/v1/whiteboard-export/{group_lesson:gl-[0-9]+}/assets/{asset_id:ma-[0-9]+}"
)
async def image(request):
    principal, factory = access(request)

    def check(connection):
        sheet = next(
            (
                s
                for s in db.published_sheets(connection)
                if s["groupLessonId"] == request.match_info["group_lesson"]
            ),
            None,
        )
        if sheet is None:
            raise PwaApiError(
                status=404,
                code="not_found",
                message="Опубликованные условия не найдены",
            )
        if not allowed(principal, sheet):
            raise PwaApiError(
                status=403, code="forbidden", message="Нет доступа к этому уровню"
            )
        document, _ = db.sheet_document(connection, sheet)
        if not any(
            asset["assetId"] == request.match_info["asset_id"]
            for asset in db.document_assets(document)
        ):
            raise PwaApiError(status=404, code="not_found", message="Рисунок не найден")

    await factory.run_read_async(check)
    response = await read_local_content_asset(request)
    response.headers["Cache-Control"] = "private, no-store"
    return response
