"""Authenticated Student course/access reads for Phase 3.

The authentication middleware already rebuilds course enrollment authority from
SQLite for every request.  These routes project that same checked state instead
of issuing a second repository query or trusting URL context.  Governing
contract: ``vmshpwa/dev/development-plan/07-phase-3-student-reading.md``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.auth_service import AuthenticatedSession
from apps.pwa_api.content_routes import PWA_CONTENT_REPOSITORY
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.auth import CourseEnrollmentRecord, CourseGroupAccessRecord
from db_methods.pwa.course_analytics import latest_student_course_metrics
from db_methods.pwa.content import (
    ContentNotFound,
    ContentRepositoryError,
    StudentProblemListRecord,
    StudentProblemSummaryRecord,
    StudentLessonMaterialRecord,
    StudentLessonSummaryRecord,
)
from db_methods.pwa.progress import (
    list_course_pending_review_rows,
    list_course_result_rows,
)
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.progress import summarize_course_results


course_routes = web.RouteTableDef()
_CANONICAL_TOKEN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_LESSON_CURSOR = re.compile(r"^[1-9][0-9]{0,8}$")
_LESSON_PAGE_SIZE = 50


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


def _course_enrollment(
    authenticated: AuthenticatedSession, course_public_id: str
) -> CourseEnrollmentRecord:
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
    return matches[0]


def _allowed_group(
    enrollment: CourseEnrollmentRecord, group_public_id: str
) -> CourseGroupAccessRecord:
    matches = [
        group
        for group in enrollment.allowed_groups
        if group.group_public_id == group_public_id
    ]
    if len(matches) != 1:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Группа недоступна этому школьнику",
        )
    return matches[0]


def _repository(request: web.Request):
    repository = request.app.get(PWA_CONTENT_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="service_unavailable",
            message="Материалы занятий временно недоступны",
        )
    return repository


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContentRepositoryError("stored lesson timestamp is naive")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def course_analytics_payload(rows: list[dict[str, object]]) -> dict[str, object] | None:
    if not rows:
        return None
    first = rows[0]
    return {
        "runId": first["run_public_id"],
        "algorithmVersion": first["algorithm_version"],
        "calculatedAt": first["completed_at"],
        "lessons": [
            {
                "lessonNumber": row["lesson_number"],
                "groupId": row["group_public_id"],
                "groupCode": row["group_short_code"],
                "simpleStrength": row["simple_strength"],
                "complexStrength": row["complex_strength"],
                "maxComplexStrength": row["max_complex_strength"],
                "solvedItems": row["solved_items"],
                "totalItems": row["total_items"],
            }
            for row in rows
        ],
    }


def _material_payload(
    material: StudentLessonMaterialRecord | None,
) -> dict[str, object]:
    if material is None:
        return {"status": "unavailable"}
    return {
        "status": "published",
        "revisionId": material.revision_public_id,
        "publishedAt": _iso(material.published_at),
        "publicationVersion": material.publication_version,
    }


def _student_lesson_payload(
    lesson: StudentLessonSummaryRecord,
) -> dict[str, object]:
    window = lesson.window
    return {
        "groupLessonId": lesson.group_lesson_public_id,
        "courseLessonId": lesson.course_lesson_public_id,
        "courseId": lesson.course_public_id,
        "groupId": lesson.group_public_id,
        "lessonNumber": lesson.lesson_number,
        "title": lesson.title,
        "cycleAnchorDate": lesson.cycle_anchor_date.isoformat(),
        "businessTimezone": lesson.business_timezone,
        "version": lesson.version,
        "problemCount": lesson.problem_count,
        "window": (
            None
            if window is None
            else {
                "windowId": window.public_id,
                "opensAt": _iso(window.opens_at),
                "submissionClosesAt": _iso(window.submission_closes_at),
                "hintScheduledAt": _iso(window.hint_scheduled_at),
                "solutionScheduledAt": _iso(window.solution_scheduled_at),
                "timezone": window.timezone,
                "source": window.source,
                "version": window.version,
            }
        ),
        "materials": {
            "condition": _material_payload(lesson.condition),
            "hint": _material_payload(lesson.hint),
            "solution": _material_payload(lesson.solution),
        },
    }


def _student_problem_payload(
    problem: StudentProblemSummaryRecord,
) -> dict[str, object]:
    problem_type = {
        1: "test",
        2: "written",
        3: "oral",
        # WRITTEN_BEFORE_ORALLY is a storage/checking distinction. Student
        # always sees an oral task; see design-system/04-product-components.md.
        4: "oral",
    }.get(problem.problem_type)
    if problem_type is None:  # pragma: no cover - repository invariant
        raise ContentRepositoryError("published problem type is invalid")
    verdict = problem.verdict
    return {
        "problemId": problem.problem_public_id,
        "configVersion": problem.config_version,
        "sourceOrdinal": problem.source_ordinal,
        "displayNumber": problem.display_number,
        "title": problem.title,
        "type": problem_type,
        "answerType": problem.answer_type,
        "materials": {
            "hint": {"status": problem.hint_state},
            "solution": {"status": problem.solution_state},
        },
        "status": problem.status,
        "verdict": (
            None
            if verdict is None
            else {
                "verdictId": verdict.verdict_id,
                "symbol": verdict.symbol,
                "weight": verdict.weight,
            }
        ),
    }


def _student_problem_list_payload(
    record: StudentProblemListRecord,
) -> dict[str, object]:
    return {
        "courseId": record.course_public_id,
        "groupId": record.group_public_id,
        "groupLessonId": record.group_lesson_public_id,
        "conditionRevisionId": record.condition_revision_public_id,
        "problems": [_student_problem_payload(problem) for problem in record.problems],
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
    enrollment = _course_enrollment(authenticated, request.match_info["course_id"])
    return web.json_response(course_enrollment_payload(enrollment))


@course_routes.get("/student/api/v1/courses/{course_id}/progress")
async def get_student_course_progress(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _student_session(request)
    enrollment = _course_enrollment(authenticated, request.match_info["course_id"])
    student_user_id = authenticated.principal.linked_user_id
    assert student_user_id is not None
    database = request.app.get(PWA_DATABASE)
    if database is None or database.factory is None:
        raise PwaApiError(
            status=503,
            code="progress_unavailable",
            message="Прогресс временно недоступен",
        )

    def read(connection):
        return (
            list_course_result_rows(
                connection,
                student_user_id=student_user_id,
                course_id=enrollment.course_id,
            ),
            list_course_pending_review_rows(
                connection,
                student_user_id=student_user_id,
                course_id=enrollment.course_id,
            ),
            latest_student_course_metrics(
                connection,
                course_id=enrollment.course_id,
                student_user_id=student_user_id,
            ),
        )

    rows, pending_review_rows, analytics_rows = await database.factory.run_read_async(
        read
    )
    return web.json_response(
        {
            "courseId": enrollment.course_public_id,
            **summarize_course_results(rows, pending_review_rows),
            "analytics": course_analytics_payload(analytics_rows),
        }
    )


@course_routes.get("/student/api/v1/home")
async def get_student_home(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _student_session(request)
    enrollments = tuple(authenticated.course_enrollments)
    snapshot = await _repository(request).get_student_home_snapshot(
        scopes=tuple(
            (enrollment.course_public_id, enrollment.active_group_public_id)
            for enrollment in enrollments
        )
    )
    lessons_by_scope = {
        (record.lesson.course_public_id, record.lesson.group_public_id): record
        for record in snapshot.lessons
    }
    if len(lessons_by_scope) != len(snapshot.lessons):
        raise ContentRepositoryError("student home returned duplicate lesson scopes")
    courses: list[dict[str, object]] = []
    for enrollment in enrollments:
        key = (enrollment.course_public_id, enrollment.active_group_public_id)
        current = lessons_by_scope.pop(key, None)
        courses.append(
            {
                "enrollment": course_enrollment_payload(enrollment),
                "phase": "no_lesson" if current is None else current.phase,
                "currentLesson": (
                    None if current is None else _student_lesson_payload(current.lesson)
                ),
            }
        )
    if lessons_by_scope:
        raise ContentRepositoryError("student home returned an unauthorized scope")
    student_public_id = authenticated.current.linked_user_public_id
    assert student_public_id is not None
    return web.json_response(
        {
            "studentId": student_public_id,
            "generatedAt": _iso(snapshot.generated_at),
            "courses": courses,
        }
    )


@course_routes.get("/student/api/v1/courses/{course_id}/lessons")
async def list_student_lessons(request: web.Request) -> web.Response:
    unexpected = set(request.query) - {"group", "cursor"}
    duplicate = any(
        len(request.query.getall(field, [])) > 1 for field in ("group", "cursor")
    )
    if unexpected or duplicate:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Параметры списка занятий некорректны",
        )
    authenticated = _student_session(request)
    enrollment = _course_enrollment(authenticated, request.match_info["course_id"])
    requested_group_id = request.query.get("group", enrollment.active_group_public_id)
    group = _allowed_group(enrollment, requested_group_id)
    cursor_value = request.query.get("cursor")
    if cursor_value is not None and _LESSON_CURSOR.fullmatch(cursor_value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Курсор списка занятий некорректен",
        )
    lessons = await _repository(request).list_student_lessons(
        course_public_id=enrollment.course_public_id,
        group_public_id=group.group_public_id,
        before_lesson_number=(None if cursor_value is None else int(cursor_value)),
        limit=_LESSON_PAGE_SIZE + 1,
    )
    page = lessons[:_LESSON_PAGE_SIZE]
    next_cursor = (
        None if len(lessons) <= _LESSON_PAGE_SIZE else str(page[-1].lesson_number)
    )
    return web.json_response(
        {
            "courseId": enrollment.course_public_id,
            "groupId": group.group_public_id,
            "activeGroupId": enrollment.active_group_public_id,
            "lessons": [_student_lesson_payload(lesson) for lesson in page],
            "nextCursor": next_cursor,
        }
    )


@course_routes.get("/student/api/v1/courses/{course_id}/lessons/{group_lesson_id}")
async def get_student_lesson(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _student_session(request)
    enrollment = _course_enrollment(authenticated, request.match_info["course_id"])
    repository = _repository(request)
    group_lesson_public_id = request.match_info["group_lesson_id"]
    if _PUBLIC_ID.fullmatch(group_lesson_public_id) is None:
        raise PwaApiError(
            status=404,
            code="not_found",
            message="Занятие не найдено",
        )
    try:
        scope = await repository.get_group_lesson_scope(group_lesson_public_id)
    except ContentNotFound as error:
        raise PwaApiError(
            status=404,
            code="not_found",
            message="Занятие не найдено",
        ) from error
    if scope.course_public_id != enrollment.course_public_id:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Занятие недоступно этому школьнику",
        )
    group = _allowed_group(enrollment, scope.group_public_id)
    try:
        lesson = await repository.get_student_lesson(
            course_public_id=enrollment.course_public_id,
            group_public_id=group.group_public_id,
            group_lesson_public_id=group_lesson_public_id,
        )
    except ContentNotFound as error:
        raise PwaApiError(
            status=404,
            code="not_found",
            message="Опубликованное занятие не найдено",
        ) from error
    return web.json_response(_student_lesson_payload(lesson))


@course_routes.get(
    "/student/api/v1/courses/{course_id}/lessons/{group_lesson_id}/problems"
)
async def list_student_problems(request: web.Request) -> web.Response:
    _reject_query(request)
    authenticated = _student_session(request)
    enrollment = _course_enrollment(authenticated, request.match_info["course_id"])
    repository = _repository(request)
    group_lesson_public_id = request.match_info["group_lesson_id"]
    if _PUBLIC_ID.fullmatch(group_lesson_public_id) is None:
        raise PwaApiError(
            status=404,
            code="not_found",
            message="Занятие не найдено",
        )
    try:
        scope = await repository.get_group_lesson_scope(group_lesson_public_id)
    except ContentNotFound as error:
        raise PwaApiError(
            status=404,
            code="not_found",
            message="Занятие не найдено",
        ) from error
    if scope.course_public_id != enrollment.course_public_id:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Занятие недоступно этому школьнику",
        )
    group = _allowed_group(enrollment, scope.group_public_id)
    student_user_id = authenticated.principal.linked_user_id
    assert student_user_id is not None
    try:
        result = await repository.list_student_problems(
            student_user_id=student_user_id,
            course_public_id=enrollment.course_public_id,
            group_public_id=group.group_public_id,
            group_lesson_public_id=group_lesson_public_id,
        )
    except ContentNotFound as error:
        raise PwaApiError(
            status=404,
            code="not_found",
            message="Опубликованный список задач не найден",
        ) from error
    return web.json_response(_student_problem_list_payload(result))


__all__ = ["course_enrollment_payload", "course_routes"]
