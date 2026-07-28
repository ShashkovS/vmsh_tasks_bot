"""Lease-safe Staff HTTP adapter for the written-review queue.

The collection is always filtered by the current public course/group grants;
integer database IDs and claim ownership never come from the browser.  See
``vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md``.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.reviews import (
    CompleteReviewCommand,
    PwaWrittenReviewQueueRepository,
    ReviewCompletionInvalid,
    ReviewEvidenceBranchExpectation,
    ReviewEvidenceEntryExpectation,
    ReviewEvidenceUnavailable,
    ReviewIdempotencyConflict,
    ReviewLease,
    ReviewLeaseConflict,
    ReviewLeaseLost,
    ReviewQueueCase,
    ReviewQueueForbidden,
    ReviewQueueNotFound,
    ReviewStaffScope,
    ReviewThreadChanged,
)
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience


REVIEW_BODY_LIMIT_BYTES = 128 * 1024
REVIEW_PAGE_SIZE = 50
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_CLAIM_TOKEN = _PUBLIC_ID
_CLAIM_FIELDS = frozenset({"schemaVersion"})
_LEASE_FIELDS = frozenset({"schemaVersion", "claimToken"})
_COMPLETE_FIELDS = frozenset(
    {
        "schemaVersion",
        "claimToken",
        "idempotencyKey",
        "verdict",
        "comment",
        "confirmWithoutComment",
        "branches",
    }
)
_LIST_QUERY_FIELDS = frozenset({"problemGroup", "sort", "cursor"})

PWA_REVIEW_QUEUE_REPOSITORY = web.AppKey(
    "pwa_review_queue_repository", PwaWrittenReviewQueueRepository
)
ReviewCompletionInvalidator = Callable[
    [tuple[str, ...], tuple[str, ...], str], Awaitable[None]
]
PWA_REVIEW_COMPLETION_INVALIDATOR = web.AppKey(
    "pwa_review_completion_invalidator", ReviewCompletionInvalidator
)
review_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def _repository(request: web.Request) -> PwaWrittenReviewQueueRepository:
    repository = request.app.get(PWA_REVIEW_QUEUE_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="review_queue_unavailable",
            message="Очередь проверки временно недоступна",
        )
    return repository


def _staff_context(request: web.Request) -> tuple[int, ReviewStaffScope]:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or not principal.has_capability(Capability.REVIEW_READ)
        or principal.linked_user_id is None
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для просмотра очереди проверки",
        )
    course_public_ids = frozenset(
        grant.course_public_id
        for grant in principal.staff_scope_grants
        if grant.group_public_id is None
    )
    group_public_ids = frozenset(
        grant.group_public_id
        for grant in principal.staff_scope_grants
        if grant.group_public_id is not None
    )
    return principal.linked_user_id, ReviewStaffScope(
        global_access=principal.is_global_admin,
        course_public_ids=course_public_ids,
        group_public_ids=group_public_ids,
    )


def _require_review_write(request: web.Request) -> tuple[int, ReviewStaffScope]:
    teacher_user_id, scope = _staff_context(request)
    if not authenticated_session(request).principal.has_capability(
        Capability.REVIEW_WRITE
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для проверки работы",
        )
    return teacher_user_id, scope


def _queue_public_id(request: web.Request) -> str:
    value = request.match_info["queue_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="review_queue_item_not_found",
            message="Работа в очереди не найдена",
        )
    return value


def _optional_public_id(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры очереди",
            details={"field": field},
        )
    return value


async def _json_object(
    request: web.Request, *, required_fields: frozenset[str]
) -> dict[str, object]:
    if (
        request.content_length is not None
        and request.content_length > REVIEW_BODY_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Запрос слишком большой",
        )
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть JSON",
        )
    body = await request.read()
    if len(body) > REVIEW_BODY_LIMIT_BYTES:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Запрос слишком большой",
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
            message="Проверьте поля запроса",
            details={"required": sorted(required_fields)},
        )
    if payload["schemaVersion"] != 1 or isinstance(payload["schemaVersion"], bool):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неподдерживаемая версия запроса",
            details={"field": "schemaVersion"},
        )
    return payload


def _claim_token(value: object) -> str:
    if not isinstance(value, str) or _CLAIM_TOKEN.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте токен блокировки",
            details={"field": "claimToken"},
        )
    return value


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _branch_payload(item) -> dict[str, object]:
    return {
        "queueId": item.queue_public_id,
        "problemId": item.problem_public_id,
        "problemTitle": item.problem_title,
        "courseId": item.course_public_id,
        "groupId": item.group_public_id,
        "submittedAt": _timestamp(item.submitted_at),
        "leaseVersion": item.lease_version,
    }


def _case_payload(case: ReviewQueueCase, *, teacher_user_id: int) -> dict[str, object]:
    lock = case.lock
    return {
        "queueId": case.queue_public_id,
        "logicalCaseId": case.logical_case_public_id,
        "student": {
            "studentId": case.student_public_id,
            "displayName": case.student_name,
        },
        "submittedAt": _timestamp(case.submitted_at),
        "branches": [_branch_payload(item) for item in case.items],
        "lock": (
            None
            if lock is None
            else {
                "kind": lock.kind,
                "teacher": {
                    "teacherId": lock.teacher_public_id,
                    "displayName": lock.teacher_name,
                },
                "expiresAt": _timestamp(lock.expires_at),
                "isOwnedByCurrentStaff": lock.teacher_user_id == teacher_user_id,
            }
        ),
    }


def _lease_payload(lease: ReviewLease) -> dict[str, object]:
    first = lease.items[0]
    return {
        "claimToken": lease.claim_token,
        "logicalCaseId": lease.logical_case_public_id,
        "student": {
            "studentId": first.student_public_id,
            "displayName": first.student_name,
        },
        "claimedAt": _timestamp(lease.claimed_at),
        "expiresAt": _timestamp(lease.expires_at),
        "branches": [_branch_payload(item) for item in lease.items],
        "evidenceBranches": [
            {
                "queueId": branch.queue_public_id,
                "thread": (
                    None
                    if branch.thread_public_id is None
                    else {
                        "threadId": branch.thread_public_id,
                        "threadVersion": branch.thread_version,
                        "entries": [
                            {
                                "entryId": entry.entry_public_id,
                                "entryVersion": entry.entry_version,
                                "entryKind": entry.entry_kind,
                                "text": entry.text,
                                "submittedAt": _timestamp(entry.server_received_at),
                                "attachments": [
                                    {
                                        "attachmentId": attachment.attachment_public_id,
                                        "ordinal": attachment.ordinal,
                                    }
                                    for attachment in entry.attachments
                                ],
                            }
                            for entry in branch.entries
                        ],
                    }
                ),
            }
            for branch in lease.evidence_branches
        ],
    }


def _positive_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные проверки",
            details={"field": field},
        )
    return value


def _complete_branches(value: object) -> tuple[ReviewEvidenceBranchExpectation, ...]:
    if not isinstance(value, list) or not value:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте границу проверяемой работы",
            details={"field": "branches"},
        )
    branches: list[ReviewEvidenceBranchExpectation] = []
    for branch_index, branch in enumerate(value):
        if not isinstance(branch, dict) or set(branch) != {
            "queueId",
            "leaseVersion",
            "threadId",
            "threadVersion",
            "evidence",
        }:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Проверьте ветви проверяемой работы",
                details={"field": f"branches.{branch_index}"},
            )
        evidence = branch["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="В проверяемой ветви нет посылок",
                details={"field": f"branches.{branch_index}.evidence"},
            )
        entries: list[ReviewEvidenceEntryExpectation] = []
        for entry_index, entry in enumerate(evidence):
            if not isinstance(entry, dict) or set(entry) != {
                "entryId",
                "entryVersion",
            }:
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="Проверьте посылки в границе работы",
                    details={
                        "field": (f"branches.{branch_index}.evidence.{entry_index}")
                    },
                )
            entries.append(
                ReviewEvidenceEntryExpectation(
                    entry_public_id=_required_public_id(
                        entry["entryId"],
                        field=(
                            f"branches.{branch_index}.evidence.{entry_index}.entryId"
                        ),
                    ),
                    entry_version=_positive_integer(
                        entry["entryVersion"],
                        field=(
                            "branches."
                            f"{branch_index}.evidence.{entry_index}.entryVersion"
                        ),
                    ),
                )
            )
        branches.append(
            ReviewEvidenceBranchExpectation(
                queue_public_id=_required_public_id(
                    branch["queueId"], field=f"branches.{branch_index}.queueId"
                ),
                lease_version=_positive_integer(
                    branch["leaseVersion"],
                    field=f"branches.{branch_index}.leaseVersion",
                ),
                thread_public_id=_required_public_id(
                    branch["threadId"], field=f"branches.{branch_index}.threadId"
                ),
                thread_version=_positive_integer(
                    branch["threadVersion"],
                    field=f"branches.{branch_index}.threadVersion",
                ),
                entries=tuple(entries),
            )
        )
    return tuple(branches)


def _required_public_id(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные проверки",
            details={"field": field},
        )
    return value


def _translate_queue_error(error: Exception) -> PwaApiError:
    if isinstance(error, ReviewQueueNotFound):
        return PwaApiError(
            status=404,
            code="review_queue_item_not_found",
            message="Работа в очереди не найдена",
        )
    if isinstance(error, ReviewQueueForbidden):
        return PwaApiError(
            status=403,
            code="forbidden",
            message="Работа находится вне доступных групп",
        )
    if isinstance(error, ReviewLeaseConflict):
        return PwaApiError(
            status=409,
            code="review_already_claimed",
            message="Эту работу уже проверяет другой преподаватель",
        )
    if isinstance(error, ReviewLeaseLost):
        return PwaApiError(
            status=409,
            code="review_lease_lost",
            message="Блокировка проверки завершилась. Обновите очередь.",
        )
    if isinstance(error, ReviewThreadChanged):
        return PwaApiError(
            status=409,
            code="review_thread_changed",
            message="Работа изменилась. Обновите её перед проверкой.",
        )
    if isinstance(error, ReviewEvidenceUnavailable):
        return PwaApiError(
            status=409,
            code="review_evidence_unavailable",
            message="Для этой работы ещё не подготовлена полная история PWA",
        )
    if isinstance(error, ReviewIdempotencyConflict):
        return PwaApiError(
            status=409,
            code="idempotency_payload_mismatch",
            message="Это действие уже было отправлено с другими данными",
        )
    if isinstance(error, ReviewCompletionInvalid):
        return PwaApiError(
            status=422,
            code="review_confirmation_required",
            message="Подтвердите отправку вердикта без комментария",
        )
    raise error


@review_routes.get("/staff/api/v1/review/items")
async def list_review_items(request: web.Request) -> web.Response:
    teacher_user_id, scope = _staff_context(request)
    if set(request.query) - _LIST_QUERY_FIELDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры очереди",
        )
    sort = request.query.get("sort", "oldest")
    if sort not in {"oldest", "newest"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный порядок очереди",
            details={"field": "sort"},
        )
    try:
        page = await _repository(request).list_cases(
            scope=scope,
            problem_group_public_id=_optional_public_id(
                request.query.get("problemGroup"), field="problemGroup"
            ),
            cursor=_optional_public_id(request.query.get("cursor"), field="cursor"),
            newest_first=sort == "newest",
            page_size=REVIEW_PAGE_SIZE,
        )
    except (ReviewQueueNotFound, ReviewQueueForbidden, ReviewLeaseConflict) as error:
        raise _translate_queue_error(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [
                _case_payload(item, teacher_user_id=teacher_user_id)
                for item in page.items
            ],
            "nextCursor": page.next_cursor,
            "requestId": request["request_id"],
        }
    )


@review_routes.post("/staff/api/v1/review/items/{queue_public_id}/claim")
async def claim_review_item(request: web.Request) -> web.Response:
    teacher_user_id, scope = _require_review_write(request)
    await _json_object(request, required_fields=_CLAIM_FIELDS)
    try:
        lease = await _repository(request).claim(
            queue_public_id=_queue_public_id(request),
            teacher_user_id=teacher_user_id,
            scope=scope,
        )
    except (
        ReviewQueueNotFound,
        ReviewQueueForbidden,
        ReviewLeaseConflict,
    ) as error:
        raise _translate_queue_error(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "lease": _lease_payload(lease),
            "requestId": request["request_id"],
        }
    )


@review_routes.post("/staff/api/v1/review/items/{queue_public_id}/heartbeat")
async def heartbeat_review_item(request: web.Request) -> web.Response:
    teacher_user_id, scope = _require_review_write(request)
    payload = await _json_object(request, required_fields=_LEASE_FIELDS)
    try:
        lease = await _repository(request).heartbeat(
            queue_public_id=_queue_public_id(request),
            claim_token=_claim_token(payload["claimToken"]),
            teacher_user_id=teacher_user_id,
            scope=scope,
        )
    except (
        ReviewQueueNotFound,
        ReviewQueueForbidden,
        ReviewLeaseLost,
    ) as error:
        raise _translate_queue_error(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "lease": _lease_payload(lease),
            "requestId": request["request_id"],
        }
    )


@review_routes.post("/staff/api/v1/review/items/{queue_public_id}/release")
async def release_review_item(request: web.Request) -> web.Response:
    teacher_user_id, scope = _require_review_write(request)
    payload = await _json_object(request, required_fields=_LEASE_FIELDS)
    try:
        released_items = await _repository(request).release(
            queue_public_id=_queue_public_id(request),
            claim_token=_claim_token(payload["claimToken"]),
            teacher_user_id=teacher_user_id,
            scope=scope,
        )
    except (
        ReviewQueueNotFound,
        ReviewQueueForbidden,
        ReviewLeaseLost,
    ) as error:
        raise _translate_queue_error(error) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "releasedItems": released_items,
            "requestId": request["request_id"],
        }
    )


@review_routes.post("/staff/api/v1/review/items/{queue_public_id}/complete")
async def complete_review_item(request: web.Request) -> web.Response:
    teacher_user_id, scope = _require_review_write(request)
    payload = await _json_object(request, required_fields=_COMPLETE_FIELDS)
    verdict = payload["verdict"]
    if (
        isinstance(verdict, bool)
        or not isinstance(verdict, int)
        or not 11 <= verdict <= 17
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Выберите корректный вердикт",
            details={"field": "verdict"},
        )
    comment = payload["comment"]
    if comment is not None and (not isinstance(comment, str) or len(comment) > 100_000):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте комментарий",
            details={"field": "comment"},
        )
    if not isinstance(payload["confirmWithoutComment"], bool):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте подтверждение отправки",
            details={"field": "confirmWithoutComment"},
        )
    try:
        command = CompleteReviewCommand(
            queue_public_id=_queue_public_id(request),
            claim_token=_claim_token(payload["claimToken"]),
            teacher_user_id=teacher_user_id,
            scope=scope,
            idempotency_key=_required_public_id(
                payload["idempotencyKey"], field="idempotencyKey"
            ),
            verdict=verdict,
            comment=comment,
            confirm_without_comment=payload["confirmWithoutComment"],
            branches=_complete_branches(payload["branches"]),
        )
        receipt = await _repository(request).complete(command)
    except (
        ReviewQueueNotFound,
        ReviewQueueForbidden,
        ReviewLeaseLost,
        ReviewThreadChanged,
        ReviewEvidenceUnavailable,
        ReviewIdempotencyConflict,
        ReviewCompletionInvalid,
    ) as error:
        raise _translate_queue_error(error) from error
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные завершения проверки",
        ) from error
    invalidator = request.app.get(PWA_REVIEW_COMPLETION_INVALIDATOR)
    if invalidator is not None and not receipt.replayed:
        try:
            await invalidator(
                receipt.owner_account_public_ids,
                receipt.evidence_problem_public_ids,
                "written-review-completed",
            )
        except Exception:
            logger.warning(
                "Review completion invalidation failed after commit: review=%s",
                receipt.review_public_id,
                exc_info=True,
            )
    return web.json_response(
        {
            "schemaVersion": 1,
            "review": {
                "reviewId": receipt.review_public_id,
                "targetThreadId": receipt.target_thread_public_id,
                "targetProblemId": receipt.target_problem_public_id,
                "targetThreadStatus": receipt.target_thread_status,
                "verdict": receipt.verdict,
                "commentEntryId": receipt.comment_entry_public_id,
                "evidenceEntryIds": list(receipt.evidence_entry_public_ids),
                "completedAt": _timestamp(receipt.completed_at),
                "replayed": receipt.replayed,
            },
            "requestId": request["request_id"],
        }
    )


__all__ = [
    "PWA_REVIEW_COMPLETION_INVALIDATOR",
    "PWA_REVIEW_QUEUE_REPOSITORY",
    "review_routes",
]
