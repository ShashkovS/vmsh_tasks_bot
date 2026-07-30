"""Admin HTTP boundary for logical problem synonyms.

Endpoints: ``vmshpwa/dev/development-plan/03-api-events-and-files.md``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.problem_synonyms import (
    ProblemSynonymError,
    merge_problem_synonyms,
    preview_synonym_merge,
    preview_synonym_split,
    split_problem_synonyms,
    synonym_candidates,
)


problem_synonym_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_SHA256 = re.compile(r"[a-f0-9]{64}")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="problem_synonyms_unavailable",
            message="Синонимы задач временно недоступны",
        )
    return state.factory


def _admin_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Объединять и разделять задачи может только администратор",
        )
    return principal.linked_user_id


def _public_id(value: str, *, code: str, message: str) -> str:
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(status=404, code=code, message=message)
    return value


async def _json(request: web.Request, fields: set[str]) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        payload = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранные задачи",
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or payload.get("schemaVersion") != 1
        or isinstance(payload.get("schemaVersion"), bool)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте выбранные задачи",
        )
    return payload


def _problem_ids(value: object, *, minimum: int) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not minimum <= len(value) <= 50
        or any(
            not isinstance(item, str) or _PUBLIC_ID.fullmatch(item) is None
            for item in value
        )
        or len(set(value)) != len(value)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Выберите задачи без повторов",
        )
    return tuple(value)


def _preview_hash(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Сначала обновите предпросмотр",
        )
    return value


def _problem_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "problemId": row["problem_public_id"],
        "courseId": row["course_public_id"],
        "courseName": row["course_name"],
        "courseLessonId": row["course_lesson_public_id"],
        "lessonNumber": row["lesson_number"],
        "groupId": row["group_public_id"],
        "groupName": row["group_name"],
        "groupCode": row["group_code"],
        "groupLessonId": row["group_lesson_public_id"],
        "title": row["title"],
        "problemType": row["problem_type"],
        "answerType": row["answer_type"],
        "submissionCount": row["submission_count"],
        "reviewCount": row["review_count"],
        "synonymId": row["synonym_public_id"],
    }


def _impact_payload(plan: dict[str, object], request_id: str) -> dict[str, object]:
    problems = plan["problems"]
    additions = plan["additions"]
    removals = plan["removals"]
    assert isinstance(problems, list)
    assert isinstance(additions, list)
    assert isinstance(removals, list)
    synonym = plan["synonym"]
    assert synonym is None or isinstance(synonym, dict)
    payload = {
        "schemaVersion": 1,
        "mode": plan["mode"],
        "synonym": None
        if synonym is None
        else {
            "synonymId": synonym["public_id"],
            "status": synonym["status"],
            "version": synonym["version"],
        },
        "problems": [_problem_payload(row) for row in problems],
        "selectedProblemIds": list(plan["selected_problem_ids"]),
        "addProblemIds": [row["problem_public_id"] for row in additions],
        "removeProblemIds": [row["problem_public_id"] for row in removals],
        "submissionCount": sum(int(row["submission_count"]) for row in problems),
        "reviewCount": sum(int(row["review_count"]) for row in problems),
        "previewSha256": plan["preview_sha256"],
        "requestId": request_id,
    }
    if "synonym_public_id" in plan:
        payload.update(
            {
                "result": {
                    "synonymId": plan["synonym_public_id"],
                    "status": plan["synonym_status"],
                    "version": plan["synonym_version"],
                    "changed": plan["changed"],
                }
            }
        )
    return payload


def _domain_error(error: ProblemSynonymError) -> PwaApiError:
    code = str(error)
    messages = {
        "problem_selection_invalid": (422, "Выберите задачи без повторов"),
        "problem_not_found": (404, "Задача не найдена"),
        "course_lesson_not_found": (404, "Занятие не найдено"),
        "synonym_not_found": (404, "Группа синонимов не найдена"),
        "course_lesson_mismatch": (422, "Задачи относятся к разным занятиям курса"),
        "group_lesson_duplicate": (
            422,
            "В одной группе можно выбрать только одну задачу",
        ),
        "different_synonym_groups": (
            409,
            "Сначала разделите существующие группы синонимов",
        ),
        "synonym_state_invalid": (409, "Группа синонимов уже изменилась"),
        "problem_not_in_synonym": (
            422,
            "Выбранная задача не входит в эту группу синонимов",
        ),
        "preview_changed": (409, "Задачи изменились после предпросмотра"),
        "version_conflict": (409, "Группа синонимов уже изменилась"),
    }
    status, message = messages.get(
        code, (409, "Операцию с синонимами нельзя выполнить")
    )
    return PwaApiError(status=status, code=f"problem_synonym_{code}", message=message)


@problem_synonym_routes.get(
    "/staff/api/v1/course-lessons/{course_lesson_public_id}/synonym-candidates"
)
async def get_synonym_candidates(request: web.Request) -> web.Response:
    _admin_user_id(request)
    course_lesson_public_id = _public_id(
        request.match_info["course_lesson_public_id"],
        code="course_lesson_not_found",
        message="Занятие не найдено",
    )
    try:
        candidates = await _factory(request).run_read_async(
            lambda connection: synonym_candidates(
                connection, course_lesson_public_id=course_lesson_public_id
            )
        )
    except ProblemSynonymError as error:
        raise _domain_error(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "courseLessonId": course_lesson_public_id,
            "candidates": [
                {
                    "normalizedTitle": candidate["normalized_title"],
                    "displayTitle": candidate["display_title"],
                    "hasGroupConflict": candidate["has_group_conflict"],
                    "problems": [
                        _problem_payload(row) for row in candidate["problems"]
                    ],
                }
                for candidate in candidates
            ],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@problem_synonym_routes.post("/staff/api/v1/problem-synonyms/impact-preview")
async def preview_problem_synonyms(request: web.Request) -> web.Response:
    _admin_user_id(request)
    payload = await _json(request, {"schemaVersion", "mode", "problemIds", "synonymId"})
    mode = payload["mode"]
    if mode not in {"merge", "split"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Выберите действие"
        )
    problem_ids = _problem_ids(
        payload["problemIds"], minimum=2 if mode == "merge" else 1
    )
    synonym_id = payload["synonymId"]
    if mode == "merge" and synonym_id is not None:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте выбранные задачи"
        )
    if mode == "split":
        if not isinstance(synonym_id, str) or _PUBLIC_ID.fullmatch(synonym_id) is None:
            raise PwaApiError(
                status=422, code="validation_error", message="Выберите группу синонимов"
            )
    try:
        if mode == "merge":
            plan = await _factory(request).run_read_async(
                lambda connection: preview_synonym_merge(
                    connection, problem_public_ids=problem_ids
                )
            )
        else:
            plan = await _factory(request).run_read_async(
                lambda connection: preview_synonym_split(
                    connection,
                    synonym_public_id=str(synonym_id),
                    problem_public_ids=problem_ids,
                )
            )
    except ProblemSynonymError as error:
        raise _domain_error(error) from error
    return web.json_response(
        _impact_payload(plan, request["request_id"]),
        headers={"Cache-Control": "no-store"},
    )


@problem_synonym_routes.post("/staff/api/v1/problem-synonyms/merge")
async def merge_problem_synonyms_route(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    payload = await _json(request, {"schemaVersion", "problemIds", "previewSha256"})
    problem_ids = _problem_ids(payload["problemIds"], minimum=2)
    preview_sha256 = _preview_hash(payload["previewSha256"])
    try:
        plan = await _factory(request).run_write_async(
            lambda connection: merge_problem_synonyms(
                connection,
                problem_public_ids=problem_ids,
                preview_sha256=preview_sha256,
                actor_user_id=actor_user_id,
                now=datetime.now(UTC).isoformat(),
            )
        )
    except ProblemSynonymError as error:
        raise _domain_error(error) from error
    except sqlite3.IntegrityError as error:
        raise PwaApiError(
            status=409,
            code="problem_synonym_conflict",
            message="Эти задачи уже изменились",
        ) from error
    return web.json_response(
        _impact_payload(plan, request["request_id"]),
        headers={"Cache-Control": "no-store"},
    )


@problem_synonym_routes.post("/staff/api/v1/problem-synonyms/{synonym_public_id}/split")
async def split_problem_synonyms_route(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    synonym_public_id = _public_id(
        request.match_info["synonym_public_id"],
        code="problem_synonym_not_found",
        message="Группа синонимов не найдена",
    )
    payload = await _json(
        request,
        {"schemaVersion", "problemIds", "previewSha256", "reason"},
    )
    problem_ids = _problem_ids(payload["problemIds"], minimum=1)
    preview_sha256 = _preview_hash(payload["previewSha256"])
    reason = payload["reason"]
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Укажите причину разделения",
        )
    try:
        plan = await _factory(request).run_write_async(
            lambda connection: split_problem_synonyms(
                connection,
                synonym_public_id=synonym_public_id,
                problem_public_ids=problem_ids,
                preview_sha256=preview_sha256,
                reason=reason.strip(),
                actor_user_id=actor_user_id,
                now=datetime.now(UTC).isoformat(),
            )
        )
    except ProblemSynonymError as error:
        raise _domain_error(error) from error
    return web.json_response(
        _impact_payload(plan, request["request_id"]),
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["problem_synonym_routes"]
