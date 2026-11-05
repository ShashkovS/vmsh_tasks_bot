"""Scoped Staff course statistics over the latest completed analytics run."""

from __future__ import annotations

import re
import sqlite3

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.course_catalog import find_season, list_courses, list_groups
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import AuthorizationPrincipal, Capability
from models.pwa.auth import AuthAudience
from apps.pwa_api.statistics_cache import (
    PWA_STATISTICS_CACHE,
    main_snapshot,
    report_snapshot,
)


staff_statistics_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_QUERY_KEYS = {"courseId", "groupId", "lessonNumber", "studentId", "refresh"}


def _refresh(request):
    value = request.query.get("refresh")
    if value not in (None, "1"):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный параметр статистики",
        )
    return value == "1"


async def _snapshot(request, key, operation):
    async def load():
        return await _factory(request).run_analytics_async(operation)

    cache = request.app.get(PWA_STATISTICS_CACHE)
    return (
        await load()
        if cache is None
        else await cache.get(key, load, force_refresh=_refresh(request))
    )


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="statistics_unavailable",
            message="Статистика временно недоступна",
        )
    return state.factory


def _principal(request: web.Request) -> AuthorizationPrincipal:
    principal = authenticated_session(request).principal
    if principal.audience is not AuthAudience.STAFF or not principal.has_capability(
        Capability.STATISTICS_READ
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для просмотра статистики",
        )
    return principal


def _query_id(request: web.Request, name: str) -> str | None:
    value = request.query.get(name)
    if value is None:
        return None
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранный курс и группу",
        )
    return value


def _catalog(
    connection: sqlite3.Connection,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    season = find_season(connection, public_id=None)
    if season is None:
        return [], []
    courses = list_courses(connection, season_id=int(season["id"]))
    groups = list_groups(
        connection, course_ids=tuple(int(course["id"]) for course in courses)
    )
    return courses, groups


def _course_payload(
    course: dict[str, object], groups: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "courseId": course["public_id"],
        "code": course["code"],
        "name": course["name"],
        "subjectCode": course["subject_code"],
        "status": course["status"],
        "groups": [
            {
                "groupId": group["public_id"],
                "code": group["short_code"],
                "name": group["public_name"],
                "colorKey": group["color_key"] or "neutral",
                "status": group["status"],
            }
            for group in groups
            if int(group["course_id"]) == int(course["id"])
        ],
    }


@staff_statistics_routes.get("/staff/api/v1/statistics")
async def get_staff_statistics(request: web.Request) -> web.Response:
    principal = _principal(request)
    _refresh(request)
    if set(request.query) - _QUERY_KEYS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный параметр статистики",
        )
    requested_course_id = _query_id(request, "courseId")
    requested_group_id = _query_id(request, "groupId")
    requested_student_id = _query_id(request, "studentId")
    try:
        requested_lesson = (
            int(request.query["lessonNumber"])
            if "lessonNumber" in request.query
            else None
        )
        if requested_lesson is not None and requested_lesson < 0:
            raise ValueError
    except ValueError:
        raise PwaApiError(
            status=422, code="validation_error", message="Неверный номер занятия"
        )

    courses, groups = await _factory(request).run_read_async(_catalog)
    accessible_courses = [
        course
        for course in courses
        if principal.has_staff_course_access(str(course["public_id"]))
    ]
    if requested_course_id is None:
        selected_course = accessible_courses[0] if accessible_courses else None
    else:
        selected_course = next(
            (
                course
                for course in accessible_courses
                if course["public_id"] == requested_course_id
            ),
            None,
        )
        if selected_course is None:
            raise PwaApiError(
                status=403,
                code="forbidden",
                message="Нет доступа к статистике этого курса",
            )

    accessible_catalog = []
    for course in accessible_courses:
        course_groups = [
            group
            for group in groups
            if int(group["course_id"]) == int(course["id"])
            and principal.has_staff_group_access(
                course_public_id=str(course["public_id"]),
                group_public_id=str(group["public_id"]),
            )
        ]
        accessible_catalog.append(_course_payload(course, course_groups))

    if selected_course is None:
        return web.json_response(
            {
                "schemaVersion": 1,
                "courses": accessible_catalog,
                "selectedCourseId": None,
                "selectedGroupId": None,
                "run": None,
                "lessons": [],
                "requestId": request["request_id"],
            },
            headers={"Cache-Control": "no-store"},
        )

    course_id = str(selected_course["public_id"])
    selected_groups = [
        group
        for group in groups
        if int(group["course_id"]) == int(selected_course["id"])
        and principal.has_staff_group_access(
            course_public_id=course_id,
            group_public_id=str(group["public_id"]),
        )
    ]
    accessible_group_ids = frozenset(
        str(group["public_id"]) for group in selected_groups
    )
    if (
        requested_group_id is not None
        and requested_group_id not in accessible_group_ids
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Нет доступа к статистике этой группы",
        )

    allowed_group_ids = (
        frozenset({requested_group_id})
        if requested_group_id is not None
        else accessible_group_ids
    )
    snapshot = await _snapshot(
        request,
        ("main", course_id, tuple(sorted(allowed_group_ids))),
        lambda connection: main_snapshot(
            connection, int(selected_course["id"]), allowed_group_ids
        ),
    )
    run, lessons, basic = snapshot["run"], snapshot["lessons"], snapshot["basic"]
    numbers = [item["lessonNumber"] for item in basic]
    selected_number = (
        requested_lesson if requested_lesson in numbers else max(numbers, default=None)
    )
    basic_lesson = next(
        (item for item in basic if item["lessonNumber"] == selected_number), None
    )
    students = snapshot["students"]
    if requested_student_id is not None and requested_student_id not in students:
        raise PwaApiError(
            status=403, code="forbidden", message="Нет доступа к статистике школьника"
        )
    selected_student = students.get(requested_student_id)
    personal = (
        []
        if selected_student is None
        else snapshot["personal"].get(selected_student["id"], [])
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "courses": accessible_catalog,
            "selectedCourseId": course_id,
            "selectedGroupId": requested_group_id,
            "run": None
            if run is None
            else {
                "runId": run["public_id"],
                "algorithm": run["algorithm"],
                "algorithmVersion": run["algorithm_version"],
                "inputThroughResultId": run["input_through_result_id"],
                "completedAt": run["completed_at"],
            },
            "lessons": lessons,
            "lessonNumbers": numbers,
            "basicLesson": basic_lesson,
            "students": [
                {"studentId": s["studentId"], "name": s["name"]}
                for s in sorted(
                    students.values(), key=lambda s: (s["name"], s["studentId"])
                )
            ],
            "personal": personal,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@staff_statistics_routes.get("/staff/api/v1/statistics/summary")
@staff_statistics_routes.get("/staff/api/v1/statistics/plus-table")
async def get_staff_statistics_report(request: web.Request) -> web.Response:
    """Live reports, independently of analytics runs; docs/lesson-statistics.md."""
    principal = _principal(request)
    _refresh(request)
    matrix = request.path.endswith("/plus-table")
    keys = (
        {"courseId", "groupId", "lessonNumber", "refresh"}
        if matrix
        else {"courseId", "groupId", "refresh"}
    )
    if set(request.query) - keys:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный параметр статистики",
        )
    course_id = _query_id(request, "courseId")
    group_id = _query_id(request, "groupId")
    try:
        number = (
            int(request.query["lessonNumber"])
            if "lessonNumber" in request.query
            else None
        )
        if number is not None and number < 0:
            raise ValueError
    except ValueError:
        raise PwaApiError(
            status=422, code="validation_error", message="Неверный номер занятия"
        )

    courses, groups = await _factory(request).run_read_async(_catalog)
    courses = [
        c for c in courses if principal.has_staff_course_access(str(c["public_id"]))
    ]
    groups = [
        g
        for g in groups
        if any(
            c["id"] == g["course_id"]
            and principal.has_staff_group_access(
                course_public_id=str(c["public_id"]),
                group_public_id=str(g["public_id"]),
            )
            for c in courses
        )
    ]
    selected = (
        next((c for c in courses if c["public_id"] == course_id), None)
        if course_id
        else next(iter(courses), None)
    )
    if course_id and selected is None:
        raise PwaApiError(
            status=403, code="forbidden", message="Нет доступа к статистике этого курса"
        )
    selected_groups = [
        g for g in groups if selected and g["course_id"] == selected["id"]
    ]
    if group_id and not any(g["public_id"] == group_id for g in selected_groups):
        raise PwaApiError(
            status=403, code="forbidden", message="Нет доступа к статистике этой группы"
        )
    selected_group = group_id or (
        str(selected_groups[0]["public_id"]) if matrix and selected_groups else None
    )
    allowed = frozenset(
        str(g["public_id"])
        for g in selected_groups
        if selected_group is None or g["public_id"] == selected_group
    )
    report = dict(lessons=[], lessonNumbers=[], lessonNumber=None, problems=[], rows=[])
    if selected:
        report = await _snapshot(
            request,
            (
                "plus-table" if matrix else "summary",
                str(selected["public_id"]),
                tuple(sorted(allowed)),
                number,
            ),
            lambda connection: report_snapshot(
                connection, int(selected["id"]), allowed, number, matrix=matrix
            ),
        )
    payload = dict(
        schemaVersion=1,
        courses=[_course_payload(c, groups) for c in courses],
        selectedCourseId=selected["public_id"] if selected else None,
        selectedGroupId=selected_group,
        requestId=request["request_id"],
    )
    if matrix:
        payload.update(
            {
                key: report[key]
                for key in ("lessonNumbers", "lessonNumber", "problems", "rows")
            }
        )
    else:
        payload["lessons"] = report["lessons"]
    return web.json_response(payload, headers={"Cache-Control": "no-store"})


__all__ = ["staff_statistics_routes"]
