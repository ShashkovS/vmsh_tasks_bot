"""Read-only Staff weekly dashboard assembled from existing projections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from apps.pwa_api.review_routes import PWA_REVIEW_QUEUE_REPOSITORY
from apps.pwa_api.support_routes import PWA_SUPPORT_REPOSITORY
from db_methods.pwa.reviews import ReviewQueueCase, ReviewStaffScope
from db_methods.pwa.staff_dashboard import (
    classroom_delivery_failures,
    list_group_lesson_rows,
    list_oral_window_rows,
    list_publication_rows,
)
from db_methods.pwa.support import SupportStaffScope, SupportThreadSummaryRecord
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.staff_dashboard import (
    InvalidStaffDashboardData,
    StaffDashboardScope,
    build_staff_dashboard_lessons,
)


staff_dashboard_routes = web.RouteTableDef()
_PAGE_SIZE = 100


def _principal(request: web.Request):
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.has_capability(Capability.STATISTICS_READ)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Рабочая сводка доступна только преподавателям",
        )
    return principal


def _scope(principal) -> StaffDashboardScope:
    return StaffDashboardScope(
        global_access=principal.is_global_admin,
        course_public_ids=frozenset(
            grant.course_public_id
            for grant in principal.staff_scope_grants
            if grant.group_public_id is None
        ),
        group_public_ids=frozenset(
            grant.group_public_id
            for grant in principal.staff_scope_grants
            if grant.group_public_id is not None
        ),
    )


def _review_scope(scope: StaffDashboardScope) -> ReviewStaffScope:
    return ReviewStaffScope(
        global_access=scope.global_access,
        course_public_ids=scope.course_public_ids,
        group_public_ids=scope.group_public_ids,
    )


def _support_scope(scope: StaffDashboardScope) -> SupportStaffScope:
    return SupportStaffScope(
        global_access=scope.global_access,
        course_public_ids=scope.course_public_ids,
        group_public_ids=scope.group_public_ids,
    )


async def _review_cases(
    request: web.Request, scope: StaffDashboardScope
) -> list[ReviewQueueCase]:
    repository = request.app.get(PWA_REVIEW_QUEUE_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="dashboard_unavailable",
            message="Очередь проверки временно недоступна",
        )
    items: list[ReviewQueueCase] = []
    cursor: str | None = None
    while True:
        page = await repository.list_cases(
            scope=_review_scope(scope),
            cursor=cursor,
            page_size=_PAGE_SIZE,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


async def _support_threads(
    request: web.Request, scope: StaffDashboardScope
) -> list[SupportThreadSummaryRecord]:
    repository = request.app.get(PWA_SUPPORT_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="dashboard_unavailable",
            message="Вопросы временно недоступны",
        )
    items: list[SupportThreadSummaryRecord] = []
    cursor: str | None = None
    while True:
        page = await repository.list_staff_threads(
            scope=_support_scope(scope),
            state="awaiting_staff",
            cursor=cursor,
            page_size=_PAGE_SIZE,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


def _database_factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="dashboard_unavailable",
            message="Рабочая сводка временно недоступна",
        )
    return state.factory


def _iso(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


@staff_dashboard_routes.get("/staff/api/v1/dashboard")
async def get_staff_dashboard(request: web.Request) -> web.Response:
    principal = _principal(request)
    if (
        any(key != "view" for key in request.query)
        or len(request.query.getall("view", [])) > 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Параметры рабочей сводки некорректны",
        )
    view = request.query.get("view", "current")
    if view not in {"current", "all"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Параметры рабочей сводки некорректны",
        )
    selection = "all" if view == "all" else "current"
    scope = _scope(principal)
    now = datetime.now(UTC)

    raw = await _database_factory(request).run_read_async(
        lambda connection: {
            "lessons": list_group_lesson_rows(connection),
            "publications": list_publication_rows(connection),
            "oral": list_oral_window_rows(connection),
            "delivery": (
                classroom_delivery_failures(connection)
                if principal.is_global_admin
                else None
            ),
        }
    )
    try:
        lessons = build_staff_dashboard_lessons(
            raw["lessons"],
            raw["publications"],
            raw["oral"],
            scope=scope,
            now=now,
            selection=selection,
        )
    except InvalidStaffDashboardData as error:
        raise PwaApiError(
            status=503,
            code="dashboard_data_invalid",
            message="Проверьте расписание текущих занятий",
        ) from error

    reviews = await _review_cases(request, scope)
    questions = await _support_threads(request, scope)
    old_question_cutoff = now - timedelta(hours=1)
    summary = {
        "review": {
            "totalCases": len(reviews),
            "claimedByOthers": sum(
                item.lock is not None
                and item.lock.teacher_user_id != principal.linked_user_id
                for item in reviews
            ),
        },
        "questions": {
            "awaitingStaff": len(questions),
            "olderThanOneHour": sum(
                item.latest_entry_at <= old_question_cutoff for item in questions
            ),
        },
        "publications": {
            "conditionsPublished": sum(
                item["publications"]["condition"]["state"] == "published"
                for item in lessons
            ),
            "groupLessons": len(lessons),
        },
        "oral": {
            "openWindows": sum(item["oral"]["openWindows"] for item in lessons),
            "upcomingWindows": sum(item["oral"]["upcomingWindows"] for item in lessons),
        },
        "delivery": (
            None
            if raw["delivery"] is None
            else {
                "failedBatches": raw["delivery"]["failed_batches"],
                "failedRecipients": raw["delivery"]["failed_recipients"],
            }
        ),
    }
    return web.json_response(
        {
            "schemaVersion": 1,
            "generatedAt": _iso(now),
            "summary": summary,
            "lessons": lessons,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["staff_dashboard_routes"]
