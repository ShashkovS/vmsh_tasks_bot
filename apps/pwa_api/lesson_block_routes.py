"""Staff authoring endpoints for Rich Markdown before/after lesson blocks."""

from __future__ import annotations

from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.content_routes import (
    PWA_CONTENT_OBJECT_STORAGE,
    _authorize,
    _authorized_lesson_window_scope,
    _etag,
    _none_etag,
    _require_if_match,
)
from apps.pwa_api.errors import PwaApiError
from db_methods.pwa.content import ContentNotFound
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from helpers.pwa.rich_media import (
    MAX_RICH_MEDIA_BYTES,
    RichMediaCopyError,
    copy_rich_document_media,
    store_uploaded_rich_image,
)
from models.pwa.lesson_blocks import (
    LessonBlockInvariantError,
    LessonBlockNotFound,
    LessonBlockPosition,
    LessonBlockService,
    LessonBlockVersionConflict,
)
from models.pwa.lesson_rich_document import validate_lesson_rich_document


lesson_block_routes = web.RouteTableDef()


def _service(request: web.Request) -> LessonBlockService:
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(status=503, code="service_unavailable", message="Материалы занятий временно недоступны")
    return LessonBlockService(state.factory)


def _position(request: web.Request) -> LessonBlockPosition:
    try:
        return LessonBlockPosition(request.match_info["position"])
    except ValueError as error:
        raise PwaApiError(status=404, code="not_found", message="Блок занятия не найден") from error


async def _json(request: web.Request, fields: set[str]) -> dict[str, object]:
    try:
        value = await request.json()
    except Exception as error:
        raise PwaApiError(status=422, code="validation_error", message="Тело запроса должно быть JSON-объектом") from error
    if not isinstance(value, dict) or set(value) != fields:
        raise PwaApiError(status=422, code="validation_error", message="Проверьте поля формы", details={"required": sorted(fields)})
    return value


async def _copy_document_media(request: web.Request, document: object) -> dict[str, object]:
    checked = validate_lesson_rich_document(document)
    if not checked["media"]:
        return checked
    from apps.pwa_app import PWA_CONTENT_ASSET_CONVERTER

    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    converter = request.app.get(PWA_CONTENT_ASSET_CONVERTER)
    if storage is None or converter is None:
        raise PwaApiError(status=503, code="rich_media_unavailable", message="Загрузка картинок временно недоступна")
    try:
        copied, _media = await copy_rich_document_media(checked, storage=storage, converter=converter)
    except RichMediaCopyError as error:
        raise PwaApiError(status=422, code="rich_media_invalid", message="Не удалось безопасно сохранить картинку", details={"diagnostic": str(error)}) from error
    return copied


def _revision_payload(revision):
    if revision is None:
        return None
    return {"revisionId": revision.public_id, "revisionNumber": revision.revision_number, "markdown": revision.markdown, "document": revision.document, "createdAt": revision.created_at.isoformat().replace("+00:00", "Z")}


def _block_payload(block, revisions: dict[int, object]) -> dict[str, object]:
    return {
        "blockId": block.public_id,
        "position": block.position,
        "version": block.version,
        "draft": _revision_payload(revisions.get(block.draft_revision_id)),
        "published": _revision_payload(revisions.get(block.published_revision_id)),
        "publishedAt": None if block.published_at is None else block.published_at.isoformat().replace("+00:00", "Z"),
        "pending": _revision_payload(revisions.get(block.pending_revision_id)),
        "pendingMode": block.pending_mode,
        "scheduledAt": None if block.scheduled_at is None else block.scheduled_at.isoformat().replace("+00:00", "Z"),
        "etag": _etag(block.public_id, block.version),
    }


async def _invalidate(request: web.Request, group_lesson_public_id: str, *, staff_only: bool, reason: str) -> None:
    from apps.pwa_app import NATS_PWA_INVALIDATE, PWA_BROKER
    resources = [f"group-lessons/{group_lesson_public_id}/blocks/staff"]
    if not staff_only:
        resources.extend((f"group-lessons/{group_lesson_public_id}/blocks", "student-course-lessons", "family-worksheets"))
    try:
        await request.app[PWA_BROKER].publish(NATS_PWA_INVALIDATE, {"resources": resources, "reason": reason})
    except Exception:
        # The SQLite commit is authoritative; realtime is an idempotent hint.
        return


async def _authorized_staff_read_scope(request: web.Request):
    """Published reader projection is intentionally available to group readers."""

    # Reuse the content repository's canonical public-id lookup and scope check;
    # authoring endpoints above continue to use CONTENT_MANAGE.
    from apps.pwa_api.content_routes import _repository

    content_repository = _repository(request)
    content_scope = await content_repository.get_group_lesson_scope(
        request.match_info["group_lesson_id"]
    )
    _authorize(
        request,
        expected_audience=AuthAudience.STAFF,
        capability=Capability.GROUP_READ,
        scope=content_scope,
    )
    return content_scope


async def _uploaded_image(request: web.Request) -> bytes:
    if request.content_type != "multipart/form-data" or (request.content_length is not None and request.content_length > MAX_RICH_MEDIA_BYTES + 16_384):
        raise PwaApiError(status=422, code="validation_error", message="Загрузка должна содержать одну картинку не больше 10 МиБ")
    try:
        reader = await request.multipart()
    except (AssertionError, ValueError) as error:
        raise PwaApiError(status=422, code="validation_error", message="Не удалось разобрать форму картинки") from error
    part = await reader.next()
    if part is None or part.name != "image" or part.filename is None:
        raise PwaApiError(status=422, code="validation_error", message="Загрузите ровно один файл в поле image")
    chunks: list[bytes] = []
    size = 0
    while chunk := await part.read_chunk(64 * 1024):
        size += len(chunk)
        if size > MAX_RICH_MEDIA_BYTES:
            raise PwaApiError(status=413, code="payload_too_large", message="Картинка не должна быть больше 10 МиБ")
        chunks.append(chunk)
    if await reader.next() is not None:
        raise PwaApiError(status=422, code="validation_error", message="Загрузите ровно один файл в поле image")
    return b"".join(chunks)


def _translate(error: Exception) -> PwaApiError:
    if isinstance(error, PwaApiError):
        return error
    if isinstance(error, LessonBlockVersionConflict):
        return PwaApiError(status=409, code="version_conflict", message="Блок уже изменился. Обновите страницу.")
    if isinstance(error, (LessonBlockNotFound, ContentNotFound)):
        return PwaApiError(status=404, code="not_found", message="Блок занятия не найден")
    if isinstance(error, (LessonBlockInvariantError, RichMediaCopyError)):
        return PwaApiError(status=422, code="validation_error", message="Проверьте содержимое или настройки публикации", details={"diagnostic": str(error)})
    return PwaApiError(status=500, code="lesson_blocks_error", message="Не удалось обработать блок занятия")


@lesson_block_routes.get("/staff/api/v1/group-lessons/{group_lesson_id}/blocks")
async def get_staff_lesson_blocks(request: web.Request) -> web.Response:
    _repository, scope, _actor = await _authorized_lesson_window_scope(request)
    service = _service(request)
    try:
        blocks, records = await service.get_staff_state(scope.group_lesson_id)
        revisions = {record.id: record for record in records}
        by_position = {block.position: _block_payload(block, revisions) for block in blocks}
        return web.json_response({"groupLessonId": scope.group_lesson_public_id, "businessTimezone": scope.business_timezone, "before": by_position.get("before"), "after": by_position.get("after"), "requestId": request["request_id"]}, headers={"Cache-Control": "no-store"})
    except Exception as error:
        raise _translate(error) from error


@lesson_block_routes.put("/staff/api/v1/group-lessons/{group_lesson_id}/blocks/{position}/draft")
async def save_lesson_block_draft(request: web.Request) -> web.Response:
    payload = await _json(request, {"markdown", "document"})
    repository, scope, actor = await _authorized_lesson_window_scope(request)
    position = _position(request)
    if not isinstance(payload["markdown"], str):
        raise PwaApiError(status=422, code="validation_error", message="Markdown должен быть текстом")
    blocks = await _service(request).get_staff_blocks(scope.group_lesson_id)
    current = next((item for item in blocks if item.position == position.value), None)
    _require_if_match(request, _none_etag() if current is None else _etag(current.public_id, current.version))
    try:
        document = None if not payload["markdown"].strip() else await _copy_document_media(request, payload["document"])
        block, revision = await _service(request).save_draft(group_lesson_id=scope.group_lesson_id, position=position, expected_version=None if current is None else current.version, markdown=payload["markdown"], document=document, actor_user_id=actor)
    except Exception as error:
        raise _translate(error) from error
    await _invalidate(request, scope.group_lesson_public_id, staff_only=True, reason="lesson-block-draft-saved")
    response = web.json_response({"groupLessonId": scope.group_lesson_public_id, "block": _block_payload(block, {revision.id: revision}), "requestId": request["request_id"]})
    response.headers["ETag"] = _etag(block.public_id, block.version)
    return response


@lesson_block_routes.post("/staff/api/v1/group-lessons/{group_lesson_id}/blocks/{position}/publication")
async def publish_lesson_block(request: web.Request) -> web.Response:
    payload = await _json(request, {"revisionId", "mode", "scheduledAt"})
    _repository, scope, actor = await _authorized_lesson_window_scope(request)
    position = _position(request)
    if not isinstance(payload["revisionId"], str):
        raise PwaApiError(status=422, code="validation_error", message="Проверьте revision")
    blocks = await _service(request).get_staff_blocks(scope.group_lesson_id)
    current = next((item for item in blocks if item.position == position.value), None)
    _require_if_match(request, _none_etag() if current is None else _etag(current.public_id, current.version))
    scheduled_at = None
    if payload["scheduledAt"] is not None:
        try:
            scheduled_at = datetime.fromisoformat(str(payload["scheduledAt"]).replace("Z", "+00:00"))
            if scheduled_at.tzinfo is None:
                raise ValueError("scheduledAt must include UTC offset")
            scheduled_at = scheduled_at.astimezone(UTC)
        except ValueError as error:
            raise PwaApiError(status=422, code="validation_error", message="Время публикации некорректно") from error
    try:
        block = await _service(request).publish_revision(group_lesson_id=scope.group_lesson_id, position=position, expected_version=0 if current is None else current.version, revision_public_id=payload["revisionId"], mode=payload["mode"], scheduled_at=scheduled_at, actor_user_id=actor)
    except Exception as error:
        raise _translate(error) from error
    await _invalidate(request, scope.group_lesson_public_id, staff_only=False, reason="lesson-block-publication")
    response = web.json_response({"groupLessonId": scope.group_lesson_public_id, "blockId": block.public_id, "version": block.version, "requestId": request["request_id"]})
    response.headers["ETag"] = _etag(block.public_id, block.version)
    return response


@lesson_block_routes.delete("/staff/api/v1/group-lessons/{group_lesson_id}/blocks/{position}/publication")
async def hide_lesson_block(request: web.Request) -> web.Response:
    _repository, scope, actor = await _authorized_lesson_window_scope(request)
    position = _position(request)
    blocks = await _service(request).get_staff_blocks(scope.group_lesson_id)
    current = next((item for item in blocks if item.position == position.value), None)
    _require_if_match(request, _none_etag() if current is None else _etag(current.public_id, current.version))
    try:
        block = await _service(request).hide_block(group_lesson_id=scope.group_lesson_id, position=position, expected_version=0 if current is None else current.version, actor_user_id=actor)
    except Exception as error:
        raise _translate(error) from error
    await _invalidate(request, scope.group_lesson_public_id, staff_only=False, reason="lesson-block-hidden")
    response = web.json_response({"blockId": block.public_id, "version": block.version, "requestId": request["request_id"]})
    response.headers["ETag"] = _etag(block.public_id, block.version)
    return response


@lesson_block_routes.delete("/staff/api/v1/group-lessons/{group_lesson_id}/blocks/{position}/pending-publication")
async def cancel_lesson_block_publication(request: web.Request) -> web.Response:
    _repository, scope, actor = await _authorized_lesson_window_scope(request)
    position = _position(request)
    blocks = await _service(request).get_staff_blocks(scope.group_lesson_id)
    current = next((item for item in blocks if item.position == position.value), None)
    _require_if_match(request, _none_etag() if current is None else _etag(current.public_id, current.version))
    try:
        block = await _service(request).cancel_pending_publication(group_lesson_id=scope.group_lesson_id, position=position, expected_version=0 if current is None else current.version, actor_user_id=actor)
    except Exception as error:
        raise _translate(error) from error
    await _invalidate(request, scope.group_lesson_public_id, staff_only=True, reason="lesson-block-publication-cancelled")
    response = web.json_response({"blockId": block.public_id, "version": block.version, "requestId": request["request_id"]})
    response.headers["ETag"] = _etag(block.public_id, block.version)
    return response


@lesson_block_routes.post("/staff/api/v1/group-lessons/{group_lesson_id}/blocks/media/uploads")
async def upload_lesson_block_image(request: web.Request) -> web.Response:
    _repository, _scope, _actor = await _authorized_lesson_window_scope(request)
    data = await _uploaded_image(request)
    from apps.pwa_app import PWA_CONTENT_ASSET_CONVERTER
    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    converter = request.app.get(PWA_CONTENT_ASSET_CONVERTER)
    if storage is None or converter is None:
        raise PwaApiError(status=503, code="rich_media_unavailable", message="Загрузка картинок временно недоступна")
    try:
        image = await store_uploaded_rich_image(data, storage=storage, converter=converter)
    except RichMediaCopyError as error:
        raise PwaApiError(status=422, code="rich_media_upload_invalid", message="Картинка должна быть PNG, JPEG или WebP", details={"diagnostic": str(error)}) from error
    return web.json_response({"schemaVersion": 1, "image": image, "requestId": request["request_id"]}, status=201)


@lesson_block_routes.get("/staff/api/v1/group-lessons/{group_lesson_id}/blocks/published")
async def get_staff_published_lesson_blocks(request: web.Request) -> web.Response:
    scope = await _authorized_staff_read_scope(request)
    try:
        blocks = await _service(request).get_published_blocks(scope.group_lesson_id)
    except Exception as error:
        raise _translate(error) from error
    value = {"before": None, "after": None}
    for item in blocks:
        value[item.block.position] = {"blockId": item.block.public_id, "revisionId": item.revision.public_id, "position": item.block.position, "version": item.block.version, "publishedAt": item.block.published_at.isoformat().replace("+00:00", "Z"), "document": item.revision.document}
    return web.json_response({"groupLessonId": scope.group_lesson_public_id, **value, "requestId": request["request_id"]}, headers={"Cache-Control": "no-store"})


__all__ = ["lesson_block_routes"]
