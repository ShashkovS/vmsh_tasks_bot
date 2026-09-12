"""Authenticated Student HTTP adapter for Phase-4 test submissions.

The route never accepts a student/account identity from the browser. It maps
the revalidated Student session onto the atomic repository and returns the
strict wire shape from ``vmshpwa/packages/contracts/src/submissions.ts``.
Authoritative requirements:
``vmshpwa/dev/development-plan/08-phase-4-test-submissions.md``.
"""

from __future__ import annotations

import asyncio
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
    TestAttemptRecheckPreview,
    TestAttemptRecheckReceipt,
    TestAttemptReceipt,
    TestSubmissionRejected,
    TestSubmissionRepositoryError,
)
from helpers.pwa.permissions import (
    AccessForbiddenError,
    AuthenticationRequiredError,
    Capability,
    require_access,
)
from models.pwa.auth import AuthAudience
from models.pwa.submissions import SubmissionConfigurationError


TEST_SUBMISSION_BODY_LIMIT_BYTES = 24 * 1024
TEST_ATTEMPT_HISTORY_PAGE_SIZE = 50
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_UTC_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_REQUEST_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "problemRevision",
        "displayAnswer",
        "clientCreatedAt",
    }
)
_RECHECK_REQUEST_FIELDS = frozenset({"schemaVersion", "problemRevision"})

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


def _staff_recheck_actor(
    request: web.Request, preview: TestAttemptRecheckPreview | None = None
) -> tuple[int, str]:
    principal = authenticated_session(request).principal
    try:
        authorized = require_access(
            principal,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.CHECKER_MANAGE,
            course_public_id=(None if preview is None else preview.course_public_id),
            group_public_id=(None if preview is None else preview.group_public_id),
        )
    except AuthenticationRequiredError as error:  # middleware invariant
        raise PwaApiError(
            status=401,
            code="authentication_required",
            message="Для продолжения войдите в кабинет.",
        ) from error
    except AccessForbiddenError as error:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для перепроверки задачи",
        ) from error
    if authorized.linked_user_id is None:  # pragma: no cover - auth invariant
        raise TestSubmissionRepositoryError("staff principal has no linked actor")
    return authorized.linked_user_id, authorized.account_public_id


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


async def _json_object(
    request: web.Request, *, required_fields: frozenset[str] = _REQUEST_FIELDS
) -> dict[str, object]:
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
    if not isinstance(payload, dict) or set(payload) != required_fields:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля ответа",
            details={"required": sorted(required_fields)},
        )
    return payload


async def _recheck_json_object(request: web.Request) -> dict[str, object]:
    return await _json_object(request, required_fields=_RECHECK_REQUEST_FIELDS)


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


def _problem_revision(value: object) -> tuple[str, int]:
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
    return condition_revision_id, config_version


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
    condition_revision_id, config_version = _problem_revision(
        payload["problemRevision"]
    )
    return SubmitTestAnswerCommand(
        account_id=account_id,
        problem_public_id=problem_public_id,
        display_answer=display_answer,
        client_created_at=_client_created_at(payload["clientCreatedAt"]),
        idempotency_key=_canonical_uuid(payload["idempotencyKey"]),
        expected_condition_revision_public_id=condition_revision_id,
        expected_config_version=config_version,
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


def _recheck_preview_payload(
    preview: TestAttemptRecheckPreview, *, request_id: str
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "problemId": preview.problem_public_id,
        "problemRevision": {
            "conditionRevisionId": preview.condition_revision_public_id,
            "configVersion": preview.config_version,
        },
        "pendingAttempts": preview.pending_attempts,
        "requestId": request_id,
    }


def _recheck_receipt_payload(
    receipt: TestAttemptRecheckReceipt, *, request_id: str
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "problemId": receipt.problem_public_id,
        "problemRevision": {
            "conditionRevisionId": receipt.condition_revision_public_id,
            "configVersion": receipt.config_version,
        },
        "pendingBefore": receipt.pending_before,
        "checked": receipt.checked,
        "correct": receipt.correct,
        "wrong": receipt.wrong,
        "stillPending": receipt.still_pending,
        "skippedConcurrent": receipt.skipped_concurrent,
        "threadInvalidationKey": (
            f"problems/{receipt.problem_public_id}/test-attempts"
        ),
        "requestId": request_id,
    }


def _translate_submission_errors(handler):
    @wraps(handler)
    async def wrapped(request: web.Request):
        try:
            return await handler(request)
        except TestSubmissionRejected as error:
            # Includes replayed refusals stored as 429 by previous deployments.
            # See vmshpwa/docs/support-problem-context.md.
            business_limit = error.code in {
                "test_attempt_hour_limit",
                "test_attempt_day_limit",
            }
            raise PwaApiError(
                status=422 if business_limit else error.http_status,
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
    reason: str = "test-attempt-created",
) -> None:
    invalidator = request.app.get(PWA_TEST_SUBMISSION_INVALIDATOR)
    if invalidator is None:
        return
    try:
        await invalidator(
            account_public_id,
            problem_public_id,
            reason,
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


async def _invalidate_rechecked_owners(
    request: web.Request, *, receipt: TestAttemptRecheckReceipt
) -> None:
    semaphore = asyncio.Semaphore(16)

    async def invalidate(account_public_id: str) -> None:
        async with semaphore:
            await _invalidate_after_commit(
                request,
                account_public_id=account_public_id,
                problem_public_id=receipt.problem_public_id,
                reason="test-attempt-rechecked",
            )

    await asyncio.gather(
        *(invalidate(account_id) for account_id in receipt.owner_account_public_ids)
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


@submission_routes.get("/student/api/v1/problems/{problem_public_id}/test-input")
@_translate_submission_errors
async def get_test_answer_input(request: web.Request) -> web.Response:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    account_id, _account_public_id = _student_identity(request)
    problem_public_id = _problem_public_id(request)
    record = await _repository(request).get_test_answer_input(
        account_id=account_id,
        problem_public_id=problem_public_id,
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "problemId": record.problem_public_id,
            "problemRevision": {
                "conditionRevisionId": record.condition_revision_public_id,
                "configVersion": record.config_version,
            },
            "answerType": record.answer_type,
            "validationPattern": record.validation_pattern,
            "validationError": record.validation_error,
            "options": list(record.options),
            "requestId": _request_id(request),
        }
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


@submission_routes.get(
    "/staff/api/v1/problems/{problem_public_id}/recheck-test-attempts"
)
@_translate_submission_errors
async def get_test_attempt_recheck_preview(request: web.Request) -> web.Response:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот запрос не принимает параметры",
        )
    _staff_recheck_actor(request)
    problem_public_id = _problem_public_id(request)
    preview = await _repository(request).get_test_attempt_recheck_preview(
        problem_public_id=problem_public_id
    )
    _staff_recheck_actor(request, preview)
    return web.json_response(
        _recheck_preview_payload(preview, request_id=_request_id(request))
    )


@submission_routes.post(
    "/staff/api/v1/problems/{problem_public_id}/recheck-test-attempts"
)
@_translate_submission_errors
async def recheck_test_attempts(request: web.Request) -> web.Response:
    actor_user_id, _staff_account_public_id = _staff_recheck_actor(request)
    problem_public_id = _problem_public_id(request)
    preview = await _repository(request).get_test_attempt_recheck_preview(
        problem_public_id=problem_public_id
    )
    _staff_recheck_actor(request, preview)
    payload = await _recheck_json_object(request)
    if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Версия формата перепроверки не поддерживается",
            details={"field": "schemaVersion"},
        )
    condition_revision_id, config_version = _problem_revision(
        payload["problemRevision"]
    )
    receipt = await _repository(request).recheck_pending_test_attempts(
        problem_public_id=problem_public_id,
        expected_condition_revision_public_id=condition_revision_id,
        expected_config_version=config_version,
        actor_user_id=actor_user_id,
    )
    await _invalidate_rechecked_owners(request, receipt=receipt)
    return web.json_response(
        _recheck_receipt_payload(receipt, request_id=_request_id(request))
    )


__all__ = [
    "PWA_TEST_SUBMISSION_INVALIDATOR",
    "PWA_TEST_SUBMISSION_REPOSITORY",
    "submission_routes",
]
