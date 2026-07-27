"""Phase-2 LaTeX upload, compile, publication and audience read routes.

This adapter intentionally exposes one narrow vertical slice over the shared
SQLite domain.  The compiler remains pure, Telegram/Google are never imported,
and Student/Family responses contain only the current published
``WebContentDocument v1``.  Governing contract:
``vmshpwa/dev/development-plan/06-phase-2-content.md``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import unicodedata
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from functools import partial, wraps
from pathlib import PurePosixPath

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.content import (
    ContentConflict,
    ContentDerivativeRecord,
    ContentNotFound,
    ContentRepositoryError,
    ContentRevisionContext,
    ContentSourceLineageConflict,
    ContentVersionConflict,
    GroupLessonContentScope,
    LessonWindowRecord,
    PublicationContext,
    PublicationRecord,
    PwaContentRepository,
    TextDerivativeDraft,
)
from helpers.pwa.content import (
    COMPILER_VERSION,
    ContentCompileError,
    ContentRole,
    DiagnosticSeverity,
    compile_latex,
)
from helpers.pwa.content.model import canonical_json
from helpers.pwa.permissions import (
    AccessForbiddenError,
    AuthenticationRequiredError,
    AuthorizationPrincipal,
    Capability,
    require_access,
)
from models.pwa.auth import AuthAudience
from models.pwa.content import (
    ContentInvariantError,
    ContentKind,
    PublicationState,
    RevisionStatus,
    LessonWindowDraft,
    SourceRevisionPayload,
    WindowSource,
    resolve_local_wall_time,
)


CONTENT_UPLOAD_SOURCE_LIMIT_BYTES = 512 * 1024
CONTENT_UPLOAD_REQUEST_LIMIT_BYTES = CONTENT_UPLOAD_SOURCE_LIMIT_BYTES + 64 * 1024
CONTENT_JSON_BODY_LIMIT_BYTES = 32 * 1024
CONTENT_PREVIEW_TEXT_LIMIT_BYTES = 8_000_000
_UPLOAD_FIELDS = frozenset({"groupLessonId", "kind", "logicalFilename", "source"})
_PUBLISH_FIELDS = frozenset(
    {
        "groupLessonId",
        "kind",
        "revisionId",
        "mode",
        "scheduledLocalTime",
        "businessTimezone",
        "expectedCurrentPublicationId",
        "expectedCurrentVersion",
        "expectedScheduledPublicationId",
        "expectedScheduledVersion",
    }
)
_LESSON_WINDOW_CREATE_FIELDS = frozenset(
    {
        "opensLocalTime",
        "submissionClosesLocalTime",
        "hintScheduledLocalTime",
        "solutionScheduledLocalTime",
        "businessTimezone",
        "confirmSubmissionCutoff",
    }
)
_LESSON_WINDOW_SCHEDULE_FIELDS = frozenset(
    {
        "opensLocalTime",
        "hintScheduledLocalTime",
        "solutionScheduledLocalTime",
        "businessTimezone",
    }
)
_LESSON_WINDOW_CUTOFF_FIELDS = frozenset(
    {"submissionClosesLocalTime", "businessTimezone", "confirmChange"}
)
_ROLLBACK_FIELDS = frozenset(
    {"revisionId", "expectedScheduledPublicationId", "expectedScheduledVersion"}
)
_CANCEL_FIELDS = frozenset()
_HIDE_FIELDS = frozenset()
_STUDENT_KINDS = frozenset(
    {ContentKind.CONDITION, ContentKind.HINT, ContentKind.SOLUTION}
)

PWA_CONTENT_REPOSITORY = web.AppKey("pwa_content_repository", PwaContentRepository)
ContentInvalidator = Callable[
    [GroupLessonContentScope, ContentKind, str], Awaitable[None]
]
PWA_CONTENT_INVALIDATOR = web.AppKey("pwa_content_invalidator", ContentInvalidator)
content_routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


def _repository(request: web.Request) -> PwaContentRepository:
    try:
        return request.app[PWA_CONTENT_REPOSITORY]
    except KeyError as error:
        raise PwaApiError(
            status=503,
            code="content_unavailable",
            message="Работа с материалами временно недоступна",
        ) from error


async def _invalidate_after_commit(
    request: web.Request,
    *,
    scope: GroupLessonContentScope,
    kind: ContentKind,
    reason: str,
) -> None:
    """Best-effort live invalidation after SQLite has committed the mutation."""

    invalidator = request.app.get(PWA_CONTENT_INVALIDATOR)
    if invalidator is None:
        return
    try:
        await invalidator(scope, kind, reason)
    except Exception:
        # NATS is transport, never the durable publication log.  The committed
        # SQLite state remains authoritative and reconnect always refetches it.
        logger.warning(
            "Content invalidation failed after commit: lesson=%s kind=%s reason=%s",
            scope.group_lesson_public_id,
            kind.value,
            reason,
            exc_info=True,
        )


def _request_id(request: web.Request) -> str:
    return request["request_id"]


def _public_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContentRepositoryError("stored content timestamp is naive")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _local_timestamp(
    value: object,
    *,
    field: str,
    business_timezone: object,
    scope: GroupLessonContentScope,
) -> datetime:
    if business_timezone != scope.business_timezone:
        raise PwaApiError(
            status=422,
            code="business_timezone_mismatch",
            message="Часовой пояс занятия изменился. Обновите страницу.",
            details={"field": "businessTimezone"},
        )
    try:
        if not isinstance(value, str):
            raise ContentInvariantError("schedule local date-time is invalid")
        return resolve_local_wall_time(value, timezone=scope.business_timezone)
    except ContentInvariantError as error:
        raise PwaApiError(
            status=422,
            code="local_time_invalid",
            message=(
                "Укажите существующее однозначное местное время занятия "
                "с точностью до минуты"
            ),
            details={"field": field},
        ) from error


def _optional_local_timestamp(
    value: object,
    *,
    field: str,
    business_timezone: object,
    scope: GroupLessonContentScope,
) -> datetime | None:
    if value is None:
        if business_timezone != scope.business_timezone:
            raise PwaApiError(
                status=422,
                code="business_timezone_mismatch",
                message="Часовой пояс занятия изменился. Обновите страницу.",
                details={"field": "businessTimezone"},
            )
        return None
    return _local_timestamp(
        value,
        field=field,
        business_timezone=business_timezone,
        scope=scope,
    )


def _content_kind(value: object) -> ContentKind:
    try:
        kind = ContentKind(value)
    except (TypeError, ValueError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный вид материала",
            details={"field": "kind"},
        ) from error
    if kind not in _STUDENT_KINDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Этот вид материала нельзя публиковать",
            details={"field": "kind"},
        )
    return kind


def _content_role(kind: ContentKind) -> ContentRole:
    return ContentRole(kind.value)


def _authorize(
    request: web.Request,
    *,
    expected_audience: AuthAudience,
    capability: Capability,
    scope: GroupLessonContentScope,
    student_user_id: int | None = None,
) -> AuthorizationPrincipal:
    principal = authenticated_session(request).principal
    try:
        return require_access(
            principal,
            expected_audience=expected_audience,
            capability=capability,
            student_user_id=student_user_id,
            course_public_id=scope.course_public_id,
            group_public_id=scope.group_public_id,
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
            message="Недостаточно прав для этого действия",
        ) from error


def _staff_actor(
    request: web.Request, scope: GroupLessonContentScope
) -> tuple[AuthorizationPrincipal, int]:
    principal = _authorize(
        request,
        expected_audience=AuthAudience.STAFF,
        capability=Capability.CONTENT_MANAGE,
        scope=scope,
    )
    if principal.linked_user_id is None:  # pragma: no cover - principal invariant
        raise ContentRepositoryError("staff principal has no linked actor")
    return principal, principal.linked_user_id


def _family_student_user_id(request: web.Request) -> int:
    requested_public_id = request.match_info["student_public_id"]
    authenticated = authenticated_session(request)
    for child in authenticated.family_children:
        if child.student_public_id == requested_public_id:
            return child.student_user_id
    raise PwaApiError(
        status=403,
        code="forbidden",
        message="Недостаточно прав для просмотра этого ученика",
    )


def _translate_content_errors(
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
    @wraps(handler)
    async def wrapped(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)
        except ContentNotFound as error:
            raise PwaApiError(
                status=404,
                code="content_not_found",
                message="Материал не найден",
            ) from error
        except ContentVersionConflict as error:
            raise PwaApiError(
                status=409,
                code="version_conflict",
                message="Материал уже изменился. Обновите страницу.",
            ) from error
        except ContentSourceLineageConflict as error:
            raise PwaApiError(
                status=409,
                code="source_lineage_conflict",
                message=(
                    "У этого материала уже есть исходный файл. "
                    "Сохраните прежнее имя и кодировку."
                ),
                details={
                    "sourceId": error.source.public_id,
                    "logicalFilename": error.source.logical_filename,
                    "sourceEncoding": error.source.source_encoding,
                },
            ) from error
        except ContentConflict as error:
            raise PwaApiError(
                status=409,
                code="content_conflict",
                message="Изменение конфликтует с текущим состоянием материала",
            ) from error
        except ContentInvariantError as error:
            raise PwaApiError(
                status=422,
                code="content_validation_failed",
                message="Материал не прошёл проверку",
            ) from error
        except ContentRepositoryError as error:
            raise PwaApiError(
                status=500,
                code="content_storage_invalid",
                message="Не удалось безопасно прочитать материал",
            ) from error

    return wrapped


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
                message="Файл слишком большой",
            )
        chunks.append(chunk)


async def _multipart_upload(request: web.Request) -> dict[str, bytes]:
    if (
        request.content_length is not None
        and request.content_length > CONTENT_UPLOAD_REQUEST_LIMIT_BYTES
    ):
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Файл слишком большой",
        )
    if request.content_type != "multipart/form-data":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Загрузка должна использовать multipart/form-data",
        )
    try:
        reader = await request.multipart()
    except (AssertionError, ValueError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Не удалось разобрать форму загрузки",
        ) from error

    values: dict[str, bytes] = {}
    while part := await reader.next():
        name = part.name
        if name not in _UPLOAD_FIELDS or name in values:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Форма загрузки содержит неизвестное или повторное поле",
            )
        limit = CONTENT_UPLOAD_SOURCE_LIMIT_BYTES if name == "source" else 2_048
        values[name] = await _read_part_bytes(part, limit=limit)
    if set(values) != _UPLOAD_FIELDS:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Заполните все поля загрузки",
            details={"required": sorted(_UPLOAD_FIELDS)},
        )
    if not values["source"]:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="LaTeX-файл пуст",
            details={"field": "source"},
        )
    return values


def _decode_form_text(values: Mapping[str, bytes], name: str) -> str:
    try:
        value = values[name].decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Поля формы должны быть в UTF-8",
            details={"field": name},
        ) from error
    if value != value.strip() or not value:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
            details={"field": name},
        )
    return value


def _logical_source_name(value: str) -> str:
    path = PurePosixPath(value)
    if (
        len(value) > 240
        or value != unicodedata.normalize("NFKC", value)
        or value != path.as_posix()
        or path.is_absolute()
        or not path.name
        or path.suffix.casefold() != ".tex"
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Имя LaTeX-файла должно быть безопасным относительным путём .tex",
            details={"field": "logicalFilename"},
        )
    return value


def _source_payload(source_bytes: bytes, *, filename: str) -> SourceRevisionPayload:
    if source_bytes.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
        had_bom = True
    else:
        had_bom = False
        try:
            source_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            try:
                source_bytes.decode("cp1251", errors="strict")
            except UnicodeDecodeError as error:
                raise PwaApiError(
                    status=422,
                    code="source_encoding_unsupported",
                    message="LaTeX-файл должен быть в UTF-8 или Windows-1251",
                ) from error
            encoding = "cp1251"
        else:
            encoding = "utf-8"
    return SourceRevisionPayload.from_bytes(
        source_bytes,
        encoding=encoding,
        provenance={
            "logicalFilename": filename,
            "sourceHadUtf8Bom": had_bom,
            "uploadProtocol": "staff-multipart-v1",
        },
    )


async def _json_object(
    request: web.Request, *, allowed_fields: frozenset[str]
) -> dict[str, object]:
    if (
        request.content_length is not None
        and request.content_length > CONTENT_JSON_BODY_LIMIT_BYTES
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
    try:
        body = await request.read()
    except web.HTTPRequestEntityTooLarge as error:
        raise PwaApiError(
            status=413,
            code="payload_too_large",
            message="Запрос слишком большой",
        ) from error
    if len(body) > CONTENT_JSON_BODY_LIMIT_BYTES:
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
    if not isinstance(payload, dict) or set(payload) != allowed_fields:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
            details={"required": sorted(allowed_fields)},
        )
    return payload


def _etag(public_id: str, version: int) -> str:
    return f'"{public_id}:v{version}"'


def _none_etag() -> str:
    return '"none"'


def _require_if_match(request: web.Request, expected: str) -> None:
    values = request.headers.getall("If-Match", [])
    if len(values) != 1:
        raise PwaApiError(
            status=422,
            code="if_match_required",
            message="Обновите данные перед сохранением",
        )
    if values[0] != expected:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Материал уже изменился. Обновите страницу.",
        )


def _diagnostics(value: object) -> list[object]:
    try:
        parsed = json.loads(canonical_json(value))
    except (TypeError, ValueError, RecursionError) as error:
        raise ContentRepositoryError("compiler diagnostics are invalid") from error
    if not isinstance(parsed, list):
        raise ContentRepositoryError("compiler diagnostics are invalid")
    return parsed


def _canonical_ast(value: object) -> object:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError, RecursionError) as error:
        raise ContentRepositoryError("compiler AST is invalid") from error


def _missing_assets(value: object) -> list[str]:
    missing: set[str] = set()
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > 200_000:
            raise ContentRepositoryError("compiler AST exceeds read boundary")
        if isinstance(current, dict):
            if (
                current.get("kind") == "asset"
                and current.get("content_sha256") is None
                and isinstance(current.get("logical_name"), str)
            ):
                missing.add(current["logical_name"])
            stack.extend(current.values())
        elif isinstance(current, list | tuple):
            stack.extend(current)
    return sorted(missing)


def _revision_payload(context: ContentRevisionContext) -> dict[str, object]:
    revision = context.revision
    return {
        "revisionId": revision.public_id,
        "sourceId": context.source.public_id,
        "groupLessonId": context.scope.group_lesson_public_id,
        "courseId": context.scope.course_public_id,
        "groupId": context.scope.group_public_id,
        "kind": context.source.kind.value,
        "logicalFilename": context.source.logical_filename,
        "revisionNumber": revision.revision_number,
        "status": revision.status.value,
        "version": revision.version,
        "sourceSha256": revision.source_sha256,
        "parserVersion": revision.parser_version,
        "compileLeaseExpiresAt": _iso(revision.compile_lease_expires_at),
        "compileAttempt": revision.compile_attempt_count,
        "diagnostics": list(revision.diagnostics),
        "missingAssets": _missing_assets(revision.canonical_document),
    }


def _publication_payload(record: PublicationRecord) -> dict[str, object]:
    return {
        "publicationId": record.public_id,
        "kind": record.kind.value,
        "state": record.state.value,
        "version": record.version,
        "scheduledAt": _iso(record.scheduled_at),
        "publishedAt": _iso(record.published_at),
        "hiddenAt": _iso(record.hidden_at),
    }


def _lesson_window_payload(
    record: LessonWindowRecord, *, group_lesson_public_id: str
) -> dict[str, object]:
    return {
        "lessonWindowId": record.public_id,
        "groupLessonId": group_lesson_public_id,
        "opensAt": _iso(record.opens_at),
        "submissionClosesAt": _iso(record.submission_closes_at),
        "hintScheduledAt": _iso(record.hint_scheduled_at),
        "solutionScheduledAt": _iso(record.solution_scheduled_at),
        "businessTimezone": record.timezone,
        "source": record.source,
        "version": record.version,
    }


async def _require_publication_readiness(
    repository: PwaContentRepository,
    context: ContentRevisionContext,
) -> None:
    readiness = await repository.get_revision_publication_readiness(
        revision_id=context.revision.id
    )
    if readiness.is_ready:
        return
    raise PwaApiError(
        status=422,
        code="problem_review_incomplete",
        message=(
            "Сначала сопоставьте все задачи и подтвердите их метаданные."
        ),
        details={
            "expectedProblems": readiness.expected_problem_count,
            "resolvedMatches": readiness.resolved_match_count,
            "reviewedProblems": readiness.reviewed_problem_count,
            "omittedProblems": readiness.omitted_problem_count,
            "structureMatches": readiness.structure_matches,
        },
    )


async def _require_solution_cutoff(
    repository: PwaContentRepository,
    *,
    scope: GroupLessonContentScope,
    kind: ContentKind,
) -> None:
    if kind is not ContentKind.SOLUTION:
        return
    window = await repository.get_lesson_window(
        group_lesson_id=scope.group_lesson_id
    )
    if window is None:
        raise PwaApiError(
            status=422,
            code="submission_cutoff_required",
            message=(
                "До публикации или планирования решения задайте дедлайн сдачи."
            ),
        )


def _publication_context_payload(
    context: PublicationContext,
) -> dict[str, object]:
    record = context.publication
    return {
        **_publication_payload(record),
        "revisionId": context.revision_public_id,
        "etag": _etag(record.public_id, record.version),
    }


def _reconstruct_source_bytes(context: ContentRevisionContext) -> bytes:
    revision = context.revision
    if context.source.source_encoding == "cp1251":
        encoding = "cp1251"
        prefix = b""
    elif context.source.source_encoding == "utf-8":
        encoding = "utf-8"
        prefix = (
            b"\xef\xbb\xbf"
            if revision.provenance.get("sourceHadUtf8Bom") is True
            else b""
        )
    else:  # pragma: no cover - database constraint
        raise ContentRepositoryError("stored source encoding is invalid")
    try:
        payload = prefix + revision.latex_text.encode(encoding, errors="strict")
    except UnicodeEncodeError as error:
        raise ContentRepositoryError(
            "stored source text contradicts encoding"
        ) from error
    if hashlib.sha256(payload).hexdigest() != revision.source_sha256:
        raise ContentRepositoryError("stored source bytes do not match their hash")
    return payload


def _web_document(
    derivative: ContentDerivativeRecord,
    *,
    revision_public_id: str,
    kind: ContentKind,
) -> Mapping[str, object]:
    content = derivative.content_text
    if (
        content is None
        or len(content.encode("utf-8")) > CONTENT_PREVIEW_TEXT_LIMIT_BYTES
    ):
        raise ContentRepositoryError("stored web document is invalid")
    try:
        document = json.loads(content)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ContentRepositoryError("stored web document is invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("contractVersion") != 1
        or document.get("revisionId") != revision_public_id
        or document.get("materialKind") != kind.value
    ):
        raise ContentRepositoryError("stored web document is invalid")
    return document


def _compile_failure_diagnostic(
    *, source_name: str, message: str, code: str = "compiler.source_invalid"
) -> dict[str, object]:
    return {
        "code": code,
        "severity": DiagnosticSeverity.ERROR.value,
        "message": message,
        "span": {
            "source_name": source_name,
            "start": {"offset": 0, "line": 1, "column": 1},
            "end": {"offset": 0, "line": 1, "column": 1},
        },
        "recovery": "Исправьте LaTeX-файл и загрузите новую revision.",
    }


@content_routes.post("/staff/api/v1/content/uploads")
@_translate_content_errors
async def upload_content_source(request: web.Request) -> web.Response:
    values = await _multipart_upload(request)
    group_lesson_public_id = _decode_form_text(values, "groupLessonId")
    kind = _content_kind(_decode_form_text(values, "kind"))
    filename = _logical_source_name(_decode_form_text(values, "logicalFilename"))
    repository = _repository(request)
    scope = await repository.get_group_lesson_scope(group_lesson_public_id)
    _principal, actor_user_id = _staff_actor(request, scope)
    payload = _source_payload(values["source"], filename=filename)
    context = await repository.resolve_source_and_append_revision(
        source_public_id=_public_id("content-source"),
        revision_public_id=_public_id("content-revision"),
        group_lesson_id=scope.group_lesson_id,
        kind=kind,
        logical_filename=filename,
        payload=payload,
        actor_user_id=actor_user_id,
    )
    revision = context.revision
    response = web.json_response(
        {**_revision_payload(context), "requestId": _request_id(request)}, status=201
    )
    response.headers["ETag"] = _etag(revision.public_id, revision.version)
    return response


@content_routes.get("/staff/api/v1/content/uploads/{revision_id}/diagnostics")
@_translate_content_errors
async def content_diagnostics(request: web.Request) -> web.Response:
    context = await _repository(request).get_revision_context(
        request.match_info["revision_id"]
    )
    _staff_actor(request, context.scope)
    response = web.json_response(_revision_payload(context))
    response.headers["ETag"] = _etag(
        context.revision.public_id, context.revision.version
    )
    return response


@content_routes.post("/staff/api/v1/content/revisions/{revision_id}/compile")
@_translate_content_errors
async def compile_content_revision(request: web.Request) -> web.Response:
    repository = _repository(request)
    context = await repository.get_revision_context(request.match_info["revision_id"])
    _staff_actor(request, context.scope)
    _require_if_match(
        request, _etag(context.revision.public_id, context.revision.version)
    )
    claim_token = uuid.uuid4().hex
    compiling = await repository.claim_revision_compilation(
        public_id=context.revision.public_id,
        expected_version=context.revision.version,
        claim_token=claim_token,
        parser_version=COMPILER_VERSION,
    )
    try:
        result = None
        canonical_ast = None
        derivatives: tuple[TextDerivativeDraft, ...] | None = None
        compile_has_errors = True
        try:
            source_bytes = _reconstruct_source_bytes(context)
            result = await asyncio.to_thread(
                partial(
                    compile_latex,
                    source_bytes,
                    source_name=context.source.logical_filename,
                    role=_content_role(context.source.kind),
                    known_assets={},
                    revision_id=context.revision.public_id,
                )
            )
            diagnostics = _diagnostics(result.diagnostics)
            canonical_ast = _canonical_ast(result.ast)
            compile_has_errors = result.has_errors
            if not compile_has_errors and result.web_document is not None:
                web_document = json.loads(result.web_document.content)
                if (
                    not isinstance(web_document, dict)
                    or web_document.get("contractVersion") != 1
                    or web_document.get("revisionId") != context.revision.public_id
                    or web_document.get("materialKind") != context.source.kind.value
                ):
                    raise ContentRepositoryError(
                        "compiler returned an invalid persisted document"
                    )
                provenance = {
                    "compilerVersion": COMPILER_VERSION,
                    "sourceSha256": context.revision.source_sha256,
                    "astSha256": result.ast_sha256,
                    "contentKind": context.source.kind.value,
                    "requestId": _request_id(request),
                }
                derivatives = (
                    TextDerivativeDraft(
                        kind="web_ast",
                        renderer_version=result.web_document.renderer_version,
                        provenance=provenance,
                        content_text=result.web_document.content,
                    ),
                    TextDerivativeDraft(
                        kind="web_html",
                        renderer_version=result.web.renderer_version,
                        provenance=provenance,
                        content_text=result.web.content,
                    ),
                    TextDerivativeDraft(
                        kind="telegram_html",
                        renderer_version=result.telegram.renderer_version,
                        provenance=provenance,
                        content_text=result.telegram.content,
                    ),
                )
        except ContentCompileError as error:
            result = None
            diagnostics = [
                _compile_failure_diagnostic(
                    source_name=context.source.logical_filename,
                    message=str(error),
                )
            ]
        except asyncio.CancelledError:
            raise
        except Exception:
            result = None
            logger.exception(
                "Unexpected or invalid content compiler result for revision %s",
                context.revision.public_id,
            )
            diagnostics = [
                _compile_failure_diagnostic(
                    source_name=context.source.logical_filename,
                    code="compiler.internal_error",
                    message=(
                        "Внутренняя ошибка компилятора. "
                        "Загрузите новую revision или обратитесь к администратору."
                    ),
                )
            ]

        if result is None or compile_has_errors or derivatives is None:
            invalid_revision = await repository.fail_revision_compilation(
                public_id=context.revision.public_id,
                expected_version=compiling.version,
                claim_token=claim_token,
                parser_version=COMPILER_VERSION,
                canonical_document=canonical_ast,
                diagnostics=diagnostics,
            )
            invalid_context = await repository.get_revision_context(
                invalid_revision.public_id
            )
            raise PwaApiError(
                status=422,
                code="content_compile_invalid",
                message="LaTeX-файл содержит ошибки и не может быть опубликован",
                details=_revision_payload(invalid_context),
                headers={
                    "ETag": _etag(invalid_revision.public_id, invalid_revision.version)
                },
            )

        try:
            ready = await repository.complete_revision_compilation(
                public_id=context.revision.public_id,
                expected_version=compiling.version,
                claim_token=claim_token,
                parser_version=COMPILER_VERSION,
                canonical_document=canonical_ast,
                diagnostics=diagnostics,
                derivatives=derivatives,
            )
        except (ContentRepositoryError, ContentInvariantError) as error:
            persistence_diagnostic = _compile_failure_diagnostic(
                source_name=context.source.logical_filename,
                code="compiler.persistence_failed",
                message="Не удалось атомарно сохранить производные компиляции.",
            )
            try:
                await repository.fail_revision_compilation(
                    public_id=context.revision.public_id,
                    expected_version=compiling.version,
                    claim_token=claim_token,
                    parser_version=COMPILER_VERSION,
                    canonical_document=canonical_ast,
                    diagnostics=[*diagnostics, persistence_diagnostic],
                )
            except ContentRepositoryError:
                logger.warning(
                    "Could not terminally fail compile claim %s",
                    context.revision.public_id,
                    exc_info=True,
                )
            raise error
    except asyncio.CancelledError:
        try:
            await asyncio.shield(
                repository.abandon_revision_compilation(
                    public_id=context.revision.public_id,
                    expected_version=compiling.version,
                    claim_token=claim_token,
                )
            )
        except ContentRepositoryError:
            logger.warning(
                "Could not abandon cancelled compile claim %s",
                context.revision.public_id,
                exc_info=True,
            )
        raise

    ready_context = await repository.get_revision_context(ready.public_id)
    response = web.json_response(
        {**_revision_payload(ready_context), "requestId": _request_id(request)}
    )
    response.headers["ETag"] = _etag(ready.public_id, ready.version)
    return response


@content_routes.get(
    "/staff/api/v1/content/revisions/{revision_id}/previews/{preview:web|telegram}"
)
@_translate_content_errors
async def content_preview(request: web.Request) -> web.Response:
    repository = _repository(request)
    context = await repository.get_revision_context(request.match_info["revision_id"])
    _staff_actor(request, context.scope)
    if context.revision.status is not RevisionStatus.READY:
        raise PwaApiError(
            status=422,
            code="revision_not_ready",
            message="Preview доступно только после успешной компиляции",
        )
    preview = request.match_info["preview"]
    derivative = await repository.get_active_derivative(
        revision_id=context.revision.id,
        kind="web_ast" if preview == "web" else "telegram_html",
    )
    if preview == "web":
        payload: dict[str, object] = {
            "revisionId": context.revision.public_id,
            "kind": "web",
            "document": _web_document(
                derivative,
                revision_public_id=context.revision.public_id,
                kind=context.source.kind,
            ),
        }
    else:
        if derivative.content_text is None:
            raise ContentRepositoryError("stored Telegram derivative is invalid")
        payload = {
            "revisionId": context.revision.public_id,
            "kind": "telegram",
            "html": derivative.content_text,
        }
    return web.json_response(payload)


def _expected_slot(
    payload: Mapping[str, object],
    *,
    public_id_field: str,
    version_field: str,
    label: str,
) -> tuple[str | None, int | None]:
    public_id = payload[public_id_field]
    version = payload[version_field]
    if public_id is None and version is None:
        return None, None
    if (
        not isinstance(public_id, str)
        or not public_id
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message=f"{label} указана неверно",
        )
    return public_id, version


def _expected_current(payload: Mapping[str, object]) -> tuple[str | None, int | None]:
    return _expected_slot(
        payload,
        public_id_field="expectedCurrentPublicationId",
        version_field="expectedCurrentVersion",
        label="Текущая версия публикации",
    )


def _expected_scheduled(
    payload: Mapping[str, object],
) -> tuple[str | None, int | None]:
    return _expected_slot(
        payload,
        public_id_field="expectedScheduledPublicationId",
        version_field="expectedScheduledVersion",
        label="Текущая отложенная публикация",
    )


async def _authorized_lesson_window_scope(
    request: web.Request,
) -> tuple[PwaContentRepository, GroupLessonContentScope, int]:
    repository = _repository(request)
    scope = await repository.get_group_lesson_scope(
        request.match_info["group_lesson_id"]
    )
    _principal, actor_user_id = _staff_actor(request, scope)
    return repository, scope, actor_user_id


@content_routes.get(
    "/staff/api/v1/group-lessons/{group_lesson_id}/lesson-window"
)
@_translate_content_errors
async def get_lesson_window(request: web.Request) -> web.Response:
    repository, scope, _actor_user_id = await _authorized_lesson_window_scope(request)
    window = await repository.get_lesson_window(
        group_lesson_id=scope.group_lesson_id
    )
    if window is None:
        raise ContentNotFound("lesson window does not exist")
    response = web.json_response(
        {
            **_lesson_window_payload(
                window, group_lesson_public_id=scope.group_lesson_public_id
            ),
            "requestId": _request_id(request),
        }
    )
    response.headers["ETag"] = _etag(window.public_id, window.version)
    return response


@content_routes.post(
    "/staff/api/v1/group-lessons/{group_lesson_id}/lesson-window"
)
@_translate_content_errors
async def create_lesson_window(request: web.Request) -> web.Response:
    payload = await _json_object(
        request, allowed_fields=_LESSON_WINDOW_CREATE_FIELDS
    )
    repository, scope, actor_user_id = await _authorized_lesson_window_scope(request)
    _require_if_match(request, _none_etag())
    if payload["confirmSubmissionCutoff"] is not True:
        raise PwaApiError(
            status=422,
            code="submission_cutoff_confirmation_required",
            message="Подтвердите дедлайн сдачи отдельным действием.",
            details={"field": "confirmSubmissionCutoff"},
        )
    timezone = payload["businessTimezone"]
    window = await repository.create_lesson_window_with_audit(
        public_id=_public_id("lesson-window"),
        audit_public_id=_public_id("lesson-window-change"),
        group_lesson_id=scope.group_lesson_id,
        draft=LessonWindowDraft(
            opens_at=_optional_local_timestamp(
                payload["opensLocalTime"],
                field="opensLocalTime",
                business_timezone=timezone,
                scope=scope,
            ),
            submission_closes_at=_local_timestamp(
                payload["submissionClosesLocalTime"],
                field="submissionClosesLocalTime",
                business_timezone=timezone,
                scope=scope,
            ),
            hint_scheduled_at=_optional_local_timestamp(
                payload["hintScheduledLocalTime"],
                field="hintScheduledLocalTime",
                business_timezone=timezone,
                scope=scope,
            ),
            solution_scheduled_at=_optional_local_timestamp(
                payload["solutionScheduledLocalTime"],
                field="solutionScheduledLocalTime",
                business_timezone=timezone,
                scope=scope,
            ),
            timezone=scope.business_timezone,
            source=WindowSource.NATIVE,
        ),
        actor_user_id=actor_user_id,
        request_id=_request_id(request),
    )
    response = web.json_response(
        {
            **_lesson_window_payload(
                window, group_lesson_public_id=scope.group_lesson_public_id
            ),
            "requestId": _request_id(request),
        },
        status=201,
    )
    response.headers["ETag"] = _etag(window.public_id, window.version)
    return response


@content_routes.patch(
    "/staff/api/v1/group-lessons/{group_lesson_id}/lesson-window/schedule"
)
@_translate_content_errors
async def update_lesson_window_schedule(request: web.Request) -> web.Response:
    payload = await _json_object(
        request, allowed_fields=_LESSON_WINDOW_SCHEDULE_FIELDS
    )
    repository, scope, actor_user_id = await _authorized_lesson_window_scope(request)
    current = await repository.get_lesson_window(
        group_lesson_id=scope.group_lesson_id
    )
    if current is None:
        raise ContentNotFound("lesson window does not exist")
    _require_if_match(request, _etag(current.public_id, current.version))
    timezone = payload["businessTimezone"]
    window = await repository.update_lesson_window_schedule_with_audit(
        public_id=current.public_id,
        expected_version=current.version,
        audit_public_id=_public_id("lesson-window-change"),
        opens_at=_optional_local_timestamp(
            payload["opensLocalTime"],
            field="opensLocalTime",
            business_timezone=timezone,
            scope=scope,
        ),
        hint_scheduled_at=_optional_local_timestamp(
            payload["hintScheduledLocalTime"],
            field="hintScheduledLocalTime",
            business_timezone=timezone,
            scope=scope,
        ),
        solution_scheduled_at=_optional_local_timestamp(
            payload["solutionScheduledLocalTime"],
            field="solutionScheduledLocalTime",
            business_timezone=timezone,
            scope=scope,
        ),
        actor_user_id=actor_user_id,
        request_id=_request_id(request),
    )
    response = web.json_response(
        {
            **_lesson_window_payload(
                window, group_lesson_public_id=scope.group_lesson_public_id
            ),
            "requestId": _request_id(request),
        }
    )
    response.headers["ETag"] = _etag(window.public_id, window.version)
    return response


@content_routes.patch(
    "/staff/api/v1/group-lessons/{group_lesson_id}/lesson-window/submission-cutoff"
)
@_translate_content_errors
async def update_submission_cutoff(request: web.Request) -> web.Response:
    payload = await _json_object(
        request, allowed_fields=_LESSON_WINDOW_CUTOFF_FIELDS
    )
    repository, scope, actor_user_id = await _authorized_lesson_window_scope(request)
    current = await repository.get_lesson_window(
        group_lesson_id=scope.group_lesson_id
    )
    if current is None:
        raise ContentNotFound("lesson window does not exist")
    _require_if_match(request, _etag(current.public_id, current.version))
    if payload["confirmChange"] is not True:
        raise PwaApiError(
            status=422,
            code="submission_cutoff_confirmation_required",
            message="Подтвердите изменение дедлайна отдельным действием.",
            details={"field": "confirmChange"},
        )
    window = await repository.update_submission_cutoff_with_audit(
        public_id=current.public_id,
        expected_version=current.version,
        audit_public_id=_public_id("lesson-window-change"),
        submission_closes_at=_local_timestamp(
            payload["submissionClosesLocalTime"],
            field="submissionClosesLocalTime",
            business_timezone=payload["businessTimezone"],
            scope=scope,
        ),
        actor_user_id=actor_user_id,
        request_id=_request_id(request),
    )
    response = web.json_response(
        {
            **_lesson_window_payload(
                window, group_lesson_public_id=scope.group_lesson_public_id
            ),
            "requestId": _request_id(request),
        }
    )
    response.headers["ETag"] = _etag(window.public_id, window.version)
    return response


@content_routes.post("/staff/api/v1/publications")
@_translate_content_errors
async def publish_content_revision(request: web.Request) -> web.Response:
    payload = await _json_object(request, allowed_fields=_PUBLISH_FIELDS)
    group_lesson_public_id = payload["groupLessonId"]
    revision_public_id = payload["revisionId"]
    if not isinstance(group_lesson_public_id, str) or not isinstance(
        revision_public_id, str
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
        )
    kind = _content_kind(payload["kind"])
    mode = payload["mode"]
    if mode not in {"publish", "schedule"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Неизвестный режим публикации",
            details={"field": "mode"},
        )
    repository = _repository(request)
    revision_context = await repository.get_revision_context(revision_public_id)
    _principal, actor_user_id = _staff_actor(request, revision_context.scope)
    if (
        revision_context.scope.group_lesson_public_id != group_lesson_public_id
        or revision_context.source.kind is not kind
    ):
        raise PwaApiError(
            status=422,
            code="revision_scope_mismatch",
            message="Revision относится к другому занятию или виду материала",
        )
    if revision_context.revision.status is not RevisionStatus.READY:
        raise PwaApiError(
            status=422,
            code="revision_not_publishable",
            message="Публиковать можно только успешно скомпилированную revision",
        )
    await _require_publication_readiness(repository, revision_context)
    await _require_solution_cutoff(
        repository,
        scope=revision_context.scope,
        kind=kind,
    )
    state = (
        PublicationState.PUBLISHED if mode == "publish" else PublicationState.SCHEDULED
    )
    scheduled_at = (
        None
        if state is PublicationState.PUBLISHED
        else _local_timestamp(
            payload["scheduledLocalTime"],
            field="scheduledLocalTime",
            business_timezone=payload["businessTimezone"],
            scope=revision_context.scope,
        )
    )
    if state is PublicationState.PUBLISHED and (
        payload["scheduledLocalTime"] is not None
        or payload["businessTimezone"] is not None
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message=(
                "Немедленная публикация не принимает местное время или часовой пояс"
            ),
        )
    expected_public_id, expected_version = _expected_current(payload)
    expected_scheduled_id, expected_scheduled_version = _expected_scheduled(payload)
    if state is PublicationState.SCHEDULED and (
        expected_scheduled_id != expected_public_id
        or expected_scheduled_version != expected_version
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message=("Для расписания текущая и отложенная версии должны совпадать"),
        )
    expected_tag = (
        _none_etag()
        if expected_public_id is None
        else _etag(expected_public_id, expected_version)
    )
    _require_if_match(request, expected_tag)
    current = await repository.get_current_publication(
        group_lesson_id=revision_context.scope.group_lesson_id,
        kind=kind,
        state=state,
    )
    if (current is None) != (expected_public_id is None) or (
        current is not None
        and (
            current.public_id != expected_public_id
            or current.version != expected_version
        )
    ):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Публикация уже изменилась. Обновите страницу.",
        )
    if state is PublicationState.PUBLISHED:
        scheduled = await repository.get_current_publication(
            group_lesson_id=revision_context.scope.group_lesson_id,
            kind=kind,
            state=PublicationState.SCHEDULED,
        )
        if (scheduled is None) != (expected_scheduled_id is None) or (
            scheduled is not None
            and (
                scheduled.public_id != expected_scheduled_id
                or scheduled.version != expected_scheduled_version
            )
        ):
            raise PwaApiError(
                status=409,
                code="version_conflict",
                message="Отложенная публикация уже изменилась. Обновите страницу.",
            )
    publication = await repository.replace_publication(
        public_id=_public_id("publication"),
        group_lesson_id=revision_context.scope.group_lesson_id,
        kind=kind,
        revision_id=revision_context.revision.id,
        state=state,
        expected_current_public_id=expected_public_id,
        expected_current_version=expected_version,
        actor_user_id=actor_user_id,
        scheduled_at=scheduled_at,
        cancel_scheduled=state is PublicationState.PUBLISHED,
        expected_scheduled_public_id=expected_scheduled_id,
        expected_scheduled_version=expected_scheduled_version,
    )
    await _invalidate_after_commit(
        request,
        scope=revision_context.scope,
        kind=kind,
        reason=(
            "content-published"
            if state is PublicationState.PUBLISHED
            else "content-scheduled"
        ),
    )
    response = web.json_response(
        {
            **_publication_payload(publication),
            "groupLessonId": revision_context.scope.group_lesson_public_id,
            "revisionId": revision_context.revision.public_id,
            "requestId": _request_id(request),
        },
        status=201,
    )
    response.headers["ETag"] = _etag(publication.public_id, publication.version)
    return response


@content_routes.get("/staff/api/v1/publications")
@_translate_content_errors
async def staff_content_history(request: web.Request) -> web.Response:
    if set(request.query) != {"groupLesson"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Укажите ровно один groupLesson",
        )
    group_lesson_public_id = request.query["groupLesson"]
    repository = _repository(request)
    scope = await repository.get_group_lesson_scope(group_lesson_public_id)
    _staff_actor(request, scope)
    history = await repository.get_group_lesson_content_history(
        group_lesson_public_id=group_lesson_public_id
    )

    materials: list[dict[str, object]] = []
    for kind in (ContentKind.CONDITION, ContentKind.HINT, ContentKind.SOLUTION):
        revisions = [
            {
                **_revision_payload(context),
                "etag": _etag(context.revision.public_id, context.revision.version),
            }
            for context in history.revisions
            if context.source.kind is kind
        ]
        publications = [
            _publication_context_payload(context)
            for context in history.publications
            if context.publication.kind is kind
        ]
        materials.append(
            {
                "kind": kind.value,
                "revisions": revisions,
                "currentPublished": next(
                    (
                        publication
                        for publication in publications
                        if publication["state"] == PublicationState.PUBLISHED.value
                    ),
                    None,
                ),
                "currentScheduled": next(
                    (
                        publication
                        for publication in publications
                        if publication["state"] == PublicationState.SCHEDULED.value
                    ),
                    None,
                ),
                "publicationHistory": publications,
            }
        )
    return web.json_response(
        {
            "groupLessonId": history.scope.group_lesson_public_id,
            "courseId": history.scope.course_public_id,
            "groupId": history.scope.group_public_id,
            "businessTimezone": history.scope.business_timezone,
            "materials": materials,
            "requestId": _request_id(request),
        }
    )


@content_routes.post("/staff/api/v1/publications/{publication_id}/rollback")
@_translate_content_errors
async def rollback_publication(request: web.Request) -> web.Response:
    payload = await _json_object(request, allowed_fields=_ROLLBACK_FIELDS)
    target_revision_public_id = payload["revisionId"]
    expected_scheduled_id, expected_scheduled_version = _expected_scheduled(payload)
    if not isinstance(target_revision_public_id, str):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте поля формы",
        )
    repository = _repository(request)
    current_context = await repository.get_publication_context(
        request.match_info["publication_id"]
    )
    _principal, actor_user_id = _staff_actor(request, current_context.scope)
    _require_if_match(
        request,
        _etag(
            current_context.publication.public_id,
            current_context.publication.version,
        ),
    )
    current_slot = await repository.get_current_publication(
        group_lesson_id=current_context.scope.group_lesson_id,
        kind=current_context.publication.kind,
        state=PublicationState.PUBLISHED,
    )
    if (
        current_slot is None
        or current_slot.public_id != current_context.publication.public_id
        or current_slot.version != current_context.publication.version
    ):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Публикация уже изменилась. Обновите страницу.",
        )
    scheduled_slot = await repository.get_current_publication(
        group_lesson_id=current_context.scope.group_lesson_id,
        kind=current_context.publication.kind,
        state=PublicationState.SCHEDULED,
    )
    if (scheduled_slot is None) != (expected_scheduled_id is None) or (
        scheduled_slot is not None
        and (
            scheduled_slot.public_id != expected_scheduled_id
            or scheduled_slot.version != expected_scheduled_version
        )
    ):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Отложенная публикация уже изменилась. Обновите страницу.",
        )
    target = await repository.get_revision_context(target_revision_public_id)
    if (
        target.scope.group_lesson_id != current_context.scope.group_lesson_id
        or target.source.kind is not current_context.publication.kind
    ):
        raise PwaApiError(
            status=422,
            code="revision_scope_mismatch",
            message="Revision относится к другому занятию или виду материала",
        )
    if target.revision.status is not RevisionStatus.READY:
        raise PwaApiError(
            status=422,
            code="revision_not_publishable",
            message="Откат возможен только на готовую revision",
        )
    await _require_publication_readiness(repository, target)
    await _require_solution_cutoff(
        repository,
        scope=target.scope,
        kind=current_context.publication.kind,
    )
    if target.revision.id == current_context.publication.revision_id:
        raise PwaApiError(
            status=422,
            code="publication_no_change",
            message="Эта revision уже опубликована",
        )
    publication = await repository.replace_publication(
        public_id=_public_id("publication-rollback"),
        group_lesson_id=current_context.scope.group_lesson_id,
        kind=current_context.publication.kind,
        revision_id=target.revision.id,
        state=PublicationState.PUBLISHED,
        expected_current_public_id=current_context.publication.public_id,
        expected_current_version=current_context.publication.version,
        actor_user_id=actor_user_id,
        cancel_scheduled=True,
        expected_scheduled_public_id=expected_scheduled_id,
        expected_scheduled_version=expected_scheduled_version,
    )
    await _invalidate_after_commit(
        request,
        scope=current_context.scope,
        kind=current_context.publication.kind,
        reason="content-rolled-back",
    )
    response = web.json_response(
        {
            **_publication_payload(publication),
            "groupLessonId": target.scope.group_lesson_public_id,
            "revisionId": target.revision.public_id,
            "requestId": _request_id(request),
        },
        status=201,
    )
    response.headers["ETag"] = _etag(publication.public_id, publication.version)
    return response


@content_routes.post("/staff/api/v1/publications/{publication_id}/cancel")
@_translate_content_errors
async def cancel_scheduled_publication(request: web.Request) -> web.Response:
    await _json_object(request, allowed_fields=_CANCEL_FIELDS)
    repository = _repository(request)
    context = await repository.get_publication_context(
        request.match_info["publication_id"]
    )
    _principal, actor_user_id = _staff_actor(request, context.scope)
    _require_if_match(
        request,
        _etag(context.publication.public_id, context.publication.version),
    )
    if context.publication.state is not PublicationState.SCHEDULED:
        raise PwaApiError(
            status=409,
            code="publication_not_scheduled",
            message="Эта отложенная публикация уже изменилась",
        )
    current = await repository.get_current_publication(
        group_lesson_id=context.scope.group_lesson_id,
        kind=context.publication.kind,
        state=PublicationState.SCHEDULED,
    )
    if (
        current is None
        or current.public_id != context.publication.public_id
        or current.version != context.publication.version
    ):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Отложенная публикация уже изменилась. Обновите страницу.",
        )
    cancelled = await repository.transition_publication(
        public_id=context.publication.public_id,
        expected_version=context.publication.version,
        target=PublicationState.SUPERSEDED,
        actor_user_id=actor_user_id,
    )
    await _invalidate_after_commit(
        request,
        scope=context.scope,
        kind=context.publication.kind,
        reason="content-schedule-cancelled",
    )
    response = web.json_response(
        {
            **_publication_payload(cancelled),
            "groupLessonId": context.scope.group_lesson_public_id,
            "revisionId": context.revision_public_id,
            "action": "cancelled",
            "requestId": _request_id(request),
        }
    )
    response.headers["ETag"] = _etag(cancelled.public_id, cancelled.version)
    return response


@content_routes.post("/staff/api/v1/publications/{publication_id}/hide")
@_translate_content_errors
async def hide_published_content(request: web.Request) -> web.Response:
    await _json_object(request, allowed_fields=_HIDE_FIELDS)
    repository = _repository(request)
    context = await repository.get_publication_context(
        request.match_info["publication_id"]
    )
    _principal, actor_user_id = _staff_actor(request, context.scope)
    _require_if_match(
        request,
        _etag(context.publication.public_id, context.publication.version),
    )
    if context.publication.state is not PublicationState.PUBLISHED:
        raise PwaApiError(
            status=409,
            code="publication_not_published",
            message="Эта публикация уже изменена",
        )
    current = await repository.get_current_publication(
        group_lesson_id=context.scope.group_lesson_id,
        kind=context.publication.kind,
        state=PublicationState.PUBLISHED,
    )
    if (
        current is None
        or current.public_id != context.publication.public_id
        or current.version != context.publication.version
    ):
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Публикация уже изменилась. Обновите страницу.",
        )
    hidden = await repository.transition_publication(
        public_id=context.publication.public_id,
        expected_version=context.publication.version,
        target=PublicationState.HIDDEN,
        actor_user_id=actor_user_id,
    )
    await _invalidate_after_commit(
        request,
        scope=context.scope,
        kind=context.publication.kind,
        reason="content-hidden",
    )
    response = web.json_response(
        {
            **_publication_payload(hidden),
            "groupLessonId": context.scope.group_lesson_public_id,
            "revisionId": context.revision_public_id,
            "action": "hidden",
            "requestId": _request_id(request),
        }
    )
    response.headers["ETag"] = _etag(hidden.public_id, hidden.version)
    return response


async def _published_content_response(
    request: web.Request,
    *,
    audience: AuthAudience,
    student_user_id: int,
) -> web.Response:
    group_lesson_public_id = request.match_info["group_lesson_id"]
    kind = _content_kind(request.match_info["kind"])
    repository = _repository(request)
    scope = await repository.get_group_lesson_scope(group_lesson_public_id)
    _authorize(
        request,
        expected_audience=audience,
        capability=Capability.GROUP_READ,
        scope=scope,
        student_user_id=student_user_id,
    )
    published = await repository.get_published_content(
        group_lesson_public_id=group_lesson_public_id,
        kind=kind,
    )
    return web.json_response(
        {
            "groupLessonId": published.scope.group_lesson_public_id,
            "courseId": published.scope.course_public_id,
            "groupId": published.scope.group_public_id,
            "kind": kind.value,
            "publicationId": published.publication.public_id,
            "publicationVersion": published.publication.version,
            "publishedAt": _iso(published.publication.published_at),
            "revisionId": published.revision_public_id,
            "document": published.document,
        }
    )


@content_routes.get(
    "/student/api/v1/group-lessons/{group_lesson_id}/content/"
    "{kind:condition|hint|solution}"
)
@_translate_content_errors
async def student_published_content(request: web.Request) -> web.Response:
    principal = authenticated_session(request).principal
    if principal.linked_user_id is None:  # pragma: no cover - principal invariant
        raise ContentRepositoryError("student principal has no linked identity")
    return await _published_content_response(
        request,
        audience=AuthAudience.STUDENT,
        student_user_id=principal.linked_user_id,
    )


@content_routes.get(
    "/family/api/v1/children/{student_public_id}/group-lessons/"
    "{group_lesson_id}/content/{kind:condition|hint|solution}"
)
@_translate_content_errors
async def family_published_content(request: web.Request) -> web.Response:
    return await _published_content_response(
        request,
        audience=AuthAudience.FAMILY,
        student_user_id=_family_student_user_id(request),
    )


__all__ = [
    "PWA_CONTENT_INVALIDATOR",
    "PWA_CONTENT_REPOSITORY",
    "ContentInvalidator",
    "content_routes",
]
