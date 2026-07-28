"""Authenticated Student course/access reads for Phase 3.

The authentication middleware already rebuilds course enrollment authority from
SQLite for every request.  These routes project that same checked state instead
of issuing a second repository query or trusting URL context.  Governing
contract: ``vmshpwa/dev/development-plan/07-phase-3-student-reading.md``.
"""

from __future__ import annotations

import re

from aiohttp import web

from apps.pwa_api.auth_service import AuthenticatedSession
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.auth import CourseEnrollmentRecord, CourseGroupAccessRecord
from models.pwa.auth import AuthAudience


course_routes = web.RouteTableDef()
_CANONICAL_TOKEN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


def _student_session(request: web.Request) -> AuthenticatedSession:
    authenticated = authenticated_session(request)
    principal = authenticated.principal
    if principal.audience is not AuthAudience.STUDENT:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для просмотра курсов",
        )
    if (
        principal.linked_user_id is None
        or authenticated.current.linked_user_public_id is None
    ):  # pragma: no cover - authentication service invariant
        raise RuntimeError("Student principal has no linked identity")
    return authenticated


def _reject_query(request: web.Request) -> None:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )


def _token(value: str | None, *, fallback: str) -> str:
    resolved = value if value is not None else fallback
    if _CANONICAL_TOKEN.fullmatch(resolved) is None:
        raise RuntimeError("Stored course presentation token is invalid")
    return resolved


def _group_payload(group: CourseGroupAccessRecord) -> dict[str, object]:
    return {
        "groupId": group.group_public_id,
        "courseId": group.course_public_id,
        "code": group.short_code,
        "name": group.public_name,
        "status": group.status,
        "sortOrder": group.sort_order,
        "colorKey": _token(group.color_key, fallback="neutral"),
        "version": group.version,
    }


def course_enrollment_payload(record: CourseEnrollmentRecord) -> dict[str, object]:
    """Project the repository record onto the shared Zod course contract."""

    return {
        "enrollmentId": record.enrollment_public_id,
        "studentId": record.student_public_id,
        "course": {
            "courseId": record.course_public_id,
            "code": record.course_code,
            "name": record.course_name,
            "subjectCode": record.course_subject_code,
            "status": record.course_status,
            "sortOrder": record.course_sort_order,
            "accentKey": _token(record.course_accent_key, fallback="neutral"),
            "version": record.course_version,
        },
        "activeGroupId": record.active_group_public_id,
        "allowedGroups": [_group_payload(group) for group in record.allowed_groups],
        "attendanceMode": record.attendance_mode,
        "status": record.enrollment_status,
        "version": record.enrollment_version,
    }


@course_routes.get("/student/api/v1/courses")
async def list_student_courses(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _student_session(request)
    student_public_id = authenticated.current.linked_user_public_id
    assert student_public_id is not None
    enrollments = tuple(authenticated.course_enrollments)
    if any(record.student_public_id != student_public_id for record in enrollments):
        raise RuntimeError("Course enrollment belongs to another student")
    return web.json_response(
        {
            "studentId": student_public_id,
            "enrollments": [
                course_enrollment_payload(record) for record in enrollments
            ],
        }
    )


@course_routes.get("/student/api/v1/courses/{course_id}/enrollment")
async def get_student_course_enrollment(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _student_session(request)
    course_public_id = request.match_info["course_id"]
    matches = [
        record
        for record in authenticated.course_enrollments
        if record.course_public_id == course_public_id
    ]
    if len(matches) != 1:
        # Do not disclose whether an ungranted course exists.
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Курс недоступен этому школьнику",
        )
    return web.json_response(course_enrollment_payload(matches[0]))


__all__ = ["course_enrollment_payload", "course_routes"]
