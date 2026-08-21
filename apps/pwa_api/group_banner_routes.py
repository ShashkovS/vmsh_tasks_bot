"""Authenticated group banners for Student, Family and admin Staff."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.group_banners import (
    find_group_id,
    list_current_group_banners,
    list_group_banners,
    replace_group_banner_media,
)
from helpers.pwa.rich_media import RichMediaCopyError, copy_rich_document_media
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.group_banners import (
    GroupBannerConflict,
    InvalidGroupBanner,
    cancel_banner,
    create_group_banner,
    edit_group_banner,
)
from models.pwa.rich_document import InvalidRichDocument, validate_rich_document


group_banner_routes = web.RouteTableDef()
BannerInvalidator = Callable[[str], Awaitable[None]]
PWA_BANNER_INVALIDATOR = web.AppKey("pwa_banner_invalidator", BannerInvalidator)
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_ETAG = re.compile(r'^"([a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?):v([1-9]\d*)"$')


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="group_banners_unavailable",
            message="Объявления временно недоступны",
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
            message="Управлять объявлениями может только администратор",
        )
    return principal.linked_user_id


def _audience_scope(request: web.Request) -> tuple[str, tuple[str, ...]]:
    authenticated = authenticated_session(request)
    audience = authenticated.principal.audience
    if audience not in {AuthAudience.STUDENT, AuthAudience.FAMILY}:
        raise PwaApiError(status=403, code="forbidden", message="Недостаточно прав")
    group_ids = tuple(
        sorted(
            {
                group.group_id
                for enrollment in authenticated.course_enrollments
                if enrollment.enrollment_status == "active"
                for group in enrollment.allowed_groups
            }
        )
    )
    return audience.value, group_ids


def _payload(item: dict[str, object], *, content_version: int = 1) -> dict[str, object]:
    document: object | None = None
    if item.get("content_format") == "rich_markdown_v1" and isinstance(
        item.get("rich_document_json"), str
    ):
        try:
            document = json.loads(str(item["rich_document_json"]))
        except json.JSONDecodeError:
            document = None
    payload: dict[str, object] = {
        "bannerId": item["public_id"],
        "group": {
            "groupId": item["group_public_id"],
            "name": item["group_name"],
            "courseId": item["course_public_id"],
            "courseName": item["course_name"],
        },
        "audience": item["audience"],
        "html": item["html_sanitized"],
        "startsAt": item["starts_at"],
        "endsAt": item["ends_at"],
        "priority": item["priority"],
        "dismissible": bool(item["dismissible"]),
        "status": item["status"],
        "version": item["version"],
    }
    if content_version == 2:
        payload["markdown"] = item.get("markdown_source") if document is not None else None
        payload["document"] = document
    return payload


def _json_body(body: object, expected: set[str]) -> dict[str, object]:
    if (
        not isinstance(body, dict)
        or set(body) != expected | {"schemaVersion"}
        or body.get("schemaVersion") != 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля объявления",
        )
    return body


async def _read_json(request: web.Request) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        body = json.loads(await request.read())
        if not isinstance(body, dict):
            raise PwaApiError(
                status=422, code="validation_error", message="Проверьте поля объявления"
            )
        return body
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля объявления",
        ) from error


async def _copy_document_media(
    request: web.Request, document: object
) -> tuple[dict[str, object], list[dict[str, object]]]:
    validated = validate_rich_document(document)
    if not validated["media"]:
        return validated, []
    from apps.pwa_app import PWA_CONTENT_ASSET_CONVERTER
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE

    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    converter = request.app.get(PWA_CONTENT_ASSET_CONVERTER)
    if storage is None or converter is None:
        raise PwaApiError(
            status=503,
            code="rich_media_unavailable",
            message="Загрузка картинок временно недоступна",
        )
    return await copy_rich_document_media(
        validated, storage=storage, converter=converter
    )


def _version(request: web.Request, public_id: str) -> int:
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
            message="Объявление уже изменилось. Обновите список.",
        )
    return int(match.group(2))


async def _active(request: web.Request) -> web.Response:
    if set(request.query) - {"contentVersion"} or request.query.get(
        "contentVersion", "1"
    ) not in {"1", "2"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    audience, group_ids = _audience_scope(request)
    rows = await _factory(request).run_read_async(
        lambda connection: list_current_group_banners(
            connection, group_ids=group_ids, audience=audience, now=_now()
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [
                _payload(item, content_version=int(request.query.get("contentVersion", "1")))
                for item in rows
            ],
            "requestId": request["request_id"],
        }
    )


@group_banner_routes.get("/staff/api/v1/group-banners")
async def list_banners(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if set(request.query) - {"groupId", "status", "limit", "contentVersion"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    group_id = request.query.get("groupId")
    status = request.query.get("status")
    try:
        limit = int(request.query.get("limit", "100"))
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметр limit"
        ) from error
    if (
        (group_id is not None and _PUBLIC_ID.fullmatch(group_id) is None)
        or status not in {None, "active", "cancelled"}
        or not 1 <= limit <= 200
        or request.query.get("contentVersion", "1") not in {"1", "2"}
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    rows = await _factory(request).run_read_async(
        lambda connection: list_group_banners(
            connection, group_public_id=group_id, status=status, limit=limit
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [
                _payload(item, content_version=int(request.query.get("contentVersion", "1")))
                for item in rows
            ],
            "requestId": request["request_id"],
        }
    )


@group_banner_routes.post("/staff/api/v1/group-banners")
async def create_banner(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    body = await _read_json(request)
    v1_fields = {
        "schemaVersion", "groupId", "audience", "html", "startsAt", "endsAt", "priority", "dismissible"
    }
    v2_fields = {
        "schemaVersion", "groupId", "audience", "markdown", "document", "startsAt", "endsAt", "priority", "dismissible"
    }
    is_v2 = body.get("schemaVersion") == 2
    if set(body) != (v2_fields if is_v2 else v1_fields) or body.get("schemaVersion") not in {1, 2}:
        raise PwaApiError(status=422, code="validation_error", message="Проверьте поля объявления")
    try:
        document, media_manifest = (
            await _copy_document_media(request, body["document"])
            if is_v2
            else (None, [])
        )
    except (InvalidRichDocument, RichMediaCopyError) as error:
        raise PwaApiError(
            status=422,
            code="rich_markdown_validation_error",
            message="Проверьте Markdown и внешние картинки",
            details={"diagnostic": str(error)},
        ) from error

    def write(connection):
        group_id = find_group_id(connection, str(body["groupId"]))
        if group_id is None:
            return None
        item = create_group_banner(
            connection,
            public_id=f"banner.{uuid.uuid4().hex}",
            group_id=group_id,
            audience=body["audience"],
            html_source=body["html"] if not is_v2 else "<p>Rich Markdown</p>",
            starts_at=body["startsAt"],
            ends_at=body["endsAt"],
            priority=body["priority"],
            dismissible=body["dismissible"],
            actor_user_id=actor_user_id,
            now=_now(),
            markdown=body["markdown"] if is_v2 else None,
            document=document,
        )
        if media_manifest:
            replace_group_banner_media(
                connection, banner_id=int(item["id"]), media=media_manifest, now=_now()
            )
        return item

    try:
        item = await _factory(request).run_write_async(write)
    except (InvalidGroupBanner, TypeError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля объявления"
        ) from error
    if item is None:
        raise PwaApiError(
            status=404, code="group_not_found", message="Группа не найдена"
        )
    await request.app[PWA_BANNER_INVALIDATOR]("group-banner-created")
    response = web.json_response(
        {
            "schemaVersion": 1,
            "item": _payload(item, content_version=2 if is_v2 else 1),
            "requestId": request["request_id"],
        },
        status=201,
    )
    response.headers["ETag"] = f'"{item["public_id"]}:v{item["version"]}"'
    return response


@group_banner_routes.patch("/staff/api/v1/group-banners/{banner_id}")
async def update_banner(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = request.match_info["banner_id"]
    if _PUBLIC_ID.fullmatch(public_id) is None:
        raise PwaApiError(
            status=404, code="banner_not_found", message="Объявление не найдено"
        )
    expected_version = _version(request, public_id)
    body = await _read_json(request)
    v1_fields = {"schemaVersion", "audience", "html", "startsAt", "endsAt", "priority", "dismissible"}
    v2_fields = {"schemaVersion", "audience", "markdown", "document", "startsAt", "endsAt", "priority", "dismissible"}
    is_v2 = body.get("schemaVersion") == 2
    if set(body) != (v2_fields if is_v2 else v1_fields) or body.get("schemaVersion") not in {1, 2}:
        raise PwaApiError(status=422, code="validation_error", message="Проверьте поля объявления")
    try:
        document, media_manifest = (
            await _copy_document_media(request, body["document"])
            if is_v2
            else (None, [])
        )
    except (InvalidRichDocument, RichMediaCopyError) as error:
        raise PwaApiError(
            status=422,
            code="rich_markdown_validation_error",
            message="Проверьте Markdown и внешние картинки",
            details={"diagnostic": str(error)},
        ) from error
    try:
        def write(connection):
            item = edit_group_banner(
                connection,
                public_id=public_id,
                expected_version=expected_version,
                audience=body["audience"],
                html_source=body["html"] if not is_v2 else "<p>Rich Markdown</p>",
                starts_at=body["startsAt"],
                ends_at=body["endsAt"],
                priority=body["priority"],
                dismissible=body["dismissible"],
                actor_user_id=actor_user_id,
                now=_now(),
                markdown=body["markdown"] if is_v2 else None,
                document=document,
            )
            replace_group_banner_media(
                connection, banner_id=int(item["id"]), media=media_manifest, now=_now()
            )
            return item
        item = await _factory(request).run_write_async(write)
    except (InvalidGroupBanner, TypeError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля объявления"
        ) from error
    except GroupBannerConflict as error:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Объявление уже изменилось. Обновите список.",
        ) from error
    await request.app[PWA_BANNER_INVALIDATOR]("group-banner-updated")
    response = web.json_response(
        {
            "schemaVersion": 1,
            "item": _payload(item, content_version=2 if is_v2 else 1),
            "requestId": request["request_id"],
        }
    )
    response.headers["ETag"] = f'"{item["public_id"]}:v{item["version"]}"'
    return response


@group_banner_routes.post("/staff/api/v1/group-banners/{banner_id}/cancel")
async def cancel_group_banner_route(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    public_id = request.match_info["banner_id"]
    if _PUBLIC_ID.fullmatch(public_id) is None:
        raise PwaApiError(
            status=404, code="banner_not_found", message="Объявление не найдено"
        )
    expected_version = _version(request, public_id)
    body = await _read_json(request)
    if set(body) != {"schemaVersion"} or body.get("schemaVersion") != 1:
        raise PwaApiError(status=422, code="validation_error", message="Проверьте поля объявления")
    try:
        item = await _factory(request).run_write_async(
            lambda connection: cancel_banner(
                connection,
                public_id=public_id,
                expected_version=expected_version,
                actor_user_id=actor_user_id,
                now=_now(),
            )
        )
    except GroupBannerConflict as error:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Объявление уже изменилось. Обновите список.",
        ) from error
    await request.app[PWA_BANNER_INVALIDATOR]("group-banner-cancelled")
    return web.json_response(
        {"schemaVersion": 1, "item": _payload(item), "requestId": request["request_id"]}
    )


for audience in ("student", "family"):
    group_banner_routes.get(f"/{audience}/api/v1/banners/active")(_active)


__all__ = ["PWA_BANNER_INVALIDATOR", "group_banner_routes"]
