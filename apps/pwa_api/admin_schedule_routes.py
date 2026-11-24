"""Admin HTTP boundary for independent course and group schedule rules."""

from __future__ import annotations

import json
import re
import sqlite3

from aiohttp import web

from apps.pwa_api.content_routes import PWA_CONTENT_REPOSITORY
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.content import (
    ContentConflict,
    ContentNotFound,
    ContentRepositoryError,
    ContentVersionConflict,
)
from db_methods.pwa.course_catalog import find_course, find_group
from db_methods.pwa.course_schedules import (
    find_course_schedule_rule,
    find_group_schedule_override,
    list_course_schedule_rules,
    list_group_schedule_overrides,
)
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.content import (
    ContentInvariantError,
    ScheduleField,
    ScheduleOverrideMode,
    ScheduleRuleValue,
)


admin_schedule_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_RULE_FIELDS = {"schemaVersion", "field", "dayOffset", "localTime", "timezone"}
_OVERRIDE_FIELDS = _RULE_FIELDS | {"mode"}


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
            message="Управлять расписанием может только администратор",
        )
    return principal.linked_user_id


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="course_schedule_unavailable",
            message="Расписание временно недоступно",
        )
    return state.factory


def _repository(request: web.Request):
    repository = request.app.get(PWA_CONTENT_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="course_schedule_unavailable",
            message="Расписание временно недоступно",
        )
    return repository


def _path_id(request: web.Request, field: str, *, code: str) -> str:
    value = request.match_info[field]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(status=404, code=code, message="Запись не найдена")
    return value


def _expected_version(request: web.Request, public_id: str) -> int:
    values = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите данные перед подтверждением",
        )
    if match.group(1) != public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Черновик уже изменился. Обновите страницу.",
        )
    return int(match.group(2))


async def _json(request: web.Request, fields: set[str]) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        payload = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте расписание"
        ) from error
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or payload.get("schemaVersion") != 1
        or isinstance(payload.get("schemaVersion"), bool)
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте расписание"
        )
    return payload


def _schedule_field(value: object) -> ScheduleField:
    try:
        return ScheduleField(value)
    except (TypeError, ValueError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Неизвестное поле расписания"
        ) from error


def _rule_value(payload: dict[str, object]) -> ScheduleRuleValue:
    day_offset = payload["dayOffset"]
    local_time = payload["localTime"]
    timezone = payload["timezone"]
    if (
        not isinstance(day_offset, int)
        or isinstance(day_offset, bool)
        or not -30 <= day_offset <= 30
        or not isinstance(local_time, str)
        or not isinstance(timezone, str)
        or len(timezone) > 64
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте время и смещение"
        )
    try:
        return ScheduleRuleValue.from_text(
            day_offset=day_offset, local_time=local_time, timezone=timezone
        )
    except ContentInvariantError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте время и часовой пояс"
        ) from error


def _rule_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "ruleId": row["public_id"],
        "field": row["schedule_field"],
        "ruleVersion": row["rule_version"],
        "dayOffset": row["day_offset"],
        "localTime": row["local_time"],
        "timezone": row["timezone"],
        "state": row["state"],
        "version": row["version"],
    }


def _override_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "overrideId": row["public_id"],
        "field": row["schedule_field"],
        "overrideVersion": row["override_version"],
        "mode": row["mode"],
        "dayOffset": row["day_offset"],
        "localTime": row["local_time"],
        "timezone": row["timezone"],
        "baseRuleId": row["based_on_schedule_rule_id"],
        "state": row["state"],
        "version": row["version"],
    }


def _raise_domain(error: Exception) -> None:
    if isinstance(error, (ContentVersionConflict, ContentConflict, sqlite3.IntegrityError)):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Расписание изменилось. Обновите страницу.",
        ) from error
    if isinstance(error, ContentNotFound):
        raise PwaApiError(status=404, code="schedule_not_found", message="Запись не найдена") from error
    if isinstance(error, (ContentInvariantError, ContentRepositoryError)):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте расписание"
        ) from error
    raise error


@admin_schedule_routes.get("/staff/api/v1/courses/{course_public_id}/schedule-rules")
async def get_course_schedule(request: web.Request) -> web.Response:
    _admin_user_id(request)
    course_public_id = _path_id(request, "course_public_id", code="course_not_found")

    def read(connection):
        course = find_course(connection, public_id=course_public_id)
        if course is None:
            return None
        return list_course_schedule_rules(connection, course_id=int(course["id"]))

    rows = await _factory(request).run_read_async(read)
    if rows is None:
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    impacts = []
    for row in rows:
        if row["state"] != "draft":
            continue
        impact = await _repository(request).preview_course_schedule_rule_change(
            draft_public_id=str(row["public_id"])
        )
        impacts.append(
            {
                "ruleId": row["public_id"],
                "groupLessons": impact.group_lesson_count,
                "materializedWindows": impact.materialized_window_count,
            }
        )
    return web.json_response(
        {
            "schemaVersion": 1,
            "courseId": course_public_id,
            "rules": [_rule_payload(row) for row in rows],
            "draftImpacts": impacts,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@admin_schedule_routes.put("/staff/api/v1/courses/{course_public_id}/schedule-rules")
async def create_course_schedule_draft(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    course_public_id = _path_id(request, "course_public_id", code="course_not_found")
    payload = await _json(request, _RULE_FIELDS)
    field = _schedule_field(payload["field"])
    value = _rule_value(payload)
    course = await _factory(request).run_read_async(
        lambda connection: find_course(connection, public_id=course_public_id)
    )
    if course is None:
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    try:
        draft = await _repository(request).create_course_schedule_rule_draft(
            public_id="schedule-rule",
            course_id=int(course["id"]),
            schedule_field=field,
            value=value,
            actor_user_id=actor_user_id,
        )
        impact = await _repository(request).preview_course_schedule_rule_change(
            draft_public_id=draft.public_id
        )
    except Exception as error:
        _raise_domain(error)
    row = await _factory(request).run_read_async(
        lambda connection: find_course_schedule_rule(connection, public_id=draft.public_id)
    )
    assert row is not None
    return web.json_response(
        {
            "schemaVersion": 1,
            "rule": _rule_payload(row),
            "impact": {
                "groupLessons": impact.group_lesson_count,
                "materializedWindows": impact.materialized_window_count,
            },
            "requestId": request["request_id"],
        },
        status=201,
        headers={"ETag": f'"{draft.public_id}:v{draft.version}"', "Cache-Control": "no-store"},
    )


@admin_schedule_routes.post("/staff/api/v1/course-schedule-rules/{rule_public_id}/confirm")
async def confirm_course_schedule_draft(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _path_id(request, "rule_public_id", code="schedule_not_found")
    expected_version = _expected_version(request, public_id)
    await _json(request, {"schemaVersion"})
    try:
        confirmed = await _repository(request).confirm_course_schedule_rule(
            draft_public_id=public_id,
            expected_version=expected_version,
            actor_user_id=actor_user_id,
        )
    except Exception as error:
        _raise_domain(error)
    row = await _factory(request).run_read_async(
        lambda connection: find_course_schedule_rule(connection, public_id=public_id)
    )
    assert row is not None
    return web.json_response(
        {"schemaVersion": 1, "rule": _rule_payload(row), "requestId": request["request_id"]},
        headers={"ETag": f'"{public_id}:v{confirmed.version}"', "Cache-Control": "no-store"},
    )


@admin_schedule_routes.get("/staff/api/v1/groups/{group_public_id}/schedule-overrides")
async def get_group_schedule(request: web.Request) -> web.Response:
    _admin_user_id(request)
    group_public_id = _path_id(request, "group_public_id", code="group_not_found")

    def read(connection):
        group = find_group(connection, public_id=group_public_id)
        if group is None:
            return None
        return (
            list_course_schedule_rules(connection, course_id=int(group["course_id"])),
            list_group_schedule_overrides(
                connection,
                course_id=int(group["course_id"]),
                group_id=str(group["group_id"]),
            ),
        )

    result = await _factory(request).run_read_async(read)
    if result is None:
        raise PwaApiError(status=404, code="group_not_found", message="Группа не найдена")
    rules, overrides = result
    return web.json_response(
        {
            "schemaVersion": 1,
            "groupId": group_public_id,
            "courseRules": [_rule_payload(row) for row in rules],
            "overrides": [_override_payload(row) for row in overrides],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@admin_schedule_routes.put("/staff/api/v1/groups/{group_public_id}/schedule-overrides")
async def create_group_schedule_draft(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    group_public_id = _path_id(request, "group_public_id", code="group_not_found")
    payload = await _json(request, _OVERRIDE_FIELDS)
    field = _schedule_field(payload["field"])
    try:
        mode = ScheduleOverrideMode(payload["mode"])
    except (TypeError, ValueError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте режим расписания"
        ) from error
    value = _rule_value(payload) if mode is ScheduleOverrideMode.OVERRIDE else None
    if mode is not ScheduleOverrideMode.OVERRIDE and any(
        payload[name] is not None for name in ("dayOffset", "localTime", "timezone")
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Для этого режима время не задаётся"
        )

    def read(connection):
        group = find_group(connection, public_id=group_public_id)
        if group is None:
            return None
        active = next(
            (
                row
                for row in list_course_schedule_rules(
                    connection, course_id=int(group["course_id"])
                )
                if row["schedule_field"] == field.value and row["state"] == "active"
            ),
            None,
        )
        return group, active

    result = await _factory(request).run_read_async(read)
    if result is None:
        raise PwaApiError(status=404, code="group_not_found", message="Группа не найдена")
    group, active_rule = result
    if active_rule is None:
        raise PwaApiError(
            status=409,
            code="course_schedule_incomplete",
            message="Сначала подтвердите это поле в расписании курса",
        )
    try:
        draft = await _repository(request).create_group_schedule_override_draft(
            public_id="schedule-override",
            course_id=int(group["course_id"]),
            group_id=str(group["group_id"]),
            schedule_field=field,
            mode=mode,
            value=value,
            based_on_schedule_rule_id=int(active_rule["id"]),
            actor_user_id=actor_user_id,
        )
    except Exception as error:
        _raise_domain(error)
    row = await _factory(request).run_read_async(
        lambda connection: find_group_schedule_override(
            connection, public_id=draft.public_id
        )
    )
    assert row is not None
    return web.json_response(
        {"schemaVersion": 1, "override": _override_payload(row), "requestId": request["request_id"]},
        status=201,
        headers={"ETag": f'"{draft.public_id}:v{draft.version}"', "Cache-Control": "no-store"},
    )


@admin_schedule_routes.post(
    "/staff/api/v1/group-schedule-overrides/{override_public_id}/confirm"
)
async def confirm_group_schedule_draft(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = _path_id(request, "override_public_id", code="schedule_not_found")
    expected_version = _expected_version(request, public_id)
    await _json(request, {"schemaVersion"})
    try:
        confirmed = await _repository(request).confirm_group_schedule_override(
            draft_public_id=public_id,
            expected_version=expected_version,
            actor_user_id=actor_user_id,
        )
    except Exception as error:
        _raise_domain(error)
    row = await _factory(request).run_read_async(
        lambda connection: find_group_schedule_override(connection, public_id=public_id)
    )
    assert row is not None
    return web.json_response(
        {
            "schemaVersion": 1,
            "override": _override_payload(row),
            "requestId": request["request_id"],
        },
        headers={"ETag": f'"{public_id}:v{confirmed.version}"', "Cache-Control": "no-store"},
    )


__all__ = ["admin_schedule_routes"]
