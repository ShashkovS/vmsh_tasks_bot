"""Admin archive HTTP adapter; vmshpwa/docs/student-results.md."""

import asyncio
import hashlib
from pathlib import Path
import re

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from apps.pwa_api.written_submission_routes import _attachment_service
from db_methods.pwa import student_results as db
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa import student_results as archive

student_results_routes = web.RouteTableDef()
LEGACY_SOLUTIONS_ROOT = web.AppKey("student_results_solutions_root", Path)
DEFAULT_SOLUTIONS_ROOT = Path(__file__).resolve().parents[2] / "solutions"
PREFIX = "/staff/api/v1/student-results"


def _admin(request):
    p = authenticated_session(request).principal
    if (
        p.audience is not AuthAudience.STAFF
        or p.linked_user_id is None
        or not p.has_capability(Capability.AUDIT_READ)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Результаты доступны только администратору",
        )


def _root(request):
    if LEGACY_SOLUTIONS_ROOT in request.app:
        return request.app[LEGACY_SOLUTIONS_ROOT]
    runtime = request.app.get(RUNTIME_CONFIG)
    if runtime is not None and runtime.runtime_profile in ("pwa-agent", "pwa-e2e"):
        return Path(runtime.pwa_media_root) / "legacy-solutions"
    return DEFAULT_SOLUTIONS_ROOT


async def _read(request, fn):
    _admin(request)
    if any(
        not re.fullmatch(r"[a-zA-Z0-9._:-]{1,128}", v)
        for v in request.match_info.values()
    ):
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректный идентификатор"
        )
    try:
        return await request.app[PWA_DATABASE].factory.run_read_async(fn)
    except archive.ArchiveNotFound as error:
        raise PwaApiError(
            status=404, code="student_results_not_found", message="Запись не найдена"
        ) from error


def _json(request, value):
    return web.json_response(
        dict(schemaVersion=1, requestId=request["request_id"], **value),
        headers={"Cache-Control": "private, no-store"},
    )


@student_results_routes.get(PREFIX + "/directory")
async def directory(request):
    return _json(request, await _read(request, archive.directory))


@student_results_routes.get(PREFIX + "/{student}/overview")
async def overview(request):
    return _json(
        request,
        await _read(
            request,
            lambda c: archive.overview(
                c, request.match_info["student"], request.query.get("course")
            ),
        ),
    )


@student_results_routes.get(PREFIX + "/{student}/lessons/{course}/{number}")
async def lesson(request):
    try:
        number = int(request.match_info["number"])
        if number < 0:
            raise ValueError()
    except ValueError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректный номер занятия"
        ) from error
    return _json(
        request,
        await _read(
            request,
            lambda c: archive.lesson(
                c,
                request.match_info["student"],
                request.match_info["course"],
                number,
                _root(request),
            ),
        ),
    )


@student_results_routes.get(PREFIX + "/{student}/problems/{problem}/history")
async def history(request):
    return _json(
        request,
        await _read(
            request,
            lambda c: archive.history(
                c,
                request.match_info["student"],
                request.match_info["problem"],
                _root(request),
                request.query.get("cursor"),
            ),
        ),
    )


@student_results_routes.get(
    PREFIX + "/{student}/problems/{problem}/condition/{revision}"
)
async def condition(request):
    def read(c):
        archive.require(db.student(c, request.match_info["student"]))
        p = archive.require(db.problem(c, request.match_info["problem"]))
        return dict(
            document=archive.document(c, p["id"], request.match_info["revision"])
        )

    return _json(request, await _read(request, read))


@student_results_routes.get(PREFIX + "/{student}/attachments/{attachment}")
async def attachment(request):
    def read(c):
        s = archive.require(db.student(c, request.match_info["student"]))
        return archive.require(
            db.attachment(c, s["id"], request.match_info["attachment"])
        )

    m = await _read(request, read)
    try:
        body = await _attachment_service(request).storage.get(m["object_key"])
    except FileNotFoundError as error:
        raise PwaApiError(
            status=404, code="attachment_missing", message="Файл не сохранился"
        ) from error
    if (
        m["media_type"] != "image/webp"
        or len(body) != m["byte_size"]
        or hashlib.sha256(body).hexdigest() != m["sha256"]
    ):
        raise PwaApiError(
            status=404,
            code="attachment_missing",
            message="Файл повреждён или недоступен",
        )
    return web.Response(
        body=body,
        content_type="image/webp",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@student_results_routes.get(PREFIX + "/{student}/legacy-attachments/{discussion}")
async def legacy_attachment(request):
    def read(c):
        s = archive.require(db.student(c, request.match_info["student"]))
        r = archive.require(
            db.legacy_attachment(c, s["id"], request.match_info["discussion"])
        )
        return archive.require(archive.legacy_path(_root(request), r["attach_path"]))

    path = await _read(request, read)
    try:
        body = await asyncio.to_thread(path.read_bytes)
    except OSError as error:
        raise PwaApiError(
            status=404, code="attachment_missing", message="Файл не сохранился"
        ) from error
    # Archive is untrusted: never serve HTML/SVG inline on the authenticated origin.
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "application/octet-stream")
    return web.Response(
        body=body,
        content_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": (
                "inline" if media_type.startswith("image/") else "attachment"
            )
            + '; filename="attachment"',
        },
    )
