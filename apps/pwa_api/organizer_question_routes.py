"""Organizer HTTP API; authoritative design: vmshpwa/docs/organizer-questions.md."""

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.content import AssetConversionError
from helpers.object_storage import ObjectStorageOperationError
from models.pwa import organizer_questions as domain
from db_methods.pwa import organizer_questions as db

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)
MAX_PHOTO_BYTES = 25 * 1024 * 1024


def principal(request):
    p = authenticated_session(request).principal
    if p.audience.value != request.match_info["audience"] or (
        p.audience.value == "staff" and not p.is_global_admin
    ):
        raise PwaApiError(status=403, code="forbidden", message="Обращение недоступно")
    return p


async def run(request, fn, write=False):
    p = principal(request)
    factory = request.app[PWA_DATABASE].factory
    try:
        return await (factory.run_write_async if write else factory.run_read_async)(
            lambda c: fn(c, p)
        )
    except domain.OrganizerError as error:
        code = error.code
        status = {
            "forbidden": 403,
            "not_found": 404,
            "validation_error": 422,
            "idempotency_conflict": 409,
        }[code]
        message = {
            "forbidden": "Обращение недоступно",
            "not_found": "Обращение или фотография не найдены",
            "validation_error": "Проверьте текст и фотографии",
            "idempotency_conflict": "Эта отправка уже сохранена с другими данными",
        }[code]
        raise PwaApiError(status=status, code=code, message=message) from error


def response(request, value):
    return web.json_response(
        dict(schemaVersion=1, requestId=request["request_id"], **value),
        headers={"Cache-Control": "private, no-store"},
    )


def cursor(request, default):
    try:
        value = int(request.query.get("cursor", str(default)))
        if not 0 <= value <= 2**63 - 1:
            raise ValueError()
        return value
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректная страница"
        ) from error


async def body(request):
    if request.content_type != "application/json":
        raise PwaApiError(status=422, code="validation_error", message="Ожидается JSON")
    try:
        payload = await request.json()
    except (ValueError, RecursionError) as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректный запрос"
        ) from error
    return payload


async def invalidate(request, question_id):
    # Import runtime keys lazily to avoid app/route initialization cycles.
    from apps.pwa_app import PWA_BROKER, NATS_PWA_INVALIDATE

    targets = await run(
        request, lambda c, p: db.targets(c, domain.authorized(c, p, question_id)[1])
    )
    if PWA_BROKER not in request.app:
        return
    outcomes = await asyncio.gather(
        *(
            request.app[PWA_BROKER].publish(
                NATS_PWA_INVALIDATE,
                dict(
                    resources=[
                        "organizer-questions",
                        f"organizer-questions/{question_id}",
                        "notification-events",
                    ],
                    reason="organizer-question-updated",
                    audience=t["audience"],
                    accountId=t["public_id"],
                ),
            )
            for t in targets
        ),
        return_exceptions=True,
    )
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            logger.warning(
                "Organizer invalidation failed after commit", exc_info=outcome
            )


PREFIX = "/{audience:student|family|staff}/api/v1/organizer-questions"


@routes.get(PREFIX)
async def list_questions(request):
    state = request.query.get("state", "all")
    if state not in ("all", "awaiting_staff", "answered"):
        raise PwaApiError(
            status=422, code="validation_error", message="Неизвестный фильтр"
        )
    before = cursor(request, 2**63 - 1)
    return response(
        request, await run(request, lambda c, p: domain.listing(c, p, state, before))
    )


@routes.post(PREFIX)
async def create_question(request):
    payload = await body(request)
    public_id = await run(request, lambda c, p: domain.send(c, p, None, payload), True)
    await invalidate(request, public_id)
    return response(request, dict(threadId=public_id))


@routes.get(PREFIX + "/{question:oq-[0-9]+}")
async def get_question(request):
    after = cursor(request, 0)
    return response(
        request,
        await run(
            request,
            lambda c, p: domain.thread(c, p, request.match_info["question"], after),
        ),
    )


@routes.post(PREFIX + "/{question:oq-[0-9]+}/entries")
async def append_entry(request):
    payload = await body(request)
    public_id = await run(
        request,
        lambda c, p: domain.send(c, p, request.match_info["question"], payload),
        True,
    )
    await invalidate(request, public_id)
    return response(request, dict(threadId=public_id))


@routes.post(PREFIX + "/{question:oq-[0-9]+}/read")
async def mark_read(request):
    payload = await body(request)
    if not isinstance(payload, dict) or set(payload) != {"sequence"}:
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректный запрос"
        )
    await run(
        request,
        lambda c, p: domain.read(
            c,
            p,
            request.match_info["question"],
            payload["sequence"],
            authenticated_session(request).current.session.id,
        ),
        True,
    )
    await invalidate(request, request.match_info["question"])
    return response(request, dict(ok=True))


@routes.post(PREFIX + "/photos")
async def upload_photo(request):
    from apps.pwa_app import PWA_CONTENT_ASSET_CONVERTER
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE

    a = await run(request, lambda c, p: domain.identity(c, p))
    if request.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise PwaApiError(
            status=422, code="validation_error", message="Выберите JPEG, PNG или WebP"
        )
    data = bytearray()
    async for part in request.content.iter_chunked(65536):
        data.extend(part)
        if len(data) > MAX_PHOTO_BYTES:
            raise PwaApiError(
                status=413, code="payload_too_large", message="Фотография больше 25 МиБ"
            )
    signatures = (
        data.startswith(b"\xff\xd8\xff"),
        data.startswith(b"\x89PNG\r\n\x1a\n"),
        data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    )
    if not any(signatures):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Не удалось прочитать фотографию",
        )
    converter = request.app.get(PWA_CONTENT_ASSET_CONVERTER)
    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    if converter is None or storage is None:
        raise PwaApiError(
            status=503,
            code="unavailable",
            message="Загрузка фотографий временно недоступна",
        )
    try:
        converted = await converter.raster_to_webp(bytes(data))
    except AssetConversionError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Не удалось прочитать фотографию",
        ) from error
    key = f"organizer-questions/{uuid.uuid4().hex}.webp"
    await storage.put(key, converted.data, "image/webp")
    try:
        photo = await run(
            request,
            lambda c, p: db.insert_photo(
                c,
                domain.identity(c, p)["id"],
                key,
                hashlib.sha256(converted.data).hexdigest(),
                len(converted.data),
                converted.width,
                converted.height,
                datetime.now(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z"),
            ),
            True,
        )
    except Exception:
        await storage.delete(key)
        raise
    return response(request, dict(photo=domain.photo_view(photo, a["audience"])))


@routes.get(PREFIX + "/photos/{photo:oqp-[0-9]+}")
async def get_photo(request):
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE

    photo = await run(
        request, lambda c, p: domain.photo_access(c, p, request.match_info["photo"])
    )
    try:
        payload = await request.app[PWA_CONTENT_OBJECT_STORAGE].get(photo["object_key"])
    except (ObjectStorageOperationError, FileNotFoundError) as error:
        raise PwaApiError(
            status=404, code="not_found", message="Фотография недоступна"
        ) from error
    if (
        len(payload) != photo["byte_size"]
        or hashlib.sha256(payload).hexdigest() != photo["sha256"]
    ):
        raise PwaApiError(status=404, code="not_found", message="Фотография недоступна")
    return web.Response(
        body=payload,
        content_type="image/webp",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
