"""Family reads for one explicitly linked child's course context.

The authentication middleware has already loaded and revalidated family links
and course enrollments for this request.  These handlers only project that
authority; they do not perform a second database read.  See Phase 9 in
``vmshpwa/dev/development-plan/13-phase-9-family-and-progress.md``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.auth_service import AuthenticatedSession
from apps.pwa_api.course_routes import (
    course_achievements_payload,
    course_analytics_payload,
    course_enrollment_payload,
)
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.family import latest_published_lesson
from db_methods.pwa.course_achievements import list_student_course_achievements
from db_methods.pwa.course_analytics import latest_student_course_metrics
from db_methods.pwa.progress import (
    list_course_pending_review_rows,
    list_course_result_rows,
)
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.family_enrollment import change_family_enrollment
from models.pwa.progress import summarize_course_results


family_course_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")


def _family_session(request: web.Request) -> AuthenticatedSession:
    authenticated = authenticated_session(request)
    if authenticated.principal.audience is not AuthAudience.FAMILY:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для просмотра данных ребёнка",
        )
    return authenticated


def _reject_query(request: web.Request) -> None:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="family_courses_unavailable",
            message="Данные курсов временно недоступны",
        )
    return state.factory


def _linked_child(authenticated: AuthenticatedSession, student_public_id: str):
    child = next(
        (
            candidate
            for candidate in authenticated.family_children
            if candidate.student_public_id == student_public_id
        ),
        None,
    )
    if child is None:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Профиль ребёнка недоступен",
        )
    return child


def _child_payload(child) -> dict[str, object]:
    return {
        "studentId": child.student_public_id,
        "displayName": f"{child.name} {child.surname}",
        "grade": child.grade,
        "birthday": child.birthday,
        "relationshipLabel": child.relationship_label,
        "isPrimary": child.is_primary,
    }


async def _enrollment_change_payload(request: web.Request) -> dict[str, object]:
    try:
        payload = await request.json()
    except (ValueError, TypeError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранную группу и режим",
        ) from error
    if not isinstance(payload, dict) or set(payload) != {
        "activeGroupId",
        "attendanceMode",
        "version",
    }:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранную группу и режим",
        )
    if (
        not isinstance(payload["activeGroupId"], str)
        or _PUBLIC_ID.fullmatch(payload["activeGroupId"]) is None
        or payload["attendanceMode"] not in {"online", "in_person"}
        or not isinstance(payload["version"], int)
        or isinstance(payload["version"], bool)
        or payload["version"] < 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранную группу и режим",
        )
    return payload


@family_course_routes.get("/family/api/v1/children/{student_public_id}/courses")
async def get_family_child_courses(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _family_session(request)
    student_public_id = request.match_info["student_public_id"]
    if _PUBLIC_ID.fullmatch(student_public_id) is None:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Профиль ребёнка недоступен",
        )

    child = _linked_child(authenticated, student_public_id)

    enrollments = [
        course_enrollment_payload(enrollment)
        for enrollment in authenticated.course_enrollments
        if enrollment.student_public_id == student_public_id
    ]
    return web.json_response(
        {
            "student": _child_payload(child),
            "enrollments": enrollments,
        },
        headers={"Cache-Control": "no-store"},
    )


@family_course_routes.patch(
    "/family/api/v1/children/{student_public_id}/courses/{course_public_id}/enrollment"
)
async def update_family_child_enrollment(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _family_session(request)
    student_public_id = request.match_info["student_public_id"]
    if _PUBLIC_ID.fullmatch(student_public_id) is None:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Профиль ребёнка недоступен",
        )
    child = _linked_child(authenticated, student_public_id)
    course_public_id = request.match_info["course_public_id"]
    enrollment = next(
        (
            candidate
            for candidate in authenticated.course_enrollments
            if candidate.student_public_id == student_public_id
            and candidate.course_public_id == course_public_id
        ),
        None,
    )
    if enrollment is None:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Курс ребёнка недоступен",
        )
    payload = await _enrollment_change_payload(request)
    group = next(
        (
            candidate
            for candidate in enrollment.allowed_groups
            if candidate.group_public_id == payload["activeGroupId"]
        ),
        None,
    )
    if group is None:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Группа недоступна ребёнку",
        )
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    def write(connection):
        return change_family_enrollment(
            connection,
            enrollment_id=enrollment.enrollment_id,
            course_id=enrollment.course_id,
            student_user_id=child.student_user_id,
            expected_version=payload["version"],
            previous_group_id=enrollment.active_group_id,
            active_group_id=group.group_id,
            previous_attendance_mode=enrollment.attendance_mode,
            attendance_mode=payload["attendanceMode"],
            request_id=request["request_id"],
            now=now,
        )

    new_version = await _factory(request).run_write_async(write)
    if new_version is None:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Настройки уже изменились. Обновите страницу.",
        )
    response = course_enrollment_payload(enrollment)
    response["activeGroupId"] = group.group_public_id
    response["attendanceMode"] = payload["attendanceMode"]
    response["version"] = new_version
    return web.json_response(response, headers={"Cache-Control": "no-store"})


@family_course_routes.get("/family/api/v1/children/{student_public_id}/home")
async def get_family_child_home(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _family_session(request)
    student_public_id = request.match_info["student_public_id"]
    if _PUBLIC_ID.fullmatch(student_public_id) is None:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Профиль ребёнка недоступен",
        )
    child = _linked_child(authenticated, student_public_id)
    enrollments = [
        enrollment
        for enrollment in authenticated.course_enrollments
        if enrollment.student_public_id == student_public_id
    ]

    def read(connection):
        return [
            (
                latest_published_lesson(
                    connection,
                    course_public_id=enrollment.course_public_id,
                    group_public_id=enrollment.active_group_public_id,
                ),
                summarize_course_results(
                    list_course_result_rows(
                        connection,
                        student_user_id=child.student_user_id,
                        course_id=enrollment.course_id,
                    ),
                    list_course_pending_review_rows(
                        connection,
                        student_user_id=child.student_user_id,
                        course_id=enrollment.course_id,
                    ),
                ),
                latest_student_course_metrics(
                    connection,
                    course_id=enrollment.course_id,
                    student_user_id=child.student_user_id,
                ),
                list_student_course_achievements(
                    connection,
                    course_id=enrollment.course_id,
                    student_user_id=child.student_user_id,
                ),
            )
            for enrollment in enrollments
        ]

    course_reads = await _factory(request).run_read_async(read)
    courses = []
    for enrollment, (lesson, progress, analytics_rows, achievement_rows) in zip(
        enrollments, course_reads, strict=True
    ):
        courses.append(
            {
                "enrollment": course_enrollment_payload(enrollment),
                "progress": {
                    "courseId": enrollment.course_public_id,
                    **progress,
                    "analytics": course_analytics_payload(analytics_rows),
                    "achievements": course_achievements_payload(achievement_rows),
                },
                "currentLesson": (
                    None
                    if lesson is None
                    else {
                        "groupLessonId": lesson["group_lesson_public_id"],
                        "courseLessonId": lesson["course_lesson_public_id"],
                        "lessonNumber": lesson["lesson_number"],
                        "title": lesson["title"],
                        "cycleAnchorDate": lesson["cycle_anchor_date"],
                        "businessTimezone": lesson["business_timezone"],
                        "problemCount": lesson["problem_count"],
                    }
                ),
            }
        )
    return web.json_response(
        {"student": _child_payload(child), "courses": courses},
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["family_course_routes"]
