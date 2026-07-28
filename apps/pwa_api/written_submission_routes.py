"""Authenticated Student HTTP adapter for Phase-5 written threads.

No browser-supplied identity crosses this boundary.  Strict request shapes map
the revalidated Student session to ``PwaWrittenSubmissionRepository`` and the
response mirrors ``packages/contracts/src/written-submissions.ts``.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.written_submissions import (
    CreateWrittenEntryCommand,
    ProblemRevisionRef,
    PwaWrittenSubmissionRepository,
    SubmitWrittenEntryCommand,
    WrittenSubmissionRejected,
    WrittenSubmissionRepositoryError,
)
from models.pwa.auth import AuthAudience


WRITTEN_SUBMISSION_BODY_LIMIT_BYTES = 128 * 1024
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

PWA_WRITTEN_SUBMISSION_REPOSITORY = web.AppKey(
    "pwa_written_submission_repository", PwaWrittenSubmissionRepository
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
    attachment_ids = payload["attachmentIds"]
    if (
        not isinstance(attachment_ids, list)
        or len(attachment_ids) > 10
        or any(
            not isinstance(item, str) or _PUBLIC_ID.fullmatch(item) is None
            for item in attachment_ids
        )
        or len(set(attachment_ids)) != len(attachment_ids)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте список фотографий",
            details={"field": "attachmentIds"},
        )
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
            attachment_public_ids=tuple(attachment_ids),
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
    "PWA_WRITTEN_SUBMISSION_INVALIDATOR",
    "PWA_WRITTEN_SUBMISSION_REPOSITORY",
    "written_submission_routes",
]
