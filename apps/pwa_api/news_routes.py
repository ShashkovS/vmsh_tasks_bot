"""Authenticated Student and Family reads for the mirrored news feed."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.news import (
    get_visible_post_by_public_id,
    list_media_for_revisions,
    list_visible_posts,
)
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience


news_routes = web.RouteTableDef()
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_ENTITY_TYPES = frozenset(
    {
        "bold",
        "italic",
        "underline",
        "strike",
        "code",
        "link",
        "spoiler",
        "mark",
        "sub",
        "sup",
    }
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="news_unavailable",
            message="Новости временно недоступны",
        )
    return state.factory


def _scope(request: web.Request) -> tuple[tuple[int, ...], tuple[str, ...]]:
    authenticated = authenticated_session(request)
    principal = authenticated.principal
    if principal.audience not in {
        AuthAudience.STUDENT,
        AuthAudience.FAMILY,
    } or not principal.has_capability(Capability.NEWS_READ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для просмотра новостей",
        )
    enrollments = [
        item
        for item in authenticated.course_enrollments
        if item.enrollment_status == "active"
    ]
    course_ids = tuple(sorted({item.course_id for item in enrollments}))
    group_ids = tuple(
        sorted(
            {group.group_id for item in enrollments for group in item.allowed_groups}
        )
    )
    return course_ids, group_ids


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _blocks(content_json: object) -> list[dict[str, object]]:
    if not isinstance(content_json, str):
        raise RuntimeError("Stored news content is invalid")
    content = json.loads(content_json)
    if not isinstance(content, list):
        raise RuntimeError("Stored news content is invalid")
    text_parts: list[str] = []
    entities: list[dict[str, object]] = []
    offset = 0
    for node in content:
        if not isinstance(node, dict) or not isinstance(node.get("text"), str):
            raise RuntimeError("Stored news content is invalid")
        text = node["text"]
        raw_marks = node.get("marks")
        marks = raw_marks if isinstance(raw_marks, list) else [node]
        for mark in marks:
            if not isinstance(mark, dict):
                raise RuntimeError("Stored news content is invalid")
            node_type = mark.get("type")
            if node_type in _ENTITY_TYPES and text:
                entity: dict[str, object] = {
                    "type": node_type,
                    "offset": offset,
                    "length": _utf16_length(text),
                }
                if node_type == "link" and isinstance(mark.get("href"), str):
                    entity["href"] = mark["href"]
                entities.append(entity)
        text_parts.append(text)
        offset += _utf16_length(text)
    block: dict[str, object] = {"kind": "text", "text": "".join(text_parts)}
    if entities:
        block["entities"] = entities
    return [block]


def _media_payload(item: dict[str, object]) -> dict[str, object]:
    public_url = item["public_url"]
    if item["media_kind"] == "image":
        return {
            "kind": "photo",
            "mediaId": f"news-media.{item['id']}",
            "previewUrl": public_url,
            "alt": "",
        }
    if item["media_kind"] == "video":
        return {
            "kind": "video",
            "mediaId": f"news-media.{item['id']}",
            "previewUrl": public_url,
        }
    return {
        "kind": "document",
        "mediaId": f"news-media.{item['id']}",
        "name": "Аудио" if item["media_kind"] == "audio" else "Файл",
        "url": public_url,
    }


def _post_payload(
    item: dict[str, object], media: list[dict[str, object]], *, content_version: int
) -> dict[str, object]:
    channel_title = item["channel_title"]
    payload: dict[str, object] = {
        "postId": item["public_id"],
        "source": item["source_type"],
        "publishedAt": item["published_at"],
        "editedAt": item["last_source_edited_at"],
        "revision": item["revision_number"],
        "state": (
            "source-revised" if int(item["revision_number"]) > 1 else "published"
        ),
        "attribution": (
            {"channel": channel_title} if isinstance(channel_title, str) else None
        ),
        "blocks": _blocks(item["content_json"]),
        "media": [_media_payload(media_item) for media_item in media],
    }
    if content_version == 2 and item.get("content_format") == "rich_markdown_v1":
        raw_document = item.get("rich_document_json")
        if isinstance(raw_document, str):
            try:
                payload["document"] = json.loads(raw_document)
            except json.JSONDecodeError as error:
                raise RuntimeError("Stored rich news document is invalid") from error
    return payload


async def _get_news(request: web.Request) -> web.Response:
    course_ids, group_ids = _scope(request)
    if set(request.query) - {"limit", "cursor", "contentVersion"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры ленты новостей",
        )
    try:
        limit = int(request.query.get("limit", "20"))
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметр limit",
        ) from error
    cursor = request.query.get("cursor")
    content_version = request.query.get("contentVersion", "1")
    if (
        limit < 1
        or limit > 50
        or (cursor is not None and _PUBLIC_ID.fullmatch(cursor) is None)
        or content_version not in {"1", "2"}
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры ленты новостей",
        )

    def read(connection):
        rows = list_visible_posts(
            connection,
            course_ids=course_ids,
            group_ids=group_ids,
            cursor_public_id=cursor,
            now=_now(),
            limit=limit + 1,
        )
        visible_rows = rows[:limit]
        media = list_media_for_revisions(
            connection, tuple(int(item["revision_id"]) for item in visible_rows)
        )
        return visible_rows, media, len(rows) > limit

    rows, media_rows, has_more = await _factory(request).run_read_async(read)
    media_by_revision: dict[int, list[dict[str, object]]] = {}
    for item in media_rows:
        media_by_revision.setdefault(int(item["revision_id"]), []).append(item)
    items = [
        _post_payload(
            item,
            media_by_revision.get(int(item["revision_id"]), []),
            content_version=int(content_version),
        )
        for item in rows[:limit]
    ]
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": items,
            "nextCursor": items[-1]["postId"] if has_more and items else None,
            "requestId": request["request_id"],
        }
    )


async def _get_news_post(request: web.Request) -> web.Response:
    course_ids, group_ids = _scope(request)
    if set(request.query) - {"contentVersion"} or request.query.get(
        "contentVersion", "1"
    ) not in {"1", "2"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры публикации",
        )
    public_id = request.match_info["post_id"]
    if _PUBLIC_ID.fullmatch(public_id) is None:
        raise PwaApiError(
            status=404,
            code="news_post_not_found",
            message="Публикация не найдена",
        )

    def read(connection):
        post = get_visible_post_by_public_id(
            connection,
            public_id=public_id,
            course_ids=course_ids,
            group_ids=group_ids,
            now=_now(),
        )
        if post is None:
            return None, []
        media = list_media_for_revisions(connection, (int(post["revision_id"]),))
        return post, media

    post, media = await _factory(request).run_read_async(read)
    if post is None:
        raise PwaApiError(
            status=404,
            code="news_post_not_found",
            message="Публикация не найдена",
        )
    return web.json_response(
        {
            "schemaVersion": 1,
            "item": _post_payload(
                post,
                media,
                content_version=int(request.query.get("contentVersion", "1")),
            ),
            "requestId": request["request_id"],
        }
    )


for audience in ("student", "family"):
    news_routes.get(f"/{audience}/api/v1/news")(_get_news)
    news_routes.get(f"/{audience}/api/v1/news/{{post_id}}")(_get_news_post)


__all__ = ["news_routes"]
