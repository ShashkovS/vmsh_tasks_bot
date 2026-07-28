"""Authenticated Student HTTP adapter for Phase-5 written threads.

No browser-supplied identity crosses this boundary.  Strict request shapes map
the revalidated Student session to ``PwaWrittenSubmissionRepository`` and the
response mirrors ``packages/contracts/src/written-submissions.ts``.
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from pathlib import PurePath
from urllib.parse import unquote

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.written_submissions import (
    CreateWrittenEntryCommand,
    DeleteWrittenAttachmentCommand,
    ProblemRevisionRef,
    PwaWrittenSubmissionRepository,
    ReorderWrittenAttachmentsCommand,
    ReplaceWrittenEntryCommand,
    SubmitWrittenEntryCommand,
    WrittenSubmissionRejected,
    WrittenSubmissionRepositoryError,
)
from helpers.object_storage import ObjectStorageOperationError
from helpers.pwa.content import AssetConversionError
from helpers.pwa.written_attachments import (
    MAX_WRITTEN_SOURCE_BYTES,
    WrittenAttachmentService,
    WrittenAttachmentServiceError,
)
from models.pwa.auth import AuthAudience


WRITTEN_SUBMISSION_BODY_LIMIT_BYTES = 128 * 1024
WRITTEN_ATTACHMENT_REQUEST_LIMIT_BYTES = MAX_WRITTEN_SOURCE_BYTES + 64 * 1024
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_UTC_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_CREATE_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "problemRevision",
        "text",
        "clientCreatedAt",
    }
)
_SUBMIT_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "expectedEntryVersion",
        "expectedThreadVersion",
        "attachmentIds",
    }
)
_REPLACE_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "replacedEntryId",
        "expectedEntryVersion",
        "expectedReplacedEntryVersion",
        "expectedThreadVersion",
        "attachmentIds",
    }
)
_ATTACHMENT_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "expectedEntryVersion",
        "expectedThreadVersion",
        "ordinal",
        "asset",
    }
)
_REORDER_ATTACHMENT_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "expectedEntryVersion",
        "expectedThreadVersion",
        "attachmentIds",
    }
)
_DELETE_ATTACHMENT_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "expectedEntryVersion",
        "expectedThreadVersion",
    }
)

PWA_WRITTEN_SUBMISSION_REPOSITORY = web.AppKey(
    "pwa_written_submission_repository", PwaWrittenSubmissionRepository
)
PWA_WRITTEN_ATTACHMENT_SERVICE = web.AppKey(
    "pwa_written_attachment_service", WrittenAttachmentService
)
WrittenSubmissionInvalidator = Callable[[str, str, str], Awaitable[None]]
PWA_WRITTEN_SUBMISSION_INVALIDATOR = web.AppKey(
    "pwa_written_submission_invalidator", WrittenSubmissionInvalidator
)
written_submission_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def _repository(request: web.Request) -> PwaWrittenSubmissionRepository:
    repository = request.app.get(PWA_WRITTEN_SUBMISSION_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="written_submissions_unavailable",
            message="Письменная сдача временно недоступна",
        )
    return repository


def _attachment_service(request: web.Request) -> WrittenAttachmentService:
    service = request.app.get(PWA_WRITTEN_ATTACHMENT_SERVICE)
    if service is None:
        raise PwaApiError(
            status=503,
            code="written_attachments_unavailable",
            message="Загрузка фотографий временно недоступна",
        )
    return service


def _student_identity(request: web.Request) -> tuple[int, str]:
    authenticated = authenticated_session(request)
    principal = authenticated.principal
    if principal.audience is not AuthAudience.STUDENT:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для сдачи задачи",
        )
    if principal.linked_user_id is None:  # pragma: no cover - auth invariant
        raise RuntimeError("Student principal has no linked identity")
    return authenticated.current.session.account_id, principal.account_public_id


def _public_id(request: web.Request, name: str, *, error_code: str) -> str:
    value = request.match_info[name]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code=error_code,
            message="Письменное решение не найдено.",
        )
    return value


async def _json_object(
    request: web.Request, *, required_fields: frozenset[str]
) -> dict[str, object]:
    if (
        request.content_length is not None
        and request.content_length > WRITTEN_SUBMISSION_BODY_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Текст решения слишком большой",
        )
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть JSON",
        )
    try:
        body = await request.read()
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть корректным JSON-объектом",
        ) from error
    if len(body) > WRITTEN_SUBMISSION_BODY_LIMIT_BYTES:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Текст решения слишком большой",
        )
    if not isinstance(payload, dict) or set(payload) != required_fields:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля письменного решения",
            details={"required": sorted(required_fields)},
        )
    return payload


def _schema_version(value: object) -> None:
    if type(value) is not int or value != 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Версия формата письменной сдачи не поддерживается",
            details={"field": "schemaVersion"},
        )


def _canonical_uuid(value: object) -> str:
    if not isinstance(value, str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте ключ отправки",
            details={"field": "idempotencyKey"},
        )
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, AttributeError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте ключ отправки",
            details={"field": "idempotencyKey"},
        ) from error
    if canonical != value:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте ключ отправки",
            details={"field": "idempotencyKey"},
        )
    return canonical


def _client_created_at(value: object) -> datetime:
    if not isinstance(value, str) or _UTC_DATETIME.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время создания решения",
            details={"field": "clientCreatedAt"},
        )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:  # pragma: no cover - guarded syntax
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время создания решения",
            details={"field": "clientCreatedAt"},
        ) from error


def _problem_revision(value: object) -> ProblemRevisionRef:
    if not isinstance(value, dict) or set(value) != {
        "conditionRevisionId",
        "configVersion",
    }:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте версию условия задачи",
            details={"field": "problemRevision"},
        )
    condition_revision_id = value["conditionRevisionId"]
    config_version = value["configVersion"]
    if (
        not isinstance(condition_revision_id, str)
        or _PUBLIC_ID.fullmatch(condition_revision_id) is None
        or type(config_version) is not int
        or config_version < 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте версию условия задачи",
            details={"field": "problemRevision"},
        )
    return ProblemRevisionRef(condition_revision_id, config_version)


def _positive_version(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте версию письменного решения",
            details={"field": field},
        )
    return value


def _attachment_ids(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) > 10
        or any(
            not isinstance(item, str) or _PUBLIC_ID.fullmatch(item) is None
            for item in value
        )
        or len(set(value)) != len(value)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте список фотографий",
            details={"field": "attachmentIds"},
        )
    return tuple(value)


async def _read_part_bytes(part, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await part.read_chunk(64 * 1024)
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if size > limit:
            raise PwaApiError(
                status=413,
                code="payload_too_large",
                message="Фотография слишком большая",
            )
        chunks.append(chunk)


async def _multipart_attachment(
    request: web.Request,
) -> tuple[dict[str, bytes], str]:
    if (
        request.content_length is not None
        and request.content_length > WRITTEN_ATTACHMENT_REQUEST_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Фотография слишком большая",
        )
    if request.content_type != "multipart/form-data":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Загрузка фотографии должна использовать multipart/form-data",
        )
    try:
        reader = await request.multipart()
    except (AssertionError, ValueError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Не удалось разобрать форму фотографии",
        ) from error

    values: dict[str, bytes] = {}
    filename: str | None = None
    while part := await reader.next():
        name = part.name
        if name not in _ATTACHMENT_FIELDS or name in values:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Форма фотографии содержит неизвестное или повторное поле",
            )
        if name == "asset":
            if not part.filename:
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="У фотографии отсутствует имя файла",
                    details={"field": "asset"},
                )
            filename = part.filename
            limit = MAX_WRITTEN_SOURCE_BYTES
        else:
            if part.filename is not None:
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="Текстовое поле формы не должно быть файлом",
                    details={"field": name},
                )
            limit = 512
        values[name] = await _read_part_bytes(part, limit=limit)
    if set(values) != _ATTACHMENT_FIELDS or filename is None or not values["asset"]:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Заполните все поля фотографии",
            details={"required": sorted(_ATTACHMENT_FIELDS)},
        )
    return values, filename


def _form_text(values: dict[str, bytes], name: str) -> str:
    try:
        value = values[name].decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Поля формы должны быть в UTF-8",
            details={"field": name},
        ) from error
    if not value or value != value.strip():
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля фотографии",
            details={"field": name},
        )
    return value


def _form_int(
    values: dict[str, bytes], name: str, *, minimum: int, maximum: int | None = None
) -> int:
    text = _form_text(values, name)
    try:
        value = int(text)
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте числовые поля фотографии",
            details={"field": name},
        ) from error
    if (
        str(value) != text
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте числовые поля фотографии",
            details={"field": name},
        )
    return value


def _attachment_filename(value: str) -> str:
    try:
        decoded = unquote(value, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Имя фотографии недопустимо",
            details={"field": "asset"},
        ) from error
    filename = PurePath(decoded.replace("\\", "/")).name.strip()
    if (
        not filename
        or len(filename) > 512
        or any(ord(character) < 32 for character in filename)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Имя фотографии недопустимо",
            details={"field": "asset"},
        )
    return filename


def _translate_repository_errors(handler):
    @wraps(handler)
    async def wrapped(request: web.Request):
        try:
            return await handler(request)
        except WrittenSubmissionRejected as error:
            raise PwaApiError(
                status=error.http_status,
                code=error.code,
                message=error.message,
                details=error.details or None,
            ) from error
        except WrittenSubmissionRepositoryError as error:
            raise PwaApiError(
                status=503,
                code="written_submissions_unavailable",
                message="Письменная сдача временно недоступна",
            ) from error
        except AssetConversionError as error:
            unavailable = error.code in {
                "asset.tool_unavailable",
                "asset.converter_start_failed",
            }
            raise PwaApiError(
                status=503 if unavailable else 422,
                code=(
                    "written_attachments_unavailable"
                    if unavailable
                    else "written_attachment_conversion_failed"
                ),
                message=(
                    "Обработка фотографий временно недоступна"
                    if unavailable
                    else "Фотография не прошла безопасную обработку"
                ),
                details={"reason": error.code, "capability": error.capability},
            ) from error
        except ObjectStorageOperationError as error:
            raise PwaApiError(
                status=503,
                code="written_attachments_unavailable",
                message="Не удалось сохранить фотографию. Повторите попытку.",
                details={"operation": error.operation},
            ) from error
        except WrittenAttachmentServiceError as error:
            raise PwaApiError(
                status=503,
                code="written_attachments_unavailable",
                message="Не удалось безопасно сохранить фотографию",
            ) from error

    return wrapped


async def _invalidate_after_commit(
    request: web.Request,
    *,
    account_public_id: str,
    problem_public_id: str,
    reason: str,
) -> None:
    invalidator = request.app.get(PWA_WRITTEN_SUBMISSION_INVALIDATOR)
    if invalidator is None:
        return
    try:
        await invalidator(account_public_id, problem_public_id, reason)
    except Exception:
        # SQLite is authoritative and reconnect always refetches full state.
        logger.warning(
            "Written-thread invalidation failed after commit: problem=%s",
            problem_public_id,
            exc_info=True,
        )


@written_submission_routes.post(
    "/student/api/v1/problems/{problem_public_id}/thread/entries"
)
@_translate_repository_errors
async def create_written_entry(request: web.Request) -> web.Response:
    account_id, account_public_id = _student_identity(request)
    problem_public_id = _public_id(
        request, "problem_public_id", error_code="written_problem_not_found"
    )
    payload = await _json_object(request, required_fields=_CREATE_FIELDS)
    _schema_version(payload["schemaVersion"])
    text = payload["text"]
    if text is not None and (not isinstance(text, str) or len(text) > 100_000):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте текст решения",
            details={"field": "text"},
        )
    receipt = await _repository(request).create_entry(
        CreateWrittenEntryCommand(
            account_id=account_id,
            problem_public_id=problem_public_id,
            problem_revision=_problem_revision(payload["problemRevision"]),
            text=text,
            client_created_at=_client_created_at(payload["clientCreatedAt"]),
            idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
        )
    )
    if not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=problem_public_id,
            reason="written-entry-created",
        )
    response = receipt.response_payload()
    response["requestId"] = request["request_id"]
    return web.json_response(response, status=201)


@written_submission_routes.get(
    "/student/api/v1/thread-entries/{entry_public_id}/attachments/"
    "{attachment_public_id}/media"
)
@_translate_repository_errors
async def get_written_attachment_media(request: web.Request) -> web.Response:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    account_id, _account_public_id = _student_identity(request)
    entry_public_id = _public_id(
        request, "entry_public_id", error_code="written_entry_not_found"
    )
    attachment_public_id = _public_id(
        request,
        "attachment_public_id",
        error_code="written_attachment_not_found",
    )
    media = await _repository(request).get_attachment_media(
        account_id=account_id,
        entry_public_id=entry_public_id,
        attachment_public_id=attachment_public_id,
    )
    try:
        payload = await _attachment_service(request).storage.get(media.object_key)
    except FileNotFoundError as error:
        raise PwaApiError(
            status=500,
            code="written_attachment_storage_invalid",
            message="Фотография недоступна из-за ошибки хранилища",
        ) from error
    if (
        media.media_type != "image/webp"
        or len(payload) != media.byte_size
        or hashlib.sha256(payload).hexdigest() != media.sha256
    ):
        logger.error(
            "Stored written attachment failed integrity check: attachment=%s",
            attachment_public_id,
        )
        raise PwaApiError(
            status=500,
            code="written_attachment_storage_invalid",
            message="Фотография недоступна из-за ошибки хранилища",
        )
    return web.Response(
        body=payload,
        content_type="image/webp",
        headers={
            "ETag": f'"sha256-{media.sha256}"',
        },
    )


@written_submission_routes.post(
    "/student/api/v1/thread-entries/{entry_public_id}/attachments"
)
@_translate_repository_errors
async def create_written_attachment(request: web.Request) -> web.Response:
    account_id, account_public_id = _student_identity(request)
    entry_public_id = _public_id(
        request, "entry_public_id", error_code="written_entry_not_found"
    )
    values, filename = await _multipart_attachment(request)
    _schema_version(_form_int(values, "schemaVersion", minimum=1, maximum=1))
    receipt = await _attachment_service(request).convert_and_attach(
        account_id=account_id,
        entry_public_id=entry_public_id,
        expected_entry_version=_form_int(values, "expectedEntryVersion", minimum=1),
        expected_thread_version=_form_int(values, "expectedThreadVersion", minimum=1),
        ordinal=_form_int(values, "ordinal", minimum=0, maximum=9),
        idempotency_key=_canonical_uuid(_form_text(values, "idempotencyKey")),
        payload=values["asset"],
        source_filename=_attachment_filename(filename),
    )
    if not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=receipt.problem_public_id,
            reason="written-attachment-created",
        )
    response = receipt.response_payload()
    response["requestId"] = request["request_id"]
    return web.json_response(response, status=201)


@written_submission_routes.patch(
    "/student/api/v1/thread-entries/{entry_public_id}/attachments/order"
)
@_translate_repository_errors
async def reorder_written_attachments(request: web.Request) -> web.Response:
    account_id, account_public_id = _student_identity(request)
    entry_public_id = _public_id(
        request, "entry_public_id", error_code="written_entry_not_found"
    )
    payload = await _json_object(request, required_fields=_REORDER_ATTACHMENT_FIELDS)
    _schema_version(payload["schemaVersion"])
    receipt = await _repository(request).reorder_attachments(
        ReorderWrittenAttachmentsCommand(
            account_id=account_id,
            entry_public_id=entry_public_id,
            expected_entry_version=_positive_version(
                payload["expectedEntryVersion"], field="expectedEntryVersion"
            ),
            expected_thread_version=_positive_version(
                payload["expectedThreadVersion"], field="expectedThreadVersion"
            ),
            attachment_public_ids=_attachment_ids(payload["attachmentIds"]),
            idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
        )
    )
    if receipt.changed and not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=receipt.problem_public_id,
            reason="written-attachments-reordered",
        )
    response = receipt.response_payload()
    response["requestId"] = request["request_id"]
    return web.json_response(response)


@written_submission_routes.delete(
    "/student/api/v1/thread-entries/{entry_public_id}/attachments/"
    "{attachment_public_id}"
)
@_translate_repository_errors
async def delete_written_attachment(request: web.Request) -> web.Response:
    account_id, account_public_id = _student_identity(request)
    entry_public_id = _public_id(
        request, "entry_public_id", error_code="written_entry_not_found"
    )
    attachment_public_id = _public_id(
        request,
        "attachment_public_id",
        error_code="written_attachment_not_found",
    )
    payload = await _json_object(request, required_fields=_DELETE_ATTACHMENT_FIELDS)
    _schema_version(payload["schemaVersion"])
    receipt = await _repository(request).delete_attachment(
        DeleteWrittenAttachmentCommand(
            account_id=account_id,
            entry_public_id=entry_public_id,
            attachment_public_id=attachment_public_id,
            expected_entry_version=_positive_version(
                payload["expectedEntryVersion"], field="expectedEntryVersion"
            ),
            expected_thread_version=_positive_version(
                payload["expectedThreadVersion"], field="expectedThreadVersion"
            ),
            idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
        )
    )
    if not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=receipt.problem_public_id,
            reason="written-attachment-deleted",
        )
    response = receipt.response_payload()
    response["requestId"] = request["request_id"]
    return web.json_response(response)


@written_submission_routes.post(
    "/student/api/v1/thread-entries/{entry_public_id}/submit"
)
@_translate_repository_errors
async def submit_written_entry(request: web.Request) -> web.Response:
    account_id, account_public_id = _student_identity(request)
    entry_public_id = _public_id(
        request, "entry_public_id", error_code="written_entry_not_found"
    )
    payload = await _json_object(request, required_fields=_SUBMIT_FIELDS)
    _schema_version(payload["schemaVersion"])
    attachment_ids = _attachment_ids(payload["attachmentIds"])
    receipt = await _repository(request).submit_entry(
        SubmitWrittenEntryCommand(
            account_id=account_id,
            entry_public_id=entry_public_id,
            expected_entry_version=_positive_version(
                payload["expectedEntryVersion"], field="expectedEntryVersion"
            ),
            expected_thread_version=_positive_version(
                payload["expectedThreadVersion"], field="expectedThreadVersion"
            ),
            attachment_public_ids=attachment_ids,
            idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
        )
    )
    if not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=receipt.problem_public_id,
            reason="written-entry-submitted",
        )
    response = receipt.response_payload()
    response["requestId"] = request["request_id"]
    return web.json_response(response)


@written_submission_routes.post(
    "/student/api/v1/thread-entries/{entry_public_id}/replace"
)
@_translate_repository_errors
async def replace_written_entry(request: web.Request) -> web.Response:
    """Atomically swap a complete draft for one unlocked submitted entry."""

    account_id, account_public_id = _student_identity(request)
    entry_public_id = _public_id(
        request, "entry_public_id", error_code="written_entry_not_found"
    )
    payload = await _json_object(request, required_fields=_REPLACE_FIELDS)
    _schema_version(payload["schemaVersion"])
    replaced_entry_public_id = payload["replacedEntryId"]
    if (
        not isinstance(replaced_entry_public_id, str)
        or _PUBLIC_ID.fullmatch(replaced_entry_public_id) is None
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте исходную версию решения",
            details={"field": "replacedEntryId"},
        )
    receipt = await _repository(request).replace_entry(
        ReplaceWrittenEntryCommand(
            account_id=account_id,
            entry_public_id=entry_public_id,
            replaced_entry_public_id=replaced_entry_public_id,
            expected_entry_version=_positive_version(
                payload["expectedEntryVersion"], field="expectedEntryVersion"
            ),
            expected_replaced_entry_version=_positive_version(
                payload["expectedReplacedEntryVersion"],
                field="expectedReplacedEntryVersion",
            ),
            expected_thread_version=_positive_version(
                payload["expectedThreadVersion"], field="expectedThreadVersion"
            ),
            attachment_public_ids=_attachment_ids(payload["attachmentIds"]),
            idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
        )
    )
    if not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=receipt.problem_public_id,
            reason="written-entry-replaced",
        )
    response = receipt.response_payload()
    response["requestId"] = request["request_id"]
    return web.json_response(response)


@written_submission_routes.get("/student/api/v1/problems/{problem_public_id}/thread")
@_translate_repository_errors
async def get_written_thread(request: web.Request) -> web.Response:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    account_id, _account_public_id = _student_identity(request)
    problem_public_id = _public_id(
        request, "problem_public_id", error_code="written_problem_not_found"
    )
    thread = await _repository(request).get_thread(
        account_id=account_id,
        problem_public_id=problem_public_id,
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "problemId": problem_public_id,
            "thread": None if thread is None else thread.payload(),
            "requestId": request["request_id"],
        }
    )


__all__ = [
    "PWA_WRITTEN_ATTACHMENT_SERVICE",
    "PWA_WRITTEN_SUBMISSION_INVALIDATOR",
    "PWA_WRITTEN_SUBMISSION_REPOSITORY",
    "written_submission_routes",
]
