"""Token-only read bridge for a11/a13; docs/printing/legacy-api.md."""

import hashlib
import hmac
import json
import re

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import validate_request_boundary
from db_methods.pwa.legacy_print import list_print_events
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG
from models.pwa.auth import AuthAudience
from models.pwa.classroom_assignments import ClassroomAssignmentNotFound
from models.pwa.legacy_print import LegacyPrintConflict, export_print_pupils


routes = web.RouteTableDef()
PREFIX = "/staff/api/legacy-print/v1"
_MESSAGES = {
    "event_cancelled": "Очное событие отменено",
    "plan_not_confirmed": "Подтвердите распределение в админке перед печатью",
    "lesson_mismatch": "Номер занятия не совпадает с выбранным событием",
    "multiple_courses": "Старые скрипты поддерживают только один курс за запуск",
    "unsupported_level": "Для старых скриптов нужны коды групп н, п, э",
    "roster_changed": "Состав или аудитории изменились: пересчитайте и подтвердите план",
    "missing_or_duplicate_login": "У ученика нет уникального логина портала",
    "mixed_room": "В одной аудитории оказались разные группы",
    "missing_name": "Для печати нужны фамилия и имя каждого ученика",
}


def _authorize(request):
    # Separate namespace from browser session API, same host/proxy/origin policy.
    validate_request_boundary(request, audience=AuthAudience.STAFF, expects_json=False)
    token = getattr(request.app[RUNTIME_CONFIG], "legacy_print_api_token", "")
    if not isinstance(token, str) or len(token) < 32 or token != token.strip():
        raise PwaApiError(
            status=503, code="legacy_print_disabled", message="API печати не настроен"
        )
    headers = request.headers.getall("Authorization", [])
    supplied = headers[0] if len(headers) == 1 else ""
    if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
        raise PwaApiError(
            status=401,
            code="legacy_print_unauthorized",
            message="Нужен токен API печати",
            headers={"WWW-Authenticate": "Bearer"},
        )
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="legacy_print_unavailable",
            message="База печати временно недоступна",
        )
    return state.factory


@routes.get(PREFIX + "/events")
async def events(request):
    factory = _authorize(request)
    rows = await factory.run_read_async(list_print_events)
    for row in rows:
        numbers = row.pop("lesson_numbers")
        row["lesson_numbers"] = (
            sorted(int(number) for number in numbers.split(",")) if numbers else []
        )
    return web.json_response({"events": rows})


@routes.get(PREFIX + "/events/{event_id}/pupils")
async def pupils(request):
    factory = _authorize(request)
    lesson = request.query.get("lesson", "")
    if (
        set(request.query) != {"lesson"}
        or len(request.query.getall("lesson")) != 1
        or not re.fullmatch(r"[1-9][0-9]{0,3}", lesson)
    ):
        raise PwaApiError(
            status=422,
            code="legacy_print_lesson_required",
            message="Укажите номер занятия в параметре lesson",
        )
    try:
        event, plan, rows = await factory.run_read_async(
            lambda connection: export_print_pupils(
                connection, request.match_info["event_id"], int(lesson)
            )
        )
    except ClassroomAssignmentNotFound:
        raise PwaApiError(
            status=404,
            code="legacy_print_event_not_found",
            message="Очное событие не найдено",
        ) from None
    except LegacyPrintConflict as error:
        code = str(error)
        raise PwaApiError(
            status=409, code="legacy_print_" + code, message=_MESSAGES[code]
        ) from None
    body = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()
    digest = hashlib.sha256(
        body + str(plan["public_id"]).encode() + str(plan["version"]).encode()
    ).hexdigest()
    etag = f'"{digest}"'
    if request.headers.get("If-Match", etag) != etag:
        raise PwaApiError(
            status=412,
            code="legacy_print_changed",
            message="Распределение изменилось после предыдущего экспорта",
        )
    return web.Response(
        body=body,
        content_type="application/json",
        charset="utf-8",
        headers={
            "ETag": etag,
            "X-Print-Event": str(event["public_id"]),
            "X-Print-Plan": str(plan["public_id"]),
            "X-Print-Lesson": lesson,
            "X-Print-Plan-Version": str(plan["version"]),
        },
    )
