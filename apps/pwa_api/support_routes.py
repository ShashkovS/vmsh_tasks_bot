"""Authenticated HTTP adapter for private Student/Staff support threads."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.support import (
    AppendStaffSupportEntryCommand,
    AppendStudentSupportEntryCommand,
    CreateSupportThreadCommand,
    PwaSupportThreadRepository,
    SupportForbidden,
    SupportIdempotencyConflict,
    SupportInvalidationTargets,
    SupportNotFound,
    SupportStaffScope,
    SupportThreadPage,
    SupportThreadRecord,
    SupportThreadSummaryRecord,
)
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience


SUPPORT_BODY_LIMIT_BYTES = 128 * 1024
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_UTC_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_CREATE_FIELDS = frozenset(
    {
        "schemaVersion",
        "idempotencyKey",
        "kind",
        "groupLessonId",
        "problemId",
        "text",
        "clientCreatedAt",
    }
)
_APPEND_FIELDS = frozenset(
    {"schemaVersion", "idempotencyKey", "text", "clientCreatedAt"}
)
_STAFF_LIST_QUERY_FIELDS = frozenset({"state", "kind", "course", "group", "cursor"})

PWA_SUPPORT_REPOSITORY = web.AppKey(
    "pwa_support_repository", PwaSupportThreadRepository
)
SupportInvalidator = Callable[[SupportInvalidationTargets, str], Awaitable[None]]
PWA_SUPPORT_INVALIDATOR = web.AppKey("pwa_support_invalidator", SupportInvalidator)
support_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def _repository(request: web.Request) -> PwaSupportThreadRepository:
    repository = request.app.get(PWA_SUPPORT_REPOSITORY)
    if repository is None:
        raise PwaApiError(
            status=503,
            code="support_unavailable",
            message="Вопросы временно недоступны",
        )
    return repository


async def _invalidate_after_commit(
    request: web.Request, *, thread_public_id: str, reason: str
) -> None:
    invalidator = request.app.get(PWA_SUPPORT_INVALIDATOR)
    if invalidator is None:
        return
    try:
        targets = await _repository(request).invalidation_targets(
            thread_public_id=thread_public_id
        )
        await invalidator(targets, reason)
    except Exception:
        # SQLite is authoritative; a transient target lookup or NATS failure
        # must not turn a committed private message into an unsafe retry.
        logger.warning(
            "Support invalidation failed after commit: thread=%s reason=%s",
            thread_public_id,
            reason,
            exc_info=True,
        )


def _student_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STUDENT
        or principal.linked_user_id is None
        or not principal.has_capability(Capability.THREAD_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для работы с этим вопросом",
        )
    return principal.linked_user_id


def _staff_context(
    request: web.Request, *, write: bool
) -> tuple[int, str, SupportStaffScope]:
    principal = authenticated_session(request).principal
    required = Capability.REVIEW_WRITE if write else Capability.REVIEW_READ
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.has_capability(required)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Недостаточно прав для работы с вопросами школьников",
        )
    scope = SupportStaffScope(
        global_access=principal.is_global_admin,
        course_public_ids=frozenset(
            grant.course_public_id
            for grant in principal.staff_scope_grants
            if grant.group_public_id is None
        ),
        group_public_ids=frozenset(
            grant.group_public_id
            for grant in principal.staff_scope_grants
            if grant.group_public_id is not None
        ),
    )
    author_kind = "admin" if principal.is_global_admin else "teacher"
    return principal.linked_user_id, author_kind, scope


def _thread_public_id(request: web.Request) -> str:
    value = request.match_info["thread_public_id"]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="support_thread_not_found",
            message="Вопрос не найден",
        )
    return value


async def _json_object(
    request: web.Request, *, required_fields: frozenset[str]
) -> dict[str, object]:
    if (
        request.content_length is not None
        and request.content_length > SUPPORT_BODY_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Текст вопроса слишком большой",
        )
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть JSON",
        )
    body = await request.read()
    if len(body) > SUPPORT_BODY_LIMIT_BYTES:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Текст вопроса слишком большой",
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
            message="Проверьте поля вопроса",
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


def _public_id(value: object, *, field: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте контекст вопроса",
            details={"field": field},
        )
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 100_000:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Введите текст вопроса",
            details={"field": "text"},
        )
    return value


def _idempotency_key(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 200
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте ключ отправки",
            details={"field": "idempotencyKey"},
        )
    return value


def _client_created_at(value: object) -> datetime:
    if not isinstance(value, str) or _UTC_DATETIME.fullmatch(value) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время создания вопроса",
            details={"field": "clientCreatedAt"},
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:  # pragma: no cover - regex accepts impossible dates
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте время создания вопроса",
            details={"field": "clientCreatedAt"},
        ) from error
    return parsed.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _thread_payload(thread: SupportThreadRecord) -> dict[str, object]:
    return {
        "threadId": thread.thread_public_id,
        "kind": thread.kind,
        "student": {
            "studentId": thread.student_public_id,
            "displayName": thread.student_display_name,
        },
        "context": {
            "courseId": thread.course_public_id,
            "courseName": thread.course_name,
            "groupId": thread.group_public_id,
            "groupName": thread.group_name,
            "groupLessonId": thread.group_lesson_public_id,
            "problemId": thread.problem_public_id,
            "problemTitle": thread.problem_title,
            "problemNumber": thread.problem_number,
        },
        "latestEntryAt": _timestamp(thread.latest_entry_at),
        "problemDocument": thread.problem_document,
        "version": thread.version,
        "entries": [
            {
                "entryId": entry.entry_public_id,
                "author": {
                    "kind": entry.author_kind,
                    "userId": entry.author_public_id,
                    "displayName": entry.author_display_name,
                },
                "text": entry.text,
                "assetId": entry.asset_public_id,
                "channel": entry.channel,
                "clientCreatedAt": (
                    None
                    if entry.client_created_at is None
                    else _timestamp(entry.client_created_at)
                ),
                "receivedAt": _timestamp(entry.server_received_at),
            }
            for entry in thread.entries
        ],
    }


def _summary_payload(summary: SupportThreadSummaryRecord) -> dict[str, object]:
    return {
        "threadId": summary.thread_public_id,
        "kind": summary.kind,
        "student": {
            "studentId": summary.student_public_id,
            "displayName": summary.student_display_name,
        },
        "context": {
            "courseId": summary.course_public_id,
            "courseName": summary.course_name,
            "groupId": summary.group_public_id,
            "groupName": summary.group_name,
            "groupLessonId": summary.group_lesson_public_id,
            "problemId": summary.problem_public_id,
            "problemTitle": summary.problem_title,
            "problemNumber": summary.problem_number,
        },
        "latestEntry": {
            "authorKind": summary.latest_author_kind,
            "textExcerpt": summary.latest_text_excerpt,
            "receivedAt": _timestamp(summary.latest_entry_at),
        },
        "replyState": summary.reply_state,
        "entryCount": summary.entry_count,
        "version": summary.version,
    }


def _page_response(request: web.Request, page: SupportThreadPage) -> web.Response:
    items = [_summary_payload(item) for item in page.items]
    if request.headers.get("X-Vmsh-Support-Context") != "1":
        for item in items:
            item["context"].pop("problemNumber", None)
    return web.json_response(
        {
            "schemaVersion": 1,
            "items": items,
            "nextCursor": page.next_cursor,
            "requestId": request["request_id"],
        }
    )


def _query_value(
    request: web.Request, field: str, *, allowed: frozenset[str] | None = None
) -> str | None:
    values = request.query.getall(field, [])
    if len(values) > 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка вопросов",
            details={"field": field},
        )
    value = values[0] if values else None
    if value is not None and allowed is not None and value not in allowed:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка вопросов",
            details={"field": field},
        )
    return value


def _response(request: web.Request, thread: SupportThreadRecord) -> web.Response:
    # Old installed PWA validates strict v1 objects; extensions require opt-in.
    # See vmshpwa/docs/support-problem-context.md.
    payload = _thread_payload(thread)
    if request.headers.get("X-Vmsh-Support-Context") != "1":
        payload["context"].pop("problemNumber", None)
        payload.pop("problemDocument", None)
    return web.json_response(
        {
            "schemaVersion": 1,
            "thread": payload,
            "requestId": request["request_id"],
        }
    )


def _translate_error(error: Exception) -> PwaApiError:
    if isinstance(error, SupportNotFound):
        return PwaApiError(
            status=404,
            code="support_thread_not_found",
            message="Вопрос или его контекст не найден",
        )
    if isinstance(error, SupportForbidden):
        return PwaApiError(
            status=403,
            code="forbidden",
            message="Этот вопрос находится вне доступного контекста",
        )
    if isinstance(error, SupportIdempotencyConflict):
        return PwaApiError(
            status=409,
            code="idempotency_payload_mismatch",
            message="Это действие уже было отправлено с другими данными",
        )
    raise error


@support_routes.post("/student/api/v1/questions")
async def create_student_question(request: web.Request) -> web.Response:
    student_user_id = _student_user_id(request)
    payload = await _json_object(request, required_fields=_CREATE_FIELDS)
    kind = payload["kind"]
    if kind not in {"problem_question", "general"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте тип вопроса",
            details={"field": "kind"},
        )
    problem_public_id = _public_id(
        payload["problemId"], field="problemId", nullable=True
    )
    if (kind == "problem_question") != (problem_public_id is not None):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте задачу, к которой относится вопрос",
            details={"field": "problemId"},
        )
    try:
        thread = await _repository(request).create_student_thread(
            CreateSupportThreadCommand(
                student_user_id=student_user_id,
                kind=kind,
                group_lesson_public_id=_public_id(
                    payload["groupLessonId"], field="groupLessonId"
                ),
                problem_public_id=problem_public_id,
                text=_text(payload["text"]),
                client_created_at=_client_created_at(payload["clientCreatedAt"]),
                idempotency_key=_idempotency_key(payload["idempotencyKey"]),
            )
        )
    except (SupportNotFound, SupportForbidden, SupportIdempotencyConflict) as error:
        raise _translate_error(error) from error
    await _invalidate_after_commit(
        request,
        thread_public_id=thread.thread_public_id,
        reason="support-thread-created",
    )
    return _response(request, thread)


@support_routes.get("/student/api/v1/questions")
async def list_student_questions(request: web.Request) -> web.Response:
    if set(request.query) - {"cursor"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка вопросов",
        )
    cursor = _query_value(request, "cursor")
    if cursor is not None and _PUBLIC_ID.fullmatch(cursor) is None:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка вопросов",
            details={"field": "cursor"},
        )
    try:
        page = await _repository(request).list_student_threads(
            student_user_id=_student_user_id(request), cursor=cursor
        )
    except SupportNotFound as error:
        raise _translate_error(error) from error
    return _page_response(request, page)


@support_routes.get("/student/api/v1/questions/{thread_public_id}")
async def get_student_question(request: web.Request) -> web.Response:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="У этого запроса нет параметров",
        )
    try:
        thread = await _repository(request).get_student_thread(
            student_user_id=_student_user_id(request),
            thread_public_id=_thread_public_id(request),
        )
    except (SupportNotFound, SupportForbidden) as error:
        raise _translate_error(error) from error
    return _response(request, thread)


@support_routes.post("/student/api/v1/questions/{thread_public_id}/entries")
async def append_student_question_entry(request: web.Request) -> web.Response:
    payload = await _json_object(request, required_fields=_APPEND_FIELDS)
    try:
        thread = await _repository(request).append_student_entry(
            AppendStudentSupportEntryCommand(
                student_user_id=_student_user_id(request),
                thread_public_id=_thread_public_id(request),
                text=_text(payload["text"]),
                client_created_at=_client_created_at(payload["clientCreatedAt"]),
                idempotency_key=_idempotency_key(payload["idempotencyKey"]),
            )
        )
    except (SupportNotFound, SupportForbidden, SupportIdempotencyConflict) as error:
        raise _translate_error(error) from error
    await _invalidate_after_commit(
        request,
        thread_public_id=thread.thread_public_id,
        reason="support-student-entry-appended",
    )
    return _response(request, thread)


@support_routes.get("/staff/api/v1/questions/{thread_public_id}")
async def get_staff_question(request: web.Request) -> web.Response:
    if request.query:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="У этого запроса нет параметров",
        )
    _, _, scope = _staff_context(request, write=False)
    try:
        thread = await _repository(request).get_staff_thread(
            thread_public_id=_thread_public_id(request), scope=scope
        )
    except (SupportNotFound, SupportForbidden) as error:
        raise _translate_error(error) from error
    return _response(request, thread)


@support_routes.get("/staff/api/v1/questions")
async def list_staff_questions(request: web.Request) -> web.Response:
    if set(request.query) - _STAFF_LIST_QUERY_FIELDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры списка вопросов",
        )
    state = _query_value(
        request,
        "state",
        allowed=frozenset({"all", "awaiting_staff", "awaiting_student"}),
    )
    kind = _query_value(
        request,
        "kind",
        allowed=frozenset({"problem_question", "general", "sos"}),
    )
    course = _query_value(request, "course")
    group = _query_value(request, "group")
    cursor = _query_value(request, "cursor")
    for field, value in (("course", course), ("group", group), ("cursor", cursor)):
        if value is not None and _PUBLIC_ID.fullmatch(value) is None:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Проверьте параметры списка вопросов",
                details={"field": field},
            )
    _, _, scope = _staff_context(request, write=False)
    try:
        page = await _repository(request).list_staff_threads(
            scope=scope,
            state="awaiting_staff" if state is None else state,
            kind=kind,
            course_public_id=course,
            group_public_id=group,
            cursor=cursor,
        )
    except SupportNotFound as error:
        raise _translate_error(error) from error
    return _page_response(request, page)


@support_routes.post("/staff/api/v1/questions/{thread_public_id}/entries")
async def append_staff_question_entry(request: web.Request) -> web.Response:
    payload = await _json_object(request, required_fields=_APPEND_FIELDS)
    staff_user_id, author_kind, scope = _staff_context(request, write=True)
    try:
        thread = await _repository(request).append_staff_entry(
            AppendStaffSupportEntryCommand(
                staff_user_id=staff_user_id,
                author_kind=author_kind,
                thread_public_id=_thread_public_id(request),
                text=_text(payload["text"]),
                client_created_at=_client_created_at(payload["clientCreatedAt"]),
                idempotency_key=_idempotency_key(payload["idempotencyKey"]),
                scope=scope,
            )
        )
    except (SupportNotFound, SupportForbidden, SupportIdempotencyConflict) as error:
        raise _translate_error(error) from error
    await _invalidate_after_commit(
        request,
        thread_public_id=thread.thread_public_id,
        reason="support-staff-entry-appended",
    )
    return _response(request, thread)


__all__ = ["PWA_SUPPORT_INVALIDATOR", "PWA_SUPPORT_REPOSITORY", "support_routes"]
