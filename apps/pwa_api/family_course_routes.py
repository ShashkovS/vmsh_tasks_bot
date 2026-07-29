"""Family reads for one explicitly linked child's course context.

The authentication middleware has already loaded and revalidated family links
and course enrollments for this request.  These handlers only project that
authority; they do not perform a second database read.  See Phase 9 in
``vmshpwa/dev/development-plan/13-phase-9-family-and-progress.md``.
"""

from __future__ import annotations

import re

from aiohttp import web

from apps.pwa_api.auth_service import AuthenticatedSession
from apps.pwa_api.course_routes import course_enrollment_payload
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from models.pwa.auth import AuthAudience


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

    child = next(
        (
            candidate
            for candidate in authenticated.family_children
            if candidate.student_public_id == student_public_id
        ),
        None,
    )
    if child is None:
        # Do not disclose whether an unlinked student exists.
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Профиль ребёнка недоступен",
        )

    enrollments = [
        course_enrollment_payload(enrollment)
        for enrollment in authenticated.course_enrollments
        if enrollment.student_public_id == student_public_id
    ]
    return web.json_response(
        {
            "student": {
                "studentId": child.student_public_id,
                "displayName": f"{child.name} {child.surname}",
                "grade": child.grade,
                "birthday": child.birthday,
                "relationshipLabel": child.relationship_label,
                "isPrimary": child.is_primary,
            },
            "enrollments": enrollments,
        },
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["family_course_routes"]
