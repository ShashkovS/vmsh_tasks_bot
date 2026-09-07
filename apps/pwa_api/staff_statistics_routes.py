"""Scoped Staff course statistics over the latest completed analytics run."""

from __future__ import annotations

import re
import sqlite3

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.course_analytics import (
    find_latest_completed_course_run,
    list_course_run_metrics,
)
from db_methods.pwa.course_catalog import find_season, list_courses, list_groups
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import AuthorizationPrincipal, Capability
from models.pwa.auth import AuthAudience
from models.pwa.staff_statistics import summarize_staff_course_metrics
from db_methods.pwa.lesson_statistics import course_facts
from db_methods.pwa.iterative_analytics import read_state
from models.pwa.lesson_statistics import summarize_lessons


staff_statistics_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_QUERY_KEYS = {"courseId", "groupId", "lessonNumber", "studentId"}


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

    def read_run(connection: sqlite3.Connection):
        connection.execute("BEGIN")
        try:
            return read_snapshot(connection)
        finally:
            connection.execute("ROLLBACK")

    def read_snapshot(connection: sqlite3.Connection):
        run = find_latest_completed_course_run(
            connection, course_id=int(selected_course["id"])
        )
        rows = (
            []
            if run is None
            else list_course_run_metrics(connection, run_id=int(run["id"]))
        )
        facts = course_facts(connection, int(selected_course["id"]))
        difficulty, _ = read_state(connection, int(selected_course["id"]))
        return run, rows, facts, difficulty

    run, metric_rows, facts, difficulty = await _factory(request).run_read_async(
        read_run
    )
    allowed_group_ids = (
        frozenset({requested_group_id})
        if requested_group_id is not None
        else accessible_group_ids
    )
    lessons = summarize_staff_course_metrics(
        metric_rows, allowed_group_public_ids=allowed_group_ids
    )
    basic = summarize_lessons(*facts, allowed_group_ids)
    numbers = [item["lessonNumber"] for item in basic]
    selected_number = (
        requested_lesson if requested_lesson in numbers else max(numbers, default=None)
    )
    basic_lesson = next(
        (item for item in basic if item["lessonNumber"] == selected_number), None
    )
    by_public = {p["public_id"]: p for p in facts[0]}
    if basic_lesson:
        for group in basic_lesson["groups"]:
            for problem in group["problems"]:
                values = difficulty.get(
                    by_public[problem["problemId"]]["logical_problem_key"]
                )
                problem["difficultyWeak"] = values[0] if values else None
                problem["difficultyStrong"] = values[1] if values else None
    allowed_problems = {
        p["problem_id"] for p in facts[0] if p["group_public_id"] in allowed_group_ids
    }
    students = {
        r["student_public_id"]: {
            "studentId": r["student_public_id"],
            "name": r["student_name"],
            "id": r["student_user_id"],
        }
        for r in facts[1]
        if r["problem_id"] in allowed_problems
    }
    if requested_student_id is not None and requested_student_id not in students:
        raise PwaApiError(
            status=403, code="forbidden", message="Нет доступа к статистике школьника"
        )
    selected_student = students.get(requested_student_id)
    personal = (
        []
        if selected_student is None
        else [
            {
                "lessonNumber": r["lesson_number"],
                "groupCode": r["group_code"],
                "simple": r["simple_strength"],
                "complex": r["complex_strength"],
                "difficulty": r["max_complex_strength"],
                "simpleSmooth": r["simple_smooth"],
                "complexSmooth": r["complex_smooth"],
                "solved": r["solved_items"],
                "total": r["total_items"],
            }
            for r in metric_rows
            if r["student_user_id"] == selected_student["id"]
            and r["group_public_id"] in allowed_group_ids
        ]
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


__all__ = ["staff_statistics_routes"]
