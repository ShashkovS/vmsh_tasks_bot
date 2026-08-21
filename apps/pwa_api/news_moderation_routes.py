"""Admin-only visibility controls for mirrored news."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.audit import insert_audit_event
from db_methods.pwa.news_moderation import list_news_for_moderation
from db_methods.pwa.news import insert_media
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.local_news import (
    InvalidLocalNews,
    LocalNewsConflict,
    LocalNewsNotFound,
    LocalNewsOwnerNotFound,
    LocalNewsPublicationTimeLocked,
    create_local_news,
    edit_local_news,
    sync_scheduled_local_news_notifications,
)
from models.pwa.news_moderation import (
    InvalidNewsVisibility,
    NewsPostNotFound,
    NewsVisibilityConflict,
    change_news_visibility,
    reconcile_news_source_state,
)
from models.pwa.news_notifications import create_news_notifications
from models.pwa.rich_document import InvalidRichDocument, validate_rich_document
from helpers.pwa.rich_media import RichMediaCopyError, copy_rich_document_media


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


def _payload(
    item: dict[str, object], *, now: str, content_version: int = 1
) -> dict[str, object]:
    editable_text = str(item["text_plain"])
    if item["source_type"] == "local" and isinstance(
        item.get("source_payload_json"), str
    ):
        try:
            source_payload = json.loads(str(item["source_payload_json"]))
        except json.JSONDecodeError:
            source_payload = None
        if isinstance(source_payload, dict) and isinstance(
            source_payload.get("markdown"), str
        ):
            editable_text = source_payload["markdown"]
    rich_document: object | None = None
    if item.get("content_format") == "rich_markdown_v1" and isinstance(
        item.get("rich_document_json"), str
    ):
        try:
            rich_document = json.loads(str(item["rich_document_json"]))
        except json.JSONDecodeError:
            rich_document = None
    payload: dict[str, object] = {
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
        "editableText": editable_text if item["source_type"] == "local" else None,
        "mediaCount": item["media_count"],
        "visibility": item["visibility_state"],
        "moderationReason": item["moderation_reason"],
        "visibilityUpdatedAt": item["visibility_updated_at"],
        "isScheduled": (
            item["source_type"] == "local"
            and item["visibility_state"] == "visible"
            and str(item["published_at"]) > now
        ),
        "version": item["visibility_version"],
    }
    # Keep existing strict v1 Staff clients working. Rich authoring fields are
    # opt-in with contentVersion=2; see Phase 8 Rich Markdown API contract.
    if content_version == 2:
        payload["markdown"] = editable_text if rich_document is not None else None
        payload["document"] = rich_document
    return payload


async def _copy_document_media(
    request: web.Request, document: object
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Acquire rich media before the SQLite transaction (Phase 8 Rich Markdown v1)."""

    validated = validate_rich_document(document)
    if not validated["media"]:
        return validated, []
    # These keys are owned by pwa_app's content startup. Importing lazily avoids
    # a route/app factory import cycle while retaining the one shared storage.
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


@news_moderation_routes.get("/staff/api/v1/news")
async def list_news(request: web.Request) -> web.Response:
    _admin_user_id(request)
    if set(request.query) - {"state", "limit", "contentVersion"}:
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
    content_version = request.query.get("contentVersion", "1")
    if (
        (state is not None and state not in _STATES)
        or not 1 <= limit <= 200
        or content_version not in {"1", "2"}
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте параметры списка"
        )
    rows = await _factory(request).run_read_async(
        lambda connection: list_news_for_moderation(
            connection, state=state, limit=limit
        )
    )
    now = _now()
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [
                _payload(item, now=now, content_version=int(content_version))
                for item in rows
            ],
            "requestId": request["request_id"],
        }
    )


@news_moderation_routes.post("/staff/api/v1/news/local")
async def create_local_publication(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    principal = authenticated_session(request).principal
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422, code="validation_error", message="Тело запроса должно быть JSON"
        )
    try:
        body = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля публикации",
        ) from error
    v1_fields = {"schemaVersion", "ownerType", "ownerId", "text", "publishedAt"}
    v2_fields = {
        "schemaVersion",
        "ownerType",
        "ownerId",
        "markdown",
        "document",
        "publishedAt",
    }
    is_v2 = isinstance(body, dict) and body.get("schemaVersion") == 2
    if (
        not isinstance(body, dict)
        or set(body) != (v2_fields if is_v2 else v1_fields)
        or body.get("schemaVersion") not in {1, 2}
        or not isinstance(body.get("ownerId"), str)
        or _PUBLIC_ID.fullmatch(body["ownerId"]) is None
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля публикации",
        )
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
    now = _now()

    def write(connection):
        created = create_local_news(
            connection,
            owner_type=body["ownerType"],
            owner_public_id=body["ownerId"],
            text=body["markdown"] if is_v2 else body["text"],
            published_at=body["publishedAt"],
            actor_user_id=actor_user_id,
            now=now,
            document=document,
        )
        if media_manifest:
            insert_media(
                connection,
                revision_id=int(created["revision_id"]),
                media=media_manifest,
                now=now,
            )
        create_news_notifications(
            connection,
            post_id=int(created["post_id"]),
            now=now,
            deliver_after=str(created["published_at"]),
        )
        items = list_news_for_moderation(
            connection,
            state=None,
            limit=1,
            public_id=str(created["public_id"]),
        )
        assert len(items) == 1
        item = items[0]
        insert_audit_event(
            connection,
            public_id=f"audit.{uuid.uuid4().hex}",
            actor_user_id=actor_user_id,
            actor_account_public_id=principal.account_public_id,
            audience="staff",
            action="news_local.created",
            object_type="news_post",
            object_id=str(created["public_id"]),
            request_id=request["request_id"],
            before_json=None,
            after_json=json.dumps(
                {
                    "source": "local",
                    "ownerType": item["owner_type"],
                    "ownerId": item["owner_public_id"],
                    "publishedAt": item["published_at"],
                    "visibility": item["visibility_state"],
                    "version": item["visibility_version"],
                },
                ensure_ascii=False,
            ),
            occurred_at=now,
        )
        return item

    try:
        item = await _factory(request).run_write_async(write)
    except LocalNewsOwnerNotFound as error:
        raise PwaApiError(
            status=404,
            code="news_owner_not_found",
            message="Курс или группа не найдены",
        ) from error
    except InvalidLocalNews as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте текст и время публикации",
        ) from error

    await request.app[PWA_NEWS_INVALIDATOR]("local-news-created")
    response = web.json_response(
        {
            "schemaVersion": 1,
            "item": _payload(item, now=now, content_version=2 if is_v2 else 1),
            "requestId": request["request_id"],
        },
        status=201,
    )
    response.headers["ETag"] = f'"{item["public_id"]}:v{item["visibility_version"]}"'
    return response


@news_moderation_routes.patch("/staff/api/v1/news/{post_id}/local")
async def edit_local_publication(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    principal = authenticated_session(request).principal
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
            status=422,
            code="validation_error",
            message="Проверьте текст и время публикации",
        ) from error
    v1_fields = ({"schemaVersion", "text"}, {"schemaVersion", "text", "publishedAt"})
    v2_fields = (
        {"schemaVersion", "markdown", "document"},
        {"schemaVersion", "markdown", "document", "publishedAt"},
    )
    is_v2 = isinstance(body, dict) and body.get("schemaVersion") == 2
    if (
        not isinstance(body, dict)
        or set(body) not in (v2_fields if is_v2 else v1_fields)
        or body.get("schemaVersion") not in {1, 2}
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте текст и время публикации",
        )
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
    now = _now()

    def write(connection):
        before_rows = list_news_for_moderation(
            connection, state=None, limit=1, public_id=public_id
        )
        changed = edit_local_news(
            connection,
            public_id=public_id,
            expected_version=int(match.group(2)),
            text=body["markdown"] if is_v2 else body["text"],
            published_at=body.get("publishedAt"),
            actor_user_id=actor_user_id,
            now=now,
            document=document,
        )
        after_rows = list_news_for_moderation(
            connection, state=None, limit=1, public_id=public_id
        )
        if len(before_rows) != 1 or len(after_rows) != 1:
            raise LocalNewsNotFound
        before = before_rows[0]
        item = after_rows[0]
        if changed:
            if media_manifest:
                # The freshly created immutable revision is selected by the
                # moderation projection; lookup its id without exposing it.
                revision_id = connection.execute(
                    "SELECT id FROM news_revisions WHERE post_id = "
                    "(SELECT id FROM news_posts WHERE public_id = ?) "
                    "ORDER BY revision_number DESC LIMIT 1",
                    (public_id,),
                ).fetchone()["id"]
                insert_media(
                    connection,
                    revision_id=int(revision_id),
                    media=media_manifest,
                    now=now,
                )
            insert_audit_event(
                connection,
                public_id=f"audit.{uuid.uuid4().hex}",
                actor_user_id=actor_user_id,
                actor_account_public_id=principal.account_public_id,
                audience="staff",
                action="news_local.updated",
                object_type="news_post",
                object_id=public_id,
                request_id=request["request_id"],
                before_json=json.dumps(
                    {
                        "publishedAt": before["published_at"],
                        "revision": before["revision_number"],
                        "version": before["visibility_version"],
                    }
                ),
                after_json=json.dumps(
                    {
                        "publishedAt": item["published_at"],
                        "revision": item["revision_number"],
                        "version": item["visibility_version"],
                    }
                ),
                occurred_at=now,
            )
        return item

    try:
        item = await _factory(request).run_write_async(write)
    except LocalNewsNotFound as error:
        raise PwaApiError(
            status=404, code="news_post_not_found", message="Публикация не найдена"
        ) from error
    except LocalNewsConflict as error:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Публикация уже изменилась. Обновите список.",
        ) from error
    except LocalNewsPublicationTimeLocked as error:
        raise PwaApiError(
            status=409,
            code="local_news_publication_time_locked",
            message="У уже опубликованной новости можно исправить текст, но не время",
        ) from error
    except InvalidLocalNews as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте текст и время публикации",
        ) from error

    await request.app[PWA_NEWS_INVALIDATOR]("local-news-updated")
    response = web.json_response(
        {
            "schemaVersion": 1,
            "item": _payload(item, now=_now(), content_version=2 if is_v2 else 1),
            "requestId": request["request_id"],
        }
    )
    response.headers["ETag"] = f'"{public_id}:v{item["visibility_version"]}"'
    return response


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
    now = _now()

    def write(connection):
        item = change_news_visibility(
            connection,
            public_id=public_id,
            expected_version=int(match.group(2)),
            target_state=body["state"],
            reason=body["reason"],
            actor_user_id=actor_user_id,
            now=now,
        )
        sync_scheduled_local_news_notifications(
            connection,
            public_id=public_id,
            now=now,
        )
        return item

    try:
        item = await _factory(request).run_write_async(write)
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
            "item": _payload(item, now=_now()),
            "requestId": request["request_id"],
        }
    )
    response.headers["ETag"] = f'"{public_id}:v{item["visibility_version"]}"'
    return response


def _source_audit_values(
    item: dict[str, object], *, reason: str | None = None
) -> dict[str, object]:
    values = {
        "source": item["source_type"],
        "ownerType": ("course" if item["owner_type"] == "course" else "group"),
        "ownerId": item["owner_public_id"],
        "visibility": item["visibility_state"],
        "sourceDeletedAt": item["source_deleted_at"],
        "version": item["visibility_version"],
    }
    if reason is not None:
        values["reconciliationReason"] = reason
    return values


@news_moderation_routes.patch("/staff/api/v1/news/{post_id}/source-state")
async def reconcile_source_state(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    principal = authenticated_session(request).principal
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
            message="Обновите данные перед сверкой",
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
            status=422, code="validation_error", message="Проверьте поля сверки"
        ) from error
    if (
        not isinstance(body, dict)
        or set(body) != {"schemaVersion", "sourceState", "reason"}
        or body.get("schemaVersion") != 1
        or body.get("sourceState") not in {"deleted", "present"}
        or not isinstance(body.get("reason"), str)
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте поля сверки"
        )
    reason = body["reason"].strip()
    if not reason or len(reason) > 500:
        raise PwaApiError(
            status=422, code="validation_error", message="Укажите краткую причину"
        )
    source_state = body["sourceState"]
    now = _now()

    def write(connection):
        before, item = reconcile_news_source_state(
            connection,
            public_id=public_id,
            expected_version=int(match.group(2)),
            source_state=source_state,
            actor_user_id=actor_user_id,
            now=now,
        )
        insert_audit_event(
            connection,
            public_id=f"audit.{uuid.uuid4().hex}",
            actor_user_id=actor_user_id,
            actor_account_public_id=principal.account_public_id,
            audience="staff",
            action=(
                "news_source.marked_deleted"
                if source_state == "deleted"
                else "news_source.marked_present"
            ),
            object_type="news_post",
            object_id=public_id,
            request_id=request["request_id"],
            before_json=json.dumps(_source_audit_values(before), ensure_ascii=False),
            after_json=json.dumps(
                _source_audit_values(item, reason=reason), ensure_ascii=False
            ),
            occurred_at=now,
        )
        return item

    try:
        item = await _factory(request).run_write_async(write)
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
            code="news_source_state_not_allowed",
            message="Состояние источника уже изменилось или недоступно для этого поста",
        ) from error

    await request.app[PWA_NEWS_INVALIDATOR]("news-source-reconciled")
    response = web.json_response(
        {
            "schemaVersion": 1,
            "item": _payload(item, now=_now()),
            "requestId": request["request_id"],
        }
    )
    response.headers["ETag"] = f'"{public_id}:v{item["visibility_version"]}"'
    return response


__all__ = ["PWA_NEWS_INVALIDATOR", "news_moderation_routes"]
