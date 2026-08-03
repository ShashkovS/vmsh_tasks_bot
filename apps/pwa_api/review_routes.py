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
from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from db_methods.pwa.review_telegram import read_review_telegram_delivery
from db_methods.pwa.reviews import (
    CompleteReviewCommand,
    PwaWrittenReviewQueueRepository,
    ReviewAnnotationManifest,
    ReviewAnnotationMark,
    ReviewCompletionInvalid,
    ReviewEvidenceBranchExpectation,
    ReviewEvidenceEntryExpectation,
    ReviewEvidenceUnavailable,
    ReviewIdempotencyConflict,
    ReviewInternalReactionConflict,
    ReviewInternalReactionInvalid,
    ReviewInternalReactionNotFound,
    ReviewInternalReactionState,
    ReviewInternalReactionWindowClosed,
    ReviewLease,
    ReviewLeaseConflict,
    ReviewLeaseLost,
    ReviewQueueCase,
    ReviewQueueForbidden,
    ReviewQueueNotFound,
    ReviewReactionInboxItem,
    ReviewStaffScope,
    ReviewStudentReactionConflict,
    ReviewStudentReactionInvalid,
    ReviewStudentReactionNotFound,
    ReviewStudentReactionReceipt,
    ReviewStudentReactionState,
    ReviewStudentReactionWindowClosed,
    ReviewThreadChanged,
)
from helpers.consts import USER_TYPE, VERDICT, VERDICT_TO_TICK
from helpers.pwa.review_composite import render_review_annotation_composite_png
from helpers.pwa.permissions import Capability
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.review_notifications import record_review_notifications
from models.pwa.review_corrections import (
    ReviewCorrectionCommand,
    ReviewCorrectionConflict,
    ReviewCorrectionForbidden,
    ReviewCorrectionInvalid,
    ReviewCorrectionNotFound,
    ReviewCorrectionStale,
    correct_written_review,
)

# Keep the route below aiohttp's default one-megabyte application limit while
# leaving room for the bounded 20k-point normalized annotation manifest.
REVIEW_BODY_LIMIT_BYTES = 900 * 1024
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
        "annotations",
        "internalReactionId",
    }
)
_REACTION_SET_FIELDS = frozenset({"schemaVersion", "reactionId", "expectedVersion"})
_REACTION_DELETE_FIELDS = frozenset({"schemaVersion", "expectedVersion"})
_CORRECTION_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "verdict",
        "comment",
        "confirmWithoutComment",
    }
)
_LIST_QUERY_FIELDS = frozenset({"problemGroup", "sort", "cursor"})
_REACTION_INBOX_QUERY_FIELDS = frozenset({"kind", "reactionId", "cursor"})

PWA_REVIEW_QUEUE_REPOSITORY = web.AppKey(
    "pwa_review_queue_repository", PwaWrittenReviewQueueRepository
)
ReviewQueueInvalidator = Callable[[str], Awaitable[None]]
PWA_REVIEW_QUEUE_INVALIDATOR = web.AppKey(
    "pwa_review_queue_invalidator", ReviewQueueInvalidator
)
ReviewCompletionInvalidator = Callable[
    [tuple[str, ...], tuple[str, ...], tuple[str, ...], str], Awaitable[None]
]
PWA_REVIEW_COMPLETION_INVALIDATOR = web.AppKey(
    "pwa_review_completion_invalidator", ReviewCompletionInvalidator
)
ReviewStudentReactionInvalidator = Callable[
    [
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        str,
    ],
    Awaitable[None],
]
PWA_REVIEW_STUDENT_REACTION_INVALIDATOR = web.AppKey(
    "pwa_review_student_reaction_invalidator", ReviewStudentReactionInvalidator
)
ReviewReactionInboxInvalidator = Callable[[tuple[str, ...], str], Awaitable[None]]
PWA_REVIEW_REACTION_INBOX_INVALIDATOR = web.AppKey(
    "pwa_review_reaction_inbox_invalidator", ReviewReactionInboxInvalidator
)
ReviewTelegramSender = Callable[[int, str, tuple[bytes, ...]], Awaitable[None]]
PWA_REVIEW_TELEGRAM_SENDER = web.AppKey(
    "pwa_review_telegram_sender", ReviewTelegramSender
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


async def _invalidate_review_queue(request: web.Request, *, reason: str) -> None:
    """Best-effort Staff refetch after an authoritative queue mutation."""

    invalidator = request.app.get(PWA_REVIEW_QUEUE_INVALIDATOR)
    if invalidator is None:
        return
    try:
        await invalidator(reason)
    except Exception:
        logger.warning(
            "Review queue invalidation failed after commit: reason=%s",
            reason,
            exc_info=True,
        )


def _review_telegram_text(
    problems: list[dict[str, object]],
    *,
    verdict: int,
    comment: str | None,
) -> str:
    labels = []
    for problem in problems:
        number = (
            f"{problem['lesson']}{problem.get('short_code') or ''}."
            f"{problem['prob']}{problem['item']}"
        )
        labels.append(f"{number} — {problem['title']}")
    if len(labels) == 1:
        lines = [f"Проверена задача {labels[0]}"]
    else:
        lines = ["Проверены задачи:", *(f"• {label}" for label in labels)]
    tick = VERDICT_TO_TICK.get(VERDICT(verdict), str(verdict))
    lines.extend(("", f"Результат: {tick}"))
    if comment:
        lines.extend(("", "Комментарий преподавателя:", comment))
    return "\n".join(lines)


async def _deliver_review_to_telegram(
    request: web.Request,
    *,
    review_public_id: str,
    comment: str | None,
) -> None:
    sender = request.app.get(PWA_REVIEW_TELEGRAM_SENDER)
    database = request.app.get(PWA_DATABASE)
    if sender is None or database is None or database.factory is None:
        return
    delivery = await database.factory.run_read_async(
        lambda connection: read_review_telegram_delivery(connection, review_public_id)
    )
    if delivery is None or delivery["chat_id"] is None:
        return

    images: list[bytes] = []
    storage = request.app.get(PWA_CONTENT_OBJECT_STORAGE)
    if storage is not None:
        for annotation in delivery["annotations"]:
            try:
                marks = json.loads(str(annotation["marks_json"]))
                source = await storage.get(str(annotation["object_key"]))
                images.append(
                    await render_review_annotation_composite_png(
                        source_webp=source,
                        rotation=int(annotation["rotation"]),
                        marks=marks,
                    )
                )
            except Exception:
                # A broken derivative must not hide the verdict or roll back the
                # authoritative review. See accepted-technical-decisions-2026-07.
                logger.warning(
                    "Review Telegram annotation failed: review=%s attachment=%s",
                    review_public_id,
                    annotation["attachment_public_id"],
                    exc_info=True,
                )
    try:
        await sender(
            int(delivery["chat_id"]),
            _review_telegram_text(
                delivery["problems"],
                verdict=int(delivery["verdict"]),
                comment=comment,
            ),
            tuple(images),
        )
    except Exception:
        logger.warning(
            "Review Telegram delivery failed after commit: review=%s",
            review_public_id,
            exc_info=True,
        )


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


def _require_reaction_admin(request: web.Request) -> None:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or not principal.is_global_admin
        or not principal.has_capability(Capability.AUDIT_READ)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Реакции учеников и преподавателей доступны только администратору",
        )


def _student_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STUDENT
        or principal.linked_user_id is None
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для реакции на эту проверку",
        )
    return principal.linked_user_id


def _queue_public_id(request: web.Request) -> str:
    value = request.match_info["queue_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="review_queue_item_not_found",
            message="Работа в очереди не найдена",
        )
    return value


def _review_public_id(request: web.Request) -> str:
    value = request.match_info["review_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="review_not_found",
            message="Проверка не найдена",
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


def _optional_reaction_id(value: str | None) -> int | None:
    if value is None:
        return None
    if re.fullmatch(r"\d{1,3}", value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте фильтр реакции",
            details={"field": "reactionId"},
        )
    return int(value)


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
        "problemNumber": item.problem_number,
        "problemTitle": item.problem_title,
        "courseId": item.course_public_id,
        "courseName": item.course_name,
        "groupId": item.group_public_id,
        "groupName": item.group_name,
        "groupShortCode": item.group_short_code,
        "groupColorKey": item.group_color_key,
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


def _reaction_inbox_payload(item: ReviewReactionInboxItem) -> dict[str, object]:
    return {
        "itemId": item.item_public_id,
        "reviewId": item.review_public_id,
        "kind": item.kind,
        "reactionId": item.reaction_id,
        "reactionLabel": item.reaction_label,
        "reactionVersion": item.reaction_version,
        "updatedAt": _timestamp(item.updated_at),
        "editableUntil": _timestamp(item.editable_until),
        "student": {
            "studentId": item.student_public_id,
            "displayName": item.student_name,
        },
        "reviewer": {
            "staffId": item.reviewer_public_id,
            "displayName": item.reviewer_name,
        },
        "problem": {
            "problemId": item.target_problem_public_id,
            "problemNumber": item.problem_number,
            "problemTitle": item.problem_title,
            "courseId": item.course_public_id,
            "courseName": item.course_name,
            "groupId": item.group_public_id,
            "groupName": item.group_name,
            "groupShortCode": item.group_short_code,
            "groupColorKey": item.group_color_key,
        },
        "verdict": item.verdict,
        "comment": item.comment,
        "completedAt": _timestamp(item.completed_at),
        "isLatestReview": item.is_latest_review,
        "evidenceEntries": [
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
            for entry in item.evidence_entries
        ],
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
                        "timelineEntries": [
                            {
                                "entryId": entry.entry_public_id,
                                "authorKind": entry.author_kind,
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
                            for entry in branch.timeline_entries
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


def _nonnegative_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные внутренней пометки",
            details={"field": field},
        )
    return value


def _internal_reaction_payload(
    state: ReviewInternalReactionState | None,
) -> dict[str, object] | None:
    if state is None:
        return None
    return {
        "reviewId": state.review_public_id,
        "reactionId": state.reaction_id,
        "version": state.version,
        "editableUntil": _timestamp(state.editable_until),
        "updatedAt": _timestamp(state.updated_at),
        "deleted": state.deleted,
    }


def _student_reaction_payload(
    state: ReviewStudentReactionState,
) -> dict[str, object]:
    return {
        "reactionId": state.reaction_id,
        "version": state.version,
        "editableUntil": _timestamp(state.editable_until),
        "updatedAt": _timestamp(state.updated_at),
        "deleted": state.deleted,
    }


async def _invalidate_student_reaction(
    request: web.Request,
    *,
    receipt: ReviewStudentReactionReceipt,
) -> None:
    invalidator = request.app.get(PWA_REVIEW_STUDENT_REACTION_INVALIDATOR)
    if invalidator is None:
        return
    try:
        await invalidator(
            receipt.owner_account_public_ids,
            receipt.family_account_public_ids,
            receipt.admin_account_public_ids,
            receipt.evidence_problem_public_ids,
            "written-review-student-reaction-changed",
        )
    except Exception:
        logger.warning(
            "Student reaction invalidation failed after commit: review=%s",
            receipt.state.review_public_id,
            exc_info=True,
        )


async def _invalidate_reaction_inbox(
    request: web.Request,
    *,
    reason: str,
) -> None:
    """Best-effort refresh for global admins after hidden reaction changes."""

    invalidator = request.app.get(PWA_REVIEW_REACTION_INBOX_INVALIDATOR)
    if invalidator is None:
        return
    try:
        account_public_ids = await _repository(
            request
        ).active_admin_account_public_ids()
        await invalidator(account_public_ids, reason)
    except Exception:
        logger.warning(
            "Review reaction inbox invalidation failed after commit: reason=%s",
            reason,
            exc_info=True,
        )


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


def _complete_annotations(value: object) -> tuple[ReviewAnnotationManifest, ...]:
    if not isinstance(value, list) or len(value) > 10:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте аннотации к работе",
            details={"field": "annotations"},
        )
    manifests: list[ReviewAnnotationManifest] = []
    try:
        for annotation_index, annotation in enumerate(value):
            if not isinstance(annotation, dict) or set(annotation) != {
                "attachmentId",
                "schemaVersion",
                "rotation",
                "marks",
            }:
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="Проверьте формат аннотации",
                    details={"field": f"annotations.{annotation_index}"},
                )
            marks_value = annotation["marks"]
            if not isinstance(marks_value, list):
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="Проверьте разметку фотографии",
                    details={"field": f"annotations.{annotation_index}.marks"},
                )
            marks: list[ReviewAnnotationMark] = []
            for mark_index, mark in enumerate(marks_value):
                if not isinstance(mark, dict) or set(mark) != {
                    "markId",
                    "kind",
                    "data",
                }:
                    raise PwaApiError(
                        status=422,
                        code="validation_error",
                        message="Проверьте элемент разметки",
                        details={
                            "field": (
                                f"annotations.{annotation_index}.marks.{mark_index}"
                            )
                        },
                    )
                kind = mark["kind"]
                if not isinstance(kind, str):
                    raise ReviewCompletionInvalid("annotation kind is invalid")
                marks.append(
                    ReviewAnnotationMark.from_payload(
                        mark_public_id=_required_public_id(
                            mark["markId"],
                            field=(
                                f"annotations.{annotation_index}.marks."
                                f"{mark_index}.markId"
                            ),
                        ),
                        kind=kind,
                        data=mark["data"],
                    )
                )
            schema_version = annotation["schemaVersion"]
            rotation = annotation["rotation"]
            if isinstance(schema_version, bool) or not isinstance(schema_version, int):
                raise ReviewCompletionInvalid("annotation schema version is invalid")
            if isinstance(rotation, bool) or not isinstance(rotation, int):
                raise ReviewCompletionInvalid("annotation rotation is invalid")
            manifests.append(
                ReviewAnnotationManifest(
                    attachment_public_id=_required_public_id(
                        annotation["attachmentId"],
                        field=f"annotations.{annotation_index}.attachmentId",
                    ),
                    schema_version=schema_version,
                    rotation=rotation,
                    marks=tuple(marks),
                )
            )
    except ReviewCompletionInvalid as error:
        raise PwaApiError(
            status=422,
            code="review_annotation_invalid",
            message="Проверьте аннотации к работе",
        ) from error
    return tuple(manifests)


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
    if isinstance(error, ReviewInternalReactionNotFound):
        return PwaApiError(
            status=404,
            code="review_internal_reaction_not_found",
            message="Внутренняя пометка не найдена",
        )
    if isinstance(error, ReviewInternalReactionInvalid):
        return PwaApiError(
            status=422,
            code="review_internal_reaction_invalid",
            message="Выберите доступную внутреннюю пометку",
        )
    if isinstance(error, ReviewInternalReactionConflict):
        return PwaApiError(
            status=409,
            code="review_internal_reaction_changed",
            message="Внутренняя пометка уже изменилась. Обновите проверку.",
        )
    if isinstance(error, ReviewInternalReactionWindowClosed):
        return PwaApiError(
            status=409,
            code="review_internal_reaction_window_closed",
            message="Время изменения внутренней пометки закончилось",
        )
    if isinstance(error, ReviewStudentReactionNotFound):
        return PwaApiError(
            status=404,
            code="review_not_found",
            message="Проверка не найдена",
        )
    if isinstance(error, ReviewStudentReactionInvalid):
        return PwaApiError(
            status=422,
            code="review_student_reaction_invalid",
            message="Выберите доступную реакцию",
        )
    if isinstance(error, ReviewStudentReactionConflict):
        return PwaApiError(
            status=409,
            code="review_student_reaction_changed",
            message="Реакция уже изменилась. Обновите проверку.",
        )
    if isinstance(error, ReviewStudentReactionWindowClosed):
        return PwaApiError(
            status=409,
            code="review_student_reaction_window_closed",
            message="Время изменения реакции закончилось",
        )
    if isinstance(error, ReviewCompletionInvalid):
        if "annotation" in str(error):
            return PwaApiError(
                status=422,
                code="review_annotation_invalid",
                message="Проверьте аннотации к работе",
            )
        return PwaApiError(
            status=422,
            code="review_confirmation_required",
            message="Подтвердите отправку вердикта без комментария",
        )
    raise error


@review_routes.get("/staff/api/v1/review/reactions")
async def list_review_reactions(request: web.Request) -> web.Response:
    _require_reaction_admin(request)
    if set(request.query) - _REACTION_INBOX_QUERY_FIELDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка реакций",
        )
    kind = request.query.get("kind", "all")
    if kind not in {"all", "student", "teacher"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный тип реакции",
            details={"field": "kind"},
        )
    try:
        page = await _repository(request).list_reaction_inbox(
            kind=kind,
            reaction_id=_optional_reaction_id(request.query.get("reactionId")),
            cursor=_optional_public_id(request.query.get("cursor"), field="cursor"),
            page_size=REVIEW_PAGE_SIZE,
        )
    except ReviewQueueNotFound as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Курсор списка реакций устарел",
            details={"field": "cursor"},
        ) from error
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте фильтры списка реакций",
        ) from error
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": [_reaction_inbox_payload(item) for item in page.items],
            "nextCursor": page.next_cursor,
            "requestId": request["request_id"],
        }
    )


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
    await _invalidate_review_queue(request, reason="review-queue-claimed")
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
    await _invalidate_review_queue(request, reason="review-queue-released")
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
            annotations=_complete_annotations(payload["annotations"]),
            internal_reaction_id=(
                None
                if payload["internalReactionId"] is None
                else _positive_integer(
                    payload["internalReactionId"], field="internalReactionId"
                )
            ),
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
        ReviewInternalReactionInvalid,
    ) as error:
        raise _translate_queue_error(error) from error
    except ValueError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте данные завершения проверки",
        ) from error
    if not receipt.replayed:
        database = request.app.get(PWA_DATABASE)
        if database is not None and database.factory is not None:
            try:
                await database.factory.run_write_async(
                    lambda connection: record_review_notifications(
                        connection,
                        account_public_ids=receipt.owner_account_public_ids,
                        review_public_id=receipt.review_public_id,
                        problem_public_ids=receipt.evidence_problem_public_ids,
                        completed_at=receipt.completed_at,
                    )
                )
            except Exception:
                logger.warning(
                    "Review notification failed after commit: review=%s",
                    receipt.review_public_id,
                    exc_info=True,
                )
    invalidator = request.app.get(PWA_REVIEW_COMPLETION_INVALIDATOR)
    if invalidator is not None and not receipt.replayed:
        try:
            await invalidator(
                receipt.owner_account_public_ids,
                receipt.family_account_public_ids,
                receipt.evidence_problem_public_ids,
                "written-review-completed",
            )
        except Exception:
            logger.warning(
                "Review completion invalidation failed after commit: review=%s",
                receipt.review_public_id,
                exc_info=True,
            )
    if receipt.internal_reaction is not None and not receipt.replayed:
        await _invalidate_reaction_inbox(
            request,
            reason="written-review-internal-reaction-created",
        )
    if not receipt.replayed:
        try:
            await _deliver_review_to_telegram(
                request,
                review_public_id=receipt.review_public_id,
                comment=comment,
            )
        except Exception:
            # The Telegram projection is never part of the review transaction.
            logger.warning(
                "Review Telegram projection failed after commit: review=%s",
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
                "annotations": [
                    {
                        "annotationId": annotation.annotation_public_id,
                        "attachmentId": annotation.attachment_public_id,
                        "schemaVersion": annotation.schema_version,
                        "rotation": annotation.rotation,
                        "markCount": annotation.mark_count,
                    }
                    for annotation in receipt.annotations
                ],
                "internalReaction": _internal_reaction_payload(
                    receipt.internal_reaction
                ),
                "completedAt": _timestamp(receipt.completed_at),
                "replayed": receipt.replayed,
            },
            "requestId": request["request_id"],
        }
    )


@review_routes.post("/staff/api/v1/reviews/{review_public_id}/correction")
async def correct_completed_review(request: web.Request) -> web.Response:
    reviewer_user_id, scope = _require_review_write(request)
    database = request.app.get(PWA_DATABASE)
    if database is None or database.factory is None:
        raise PwaApiError(
            status=503,
            code="review_queue_unavailable",
            message="Проверка временно недоступна",
        )
    payload = await _json_object(request, required_fields=_CORRECTION_FIELDS)
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
    principal = authenticated_session(request).principal
    try:
        receipt = await correct_written_review(
            database.factory,
            ReviewCorrectionCommand(
                source_review_public_id=_review_public_id(request),
                reviewer_user_id=reviewer_user_id,
                reviewer_type=(
                    int(USER_TYPE.ADMIN)
                    if principal.is_global_admin
                    else int(USER_TYPE.TEACHER)
                ),
                scope=scope,
                idempotency_key=_required_public_id(
                    payload["idempotencyKey"], field="idempotencyKey"
                ),
                verdict=verdict,
                comment=comment,
                confirm_without_comment=payload["confirmWithoutComment"],
            ),
        )
    except ReviewCorrectionNotFound as error:
        raise PwaApiError(
            status=404,
            code="review_not_found",
            message="Проверка не найдена",
        ) from error
    except ReviewCorrectionForbidden as error:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Эту проверку нельзя исправить с текущими правами",
        ) from error
    except ReviewCorrectionStale as error:
        raise PwaApiError(
            status=409,
            code="review_correction_stale",
            message="У работы уже есть более новая проверка. Обновите страницу.",
        ) from error
    except ReviewCorrectionConflict as error:
        raise PwaApiError(
            status=409,
            code="idempotency_payload_mismatch",
            message="Это действие уже было отправлено с другими данными",
        ) from error
    except ReviewCorrectionInvalid as error:
        raise PwaApiError(
            status=422,
            code="review_confirmation_required",
            message="Подтвердите отправку вердикта без комментария",
        ) from error

    if not receipt.replayed:
        try:
            await database.factory.run_write_async(
                lambda connection: record_review_notifications(
                    connection,
                    account_public_ids=receipt.owner_account_public_ids,
                    review_public_id=receipt.review_public_id,
                    problem_public_ids=(receipt.problem_public_id,),
                    completed_at=receipt.completed_at,
                )
            )
        except Exception:
            logger.warning(
                "Review correction notification failed after commit: review=%s",
                receipt.review_public_id,
                exc_info=True,
            )
        invalidator = request.app.get(PWA_REVIEW_COMPLETION_INVALIDATOR)
        if invalidator is not None:
            try:
                await invalidator(
                    receipt.owner_account_public_ids,
                    receipt.family_account_public_ids,
                    (receipt.problem_public_id,),
                    "written-review-corrected",
                )
            except Exception:
                logger.warning(
                    "Review correction invalidation failed after commit: review=%s",
                    receipt.review_public_id,
                    exc_info=True,
                )
        await _invalidate_reaction_inbox(request, reason="written-review-corrected")

    return web.json_response(
        {
            "schemaVersion": 1,
            "correction": {
                "reviewId": receipt.review_public_id,
                "correctsReviewId": receipt.source_review_public_id,
                "threadId": receipt.thread_public_id,
                "problemId": receipt.problem_public_id,
                "verdict": receipt.verdict,
                "threadStatus": receipt.status,
                "completedAt": _timestamp(receipt.completed_at),
                "replayed": receipt.replayed,
            },
            "requestId": request["request_id"],
        }
    )


@review_routes.put("/staff/api/v1/reviews/{review_public_id}/internal-reaction")
async def set_review_internal_reaction(request: web.Request) -> web.Response:
    teacher_user_id, scope = _require_review_write(request)
    payload = await _json_object(request, required_fields=_REACTION_SET_FIELDS)
    try:
        state = await _repository(request).set_internal_reaction(
            review_public_id=_review_public_id(request),
            reaction_id=_positive_integer(payload["reactionId"], field="reactionId"),
            expected_version=_nonnegative_integer(
                payload["expectedVersion"], field="expectedVersion"
            ),
            teacher_user_id=teacher_user_id,
            scope=scope,
        )
    except (
        ReviewInternalReactionNotFound,
        ReviewInternalReactionInvalid,
        ReviewInternalReactionConflict,
        ReviewInternalReactionWindowClosed,
        ReviewQueueForbidden,
    ) as error:
        raise _translate_queue_error(error) from error
    await _invalidate_reaction_inbox(
        request,
        reason="written-review-internal-reaction-changed",
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "internalReaction": _internal_reaction_payload(state),
            "requestId": request["request_id"],
        }
    )


@review_routes.delete("/staff/api/v1/reviews/{review_public_id}/internal-reaction")
async def delete_review_internal_reaction(request: web.Request) -> web.Response:
    teacher_user_id, scope = _require_review_write(request)
    payload = await _json_object(request, required_fields=_REACTION_DELETE_FIELDS)
    try:
        state = await _repository(request).delete_internal_reaction(
            review_public_id=_review_public_id(request),
            expected_version=_positive_integer(
                payload["expectedVersion"], field="expectedVersion"
            ),
            teacher_user_id=teacher_user_id,
            scope=scope,
        )
    except (
        ReviewInternalReactionNotFound,
        ReviewInternalReactionConflict,
        ReviewInternalReactionWindowClosed,
        ReviewQueueForbidden,
    ) as error:
        raise _translate_queue_error(error) from error
    await _invalidate_reaction_inbox(
        request,
        reason="written-review-internal-reaction-deleted",
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "internalReaction": _internal_reaction_payload(state),
            "requestId": request["request_id"],
        }
    )


@review_routes.put("/student/api/v1/reviews/{review_public_id}/reaction")
async def set_review_student_reaction(request: web.Request) -> web.Response:
    student_user_id = _student_user_id(request)
    payload = await _json_object(request, required_fields=_REACTION_SET_FIELDS)
    try:
        receipt = await _repository(request).set_student_reaction(
            review_public_id=_review_public_id(request),
            reaction_id=_nonnegative_integer(payload["reactionId"], field="reactionId"),
            expected_version=_nonnegative_integer(
                payload["expectedVersion"], field="expectedVersion"
            ),
            student_user_id=student_user_id,
        )
    except (
        ReviewStudentReactionNotFound,
        ReviewStudentReactionInvalid,
        ReviewStudentReactionConflict,
        ReviewStudentReactionWindowClosed,
    ) as error:
        raise _translate_queue_error(error) from error
    await _invalidate_student_reaction(request, receipt=receipt)
    return web.json_response(
        {
            "schemaVersion": 1,
            "reviewId": receipt.state.review_public_id,
            "studentReaction": _student_reaction_payload(receipt.state),
            "requestId": request["request_id"],
        }
    )


@review_routes.delete("/student/api/v1/reviews/{review_public_id}/reaction")
async def delete_review_student_reaction(request: web.Request) -> web.Response:
    student_user_id = _student_user_id(request)
    payload = await _json_object(request, required_fields=_REACTION_DELETE_FIELDS)
    try:
        receipt = await _repository(request).delete_student_reaction(
            review_public_id=_review_public_id(request),
            expected_version=_positive_integer(
                payload["expectedVersion"], field="expectedVersion"
            ),
            student_user_id=student_user_id,
        )
    except (
        ReviewStudentReactionNotFound,
        ReviewStudentReactionConflict,
        ReviewStudentReactionWindowClosed,
    ) as error:
        raise _translate_queue_error(error) from error
    await _invalidate_student_reaction(request, receipt=receipt)
    return web.json_response(
        {
            "schemaVersion": 1,
            "reviewId": receipt.state.review_public_id,
            "studentReaction": _student_reaction_payload(receipt.state),
            "requestId": request["request_id"],
        }
    )


__all__ = [
    "PWA_REVIEW_COMPLETION_INVALIDATOR",
    "PWA_REVIEW_QUEUE_INVALIDATOR",
    "PWA_REVIEW_QUEUE_REPOSITORY",
    "PWA_REVIEW_REACTION_INBOX_INVALIDATOR",
    "PWA_REVIEW_STUDENT_REACTION_INVALIDATOR",
    "PWA_REVIEW_TELEGRAM_SENDER",
    "ReviewTelegramSender",
    "review_routes",
]
