"""Admin-only HTTP boundary for the course/group catalog."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, date, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.course_catalog import (
    find_course,
    find_group,
    find_season,
    insert_course,
    insert_group,
    insert_season,
    list_courses,
    list_groups,
    update_course,
    update_group,
)
from db_methods.pwa.admin_lessons import (
    find_course_group,
    find_course_lesson,
    insert_course_lesson,
    insert_group_lesson_with_window,
)
from db_methods.pwa.course_runtime_settings import (
    find_course_runtime_settings,
    insert_course_runtime_settings,
    update_course_runtime_settings,
)
from db_methods.pwa.audit import insert_audit_event
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.course_runtime_settings import (
    DEFAULT_COURSE_RUNTIME_SETTINGS,
    InvalidCourseRuntimeSettings,
    normalize_course_runtime_settings,
)
from models.pwa.content import ContentInvariantError, resolve_local_wall_time


admin_course_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_COLOR = re.compile(r"[a-z](?:[a-z0-9-]{0,30}[a-z0-9])?")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_RUNTIME_SETTINGS_ETAG = re.compile(
    r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):runtime-settings:v(\d+)"$'
)
_COURSE_FIELDS = {
    "schemaVersion",
    "code",
    "name",
    "subjectCode",
    "status",
    "sortOrder",
    "accentKey",
}
_GROUP_FIELDS = {
    "schemaVersion",
    "shortCode",
    "name",
    "status",
    "colorKey",
    "sortOrder",
    "allowSelfSwitch",
    "scoreWeight",
}
_SEASON_FIELDS = {
    "schemaVersion",
    "code",
    "title",
    "startsOn",
    "endsOn",
    "sessionExpiresOn",
    "status",
}
_GROUP_LESSON_FIELDS = {
    "schemaVersion",
    "courseId",
    "groupId",
    "lessonNumber",
    "title",
    "cycleAnchorDate",
    "businessTimezone",
    "opensLocalTime",
    "submissionClosesLocalTime",
    "hintScheduledLocalTime",
    "solutionScheduledLocalTime",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="course_catalog_unavailable",
            message="Каталог курсов временно недоступен",
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
            message="Управлять курсами и группами может только администратор",
        )
    return principal.linked_user_id


def _actor_account_id(request: web.Request) -> str:
    """Return the already-authorized Staff account for the audit row."""

    return authenticated_session(request).principal.account_public_id


def _path_public_id(request: web.Request, field: str, *, code: str) -> str:
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
            message="Обновите данные перед сохранением",
        )
    if match.group(1) != public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Запись уже изменилась. Обновите страницу.",
        )
    return int(match.group(2))


def _expected_runtime_settings_version(request: web.Request, public_id: str) -> int:
    values = request.headers.getall("If-Match", [])
    match = _RUNTIME_SETTINGS_ETAG.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите настройки перед сохранением",
        )
    if match.group(1) != public_id:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Настройки уже изменились. Обновите страницу.",
        )
    return int(match.group(2))


async def _read_json(request: web.Request, fields: set[str]) -> dict[str, object]:
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
            message="Проверьте поля курса или группы",
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
            message="Проверьте поля курса или группы",
        )
    return payload


def _text(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if 0 < len(normalized) <= maximum else None


def _code(value: object, *, maximum: int) -> str | None:
    normalized = _text(value, maximum=maximum)
    if normalized is None:
        return None
    normalized = normalized.casefold()
    if (
        normalized.startswith("-")
        or normalized.endswith("-")
        or "--" in normalized
        or not all(character.isalnum() or character == "-" for character in normalized)
    ):
        return None
    return normalized


def _local_time(
    value: object, *, timezone: str, optional: bool
) -> datetime | None:
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте расписание занятия"
        )
    try:
        return resolve_local_wall_time(value, timezone=timezone)
    except ContentInvariantError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте расписание занятия"
        ) from error


def _is_duplicate(error: sqlite3.IntegrityError, table: str) -> bool:
    """Do not disguise unrelated transaction failures as catalog duplicates."""

    message = str(error)
    return "UNIQUE constraint failed" in message and f"{table}." in message


def _season_values(payload: dict[str, object]) -> dict[str, str]:
    code = _code(payload["code"], maximum=30)
    title = _text(payload["title"], maximum=200)
    try:
        starts_on = date.fromisoformat(str(payload["startsOn"]))
        ends_on = date.fromisoformat(str(payload["endsOn"]))
        session_expires_on = date.fromisoformat(str(payload["sessionExpiresOn"]))
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте даты сезона"
        ) from error
    status = payload["status"]
    if (
        code is None
        or title is None
        or status not in {"draft", "active", "archived"}
        or starts_on > ends_on
        or session_expires_on < ends_on
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте сезон"
        )
    return {
        "code": code,
        "title": title,
        "starts_on": starts_on.isoformat(),
        "ends_on": ends_on.isoformat(),
        "session_expires_on": session_expires_on.isoformat(),
        "status": str(status),
    }


def _course_values(payload: dict[str, object]) -> dict[str, object]:
    code = _code(payload["code"], maximum=20)
    name = _text(payload["name"], maximum=200)
    subject_code = _code(payload["subjectCode"], maximum=50)
    accent_key = _text(payload["accentKey"], maximum=32)
    status = payload["status"]
    sort_order = payload["sortOrder"]
    if (
        code is None
        or name is None
        or subject_code is None
        or accent_key is None
        or _COLOR.fullmatch(accent_key) is None
        or status not in {"draft", "active", "archived"}
        or not isinstance(sort_order, int)
        or isinstance(sort_order, bool)
        or not -10_000 <= sort_order <= 10_000
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля курса"
        )
    return {
        "code": code,
        "name": name,
        "subject_code": subject_code,
        "status": status,
        "sort_order": sort_order,
        "accent_key": accent_key,
    }


def _group_values(payload: dict[str, object]) -> dict[str, object]:
    short_code = _code(payload["shortCode"], maximum=20)
    name = _text(payload["name"], maximum=100)
    color_key = _text(payload["colorKey"], maximum=32)
    status = payload["status"]
    sort_order = payload["sortOrder"]
    allow_self_switch = payload["allowSelfSwitch"]
    score_weight = payload["scoreWeight"]
    if (
        short_code is None
        or name is None
        or color_key is None
        or _COLOR.fullmatch(color_key) is None
        or status not in {"draft", "active", "archived"}
        or not isinstance(sort_order, int)
        or isinstance(sort_order, bool)
        or not -10_000 <= sort_order <= 10_000
        or not isinstance(allow_self_switch, bool)
        or not isinstance(score_weight, (int, float))
        or isinstance(score_weight, bool)
        or not 0 < score_weight <= 10
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля группы"
        )
    return {
        "short_code": short_code,
        "name": name,
        "status": status,
        "color_key": color_key,
        "sort_order": sort_order,
        "allow_self_switch": allow_self_switch,
        "score_weight": float(score_weight),
    }


def _group_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "groupId": row["public_id"],
        "shortCode": row["short_code"],
        "name": row["public_name"],
        "status": row["status"],
        "colorKey": row["color_key"],
        "sortOrder": row["sort_order"],
        "allowSelfSwitch": bool(row["allow_self_switch"]),
        "isDefault": bool(row.get("is_default", False)),
        "isSystem": bool(row.get("is_system", False)),
        "scoreWeight": row["score_weight"],
        "activeStudents": row.get("active_students", 0),
        "version": row["version"],
    }


def _course_payload(
    row: dict[str, object], *, groups: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "courseId": row["public_id"],
        "code": row["code"],
        "name": row["name"],
        "subjectCode": row["subject_code"],
        "status": row["status"],
        "sortOrder": row["sort_order"],
        "accentKey": row["accent_key"],
        "activeStudents": row.get("active_students", 0),
        "groups": [_group_payload(group) for group in groups],
        "version": row["version"],
    }


def _course_audit_values(row: dict[str, object]) -> dict[str, object]:
    return {
        "code": row["code"],
        "name": row["name"],
        "subjectCode": row["subject_code"],
        "status": row["status"],
        "sortOrder": row["sort_order"],
        "accentKey": row["accent_key"],
        "version": row["version"],
    }


def _runtime_settings_values(row: dict[str, object] | None) -> dict[str, str]:
    if row is None:
        return dict(DEFAULT_COURSE_RUNTIME_SETTINGS)
    try:
        stored = json.loads(str(row["values_json"]))
        return normalize_course_runtime_settings(stored)
    except (json.JSONDecodeError, InvalidCourseRuntimeSettings) as error:
        # Invalid persisted JSON is an operator-visible integrity failure. It
        # must not silently fall back to defaults and change course behavior.
        raise RuntimeError("stored course runtime settings are invalid") from error


def _runtime_settings_payload(
    *,
    course_public_id: str,
    row: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "courseId": course_public_id,
        "values": _runtime_settings_values(row),
        "version": 0 if row is None else int(row["version"]),
        "source": "defaults" if row is None else "stored",
        "appliesAfter": "restart",
    }


def _group_audit_values(row: dict[str, object]) -> dict[str, object]:
    return {
        "shortCode": row["short_code"],
        "name": row["public_name"],
        "status": row["status"],
        "colorKey": row["color_key"],
        "sortOrder": row["sort_order"],
        "allowSelfSwitch": bool(row["allow_self_switch"]),
        "scoreWeight": row["score_weight"],
        "version": row["version"],
    }


def _catalog(connection, season_public_id: str | None):
    season = find_season(connection, public_id=season_public_id)
    if season is None:
        return None
    courses = list_courses(connection, season_id=int(season["id"]))
    groups = list_groups(
        connection, course_ids=tuple(int(course["id"]) for course in courses)
    )
    grouped: dict[int, list[dict[str, object]]] = {}
    for group in groups:
        grouped.setdefault(int(group["course_id"]), []).append(group)
    return {
        "season": season,
        "courses": [
            _course_payload(course, groups=grouped.get(int(course["id"]), []))
            for course in courses
        ],
    }


@admin_course_routes.post("/staff/api/v1/group-lessons")
async def create_group_lesson(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    payload = await _read_json(request, _GROUP_LESSON_FIELDS)
    course_public_id = payload["courseId"]
    group_public_id = payload["groupId"]
    lesson_number = payload["lessonNumber"]
    title_value = payload["title"]
    timezone = _text(payload["businessTimezone"], maximum=100)
    try:
        anchor = date.fromisoformat(str(payload["cycleAnchorDate"]))
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте дату занятия"
        ) from error
    if (
        not isinstance(course_public_id, str)
        or _PUBLIC_ID.fullmatch(course_public_id) is None
        or not isinstance(group_public_id, str)
        or _PUBLIC_ID.fullmatch(group_public_id) is None
        or isinstance(lesson_number, bool)
        or not isinstance(lesson_number, int)
        or lesson_number < 0
        or lesson_number > 10_000
        or timezone is None
        or (title_value is not None and _text(title_value, maximum=200) is None)
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте данные занятия"
        )
    title = None if title_value is None else _text(title_value, maximum=200)
    opens_at = _local_time(payload["opensLocalTime"], timezone=timezone, optional=True)
    closes_at = _local_time(
        payload["submissionClosesLocalTime"], timezone=timezone, optional=False
    )
    hint_at = _local_time(
        payload["hintScheduledLocalTime"], timezone=timezone, optional=True
    )
    solution_at = _local_time(
        payload["solutionScheduledLocalTime"], timezone=timezone, optional=True
    )
    assert closes_at is not None
    if opens_at is not None and opens_at >= closes_at:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Начало приёма должно быть раньше дедлайна",
        )

    now = _now()

    def write(connection):
        owner = find_course_group(
            connection,
            course_public_id=course_public_id,
            group_public_id=group_public_id,
        )
        if owner is None:
            return "not_found"
        course_lesson = find_course_lesson(
            connection,
            course_id=int(owner["course_id"]),
            lesson_number=lesson_number,
        )
        if course_lesson is None:
            course_lesson_id, resolved_course_lesson_public_id = insert_course_lesson(
                connection,
                course_id=int(owner["course_id"]),
                lesson_number=lesson_number,
                title=title,
                actor_user_id=actor_user_id,
                now=now,
            )
        else:
            course_lesson_id = int(course_lesson["id"])
            resolved_course_lesson_public_id = str(course_lesson["public_id"])
        group_lesson_public_id, _ = insert_group_lesson_with_window(
            connection,
            course_lesson_id=course_lesson_id,
            course_id=int(owner["course_id"]),
            group_id=str(owner["group_id"]),
            cycle_anchor_date=anchor.isoformat(),
            business_timezone=timezone,
            opens_at=_utc(opens_at),
            submission_closes_at=_utc(closes_at),
            hint_scheduled_at=_utc(hint_at),
            solution_scheduled_at=_utc(solution_at),
            actor_user_id=actor_user_id,
            now=now,
        )
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="group_lesson.created",
            object_type="group_lesson",
            object_id=group_lesson_public_id,
            request_id=request["request_id"],
            before_json=None,
            after_json=json.dumps(
                {
                    "courseId": course_public_id,
                    "groupId": group_public_id,
                    "lessonNumber": lesson_number,
                    "submissionClosesAt": _utc(closes_at),
                },
                ensure_ascii=False,
            ),
            occurred_at=now,
        )
        return "created", group_lesson_public_id, resolved_course_lesson_public_id

    try:
        course_lesson_id = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_duplicate(error, "group_lessons"):
            raise
        raise PwaApiError(
            status=409,
            code="group_lesson_duplicate",
            message="Для этой группы занятие с таким номером уже создано",
        ) from error
    if course_lesson_id == "not_found":
        raise PwaApiError(
            status=404, code="group_not_found", message="Курс или группа не найдены"
        )
    _, group_lesson_public_id, course_lesson_public_id = course_lesson_id
    return web.json_response(
        {
            "schemaVersion": 1,
            "groupLesson": {
                "groupLessonId": group_lesson_public_id,
                "courseLessonId": course_lesson_public_id,
                "courseId": course_public_id,
                "groupId": group_public_id,
                "lessonNumber": lesson_number,
                "title": title,
                "cycleAnchorDate": anchor.isoformat(),
                "businessTimezone": timezone,
                "opensAt": _utc(opens_at),
                "submissionClosesAt": _utc(closes_at),
                "hintScheduledAt": _utc(hint_at),
                "solutionScheduledAt": _utc(solution_at),
            },
            "requestId": request["request_id"],
        },
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@admin_course_routes.post("/staff/api/v1/seasons")
async def create_season(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    payload = await _read_json(request, _SEASON_FIELDS)
    values = _season_values(payload)
    now = _now()

    def write(connection):
        public_id = insert_season(connection, now=now, **values)
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="season.created",
            object_type="season",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=None,
            after_json=json.dumps(
                {"seasonId": public_id, **values}, ensure_ascii=False
            ),
            occurred_at=now,
        )
        return public_id

    try:
        public_id = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_duplicate(error, "seasons"):
            raise
        raise PwaApiError(
            status=409,
            code="season_duplicate",
            message="Сезон с таким кодом уже существует",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "season": {
                "seasonId": public_id,
                "code": values["code"],
                "title": values["title"],
                "status": values["status"],
            },
            "requestId": request["request_id"],
        },
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@admin_course_routes.get("/staff/api/v1/courses")
async def get_course_catalog(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if set(request.query) - {"seasonId"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    season_public_id = request.query.get("seasonId")
    if season_public_id is not None and _PUBLIC_ID.fullmatch(season_public_id) is None:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте сезон"
        )
    result = await _factory(request).run_read_async(
        lambda connection: _catalog(connection, season_public_id)
    )
    if result is None:
        raise PwaApiError(
            status=404, code="season_not_found", message="Сезон не найден"
        )
    season = result["season"]
    return web.json_response(
        {
            "schemaVersion": 1,
            "season": {
                "seasonId": season["public_id"],
                "code": season["code"],
                "title": season["title"],
                "status": season["status"],
            },
            "courses": result["courses"],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


@admin_course_routes.post("/staff/api/v1/courses")
async def create_course(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    payload = await _read_json(request, _COURSE_FIELDS | {"seasonId"})
    values = _course_values(payload)
    season_public_id = payload["seasonId"]
    if (
        not isinstance(season_public_id, str)
        or _PUBLIC_ID.fullmatch(season_public_id) is None
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте сезон"
        )
    now = _now()

    def write(connection):
        season = find_season(connection, public_id=season_public_id)
        if season is None:
            return None
        public_id = insert_course(
            connection,
            season_id=int(season["id"]),
            actor_user_id=actor_user_id,
            now=now,
            **values,
        )
        row = find_course(connection, public_id=public_id)
        assert row is not None
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="course.created",
            object_type="course",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=None,
            after_json=json.dumps(_course_audit_values(row), ensure_ascii=False),
            occurred_at=now,
        )
        return row

    try:
        row = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_duplicate(error, "courses"):
            raise
        raise PwaApiError(
            status=409,
            code="course_duplicate",
            message="В этом сезоне уже есть курс с таким кодом",
        ) from error
    if row is None:
        raise PwaApiError(
            status=404, code="season_not_found", message="Сезон не найден"
        )
    response = _course_payload(row, groups=[])
    return web.json_response(
        {"schemaVersion": 1, "course": response, "requestId": request["request_id"]},
        status=201,
        headers={"ETag": f'"{row["public_id"]}:v1"', "Cache-Control": "no-store"},
    )


@admin_course_routes.put("/staff/api/v1/courses/{course_public_id}")
async def edit_course(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    public_id = _path_public_id(request, "course_public_id", code="course_not_found")
    expected_version = _expected_version(request, public_id)
    payload = await _read_json(request, _COURSE_FIELDS)
    values = _course_values(payload)
    now = _now()

    def write(connection):
        current = find_course(connection, public_id=public_id)
        if current is None:
            return "not_found", None
        if int(current["version"]) != expected_version:
            return "conflict", None
        changed = update_course(
            connection,
            public_id=public_id,
            expected_version=expected_version,
            actor_user_id=actor_user_id,
            now=now,
            **values,
        )
        if not changed:
            return "conflict", None
        row = find_course(connection, public_id=public_id)
        assert row is not None
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="course.updated",
            object_type="course",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=json.dumps(_course_audit_values(current), ensure_ascii=False),
            after_json=json.dumps(_course_audit_values(row), ensure_ascii=False),
            occurred_at=now,
        )
        return "ok", row

    try:
        state, row = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_duplicate(error, "courses"):
            raise
        raise PwaApiError(
            status=409,
            code="course_duplicate",
            message="Такой код курса уже используется",
        ) from error
    if state == "not_found":
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    if state == "conflict":
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Курс уже изменился. Обновите страницу.",
        )
    assert row is not None
    version = int(row["version"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "course": _course_payload(row, groups=[]),
            "requestId": request["request_id"],
        },
        headers={"ETag": f'"{public_id}:v{version}"', "Cache-Control": "no-store"},
    )


@admin_course_routes.get("/staff/api/v1/courses/{course_public_id}/runtime-settings")
async def get_course_runtime_settings(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    public_id = _path_public_id(request, "course_public_id", code="course_not_found")

    def read(connection):
        course = find_course(connection, public_id=public_id)
        if course is None:
            return None
        settings = find_course_runtime_settings(connection, course_id=int(course["id"]))
        return _runtime_settings_payload(
            course_public_id=public_id,
            row=settings,
        )

    result = await _factory(request).run_read_async(read)
    if result is None:
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    version = int(result["version"])
    return web.json_response(
        {"schemaVersion": 1, "settings": result, "requestId": request["request_id"]},
        headers={
            "ETag": f'"{public_id}:runtime-settings:v{version}"',
            "Cache-Control": "no-store",
        },
    )


@admin_course_routes.put("/staff/api/v1/courses/{course_public_id}/runtime-settings")
async def put_course_runtime_settings(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    public_id = _path_public_id(request, "course_public_id", code="course_not_found")
    expected_version = _expected_runtime_settings_version(request, public_id)
    payload = await _read_json(request, {"schemaVersion", "values"})
    try:
        values = normalize_course_runtime_settings(payload["values"])
    except InvalidCourseRuntimeSettings as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте настройки курса",
        ) from error
    values_json = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    now = _now()

    def write(connection):
        course = find_course(connection, public_id=public_id)
        if course is None:
            return "not_found", None
        course_id = int(course["id"])
        current = find_course_runtime_settings(connection, course_id=course_id)
        current_version = 0 if current is None else int(current["version"])
        if current_version != expected_version:
            return "conflict", None
        before = _runtime_settings_payload(
            course_public_id=public_id,
            row=current,
        )
        if current is None:
            insert_course_runtime_settings(
                connection,
                course_id=course_id,
                values_json=values_json,
                actor_user_id=actor_user_id,
                now=now,
            )
        elif not update_course_runtime_settings(
            connection,
            course_id=course_id,
            expected_version=expected_version,
            values_json=values_json,
            actor_user_id=actor_user_id,
            now=now,
        ):
            return "conflict", None
        stored = find_course_runtime_settings(connection, course_id=course_id)
        assert stored is not None
        after = _runtime_settings_payload(
            course_public_id=public_id,
            row=stored,
        )
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="course_runtime_settings.updated",
            object_type="course_runtime_settings",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=json.dumps(before, ensure_ascii=False, sort_keys=True),
            after_json=json.dumps(after, ensure_ascii=False, sort_keys=True),
            occurred_at=now,
        )
        return "ok", after

    try:
        state, result = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: course_runtime_settings.course_id" not in str(
            error
        ):
            # Audit/FK/check failures are server integrity errors, not an
            # optimistic conflict that the administrator can fix by retrying.
            raise
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Настройки уже изменились. Обновите страницу.",
        ) from error
    if state == "not_found":
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    if state == "conflict":
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Настройки уже изменились. Обновите страницу.",
        )
    assert result is not None
    version = int(result["version"])
    return web.json_response(
        {"schemaVersion": 1, "settings": result, "requestId": request["request_id"]},
        headers={
            "ETag": f'"{public_id}:runtime-settings:v{version}"',
            "Cache-Control": "no-store",
        },
    )


@admin_course_routes.post("/staff/api/v1/courses/{course_public_id}/groups")
async def create_group(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    course_public_id = _path_public_id(
        request, "course_public_id", code="course_not_found"
    )
    payload = await _read_json(request, _GROUP_FIELDS)
    values = _group_values(payload)
    now = _now()

    def write(connection):
        course = find_course(connection, public_id=course_public_id)
        if course is None:
            return None
        internal_id = f"pwa-{int(course['id'])}-{values['short_code']}"
        public_id = insert_group(
            connection,
            group_id=internal_id,
            course_id=int(course["id"]),
            now=now,
            **values,
        )
        row = find_group(connection, public_id=public_id)
        assert row is not None
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="group.created",
            object_type="group",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=None,
            after_json=json.dumps(_group_audit_values(row), ensure_ascii=False),
            occurred_at=now,
        )
        return row

    try:
        row = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_duplicate(error, "groups"):
            raise
        raise PwaApiError(
            status=409,
            code="group_duplicate",
            message="В этом курсе уже есть группа с таким кодом или названием",
        ) from error
    if row is None:
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    return web.json_response(
        {
            "schemaVersion": 1,
            "group": _group_payload(row),
            "requestId": request["request_id"],
        },
        status=201,
        headers={"ETag": f'"{row["public_id"]}:v1"', "Cache-Control": "no-store"},
    )


@admin_course_routes.put("/staff/api/v1/groups/{group_public_id}")
async def edit_group(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    actor_account_id = _actor_account_id(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    public_id = _path_public_id(request, "group_public_id", code="group_not_found")
    expected_version = _expected_version(request, public_id)
    payload = await _read_json(request, _GROUP_FIELDS)
    values = _group_values(payload)
    now = _now()

    def write(connection):
        current = find_group(connection, public_id=public_id)
        if current is None:
            return "not_found", None
        if int(current["version"]) != expected_version:
            return "conflict", None
        changed = update_group(
            connection,
            public_id=public_id,
            expected_version=expected_version,
            now=now,
            **values,
        )
        if not changed:
            return "conflict", None
        row = find_group(connection, public_id=public_id)
        assert row is not None
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_id,
            audience="staff",
            action="group.updated",
            object_type="group",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=json.dumps(_group_audit_values(current), ensure_ascii=False),
            after_json=json.dumps(_group_audit_values(row), ensure_ascii=False),
            occurred_at=now,
        )
        return "ok", row

    try:
        state, row = await _factory(request).run_write_async(write)
    except sqlite3.IntegrityError as error:
        if not _is_duplicate(error, "groups"):
            raise
        raise PwaApiError(
            status=409,
            code="group_duplicate",
            message="Такой код или название группы уже используется в курсе",
        ) from error
    if state == "not_found":
        raise PwaApiError(
            status=404, code="group_not_found", message="Группа не найдена"
        )
    if state == "conflict":
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Группа уже изменилась. Обновите страницу.",
        )
    assert row is not None
    version = int(row["version"])
    return web.json_response(
        {
            "schemaVersion": 1,
            "group": _group_payload(row),
            "requestId": request["request_id"],
        },
        headers={"ETag": f'"{public_id}:v{version}"', "Cache-Control": "no-store"},
    )


__all__ = ["admin_course_routes"]
