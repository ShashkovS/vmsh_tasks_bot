"""Cookie-only Staff UI plus token-only MCP bridge; ai-review-assistant.md."""

import asyncio
import hashlib
import json

from aiohttp import web
from pydantic import ValidationError

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session, validate_request_boundary
from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from apps.pwa_api.student_results_routes import legacy_solutions_root
from apps.pwa_api.written_submission_routes import PWA_WRITTEN_ATTACHMENT_SERVICE
from db_methods.pwa import ai_review as db
from db_methods.pwa.reviews import (
    ReviewQueueNotFound,
    ReviewQueueForbidden,
    ReviewThreadChanged,
)
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG
from helpers.pwa.ai_review_images import MAX_IMAGE_BYTES, rasterize_svg
from helpers.pwa.review_composite import render_review_annotation_composite_png
from models.pwa import ai_review as ai, student_results as archive
from models.pwa.ai_review_contract import TOOLS
from models.pwa.auth import AuthAudience

routes = web.RouteTableDef()
PREFIX = "/staff/api/ai-review/v1"


def factory(request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="ai_review_unavailable",
            message="Предложения ИИ временно недоступны",
        )
    return state.factory


def translate(error):
    if isinstance(error, ai.AssistantError):
        return PwaApiError(
            status=error.status,
            code=error.code,
            message="Не удалось выполнить запрос AI-помощника",
        )
    if isinstance(error, (ReviewQueueNotFound, archive.ArchiveNotFound)):
        return PwaApiError(
            status=404,
            code="review_not_found",
            message="Работа или материал недоступны",
        )
    if isinstance(error, ReviewQueueForbidden):
        return PwaApiError(
            status=403, code="forbidden", message="Недостаточно прав для этой работы"
        )
    return PwaApiError(
        status=409, code="ai_context_changed", message="Материалы работы изменились"
    )


ERRORS = (
    ai.AssistantError,
    ReviewQueueNotFound,
    ReviewQueueForbidden,
    ReviewThreadChanged,
    archive.ArchiveNotFound,
)


async def body(request):
    if request.content_type != "application/json":
        raise PwaApiError(status=415, code="json_required", message="Нужен JSON")
    if request.content_length is not None and request.content_length > 512 * 1024:
        raise web.HTTPRequestEntityTooLarge(
            max_size=512 * 1024, actual_size=request.content_length
        )
    try:
        value = json.loads(await request.read())
    except (ValueError, UnicodeDecodeError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте данные запроса"
        ) from error
    if not isinstance(value, dict):
        raise PwaApiError(
            status=422, code="validation_error", message="Нужен JSON-объект"
        )
    return value


def response(value):
    return web.json_response(value, headers={"Cache-Control": "private, no-store"})


def staff(request):
    principal = authenticated_session(request).principal
    try:
        scope = ai.scope_for(principal)
    except ai.AssistantError as error:
        raise translate(error) from error
    return principal, scope


@routes.get("/staff/api/v1/ai-review/tokens")
async def tokens(request):
    principal, _ = staff(request)
    rows = await factory(request).run_read_async(
        lambda c: db.list_tokens(c, principal.account_public_id)
    )
    return response({"items": rows})


@routes.post("/staff/api/v1/ai-review/tokens")
async def create_token(request):
    principal, _ = staff(request)
    payload = await body(request)
    if set(payload) != {"name"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Укажите имя токена"
        )
    try:
        result = await factory(request).run_write_async(
            lambda c: ai.create_token(
                c,
                principal.account_public_id,
                payload["name"],
                credential_version=principal.credential_version,
            )
        )
    except ai.AssistantError as error:
        raise translate(error) from error
    return response(result)


@routes.delete("/staff/api/v1/ai-review/tokens/{token_id}")
async def revoke_token(request):
    principal, _ = staff(request)
    try:
        await factory(request).run_write_async(
            lambda c: ai.revoke_token(
                c, principal.account_public_id, request.match_info["token_id"]
            )
        )
    except ai.AssistantError as error:
        raise translate(error) from error
    return response({"revoked": True})


@routes.get("/staff/api/v1/review/ai-suggestions")
async def suggestions(request):
    _, scope = staff(request)
    if set(request.query) - {"caseId", "queueId", "cursor"} or bool(
        request.query.get("caseId")
    ) == bool(request.query.get("queueId")):
        raise PwaApiError(status=422, code="validation_error", message="Укажите работу")
    try:
        result = await factory(request).run_read_async(
            lambda c: db.read_snapshot(
                c,
                lambda snapshot: ai.list_suggestions(
                    snapshot,
                    scope,
                    legacy_solutions_root(request),
                    case_id=request.query.get("caseId"),
                    queue_id=request.query.get("queueId"),
                    cursor=request.query.get("cursor"),
                ),
            )
        )
    except ERRORS as error:
        raise translate(error) from error
    return response(result)


@routes.post(PREFIX + "/tools/{tool}")
async def call_tool(request):
    validate_request_boundary(request, audience=AuthAudience.STAFF, expects_json=True)
    return await execute_tool(
        request, bearer_secret(request), request.match_info["tool"], await body(request)
    )


def bearer_secret(request):
    headers = request.headers.getall("Authorization", [])
    header = headers[0] if len(headers) == 1 else ""
    return header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""


async def execute_tool(request, secret, tool, value):
    """Shared authorization/domain path for stdio bridge and remote MCP."""
    if tool not in TOOLS:
        raise PwaApiError(
            status=404, code="unknown_tool", message="Неизвестный инструмент"
        )
    try:
        payload = TOOLS[tool].model_validate(value).model_dump()
    except ValidationError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры инструмента",
        ) from error
    root = legacy_solutions_root(request)

    def execute(connection):
        token, _, scope = ai.authenticate(connection, secret)
        if tool == "submit_ai_suggestion":
            return ai.submit(connection, scope, token, payload, root)
        return ai.read_tool(connection, scope, root, tool, payload)

    try:
        operation = (
            factory(request).run_write_async
            if tool == "submit_ai_suggestion"
            else factory(request).run_read_async
        )
        result = await operation(
            execute
            if tool == "submit_ai_suggestion"
            else lambda c: db.read_snapshot(c, execute)
        )
    except ERRORS as error:
        raise translate(error) from error
    if tool in {"get_review_image", "get_lesson_material_image"}:
        return await image_response(request, result, root)
    return response(result)


async def image_response(request, result, root):
    try:
        if "legacyPath" in result:
            path = archive.legacy_path(root, result["legacyPath"])
            if path is None or path.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("image_missing")
            mime = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }.get(path.suffix.lower())
            if mime is None:
                raise ValueError("unsupported_image")
            data = await asyncio.to_thread(path.read_bytes)
        else:
            metadata = result["storage"]
            if metadata["byte_size"] > MAX_IMAGE_BYTES:
                raise ValueError("image_too_large")
            if "public_id" in metadata:
                storage = request.app[PWA_CONTENT_OBJECT_STORAGE]
            else:
                storage = request.app[PWA_WRITTEN_ATTACHMENT_SERVICE].storage
            data = await storage.get(metadata["object_key"])
            if (
                len(data) != metadata["byte_size"]
                or hashlib.sha256(data).hexdigest() != metadata["sha256"]
            ):
                raise ValueError("image_corrupt")
            mime = metadata["media_type"]
            executable = getattr(request.app[RUNTIME_CONFIG], "magick_path", None)
            if result.get("annotation"):
                annotation = result["annotation"]
                data = await render_review_annotation_composite_png(
                    source_webp=data,
                    rotation=annotation["rotation"],
                    marks=annotation["marks"],
                    magick_path=executable or "magick",
                )
                mime = "image/png"
            elif mime == "image/svg+xml":
                if not executable:
                    raise ValueError("image_preview_unavailable")
                data = await rasterize_svg(data, executable)
                mime = "image/png"
        if (
            mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}
            or len(data) > MAX_IMAGE_BYTES
        ):
            raise ValueError("unsupported_image")
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        raise PwaApiError(
            status=404, code="image_unavailable", message="Изображение недоступно"
        ) from error
    return web.Response(
        body=data,
        content_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
