"""Staff uploads/public filesystem reads; docs/rich-file-attachments.md."""

from __future__ import annotations

import asyncio
import hashlib

from aiohttp import BodyPartReader, web

from apps.pwa_api.content_routes import (
    PWA_CONTENT_OBJECT_STORAGE,
    _authorized_lesson_window_scope,
    _translate_content_errors,
)
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.news_moderation_routes import _admin_user_id
from helpers.object_storage import (
    LocalObjectStorage,
    ObjectStorageOperationError,
    StoragePathError,
)
from helpers.pwa.rich_files import store_uploaded_rich_file
from models.pwa.rich_files import (
    MAX_RICH_FILE_BYTES,
    InvalidRichFile,
    rich_file_key,
    rich_file_mime_type,
    rich_file_name,
)


rich_file_routes = web.RouteTableDef()


def _invalid_file() -> PwaApiError:
    return PwaApiError(
        status=422,
        code="rich_file_invalid",
        message="Выберите непустой документ или архив поддерживаемого формата с именем до 255 байт",
    )


def _too_large() -> PwaApiError:
    return PwaApiError(
        status=413,
        code="payload_too_large",
        message="Файл не должен быть больше 50 МиБ",
    )


async def _uploaded_file(request: web.Request) -> tuple[bytes, str]:
    if request.content_type != "multipart/form-data":
        raise _invalid_file()
    if (
        request.content_length is not None
        and request.content_length > MAX_RICH_FILE_BYTES + 16_384
    ):
        raise _too_large()
    try:
        reader = await request.multipart()
        part = await reader.next()
        if (
            not isinstance(part, BodyPartReader)
            or part.name != "file"
            or part.filename is None
        ):
            raise _invalid_file()
        filename = rich_file_name(part.filename)
        chunks: list[bytes] = []
        size = 0
        while chunk := await part.read_chunk(64 * 1024):
            size += len(chunk)
            if size > MAX_RICH_FILE_BYTES:
                raise _too_large()
            chunks.append(chunk)
        if not size or await reader.next() is not None:
            raise _invalid_file()
    except (AssertionError, ValueError) as error:
        raise _invalid_file() from error
    return b"".join(chunks), filename


async def _upload(request: web.Request) -> web.Response:
    data, filename = await _uploaded_file(request)
    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    if storage is None:
        raise PwaApiError(
            status=503,
            code="rich_files_unavailable",
            message="Загрузка файлов временно недоступна",
        )
    try:
        uploaded = await store_uploaded_rich_file(data, filename, storage=storage)
    except InvalidRichFile as error:
        raise _invalid_file() from error
    except ObjectStorageOperationError, StoragePathError, OSError:
        raise PwaApiError(
            status=503,
            code="rich_files_unavailable",
            message="Загрузка файлов временно недоступна",
        ) from None
    return web.json_response(
        {"schemaVersion": 1, "file": uploaded, "requestId": request["request_id"]},
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@rich_file_routes.post("/staff/api/v1/rich-media/files/uploads")
async def upload_staff_rich_file(request: web.Request) -> web.Response:
    _admin_user_id(request)
    return await _upload(request)


@rich_file_routes.post(
    "/staff/api/v1/group-lessons/{group_lesson_id}/blocks/files/uploads"
)
@_translate_content_errors
async def upload_lesson_rich_file(request: web.Request) -> web.Response:
    await _authorized_lesson_window_scope(request)
    return await _upload(request)


@rich_file_routes.get("/pwa-rich-files/{sha256}/{filename}")
async def read_local_rich_file(request: web.Request) -> web.Response:
    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    if not isinstance(storage, LocalObjectStorage):
        raise web.HTTPNotFound()
    digest = request.match_info["sha256"]
    filename = request.match_info["filename"]
    try:
        key = rich_file_key(digest, filename)
        data = await storage.get(key)
    except InvalidRichFile, StoragePathError, FileNotFoundError:
        raise web.HTTPNotFound() from None
    actual_digest = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())
    if actual_digest != digest:
        raise web.HTTPInternalServerError(text="File integrity check failed")
    return web.Response(
        body=data,
        headers={
            "Content-Type": rich_file_mime_type(filename),
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"sha256-{digest}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
