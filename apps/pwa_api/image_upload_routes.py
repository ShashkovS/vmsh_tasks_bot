"""Shared upload permissions/wiring; docs/performance/browser-image-uploads.md."""

import asyncio
import json
import logging

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.image_uploads import ImageUploadService, ImageUploadRejected
from helpers.object_storage import ObjectStorageOperationError

routes = web.RouteTableDef()
PREFIX = "/{audience:student|family|staff}/api/v1/image-uploads"
PWA_IMAGE_UPLOAD_CLEANUP_TASK = web.AppKey(
    "pwa_image_upload_cleanup_task", asyncio.Task
)
logger = logging.getLogger(__name__)


def service(request):
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE

    state = request.app.get(PWA_DATABASE)
    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    if state is None or state.factory is None or storage is None:
        raise PwaApiError(
            status=503,
            code="image_upload_unavailable",
            message="Загрузка фотографий временно недоступна",
        )
    return ImageUploadService(state.factory, storage)


def identity(request):
    auth = authenticated_session(request)
    audience = request.path.split("/")[1]
    if auth.principal.audience.value != audience:
        raise PwaApiError(status=403, code="forbidden", message="Фотография недоступна")
    return auth.current.session.account_id, audience


async def authorize(request, purpose, context):
    from apps.pwa_api import written_submission_routes as written
    from apps.pwa_api import support_routes as support
    from apps.pwa_api import organizer_question_routes as organizer
    from apps.pwa_api.news_moderation_routes import _admin_user_id
    from apps.pwa_api.content_routes import _authorized_lesson_window_scope

    if not isinstance(context, dict):
        raise ImageUploadRejected("image_upload_invalid", 422)
    if (
        purpose == "written"
        and set(context) == {"problemId"}
        and isinstance(context["problemId"], str)
    ):
        account, _ = written._student_identity(request)
        await written._repository(request).authorize_image_upload(
            account_id=account, problem_public_id=context["problemId"]
        )
    elif purpose == "support" and not context:
        if identity(request)[1] == "staff":
            support._staff_context(request, write=True)
        else:
            support._student_user_id(request)
    elif purpose == "organizer" and not context:
        organizer.principal(request)
    elif purpose == "rich" and not context:
        _admin_user_id(request)
    elif (
        purpose == "lesson-block"
        and set(context) == {"groupLessonId"}
        and isinstance(context["groupLessonId"], str)
    ):
        previous = request.match_info.get("group_lesson_id")
        request.match_info["group_lesson_id"] = context["groupLessonId"]
        try:
            await _authorized_lesson_window_scope(request)
        finally:
            if previous is None:
                request.match_info.pop("group_lesson_id", None)
            else:
                request.match_info["group_lesson_id"] = previous
    else:
        raise ImageUploadRejected("image_upload_invalid", 422)


def translated(error):
    if isinstance(error, ImageUploadRejected):
        return PwaApiError(
            status=error.status,
            code=error.code,
            message="Не удалось сохранить фотографию. Повторите отправку.",
        )
    return PwaApiError(
        status=503,
        code="image_upload_unavailable",
        message="Загрузка фотографий временно недоступна",
    )


async def json_body(request):
    if (
        request.content_type != "application/json"
        or (request.content_length or 0) > 16_384
    ):
        raise ImageUploadRejected("image_upload_invalid", 422)
    try:
        # Stream the small control body too; chunked JSON must not evade the cap.
        data = bytearray()
        async for chunk in request.content.iter_chunked(4096):
            data.extend(chunk)
            if len(data) > 16_384:
                raise ImageUploadRejected("image_upload_invalid", 422)
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, RecursionError) as error:
        raise ImageUploadRejected("image_upload_invalid", 422) from error


@routes.post(PREFIX + "/prepare")
async def prepare_image(request):
    try:
        payload = await json_body(request)
        await authorize(request, payload.get("purpose"), payload.get("context"))
        account, audience = identity(request)
        result = await service(request).prepare(account, audience, payload)
        return web.json_response(result, headers={"Cache-Control": "no-store"})
    except (ImageUploadRejected, ObjectStorageOperationError) as error:
        raise translated(error) from error


@routes.post(PREFIX + "/{upload_id}/renew")
async def renew_image(request):
    try:
        account, audience = identity(request)
        uploader = service(request)
        record = await uploader.owned(
            request.match_info["upload_id"], account, audience
        )
        await authorize(request, record["purpose"], json.loads(record["context"]))
        result = await uploader.grant(record)
        return web.json_response(result, headers={"Cache-Control": "no-store"})
    except (ImageUploadRejected, ObjectStorageOperationError) as error:
        raise translated(error) from error


def is_image_reference(request):
    return request.content_type == "application/json" or bool(
        request.headers.get("X-Vmsh-Image-Upload")
    )


async def finalize_reference(
    request, *, purpose, context, persist, payload=None, body=None, binding=None
):
    try:
        if body is None:
            body = await json_body(request) if payload is None else {}
        upload_id = (
            request.headers.get("X-Vmsh-Image-Upload")
            if payload is not None
            else body.get("uploadId")
        )
        if not isinstance(upload_id, str) or len(upload_id) != 36:
            raise ImageUploadRejected("image_upload_invalid", 422)
        if (
            payload is None
            and binding is None
            and set(body) != {"schemaVersion", "uploadId"}
        ):
            raise ImageUploadRejected("image_upload_invalid", 422)
        if payload is None and (
            type(body.get("schemaVersion")) is not int or body["schemaVersion"] != 1
        ):
            raise ImageUploadRejected("image_upload_invalid", 422)
        account, audience = identity(request)
        return await service(request).finalize(
            upload_id=upload_id,
            account_id=account,
            audience=audience,
            purpose=purpose,
            context=context,
            binding=binding or {"path": request.path},
            persist=persist,
            payload=payload,
        )
    except (ImageUploadRejected, ObjectStorageOperationError) as error:
        raise translated(error) from error


async def finalize_rich_image(request, *, purpose, context, payload=None):
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE

    async def persist(record, on_saved):
        url = request.app[PWA_CONTENT_OBJECT_STORAGE].public_url(record["object_key"])
        if url is None:
            raise ImageUploadRejected("image_upload_unavailable", 503)
        result = {
            "schemaVersion": 1,
            "image": {
                "url": url,
                "mimeType": "image/webp",
                "width": record["width"],
                "height": record["height"],
            },
        }
        await service(request).factory.run_write_async(lambda c: on_saved(c, result))
        return result

    result = await finalize_reference(
        request, purpose=purpose, context=context, persist=persist, payload=payload
    )
    return web.json_response({**result, "requestId": request["request_id"]}, status=201)


async def known_rich_images(request, document):
    from db_methods.pwa import image_uploads as db

    urls = {item["sourceUrl"] for item in document["media"]}
    return await service(request).factory.run_read_async(
        lambda c: db.known_rich_images(c, urls)
    )


async def cleanup_lifecycle(app):
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE

    factory = app[PWA_DATABASE].factory
    storage = app.get(PWA_CONTENT_OBJECT_STORAGE)
    if factory is None or storage is None:
        yield
        return
    uploader = ImageUploadService(factory, storage)

    async def sweep():
        while True:
            try:
                await uploader.cleanup()
            except Exception:
                logger.exception("Unfinished image cleanup failed")
            await asyncio.sleep(3600)

    task = asyncio.create_task(sweep(), name="pwa-image-upload-cleanup")
    app[PWA_IMAGE_UPLOAD_CLEANUP_TASK] = task
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
