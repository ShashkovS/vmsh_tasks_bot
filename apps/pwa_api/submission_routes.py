"""Authenticated Student HTTP adapter for Phase-4 test submissions.

The route never accepts a student/account identity from the browser. It maps
the revalidated Student session onto the atomic repository and returns the
strict wire shape from ``vmshpwa/packages/contracts/src/submissions.ts``.
Authoritative requirements:
``vmshpwa/dev/development-plan/08-phase-4-test-submissions.md``.
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
from db_methods.pwa.submissions import (
    PwaTestSubmissionRepository,
    SubmitTestAnswerCommand,
    TestAttemptHistoryRecord,
    TestAttemptReceipt,
    TestSubmissionRejected,
    TestSubmissionRepositoryError,
)
from models.pwa.auth import AuthAudience
from models.pwa.submissions import SubmissionConfigurationError


TEST_SUBMISSION_BODY_LIMIT_BYTES = 24 * 1024
TEST_ATTEMPT_HISTORY_PAGE_SIZE = 50
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_UTC_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_REQUEST_FIELDS = frozenset(
    {"schemaVersion", "idempotencyKey", "displayAnswer", "clientCreatedAt"}
)

PWA_TEST_SUBMISSION_REPOSITORY = web.AppKey(
    "pwa_test_submission_repository", PwaTestSubmissionRepository
)
TestSubmissionInvalidator = Callable[[str, str, str], Awaitable[None]]
PWA_TEST_SUBMISSION_INVALIDATOR = web.AppKey(
    "pwa_test_submission_invalidator", TestSubmissionInvalidator
)
submission_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def _repository(request: web.Request) -> PwaTestSubmissionRepository:
    repository = request.app.get(PWA_TEST_SUBMISSION_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="test_submissions_unavailable",
            message="Сдача тестовых задач временно недоступна",
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
    account_id = authenticated.current.session.account_id
    if principal.linked_user_id is None:  # pragma: no cover - auth invariant
        raise RuntimeError("Student principal has no linked identity")
    return account_id, principal.account_public_id


def _request_id(request: web.Request) -> str:
    return request["request_id"]


def _problem_public_id(request: web.Request) -> str:
    value = request.match_info["problem_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="test_problem_not_found",
            message="Тестовая задача недоступна.",
        )
    return value


async def _json_object(request: web.Request) -> dict[str, object]:
    if (
        request.content_length is not None
        and request.content_length > TEST_SUBMISSION_BODY_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Ответ слишком большой",
        )
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть JSON",
        )
    try:
        body = await request.read()
    except web.HTTPRequestEntityTooLarge as error:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Ответ слишком большой",
        ) from error
    if len(body) > TEST_SUBMISSION_BODY_LIMIT_BYTES:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Ответ слишком большой",
        )
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть корректным JSON-объектом",
        ) from error
    if not isinstance(payload, dict) or set(payload) != _REQUEST_FIELDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля ответа",
            details={"required": sorted(_REQUEST_FIELDS)},
        )
    return payload


def _canonical_uuid(value: object) -> str:
    if not isinstance(value, str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте ключ отправки",
            details={"field": "idempotencyKey"},
        )
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте ключ отправки",
            details={"field": "idempotencyKey"},
        ) from error
    canonical = str(parsed)
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
            message="Проверьте время создания ответа",
            details={"field": "clientCreatedAt"},
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время создания ответа",
            details={"field": "clientCreatedAt"},
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время создания ответа",
            details={"field": "clientCreatedAt"},
        )
    return parsed.astimezone(UTC)


def _command(
    *, account_id: int, problem_public_id: str, payload: dict[str, object]
) -> SubmitTestAnswerCommand:
    if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Версия формата ответа не поддерживается",
            details={"field": "schemaVersion"},
        )
    display_answer = payload["displayAnswer"]
    if not isinstance(display_answer, str) or len(display_answer) > 16_384:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте введённый ответ",
            details={"field": "displayAnswer"},
        )
    try:
        display_answer.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте введённый ответ",
            details={"field": "displayAnswer"},
        ) from error
    return SubmitTestAnswerCommand(
        account_id=account_id,
        problem_public_id=problem_public_id,
        display_answer=display_answer,
        client_created_at=_client_created_at(payload["clientCreatedAt"]),
        idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
    )


def _check_status(outcome: str) -> str:
    try:
        return {
            "correct": "checked",
            "wrong": "checked",
            "invalid_format": "checked",
            "pending_configuration": "pending_configuration",
            "checker_failed": "failed",
        }[outcome]
    except KeyError as error:  # pragma: no cover - repository invariant
        raise TestSubmissionRepositoryError(
            "test attempt outcome has no wire check status"
        ) from error


def _receipt_payload(
    receipt: TestAttemptReceipt, *, request_id: str
) -> dict[str, object]:
    payload = receipt.response_payload()
    payload.update(
        {
            "checkStatus": _check_status(receipt.outcome),
            "resultVersion": None if receipt.verdict is None else 1,
            "threadInvalidationKey": (
                f"problems/{receipt.problem_public_id}/test-attempts"
            ),
            "requestId": request_id,
        }
    )
    return payload


def _history_payload(record: TestAttemptHistoryRecord) -> dict[str, object]:
    return record.response_payload()


def _translate_submission_errors(handler):
    @wraps(handler)
    async def wrapped(request: web.Request):
        try:
            return await handler(request)
        except TestSubmissionRejected as error:
            raise PwaApiError(
                status=error.http_status,
                code=error.code,
                message=error.message,
                details=error.details or None,
            ) from error
        except (TestSubmissionRepositoryError, SubmissionConfigurationError) as error:
            raise PwaApiError(
                status=503,
                code="test_submissions_unavailable",
                message="Сдача тестовых задач временно недоступна",
            ) from error

    return wrapped


async def _invalidate_after_commit(
    request: web.Request,
    *,
    account_public_id: str,
    problem_public_id: str,
) -> None:
    invalidator = request.app.get(PWA_TEST_SUBMISSION_INVALIDATOR)
    if invalidator is None:
        return
    try:
        await invalidator(
            account_public_id,
            problem_public_id,
            "test-attempt-created",
        )
    except Exception:
        # SQLite is authoritative; reconnect performs a full refetch. A NATS
        # failure must not turn the committed answer into a retryable HTTP
        # failure and accidentally encourage a second idempotency key.
        logger.warning(
            "Test-attempt invalidation failed after commit: problem=%s",
            problem_public_id,
            exc_info=True,
        )


@submission_routes.post("/student/api/v1/problems/{problem_public_id}/test-attempts")
@_translate_submission_errors
async def submit_test_answer(request: web.Request) -> web.Response:
    account_id, account_public_id = _student_identity(request)
    problem_public_id = _problem_public_id(request)
    command = _command(
        account_id=account_id,
        problem_public_id=problem_public_id,
        payload=await _json_object(request),
    )
    receipt = await _repository(request).submit_test_answer(command)
    if not receipt.replayed:
        await _invalidate_after_commit(
            request,
            account_public_id=account_public_id,
            problem_public_id=problem_public_id,
        )
    return web.json_response(
        _receipt_payload(receipt, request_id=_request_id(request)),
        status=201,
    )


@submission_routes.get("/student/api/v1/problems/{problem_public_id}/test-attempts")
@_translate_submission_errors
async def list_test_attempts(request: web.Request) -> web.Response:
    unexpected = set(request.query) - {"cursor"}
    duplicate_cursor = len(request.query.getall("cursor", [])) > 1
    if unexpected or duplicate_cursor:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Параметры истории ответов некорректны",
        )
    account_id, _account_public_id = _student_identity(request)
    problem_public_id = _problem_public_id(request)
    cursor = request.query.get("cursor")
    if cursor is not None and _PUBLIC_ID.fullmatch(cursor) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Курсор истории ответов некорректен",
            details={"field": "cursor"},
        )
    page = await _repository(request).list_test_attempts(
        account_id=account_id,
        problem_public_id=problem_public_id,
        cursor=cursor,
        limit=TEST_ATTEMPT_HISTORY_PAGE_SIZE,
    )
    return web.json_response(
        {
            "problemId": page.problem_public_id,
            "attempts": [_history_payload(record) for record in page.attempts],
            "nextCursor": page.next_cursor,
            "requestId": _request_id(request),
        }
    )


__all__ = [
    "PWA_TEST_SUBMISSION_INVALIDATOR",
    "PWA_TEST_SUBMISSION_REPOSITORY",
    "submission_routes",
]
