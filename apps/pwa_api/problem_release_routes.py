"""Group-owned PWA release controls; vmshpwa/docs/problem-release.md."""

import logging

from aiohttp import web

from apps.pwa_api.content_routes import (
    _authorized_lesson_window_scope,
    _etag,
    _json_object,
    _revision_if_match_version,
    _translate_content_errors,
)
from apps.pwa_api.errors import PwaApiError
from models.pwa.problem_release import (
    ProblemReleaseConflict,
    ProblemReleaseNotFound,
    ProblemReleaseService,
)

problem_release_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def _payload(scope, revision_id: str, snapshot: dict) -> dict:
    return {
        "groupLessonId": scope.group_lesson_public_id,
        "conditionRevisionId": revision_id,
        **snapshot,
        "etag": _etag(scope.group_lesson_public_id + "-release", snapshot["version"]),
    }


def _translate(error):
    if isinstance(error, ProblemReleaseConflict):
        return PwaApiError(
            status=409,
            code="version_conflict",
            message="Доступность задач уже изменилась. Повторите действие.",
        )
    return PwaApiError(
        status=404, code="not_found", message="Задачи этого листка пока недоступны."
    )


@problem_release_routes.get(
    "/staff/api/v1/group-lessons/{group_lesson_id}/problem-release"
)
@_translate_content_errors
async def get_problem_release(request: web.Request) -> web.Response:
    repository, scope, _actor = await _authorized_lesson_window_scope(request)
    if (
        set(request.query) != {"revisionId"}
        or len(request.query.getall("revisionId")) != 1
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Выберите версию условий."
        )
    revision_id = request.query["revisionId"]
    try:
        snapshot = await ProblemReleaseService(repository.factory).get(
            scope.group_lesson_id, revision_id
        )
    except ProblemReleaseNotFound as error:
        raise _translate(error) from error
    payload = _payload(scope, revision_id, snapshot)
    return web.json_response(
        payload, headers={"ETag": payload["etag"], "Cache-Control": "no-store"}
    )


@problem_release_routes.put(
    "/staff/api/v1/group-lessons/{group_lesson_id}/problem-release"
)
@_translate_content_errors
async def change_problem_release(request: web.Request) -> web.Response:
    repository, scope, actor = await _authorized_lesson_window_scope(request)
    body = await _json_object(
        request, allowed_fields=frozenset({"conditionRevisionId", "changes"})
    )
    revision_id = body.get("conditionRevisionId")
    items = body.get("changes")
    if (
        not isinstance(revision_id, str)
        or not isinstance(items, list)
        or not 0 < len(items) <= 2000
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте настройки задач."
        )
    changes = {}
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item) != {"sourceOrdinal", "isOpen"}
            or type(item["sourceOrdinal"]) is not int
            or item["sourceOrdinal"] < 0
            or type(item["isOpen"]) is not bool
            or item["sourceOrdinal"] in changes
        ):
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Проверьте настройки задач.",
            )
        changes[item["sourceOrdinal"]] = item["isOpen"]
    expected = _revision_if_match_version(
        request, public_id=scope.group_lesson_public_id + "-release"
    )
    try:
        snapshot = await ProblemReleaseService(repository.factory).change(
            group_lesson_id=scope.group_lesson_id,
            revision_public_id=revision_id,
            expected_version=expected,
            changes=changes,
            actor_user_id=actor,
            request_id=request["request_id"],
        )
    except (ProblemReleaseConflict, ProblemReleaseNotFound) as error:
        raise _translate(error) from error
    from apps.pwa_app import NATS_PWA_INVALIDATE, PWA_BROKER

    try:
        await request.app[PWA_BROKER].publish(
            NATS_PWA_INVALIDATE,
            {
                "reason": "problem-release-changed",
                "resources": [
                    f"group-lessons/{scope.group_lesson_public_id}/problem-release",
                    *(
                        f"group-lessons/{scope.group_lesson_public_id}/content/{kind}"
                        for kind in ("condition", "hint", "solution")
                    ),
                    "student-course-lessons",
                    "family-worksheets",
                ],
            },
        )
    except Exception:
        # SQLite remains authoritative; reconnect refetches without notifications.
        logger.warning(
            "Problem release invalidation failed after commit: lesson=%s",
            scope.group_lesson_public_id,
            exc_info=True,
        )
    payload = _payload(scope, revision_id, snapshot)
    return web.json_response(
        payload, headers={"ETag": payload["etag"], "Cache-Control": "no-store"}
    )
