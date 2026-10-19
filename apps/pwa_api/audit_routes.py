"""Admin-only searchable audit timeline for Staff."""

from __future__ import annotations

import re

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.audit import find_audit_cursor, list_audit_events
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.audit import InvalidAuditEvent, audit_event_payload
from models.pwa.auth import AuthAudience


audit_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_OBJECT_TYPES = {
    "all",
    "account",
    "family_link",
    "course_enrollment",
    "problem_import",
    "course",
    "group",
    "telegram_binding",
    "problem_synonym",
    "news_post",
    "staff_scope",
}
_QUERY_KEYS = {"objectType", "q", "cursor", "limit"}


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="audit_unavailable",
            message="Журнал изменений временно недоступен",
        )
    return state.factory


def _admin(request: web.Request):
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.has_capability(Capability.AUDIT_READ)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Журнал изменений доступен только администратору",
        )
    return principal


def _query(request: web.Request) -> tuple[str, str, str | None, int]:
    if set(request.query) - _QUERY_KEYS or any(
        len(request.query.getall(key, [])) > 1 for key in _QUERY_KEYS
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры журнала"
        )
    object_type = request.query.get("objectType", "all")
    query = request.query.get("q", "").strip()
    cursor = request.query.get("cursor")
    try:
        limit = int(request.query.get("limit", "50"))
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте размер страницы"
        ) from error
    if (
        object_type not in _OBJECT_TYPES
        or len(query) > 100
        or any(ord(character) < 32 for character in query)
        or (cursor is not None and _PUBLIC_ID.fullmatch(cursor) is None)
        or not 1 <= limit <= 100
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры журнала"
        )
    return object_type, query, cursor, limit


@audit_routes.get("/staff/api/v1/audit")
async def get_audit(request: web.Request) -> web.Response:
    _admin(request)
    object_type, query, cursor_public_id, limit = _query(request)

    def read(connection):
        cursor = (
            None
            if cursor_public_id is None
            else find_audit_cursor(connection, public_id=cursor_public_id)
        )
        if cursor_public_id is not None and cursor is None:
            return None
        return list_audit_events(
            connection,
            source=object_type,
            query=query,
            cursor=cursor,
            limit=limit + 1,
        )

    rows = await _factory(request).run_read_async(read)
    if rows is None:
        raise PwaApiError(
            status=422,
            code="audit_cursor_invalid",
            message="Обновите журнал и повторите поиск",
        )
    try:
        items = [audit_event_payload(row) for row in rows[:limit]]
    except InvalidAuditEvent as error:
        raise RuntimeError("Stored audit event violates the safe projection") from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": items,
            "nextCursor": items[-1]["eventId"] if len(rows) > limit and items else None,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["audit_routes"]
