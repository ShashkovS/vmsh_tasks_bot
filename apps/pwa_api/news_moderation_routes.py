"""Admin-only visibility controls for mirrored news."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.news_moderation import list_news_for_moderation
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.news_moderation import (
    InvalidNewsVisibility,
    NewsPostNotFound,
    NewsVisibilityConflict,
    change_news_visibility,
)


news_moderation_routes = web.RouteTableDef()
NewsInvalidator = Callable[[str], Awaitable[None]]
PWA_NEWS_INVALIDATOR = web.AppKey("pwa_news_invalidator", NewsInvalidator)
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')
_STATES = frozenset({"visible", "manual_hidden", "source_deleted"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="news_moderation_unavailable",
            message="Управление новостями временно недоступно",
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
            message="Управлять новостями может только администратор",
        )
    return principal.linked_user_id


def _payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "postId": item["public_id"],
        "source": item["source_type"],
        "channelTitle": item["channel_title"],
        "ownerType": item["owner_type"],
        "ownerId": item["owner_public_id"],
        "ownerName": item["owner_name"],
        "publishedAt": item["published_at"],
        "editedAt": item["last_source_edited_at"],
        "revision": item["revision_number"],
        "textExcerpt": str(item["text_plain"])[:500],
        "mediaCount": item["media_count"],
        "visibility": item["visibility_state"],
        "moderationReason": item["moderation_reason"],
        "visibilityUpdatedAt": item["visibility_updated_at"],
        "version": item["visibility_version"],
    }


@news_moderation_routes.get("/staff/api/v1/news")
async def list_news(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if set(request.query) - {"state", "limit"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    raw_state = request.query.get("state", "all")
    state = None if raw_state == "all" else raw_state
    try:
        limit = int(request.query.get("limit", "100"))
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметр limit"
        ) from error
    if (state is not None and state not in _STATES) or not 1 <= limit <= 200:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    rows = await _factory(request).run_read_async(
        lambda connection: list_news_for_moderation(
            connection, state=state, limit=limit
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_payload(item) for item in rows],
            "requestId": request["request_id"],
        }
    )


@news_moderation_routes.patch("/staff/api/v1/news/{post_id}/visibility")
async def change_visibility(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = request.match_info["post_id"]
    if _PUBLIC_ID.fullmatch(public_id) is None:
        raise PwaApiError(
            status=404, code="news_post_not_found", message="Публикация не найдена"
        )
    etags = request.headers.getall("If-Match", [])
    match = _ETAG.fullmatch(etags[0]) if len(etags) == 1 else None
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
            message="Публикация уже изменилась. Обновите список.",
        )
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        body = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля изменения"
        ) from error
    if (
        not isinstance(body, dict)
        or set(body) != {"schemaVersion", "state", "reason"}
        or body.get("schemaVersion") != 1
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля изменения"
        )
    try:
        item = await _factory(request).run_write_async(
            lambda connection: change_news_visibility(
                connection,
                public_id=public_id,
                expected_version=int(match.group(2)),
                target_state=body["state"],
                reason=body["reason"],
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except NewsPostNotFound as error:
        raise PwaApiError(
            status=404, code="news_post_not_found", message="Публикация не найдена"
        ) from error
    except NewsVisibilityConflict as error:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Публикация уже изменилась. Обновите список.",
        ) from error
    except InvalidNewsVisibility as error:
        raise PwaApiError(
            status=409,
            code="news_visibility_not_allowed",
            message="Это состояние публикации нельзя изменить вручную",
        ) from error
    await request.app[PWA_NEWS_INVALIDATOR]("news-visibility-changed")
    response = web.json_response(
        {
            "schemaVersion": 1,
            "item": _payload(item),
            "requestId": request["request_id"],
        }
    )
    response.headers["ETag"] = f'"{public_id}:v{item["visibility_version"]}"'
    return response


__all__ = ["PWA_NEWS_INVALIDATOR", "news_moderation_routes"]
