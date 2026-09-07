"""Best-effort product analytics ingestion and global-admin reporting."""

from __future__ import annotations

import sqlite3
import re
from datetime import UTC, datetime, timedelta

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session, validate_request_boundary
from db_methods.pwa.product_analytics import utc_now_text
from helpers.pwa.app_keys import PWA_ANALYTICS_DATABASE, PWA_DATABASE
from helpers.pwa.permissions import AuthorizationPrincipal, Capability
from helpers.config import logger
from models.pwa.auth import AuthAudience


product_analytics_routes = web.RouteTableDef()
_AUDIENCES = frozenset(item.value for item in AuthAudience)
_EVENT_TYPES = frozenset(
    {
        "page.view",
        "task.open",
        "material.open",
        "test.submit",
        "written.submit",
        "photo.attach",
        "question.create",
        "question.reply",
        "group.change",
        "attendance.change",
        "notifications.change",
        "queue.open",
        "content.upload",
        "content.compile",
        "content.publish",
        "metadata.generate",
        "metadata.change",
        "review.verdict",
        "news.publish",
        "broadcast.publish",
        "schedule.change",
        "classroom.change",
    }
)
_ENTITY_TYPES = frozenset(
    {
        "course",
        "group",
        "lesson",
        "problem",
        "submission",
        "thread",
        "content",
        "news",
        "broadcast",
        "classroom",
    }
)
_POINTER_TYPES = frozenset({"fine", "coarse", "none", "unknown"})
_DISPLAY_MODES = frozenset({"browser", "standalone", "minimal-ui", "fullscreen"})
_ROUTE_ID = re.compile(r"^/[a-z0-9/:._-]{0,159}$")
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")


def _analytics_factory(request: web.Request):
    state = request.app.get(PWA_ANALYTICS_DATABASE)
    if state is None or state.factory is None:
        return None
    return state.factory


def _core_factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="analytics_unavailable",
            message="Аналитика временно недоступна",
        )
    return state.factory


def _global_admin(request: web.Request) -> AuthorizationPrincipal:
    principal = authenticated_session(request).principal
    if principal.audience is not AuthAudience.STAFF or not principal.has_capability(
        Capability.PRODUCT_ANALYTICS_READ
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Нет доступа к продуктовой аналитике",
        )
    return principal


def _event(value: object) -> tuple[str, str | None, str | None, int, int, float, str, str]:
    if not isinstance(value, dict) or set(value) - {
        "eventType", "routeId", "entityType", "entityId", "viewportWidth", "viewportHeight", "devicePixelRatio", "pointerType", "displayMode"
    }:
        raise ValueError
    event_type = value.get("eventType")
    route_id = value.get("routeId")
    entity_type = value.get("entityType")
    entity_id = value.get("entityId")
    width, height, dpr = value.get("viewportWidth"), value.get("viewportHeight"), value.get("devicePixelRatio")
    pointer_type, display_mode = value.get("pointerType"), value.get("displayMode")
    if (
        event_type not in _EVENT_TYPES
        or not isinstance(route_id, str)
        or _ROUTE_ID.fullmatch(route_id) is None
        or (entity_type is None) != (entity_id is None)
        or entity_type is not None
        and (
            entity_type not in _ENTITY_TYPES
            or not isinstance(entity_id, str)
            or _PUBLIC_ID.fullmatch(entity_id) is None
        )
        or not isinstance(width, int) or not 0 <= width <= 10000
        or not isinstance(height, int) or not 0 <= height <= 10000
        or not isinstance(dpr, (int, float)) or not 0.1 <= float(dpr) <= 10
        or pointer_type not in _POINTER_TYPES
        or display_mode not in _DISPLAY_MODES
    ):
        raise ValueError
    return event_type, entity_type, entity_id, width, height, float(dpr), pointer_type, display_mode


@product_analytics_routes.post("/{audience:student|family|staff}/api/v1/analytics/events")
async def record_events(request: web.Request) -> web.Response:
    audience = AuthAudience(request.match_info["audience"])
    validate_request_boundary(request, audience=audience, expects_json=True, require_browser_source=True)
    session = authenticated_session(request)
    if session.principal.audience is not audience:
        raise PwaApiError(403, "forbidden", "Неверная аудитория аналитики")
    try:
        payload = await request.json()
        events = payload["events"] if isinstance(payload, dict) and set(payload) == {"events"} else None
        if not isinstance(events, list) or not 1 <= len(events) <= 20:
            raise ValueError
        parsed = [(item, _event(item)) for item in events]
    except (ValueError, TypeError, KeyError):
        raise PwaApiError(422, "validation_error", "Некорректное аналитическое событие")

    factory = _analytics_factory(request)
    if factory is None:
        return web.Response(status=204)
    occurred_at = utc_now_text()
    account_id = session.principal.account_public_id
    session_id = session.principal.session_public_id

    def write(connection: sqlite3.Connection) -> None:
        connection.executemany(
            "INSERT INTO product_events (occurred_at, audience, account_public_id, session_public_id, event_type, route_id, entity_type, entity_public_id, viewport_width, viewport_height, device_pixel_ratio, pointer_type, display_mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (occurred_at, audience.value, account_id, session_id, parsed_event[0], str(raw["routeId"]), parsed_event[1], parsed_event[2], parsed_event[3], parsed_event[4], parsed_event[5], parsed_event[6], parsed_event[7])
                for raw, parsed_event in parsed
            ],
        )

    try:
        await factory.run_write_async(write)
    except Exception:  # analytics intentionally never affects product work
        logger.warning("Product analytics write failed", exc_info=True)
    return web.Response(status=204, headers={"Cache-Control": "no-store"})


def _report_filter(request: web.Request) -> tuple[datetime, datetime, str | None, str | None, str | None]:
    allowed = {"from", "to", "audience", "accountId", "eventType", "limit", "before"}
    if set(request.query) - allowed:
        raise PwaApiError(422, "validation_error", "Неизвестный параметр аналитики")
    now = datetime.now(UTC)
    start = now - timedelta(days=14)
    try:
        if request.query.get("from"):
            start = datetime.fromisoformat(request.query["from"].replace("Z", "+00:00")).astimezone(UTC)
        end = datetime.fromisoformat(request.query.get("to", now.isoformat()).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise PwaApiError(422, "validation_error", "Неверный период аналитики") from exc
    if end < start or end - start > timedelta(days=370):
        raise PwaApiError(422, "validation_error", "Выберите период не более года")
    audience = request.query.get("audience")
    event_type = request.query.get("eventType")
    if (audience is not None and audience not in _AUDIENCES) or (
        event_type is not None and event_type not in _EVENT_TYPES
    ):
        raise PwaApiError(422, "validation_error", "Неверный фильтр аналитики")
    return start, end, audience, request.query.get("accountId"), event_type


@product_analytics_routes.get("/staff/api/v1/analytics/summary")
async def analytics_summary(request: web.Request) -> web.Response:
    _global_admin(request)
    factory = _analytics_factory(request)
    if factory is None:
        raise PwaApiError(
            status=503,
            code="analytics_unavailable",
            message="Аналитика временно недоступна",
        )
    start, end, audience, account_id, event_type = _report_filter(request)
    clauses, params = ["occurred_at >= ?", "occurred_at <= ?"], [start.isoformat(), end.isoformat()]
    for clause, value in (("audience", audience), ("account_public_id", account_id), ("event_type", event_type)):
        if value is not None:
            clauses.append(f"{clause} = ?")
            params.append(value)
    where = " WHERE " + " AND ".join(clauses)
    def read(connection: sqlite3.Connection):
        totals = connection.execute("SELECT COUNT(*) AS actions, COUNT(DISTINCT account_public_id) AS users, SUM(event_type = 'page.view') AS views FROM product_events" + where, params).fetchone()
        routes = connection.execute("SELECT route_id, COUNT(*) AS count FROM product_events" + where + " GROUP BY route_id ORDER BY count DESC, route_id LIMIT 12", params).fetchall()
        return totals, routes
    totals, routes = await factory.run_read_async(read)
    return web.json_response({"activeUsers": int(totals["users"] or 0), "pageViews": int(totals["views"] or 0), "actions": int(totals["actions"] or 0), "popularRoutes": [{"routeId": row["route_id"], "count": int(row["count"])} for row in routes], "requestId": request["request_id"]}, headers={"Cache-Control": "no-store"})


@product_analytics_routes.get("/staff/api/v1/analytics/events")
async def analytics_events(request: web.Request) -> web.Response:
    _global_admin(request)
    factory = _analytics_factory(request)
    if factory is None:
        raise PwaApiError(
            status=503,
            code="analytics_unavailable",
            message="Аналитика временно недоступна",
        )
    start, end, audience, account_id, event_type = _report_filter(request)
    try:
        limit = min(100, max(1, int(request.query.get("limit", "50"))))
        before = int(request.query["before"]) if request.query.get("before") else None
    except ValueError as exc:
        raise PwaApiError(422, "validation_error", "Неверная страница аналитики") from exc
    clauses, params = ["occurred_at >= ?", "occurred_at <= ?"], [start.isoformat(), end.isoformat()]
    for clause, value in (("audience", audience), ("account_public_id", account_id), ("event_type", event_type)):
        if value is not None:
            clauses.append(f"{clause} = ?")
            params.append(value)
    if before is not None:
        clauses.append("id < ?")
        params.append(before)

    def read(connection: sqlite3.Connection):
        return connection.execute(
            "SELECT * FROM product_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY id DESC LIMIT ?",
            [*params, limit + 1],
        ).fetchall()

    rows = await factory.run_read_async(read)
    more = len(rows) > limit
    rows = rows[:limit]
    account_ids = tuple({str(row["account_public_id"]) for row in rows})

    def names(connection: sqlite3.Connection):
        if not account_ids:
            return []
        marks = ",".join("?" for _ in account_ids)
        return connection.execute(
            "SELECT public_id, display_name, audience FROM auth_accounts "
            "WHERE public_id IN (" + marks + ")",
            account_ids,
        ).fetchall()

    name_rows = await _core_factory(request).run_read_async(names)
    names_by_id = {
        str(row["public_id"]): {
            "displayName": row["display_name"],
            "currentAudience": row["audience"],
        }
        for row in name_rows
    }
    items = []
    for row in rows:
        item = dict(row)
        item["account"] = names_by_id.get(
            str(row["account_public_id"]),
            {"displayName": "Удалённый аккаунт", "currentAudience": None},
        )
        item["eventId"] = item.pop("id")
        items.append(item)
    return web.json_response(
        {
            "events": items,
            "nextBefore": int(rows[-1]["id"]) if more and rows else None,
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )
