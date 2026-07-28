"""Atomic repository for Student written-submission threads.

The first Phase-5 vertical slice deliberately supports text-only material while
the upload pipeline is built separately.  Its wire and persistence semantics
already cover the final model: one durable draft entry, exact problem-revision
provenance, optimistic versions, idempotent submit and append-only history.
See ``vmshpwa/dev/development-plan/09-phase-5-written-submissions.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from models.pwa.submissions import assess_submission_clock

from .connection import PwaConnectionFactory


CREATE_ENTRY_OPERATION = "written-entry:create"
CREATE_ATTACHMENT_OPERATION = "written-attachment:create"
REORDER_ATTACHMENTS_OPERATION = "written-attachment:reorder"
DELETE_ATTACHMENT_OPERATION = "written-attachment:delete"
SUBMIT_ENTRY_OPERATION = "written-entry:submit"
REPLACE_ENTRY_OPERATION = "written-entry:replace"
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class WrittenSubmissionRepositoryError(RuntimeError):
    """Base class for an unavailable or internally inconsistent repository."""


class WrittenSubmissionRejected(WrittenSubmissionRepositoryError):
    """Expected request rejection which is safe to expose through HTTP."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        http_status: int,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = dict(details or {})

    def response_payload(self) -> dict[str, object]:
        error: dict[str, object] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"schemaVersion": 1, "error": error}

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object], http_status: int
    ) -> "WrittenSubmissionRejected":
        error = payload.get("error")
        if not isinstance(error, Mapping):
            raise WrittenSubmissionRepositoryError(
                "stored written-submission error is invalid"
            )
        code = error.get("code")
        message = error.get("message")
        details = error.get("details")
        if not isinstance(code, str) or not isinstance(message, str):
            raise WrittenSubmissionRepositoryError(
                "stored written-submission error is invalid"
            )
        return cls(
            code=code,
            message=message,
            http_status=http_status,
            details=details if isinstance(details, Mapping) else None,
        )


class WrittenIdempotencyPayloadMismatch(WrittenSubmissionRejected):
    def __init__(self) -> None:
        super().__init__(
            code="idempotency_payload_mismatch",
            message="Этот ключ уже использован для другого действия.",
            http_status=409,
        )


@dataclass(frozen=True, slots=True)
class ProblemRevisionRef:
    condition_revision_public_id: str
    config_version: int

    def __post_init__(self) -> None:
        if not _PUBLIC_ID.fullmatch(self.condition_revision_public_id):
            raise ValueError("condition revision public ID is invalid")
        if type(self.config_version) is not int or self.config_version < 1:
            raise ValueError("problem config version must be positive")

    def payload(self) -> dict[str, object]:
        return {
            "conditionRevisionId": self.condition_revision_public_id,
            "configVersion": self.config_version,
        }


@dataclass(frozen=True, slots=True)
class CreateWrittenEntryCommand:
    account_id: int
    problem_public_id: str
    problem_revision: ProblemRevisionRef
    text: str | None
    client_created_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        _validate_common_command(
            account_id=self.account_id,
            public_id=self.problem_public_id,
            public_id_label="problem",
            idempotency_key=self.idempotency_key,
            client_created_at=self.client_created_at,
        )
        if self.text is not None and (
            not isinstance(self.text, str) or len(self.text) > 100_000
        ):
            raise ValueError("written entry text is invalid")


@dataclass(frozen=True, slots=True)
class SubmitWrittenEntryCommand:
    account_id: int
    entry_public_id: str
    expected_entry_version: int
    expected_thread_version: int
    attachment_public_ids: tuple[str, ...]
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.account_id < 1:
            raise ValueError("account ID must be positive")
        if not _PUBLIC_ID.fullmatch(self.entry_public_id):
            raise ValueError("entry public ID is invalid")
        if (
            type(self.expected_entry_version) is not int
            or self.expected_entry_version < 1
            or type(self.expected_thread_version) is not int
            or self.expected_thread_version < 1
        ):
            raise ValueError("expected versions must be positive")
        _validate_idempotency_key(self.idempotency_key)
        if len(self.attachment_public_ids) > 10 or len(
            set(self.attachment_public_ids)
        ) != len(self.attachment_public_ids):
            raise ValueError("attachment IDs must be unique and limited to ten")
        if any(not _PUBLIC_ID.fullmatch(item) for item in self.attachment_public_ids):
            raise ValueError("attachment public ID is invalid")


@dataclass(frozen=True, slots=True)
class ReplaceWrittenEntryCommand:
    """Atomically publish a prepared draft in place of unlocked evidence."""

    account_id: int
    entry_public_id: str
    replaced_entry_public_id: str
    expected_entry_version: int
    expected_replaced_entry_version: int
    expected_thread_version: int
    attachment_public_ids: tuple[str, ...]
    idempotency_key: str

    def __post_init__(self) -> None:
        _validate_attachment_mutation_command(
            account_id=self.account_id,
            entry_public_id=self.entry_public_id,
            expected_entry_version=self.expected_entry_version,
            expected_thread_version=self.expected_thread_version,
            idempotency_key=self.idempotency_key,
        )
        if (
            not _PUBLIC_ID.fullmatch(self.replaced_entry_public_id)
            or self.replaced_entry_public_id == self.entry_public_id
        ):
            raise ValueError("replaced entry public ID is invalid")
        if (
            type(self.expected_replaced_entry_version) is not int
            or self.expected_replaced_entry_version < 1
        ):
            raise ValueError("expected replaced-entry version must be positive")
        if len(self.attachment_public_ids) > 10 or len(
            set(self.attachment_public_ids)
        ) != len(self.attachment_public_ids):
            raise ValueError("attachment IDs must be unique and limited to ten")
        if any(not _PUBLIC_ID.fullmatch(item) for item in self.attachment_public_ids):
            raise ValueError("attachment public ID is invalid")

    def request_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "entryId": self.entry_public_id,
            "replacedEntryId": self.replaced_entry_public_id,
            "expectedEntryVersion": self.expected_entry_version,
            "expectedReplacedEntryVersion": self.expected_replaced_entry_version,
            "expectedThreadVersion": self.expected_thread_version,
            "attachmentIds": list(self.attachment_public_ids),
        }


@dataclass(frozen=True, slots=True)
class CreateWrittenAttachmentCommand:
    """Identity and optimistic state of one browser-selected source image."""

    account_id: int
    entry_public_id: str
    expected_entry_version: int
    expected_thread_version: int
    ordinal: int
    client_filename: str
    source_sha256: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.account_id < 1:
            raise ValueError("account ID must be positive")
        if not _PUBLIC_ID.fullmatch(self.entry_public_id):
            raise ValueError("entry public ID is invalid")
        if (
            type(self.expected_entry_version) is not int
            or self.expected_entry_version < 1
            or type(self.expected_thread_version) is not int
            or self.expected_thread_version < 1
        ):
            raise ValueError("expected versions must be positive")
        if type(self.ordinal) is not int or not 0 <= self.ordinal < 10:
            raise ValueError("attachment ordinal must be between zero and nine")
        if (
            not isinstance(self.client_filename, str)
            or not self.client_filename
            or len(self.client_filename) > 512
            or self.client_filename != self.client_filename.strip()
            or "/" in self.client_filename
            or "\\" in self.client_filename
            or any(ord(character) < 32 for character in self.client_filename)
        ):
            raise ValueError("client filename is invalid")
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("source SHA-256 is invalid")
        _validate_idempotency_key(self.idempotency_key)

    def request_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "entryId": self.entry_public_id,
            "expectedEntryVersion": self.expected_entry_version,
            "expectedThreadVersion": self.expected_thread_version,
            "ordinal": self.ordinal,
            "clientFilename": self.client_filename,
            "sourceSha256": self.source_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReorderWrittenAttachmentsCommand:
    """Complete desired page order for one mutable Student entry."""

    account_id: int
    entry_public_id: str
    expected_entry_version: int
    expected_thread_version: int
    attachment_public_ids: tuple[str, ...]
    idempotency_key: str

    def __post_init__(self) -> None:
        _validate_attachment_mutation_command(
            account_id=self.account_id,
            entry_public_id=self.entry_public_id,
            expected_entry_version=self.expected_entry_version,
            expected_thread_version=self.expected_thread_version,
            idempotency_key=self.idempotency_key,
        )
        if (
            len(self.attachment_public_ids) > 10
            or len(set(self.attachment_public_ids)) != len(self.attachment_public_ids)
            or any(
                not _PUBLIC_ID.fullmatch(item) for item in self.attachment_public_ids
            )
        ):
            raise ValueError("attachment IDs must be unique and limited to ten")

    def request_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "entryId": self.entry_public_id,
            "expectedEntryVersion": self.expected_entry_version,
            "expectedThreadVersion": self.expected_thread_version,
            "attachmentIds": list(self.attachment_public_ids),
        }


@dataclass(frozen=True, slots=True)
class DeleteWrittenAttachmentCommand:
    """Remove one page from mutable evidence without trusting browser identity."""

    account_id: int
    entry_public_id: str
    attachment_public_id: str
    expected_entry_version: int
    expected_thread_version: int
    idempotency_key: str

    def __post_init__(self) -> None:
        _validate_attachment_mutation_command(
            account_id=self.account_id,
            entry_public_id=self.entry_public_id,
            expected_entry_version=self.expected_entry_version,
            expected_thread_version=self.expected_thread_version,
            idempotency_key=self.idempotency_key,
        )
        if not _PUBLIC_ID.fullmatch(self.attachment_public_id):
            raise ValueError("attachment public ID is invalid")

    def request_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "entryId": self.entry_public_id,
            "attachmentId": self.attachment_public_id,
            "expectedEntryVersion": self.expected_entry_version,
            "expectedThreadVersion": self.expected_thread_version,
        }


@dataclass(frozen=True, slots=True)
class WrittenAttachmentRecord:
    public_id: str
    ordinal: int
    upload_status: str
    media_public_id: str
    public_url: str | None
    media_path: str
    media_type: str
    width: int
    height: int

    def payload(self) -> dict[str, object]:
        return {
            "attachmentId": self.public_id,
            "ordinal": self.ordinal,
            "uploadStatus": self.upload_status,
            "mediaId": self.media_public_id,
            "publicUrl": self.public_url,
            "mediaPath": self.media_path,
            "mediaType": self.media_type,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True)
class WrittenEntryRecord:
    public_id: str
    author_kind: str
    entry_kind: str
    state: str
    text: str | None
    problem_revision: ProblemRevisionRef | None
    version: int
    client_created_at: str | None
    server_received_at: str
    attachments: tuple[WrittenAttachmentRecord, ...]

    def payload(self) -> dict[str, object]:
        return {
            "entryId": self.public_id,
            "authorKind": self.author_kind,
            "entryKind": self.entry_kind,
            "state": self.state,
            "text": self.text,
            "problemRevision": (
                None
                if self.problem_revision is None
                else self.problem_revision.payload()
            ),
            "version": self.version,
            "clientCreatedAt": self.client_created_at,
            "serverReceivedAt": self.server_received_at,
            "attachments": [item.payload() for item in self.attachments],
        }


@dataclass(frozen=True, slots=True)
class WrittenThreadRecord:
    public_id: str
    problem_public_id: str
    status: str
    condition_revision_public_id: str
    version: int
    latest_entry_at: str
    entries: tuple[WrittenEntryRecord, ...]

    def payload(self) -> dict[str, object]:
        return {
            "threadId": self.public_id,
            "problemId": self.problem_public_id,
            "status": self.status,
            "conditionRevisionId": self.condition_revision_public_id,
            "version": self.version,
            "latestEntryAt": self.latest_entry_at,
            "entries": [entry.payload() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class CreateWrittenEntryReceipt:
    thread_public_id: str
    problem_public_id: str
    thread_status: str
    thread_version: int
    entry: WrittenEntryRecord
    replayed: bool = field(default=False, compare=False)

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "threadId": self.thread_public_id,
            "problemId": self.problem_public_id,
            "threadStatus": self.thread_status,
            "threadVersion": self.thread_version,
            "entry": self.entry.payload(),
        }

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object]
    ) -> "CreateWrittenEntryReceipt":
        try:
            entry = _entry_from_payload(payload["entry"])
            return cls(
                thread_public_id=str(payload["threadId"]),
                problem_public_id=str(payload["problemId"]),
                thread_status=str(payload["threadStatus"]),
                thread_version=int(payload["threadVersion"]),
                entry=entry,
                replayed=True,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WrittenSubmissionRepositoryError(
                "stored create-entry response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class WrittenAttachmentUploadScope:
    """Server-derived path scope; none of these values come from multipart fields."""

    student_user_id: int
    season_year: int
    lesson_number: int
    problem_public_id: str


@dataclass(frozen=True, slots=True)
class WrittenAttachmentMedia:
    object_key: str
    sha256: str
    byte_size: int
    media_type: str


@dataclass(frozen=True, slots=True)
class PreparedWrittenAttachmentUpload:
    command: CreateWrittenAttachmentCommand
    payload_sha256: str
    scope: WrittenAttachmentUploadScope


@dataclass(frozen=True, slots=True)
class PersistWrittenAttachment:
    """Verified final WebP metadata passed from the conversion/storage service."""

    object_key: str
    public_url: str | None
    output_sha256: str
    byte_size: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.output_sha256):
            raise ValueError("output SHA-256 is invalid")
        if not self.object_key or self.object_key != self.object_key.strip():
            raise ValueError("object key is invalid")
        if (
            self.byte_size < 1
            or not 1 <= self.width <= 1920
            or not 1 <= self.height <= 1920
        ):
            raise ValueError("final WebP metadata is invalid")


@dataclass(frozen=True, slots=True)
class CreateWrittenAttachmentReceipt:
    thread_public_id: str
    problem_public_id: str
    thread_status: str
    thread_version: int
    entry: WrittenEntryRecord
    replayed: bool = field(default=False, compare=False)

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "threadId": self.thread_public_id,
            "problemId": self.problem_public_id,
            "threadStatus": self.thread_status,
            "threadVersion": self.thread_version,
            "entry": self.entry.payload(),
        }

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object]
    ) -> "CreateWrittenAttachmentReceipt":
        try:
            return cls(
                thread_public_id=str(payload["threadId"]),
                problem_public_id=str(payload["problemId"]),
                thread_status=str(payload["threadStatus"]),
                thread_version=int(payload["threadVersion"]),
                entry=_entry_from_payload(payload["entry"]),
                replayed=True,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WrittenSubmissionRepositoryError(
                "stored create-attachment response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class MutateWrittenAttachmentsReceipt:
    thread_public_id: str
    problem_public_id: str
    thread_status: str
    thread_version: int
    entry: WrittenEntryRecord
    changed: bool
    replayed: bool = field(default=False, compare=False)

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "threadId": self.thread_public_id,
            "problemId": self.problem_public_id,
            "threadStatus": self.thread_status,
            "threadVersion": self.thread_version,
            "entry": self.entry.payload(),
            "changed": self.changed,
        }

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object]
    ) -> "MutateWrittenAttachmentsReceipt":
        try:
            changed = payload["changed"]
            if type(changed) is not bool:
                raise TypeError
            return cls(
                thread_public_id=str(payload["threadId"]),
                problem_public_id=str(payload["problemId"]),
                thread_status=str(payload["threadStatus"]),
                thread_version=int(payload["threadVersion"]),
                entry=_entry_from_payload(payload["entry"]),
                changed=changed,
                replayed=True,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WrittenSubmissionRepositoryError(
                "stored attachment-mutation response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class SubmitWrittenEntryReceipt:
    thread_public_id: str
    problem_public_id: str
    thread_status: str
    thread_version: int
    entry: WrittenEntryRecord
    clock_suspicious: bool
    replayed: bool = field(default=False, compare=False)

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "threadId": self.thread_public_id,
            "problemId": self.problem_public_id,
            "threadStatus": self.thread_status,
            "threadVersion": self.thread_version,
            "entry": self.entry.payload(),
            "clockSuspicious": self.clock_suspicious,
        }

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object]
    ) -> "SubmitWrittenEntryReceipt":
        try:
            return cls(
                thread_public_id=str(payload["threadId"]),
                problem_public_id=str(payload["problemId"]),
                thread_status=str(payload["threadStatus"]),
                thread_version=int(payload["threadVersion"]),
                entry=_entry_from_payload(payload["entry"]),
                clock_suspicious=bool(payload["clockSuspicious"]),
                replayed=True,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WrittenSubmissionRepositoryError(
                "stored submit-entry response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class ReplaceWrittenEntryReceipt:
    thread_public_id: str
    problem_public_id: str
    thread_status: str
    thread_version: int
    entry: WrittenEntryRecord
    replaced_entry_public_id: str
    replacement_event_public_id: str
    clock_suspicious: bool
    replayed: bool = field(default=False, compare=False)

    def response_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "threadId": self.thread_public_id,
            "problemId": self.problem_public_id,
            "threadStatus": self.thread_status,
            "threadVersion": self.thread_version,
            "entry": self.entry.payload(),
            "replacedEntryId": self.replaced_entry_public_id,
            "replacementEventId": self.replacement_event_public_id,
            "clockSuspicious": self.clock_suspicious,
        }

    @classmethod
    def from_response(
        cls, payload: Mapping[str, object]
    ) -> "ReplaceWrittenEntryReceipt":
        try:
            clock_suspicious = payload["clockSuspicious"]
            if type(clock_suspicious) is not bool:
                raise TypeError
            return cls(
                thread_public_id=str(payload["threadId"]),
                problem_public_id=str(payload["problemId"]),
                thread_status=str(payload["threadStatus"]),
                thread_version=int(payload["threadVersion"]),
                entry=_entry_from_payload(payload["entry"]),
                replaced_entry_public_id=str(payload["replacedEntryId"]),
                replacement_event_public_id=str(payload["replacementEventId"]),
                clock_suspicious=clock_suspicious,
                replayed=True,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WrittenSubmissionRepositoryError(
                "stored replace-entry response is invalid"
            ) from error


@dataclass(frozen=True, slots=True)
class _WrittenContext:
    account_id: int
    student_user_id: int
    problem_id: int
    problem_public_id: str
    problem_revision_id: int
    content_revision_id: int
    condition_revision_public_id: str
    config_version: int
    submission_closes_at: datetime
    season_year: int
    lesson_number: int


@dataclass(frozen=True, slots=True)
class _AttachmentTarget:
    entry_id: int
    thread_id: int
    thread_public_id: str
    thread_status: str
    context: _WrittenContext


@dataclass(frozen=True, slots=True)
class _MutableAttachment:
    id: int
    public_id: str
    asset_id: int
    upload_status: str


@dataclass(frozen=True, slots=True)
class _MutableEntryTarget:
    entry_id: int
    entry_state: str
    entry_version: int
    text: str | None
    thread_id: int
    thread_public_id: str
    thread_status: str
    thread_version: int
    problem_public_id: str
    attachments: tuple[_MutableAttachment, ...]


@dataclass(frozen=True, slots=True)
class _IdempotencyReplay:
    state: str
    http_status: int
    response: Mapping[str, object]


_WRITTEN_CONTEXT_SELECT = """
SELECT account.id AS account_id,
       account.linked_user_id AS student_user_id,
       problem.id AS problem_id,
       problem.public_id AS problem_public_id,
       problem_revision.id AS problem_revision_id,
       condition_revision.id AS content_revision_id,
       condition_revision.public_id AS condition_revision_public_id,
       problem_revision.config_version,
       lesson_window.submission_closes_at,
       season.starts_on AS season_starts_on,
       course_lesson.lesson_number
FROM auth_accounts AS account
JOIN course_enrollments AS enrollment
  ON enrollment.student_user_id = account.linked_user_id
 AND enrollment.status = 'active'
JOIN course_group_access AS access
  ON access.enrollment_id = enrollment.id
 AND access.course_id = enrollment.course_id
JOIN group_lessons AS group_lesson
  ON group_lesson.course_id = enrollment.course_id
 AND group_lesson.group_id = access.group_id
 AND group_lesson.status = 'active'
JOIN groups AS group_record
  ON group_record.course_id = group_lesson.course_id
 AND group_record.group_id = group_lesson.group_id
 AND group_record.status = 'active'
JOIN courses AS course
  ON course.id = group_lesson.course_id
 AND course.status = 'active'
JOIN seasons AS season ON season.id = course.season_id
JOIN course_lessons AS course_lesson
  ON course_lesson.id = group_lesson.course_lesson_id
 AND course_lesson.course_id = course.id
JOIN lesson_windows AS lesson_window
  ON lesson_window.group_lesson_id = group_lesson.id
JOIN lesson_publications AS publication
  ON publication.group_lesson_id = group_lesson.id
 AND publication.kind = 'condition'
 AND publication.state = 'published'
JOIN content_revisions AS condition_revision
  ON condition_revision.id = publication.revision_id
 AND condition_revision.status = 'ready'
JOIN problem_revisions AS problem_revision
  ON problem_revision.content_revision_id = condition_revision.id
 AND problem_revision.problem_type IN (2, 3, 4)
JOIN problems AS problem
  ON problem.id = problem_revision.problem_id
WHERE account.id = :account_id
  AND account.audience = 'student'
  AND account.status = 'active'
  AND problem.public_id = :problem_public_id
  AND access.valid_from <= :now
  AND (access.valid_to IS NULL OR access.valid_to > :now)
  AND EXISTS (
      SELECT 1 FROM content_derivatives AS derivative
      WHERE derivative.revision_id = condition_revision.id
        AND derivative.kind = 'web_ast'
        AND derivative.invalidated_at IS NULL
  )
"""


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise WrittenSubmissionRepositoryError(f"stored {label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise WrittenSubmissionRepositoryError(f"stored {label} is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WrittenSubmissionRepositoryError(f"stored {label} is invalid")
    return parsed.astimezone(UTC)


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _validate_idempotency_key(value: str) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 200
        or value != value.strip()
    ):
        raise ValueError("idempotency key must be canonical")


def _validate_common_command(
    *,
    account_id: int,
    public_id: str,
    public_id_label: str,
    idempotency_key: str,
    client_created_at: datetime,
) -> None:
    if account_id < 1:
        raise ValueError("account ID must be positive")
    if not _PUBLIC_ID.fullmatch(public_id):
        raise ValueError(f"{public_id_label} public ID is invalid")
    _validate_idempotency_key(idempotency_key)
    if client_created_at.tzinfo is None or client_created_at.utcoffset() is None:
        raise ValueError("client creation time must be timezone-aware")


def _validate_attachment_mutation_command(
    *,
    account_id: int,
    entry_public_id: str,
    expected_entry_version: int,
    expected_thread_version: int,
    idempotency_key: str,
) -> None:
    if account_id < 1:
        raise ValueError("account ID must be positive")
    if not _PUBLIC_ID.fullmatch(entry_public_id):
        raise ValueError("entry public ID is invalid")
    if (
        type(expected_entry_version) is not int
        or expected_entry_version < 1
        or type(expected_thread_version) is not int
        or expected_thread_version < 1
    ):
        raise ValueError("expected versions must be positive")
    _validate_idempotency_key(idempotency_key)


def _resolve_context(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    problem_public_id: str,
    now: datetime,
) -> _WrittenContext:
    rows = connection.execute(
        _WRITTEN_CONTEXT_SELECT,
        {
            "account_id": account_id,
            "problem_public_id": problem_public_id,
            "now": _timestamp(now),
        },
    ).fetchall()
    if len(rows) != 1:
        raise WrittenSubmissionRejected(
            code="written_problem_not_found",
            message="Задача недоступна для письменной сдачи.",
            http_status=404,
        )
    row = rows[0]
    return _WrittenContext(
        account_id=int(row["account_id"]),
        student_user_id=int(row["student_user_id"]),
        problem_id=int(row["problem_id"]),
        problem_public_id=str(row["problem_public_id"]),
        problem_revision_id=int(row["problem_revision_id"]),
        content_revision_id=int(row["content_revision_id"]),
        condition_revision_public_id=str(row["condition_revision_public_id"]),
        config_version=int(row["config_version"]),
        submission_closes_at=_parse_timestamp(
            row["submission_closes_at"], label="submission cutoff"
        ),
        season_year=int(str(row["season_starts_on"])[:4]),
        lesson_number=int(row["lesson_number"]),
    )


def _require_revision(expected: ProblemRevisionRef, context: _WrittenContext) -> None:
    if (
        expected.condition_revision_public_id != context.condition_revision_public_id
        or expected.config_version != context.config_version
    ):
        raise WrittenSubmissionRejected(
            code="written_problem_revision_changed",
            message="Условие задачи изменилось. Обновите страницу.",
            http_status=409,
        )


def _read_idempotency(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    operation: str,
    idempotency_key: str,
    payload_sha256: str,
) -> _IdempotencyReplay | None:
    row = connection.execute(
        "SELECT payload_sha256, state, http_status, response_json "
        "FROM idempotency_records WHERE audience = 'student' "
        "AND account_id = ? AND operation = ? AND idempotency_key = ?",
        (account_id, operation, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    if row["payload_sha256"] != payload_sha256:
        raise WrittenIdempotencyPayloadMismatch()
    if row["state"] == "processing":
        raise WrittenSubmissionRejected(
            code="idempotency_request_in_progress",
            message="Это действие уже выполняется.",
            http_status=409,
        )
    try:
        response = json.loads(str(row["response_json"]))
    except (json.JSONDecodeError, RecursionError) as error:
        raise WrittenSubmissionRepositoryError(
            "stored idempotency response is invalid"
        ) from error
    if not isinstance(response, dict) or row["http_status"] is None:
        raise WrittenSubmissionRepositoryError(
            "stored idempotency response is incomplete"
        )
    return _IdempotencyReplay(
        state=str(row["state"]),
        http_status=int(row["http_status"]),
        response=response,
    )


def _raise_replay_failure(replay: _IdempotencyReplay) -> None:
    raise WrittenSubmissionRejected.from_response(replay.response, replay.http_status)


def _attachment_target(
    connection: sqlite3.Connection,
    *,
    command: CreateWrittenAttachmentCommand,
    now: datetime,
) -> _AttachmentTarget:
    """Revalidate ownership and both optimistic versions at each DB boundary."""

    row = connection.execute(
        "SELECT entry.id AS entry_id, entry.state, "
        "entry.version AS entry_version, entry.problem_revision_id, "
        "thread.id AS thread_id, thread.public_id AS thread_public_id, "
        "thread.status AS thread_status, thread.version AS thread_version, "
        "problem.public_id AS problem_public_id "
        "FROM auth_accounts AS account "
        "JOIN submission_threads AS thread "
        "ON thread.student_user_id = account.linked_user_id "
        "JOIN submission_entries AS entry ON entry.thread_id = thread.id "
        "JOIN problems AS problem ON problem.id = thread.problem_id "
        "WHERE account.id = ? AND account.audience = 'student' "
        "AND account.status = 'active' AND entry.public_id = ?",
        (command.account_id, command.entry_public_id),
    ).fetchone()
    if row is None:
        raise WrittenSubmissionRejected(
            code="written_entry_not_found",
            message="Черновик письменного решения не найден.",
            http_status=404,
        )
    if row["state"] not in ("draft", "uploading"):
        raise WrittenSubmissionRejected(
            code="written_entry_not_editable",
            message="Эта версия решения уже отправлена.",
            http_status=409,
        )
    if (
        int(row["entry_version"]) != command.expected_entry_version
        or int(row["thread_version"]) != command.expected_thread_version
    ):
        raise WrittenSubmissionRejected(
            code="written_submission_version_conflict",
            message="Решение изменилось в другом окне. Обновите страницу.",
            http_status=409,
        )
    context = _resolve_context(
        connection,
        account_id=command.account_id,
        problem_public_id=str(row["problem_public_id"]),
        now=now,
    )
    if context.problem_revision_id != int(row["problem_revision_id"]):
        raise WrittenSubmissionRejected(
            code="written_problem_revision_changed",
            message="Условие задачи изменилось. Проверьте решение перед загрузкой.",
            http_status=409,
        )
    attachment_rows = connection.execute(
        "SELECT ordinal FROM submission_attachments WHERE entry_id = ?",
        (row["entry_id"],),
    ).fetchall()
    if len(attachment_rows) >= 10:
        raise WrittenSubmissionRejected(
            code="written_attachment_limit_reached",
            message="К одному решению можно приложить не больше 10 фотографий.",
            http_status=409,
        )
    if any(int(item["ordinal"]) == command.ordinal for item in attachment_rows):
        raise WrittenSubmissionRejected(
            code="written_attachment_ordinal_conflict",
            message="Порядок фотографий изменился. Обновите страницу.",
            http_status=409,
        )
    return _AttachmentTarget(
        entry_id=int(row["entry_id"]),
        thread_id=int(row["thread_id"]),
        thread_public_id=str(row["thread_public_id"]),
        thread_status=str(row["thread_status"]),
        context=context,
    )


def _mutable_entry_target(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    entry_public_id: str,
    expected_entry_version: int,
    expected_thread_version: int,
) -> _MutableEntryTarget:
    """Resolve owner-scoped mutable evidence and fail closed after review lock."""

    row = connection.execute(
        "SELECT entry.id AS entry_id, entry.state AS entry_state, "
        "entry.version AS entry_version, entry.text, "
        "thread.id AS thread_id, thread.public_id AS thread_public_id, "
        "thread.status AS thread_status, thread.version AS thread_version, "
        "problem.public_id AS problem_public_id "
        "FROM auth_accounts AS account "
        "JOIN submission_threads AS thread "
        "ON thread.student_user_id = account.linked_user_id "
        "JOIN submission_entries AS entry ON entry.thread_id = thread.id "
        "JOIN problems AS problem ON problem.id = thread.problem_id "
        "WHERE account.id = ? AND account.audience = 'student' "
        "AND account.status = 'active' AND entry.public_id = ?",
        (account_id, entry_public_id),
    ).fetchone()
    if row is None:
        raise WrittenSubmissionRejected(
            code="written_entry_not_found",
            message="Письменное решение не найдено.",
            http_status=404,
        )
    if row["entry_state"] == "locked":
        raise WrittenSubmissionRejected(
            code="written_attachment_locked",
            message="Фотографии уже зафиксированы проверкой.",
            http_status=409,
        )
    if row["entry_state"] not in ("draft", "uploading", "submitted"):
        raise WrittenSubmissionRejected(
            code="written_entry_not_editable",
            message="Эту версию решения уже нельзя изменить.",
            http_status=409,
        )
    if row["entry_state"] == "submitted" and row["thread_status"] != "awaiting_review":
        raise WrittenSubmissionRejected(
            code="written_entry_not_editable",
            message="Эту версию решения уже нельзя изменить.",
            http_status=409,
        )
    if (
        int(row["entry_version"]) != expected_entry_version
        or int(row["thread_version"]) != expected_thread_version
    ):
        raise WrittenSubmissionRejected(
            code="written_submission_version_conflict",
            message="Решение изменилось в другом окне. Обновите страницу.",
            http_status=409,
        )
    attachment_rows = connection.execute(
        "SELECT id, public_id, asset_id, upload_status "
        "FROM submission_attachments WHERE entry_id = ? "
        "ORDER BY ordinal, id",
        (row["entry_id"],),
    ).fetchall()
    if any(item["upload_status"] == "locked" for item in attachment_rows):
        raise WrittenSubmissionRejected(
            code="written_attachment_locked",
            message="Фотографии уже зафиксированы проверкой.",
            http_status=409,
        )
    return _MutableEntryTarget(
        entry_id=int(row["entry_id"]),
        entry_state=str(row["entry_state"]),
        entry_version=int(row["entry_version"]),
        text=None if row["text"] is None else str(row["text"]),
        thread_id=int(row["thread_id"]),
        thread_public_id=str(row["thread_public_id"]),
        thread_status=str(row["thread_status"]),
        thread_version=int(row["thread_version"]),
        problem_public_id=str(row["problem_public_id"]),
        attachments=tuple(
            _MutableAttachment(
                id=int(item["id"]),
                public_id=str(item["public_id"]),
                asset_id=int(item["asset_id"]),
                upload_status=str(item["upload_status"]),
            )
            for item in attachment_rows
        ),
    )


def _renumber_attachments(
    connection: sqlite3.Connection,
    *,
    entry_id: int,
    ordered_attachment_ids: tuple[int, ...],
) -> None:
    """Avoid immediate SQLite UNIQUE collisions while assigning dense ordinals."""

    connection.execute(
        "UPDATE submission_attachments SET ordinal = ordinal + 1000000 "
        "WHERE entry_id = ?",
        (entry_id,),
    )
    for ordinal, attachment_id in enumerate(ordered_attachment_ids):
        connection.execute(
            "UPDATE submission_attachments SET ordinal = ? "
            "WHERE id = ? AND entry_id = ?",
            (ordinal, attachment_id, entry_id),
        )


def _entry_from_payload(value: object) -> WrittenEntryRecord:
    if not isinstance(value, Mapping):
        raise TypeError
    revision = value.get("problemRevision")
    problem_revision = None
    if revision is not None:
        if not isinstance(revision, Mapping):
            raise TypeError
        problem_revision = ProblemRevisionRef(
            condition_revision_public_id=str(revision["conditionRevisionId"]),
            config_version=int(revision["configVersion"]),
        )
    attachments_value = value["attachments"]
    if not isinstance(attachments_value, list):
        raise TypeError
    attachments_list: list[WrittenAttachmentRecord] = []
    for item in attachments_value:
        if not isinstance(item, Mapping):
            raise TypeError
        attachments_list.append(
            WrittenAttachmentRecord(
                public_id=str(item["attachmentId"]),
                ordinal=int(item["ordinal"]),
                upload_status=str(item["uploadStatus"]),
                media_public_id=str(item["mediaId"]),
                public_url=None
                if item["publicUrl"] is None
                else str(item["publicUrl"]),
                media_path=str(item["mediaPath"]),
                media_type=str(item["mediaType"]),
                width=int(item["width"]),
                height=int(item["height"]),
            )
        )
    attachments = tuple(attachments_list)
    return WrittenEntryRecord(
        public_id=str(value["entryId"]),
        author_kind=str(value["authorKind"]),
        entry_kind=str(value["entryKind"]),
        state=str(value["state"]),
        text=None if value["text"] is None else str(value["text"]),
        problem_revision=problem_revision,
        version=int(value["version"]),
        client_created_at=(
            None if value["clientCreatedAt"] is None else str(value["clientCreatedAt"])
        ),
        server_received_at=str(value["serverReceivedAt"]),
        attachments=attachments,
    )


def _entry_record(
    connection: sqlite3.Connection, *, entry_id: int
) -> WrittenEntryRecord:
    row = connection.execute(
        "SELECT entry.*, revision.public_id AS condition_revision_public_id, "
        "problem_revision.config_version FROM submission_entries AS entry "
        "LEFT JOIN problem_revisions AS problem_revision "
        "ON problem_revision.id = entry.problem_revision_id "
        "LEFT JOIN content_revisions AS revision "
        "ON revision.id = problem_revision.content_revision_id WHERE entry.id = ?",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise WrittenSubmissionRepositoryError("stored written entry disappeared")
    attachment_rows = connection.execute(
        "SELECT attachment.public_id, attachment.ordinal, attachment.upload_status, "
        "asset.public_id AS media_public_id, asset.public_url, asset.media_type, "
        "asset.width, asset.height FROM submission_attachments AS attachment "
        "JOIN media_assets AS asset ON asset.id = attachment.asset_id "
        "WHERE attachment.entry_id = ? ORDER BY attachment.ordinal, attachment.id",
        (entry_id,),
    ).fetchall()
    revision = None
    if row["problem_revision_id"] is not None:
        revision = ProblemRevisionRef(
            condition_revision_public_id=str(row["condition_revision_public_id"]),
            config_version=int(row["config_version"]),
        )
    return WrittenEntryRecord(
        public_id=str(row["public_id"]),
        author_kind=str(row["author_kind"]),
        entry_kind=str(row["entry_kind"]),
        state=str(row["state"]),
        text=None if row["text"] is None else str(row["text"]),
        problem_revision=revision,
        version=int(row["version"]),
        client_created_at=(
            None if row["client_created_at"] is None else str(row["client_created_at"])
        ),
        server_received_at=str(row["server_received_at"]),
        attachments=tuple(
            WrittenAttachmentRecord(
                public_id=str(item["public_id"]),
                ordinal=int(item["ordinal"]),
                upload_status=str(item["upload_status"]),
                media_public_id=str(item["media_public_id"]),
                public_url=(
                    None if item["public_url"] is None else str(item["public_url"])
                ),
                media_path=(
                    f"/student/api/v1/thread-entries/{row['public_id']}"
                    f"/attachments/{item['public_id']}/media"
                ),
                media_type=str(item["media_type"]),
                width=int(item["width"]),
                height=int(item["height"]),
            )
            for item in attachment_rows
        ),
    )


def _complete_idempotency(
    connection: sqlite3.Connection,
    *,
    record_id: int,
    state: str,
    http_status: int,
    response: Mapping[str, object],
    completed_at: str,
) -> None:
    connection.execute(
        "UPDATE idempotency_records SET state = ?, http_status = ?, "
        "response_json = ?, completed_at = ? WHERE id = ?",
        (state, http_status, _canonical_json(response), completed_at, record_id),
    )


class PwaWrittenSubmissionRepository:
    """Persist Student written material without touching legacy bot tables."""

    def __init__(
        self,
        factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        thread_public_id_factory: Callable[[], str] | None = None,
        entry_public_id_factory: Callable[[], str] | None = None,
        attachment_public_id_factory: Callable[[], str] | None = None,
        media_public_id_factory: Callable[[], str] | None = None,
        replacement_event_public_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._thread_public_id_factory = thread_public_id_factory or (
            lambda: f"written-thread-{uuid.uuid4()}"
        )
        self._entry_public_id_factory = entry_public_id_factory or (
            lambda: f"written-entry-{uuid.uuid4()}"
        )
        self._attachment_public_id_factory = attachment_public_id_factory or (
            lambda: f"written-attachment-{uuid.uuid4()}"
        )
        self._media_public_id_factory = media_public_id_factory or (
            lambda: f"submission-media-{uuid.uuid4()}"
        )
        self._replacement_event_public_id_factory = (
            replacement_event_public_id_factory
            or (lambda: f"written-replacement-{uuid.uuid4()}")
        )

    async def create_entry(
        self, command: CreateWrittenEntryCommand
    ) -> CreateWrittenEntryReceipt:
        now = self._clock()
        request = {
            "schemaVersion": 1,
            "problemId": command.problem_public_id,
            "problemRevision": command.problem_revision.payload(),
            "text": command.text,
            "clientCreatedAt": _timestamp(command.client_created_at),
        }
        payload_sha256 = _payload_hash(request)
        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                operation=CREATE_ENTRY_OPERATION,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return CreateWrittenEntryReceipt.from_response(replay.response)
        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_create_entry(
                connection,
                command=command,
                now=now,
                payload_sha256=payload_sha256,
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    def _write_create_entry(
        self,
        connection: sqlite3.Connection,
        *,
        command: CreateWrittenEntryCommand,
        now: datetime,
        payload_sha256: str,
    ) -> tuple[CreateWrittenEntryReceipt | None, WrittenSubmissionRejected | None]:
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            operation=CREATE_ENTRY_OPERATION,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return CreateWrittenEntryReceipt.from_response(replay.response), None
        received_at = _timestamp(now)
        idempotency_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, ?, ?, ?, 'processing', ?) "
                "RETURNING id",
                (
                    command.account_id,
                    CREATE_ENTRY_OPERATION,
                    command.idempotency_key,
                    payload_sha256,
                    received_at,
                ),
            ).fetchone()["id"]
        )
        try:
            context = _resolve_context(
                connection,
                account_id=command.account_id,
                problem_public_id=command.problem_public_id,
                now=now,
            )
            _require_revision(command.problem_revision, context)
            thread = connection.execute(
                "SELECT id, public_id, status, version FROM submission_threads "
                "WHERE student_user_id = ? AND problem_id = ? AND status <> 'closed'",
                (context.student_user_id, context.problem_id),
            ).fetchone()
            if thread is None:
                thread_public_id = self._thread_public_id_factory()
                if not _PUBLIC_ID.fullmatch(thread_public_id):
                    raise WrittenSubmissionRepositoryError(
                        "thread public ID factory returned an invalid value"
                    )
                thread_id = int(
                    connection.execute(
                        "INSERT INTO submission_threads "
                        "(public_id, student_user_id, problem_id, condition_revision_id, "
                        "status, latest_entry_at, created_at, updated_at) VALUES "
                        "(?, ?, ?, ?, 'open', ?, ?, ?) RETURNING id",
                        (
                            thread_public_id,
                            context.student_user_id,
                            context.problem_id,
                            context.content_revision_id,
                            received_at,
                            received_at,
                            received_at,
                        ),
                    ).fetchone()["id"]
                )
                thread_status = "open"
                thread_version = 1
            else:
                thread_id = int(thread["id"])
                thread_public_id = str(thread["public_id"])
                thread_status = str(thread["status"])
                thread_version = int(thread["version"]) + 1
                connection.execute(
                    "UPDATE submission_threads SET latest_entry_at = ?, updated_at = ?, "
                    "version = ? WHERE id = ?",
                    (received_at, received_at, thread_version, thread_id),
                )
            entry_public_id = self._entry_public_id_factory()
            if not _PUBLIC_ID.fullmatch(entry_public_id):
                raise WrittenSubmissionRepositoryError(
                    "entry public ID factory returned an invalid value"
                )
            entry_id = int(
                connection.execute(
                    "INSERT INTO submission_entries "
                    "(public_id, thread_id, problem_revision_id, author_kind, "
                    "author_user_id, channel, entry_kind, state, text, "
                    "client_created_at, server_received_at, idempotency_key, "
                    "payload_sha256) VALUES (?, ?, ?, 'student', ?, 'pwa', "
                    "'submission', 'draft', ?, ?, ?, ?, ?) RETURNING id",
                    (
                        entry_public_id,
                        thread_id,
                        context.problem_revision_id,
                        context.student_user_id,
                        command.text,
                        _timestamp(command.client_created_at),
                        received_at,
                        command.idempotency_key,
                        payload_sha256,
                    ),
                ).fetchone()["id"]
            )
            receipt = CreateWrittenEntryReceipt(
                thread_public_id=thread_public_id,
                problem_public_id=context.problem_public_id,
                thread_status=thread_status,
                thread_version=thread_version,
                entry=_entry_record(connection, entry_id=entry_id),
            )
        except WrittenSubmissionRejected as error:
            _complete_idempotency(
                connection,
                record_id=idempotency_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=received_at,
            )
            return None, error
        _complete_idempotency(
            connection,
            record_id=idempotency_id,
            state="completed",
            http_status=201,
            response=receipt.response_payload(),
            completed_at=received_at,
        )
        return receipt, None

    async def prepare_attachment_upload(
        self, command: CreateWrittenAttachmentCommand
    ) -> PreparedWrittenAttachmentUpload | CreateWrittenAttachmentReceipt:
        """Fail before conversion when an upload is stale, foreign or replayed."""

        payload_sha256 = _payload_hash(command.request_payload())
        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                operation=CREATE_ATTACHMENT_OPERATION,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return CreateWrittenAttachmentReceipt.from_response(replay.response)
        now = self._clock()
        target = await self._factory.run_read_async(
            lambda connection: _attachment_target(connection, command=command, now=now)
        )
        return PreparedWrittenAttachmentUpload(
            command=command,
            payload_sha256=payload_sha256,
            scope=WrittenAttachmentUploadScope(
                student_user_id=target.context.student_user_id,
                season_year=target.context.season_year,
                lesson_number=target.context.lesson_number,
                problem_public_id=target.context.problem_public_id,
            ),
        )

    async def complete_attachment_upload(
        self,
        prepared: PreparedWrittenAttachmentUpload,
        asset: PersistWrittenAttachment,
    ) -> CreateWrittenAttachmentReceipt:
        """Atomically publish final media metadata and its entry attachment."""

        now = self._clock()
        media_public_id = self._media_public_id_factory()
        attachment_public_id = self._attachment_public_id_factory()
        if not _PUBLIC_ID.fullmatch(media_public_id) or not _PUBLIC_ID.fullmatch(
            attachment_public_id
        ):
            raise WrittenSubmissionRepositoryError(
                "attachment public ID factory returned an invalid value"
            )
        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_complete_attachment_upload(
                connection,
                prepared=prepared,
                asset=asset,
                media_public_id=media_public_id,
                attachment_public_id=attachment_public_id,
                now=now,
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    def _write_complete_attachment_upload(
        self,
        connection: sqlite3.Connection,
        *,
        prepared: PreparedWrittenAttachmentUpload,
        asset: PersistWrittenAttachment,
        media_public_id: str,
        attachment_public_id: str,
        now: datetime,
    ) -> tuple[
        CreateWrittenAttachmentReceipt | None,
        WrittenSubmissionRejected | None,
    ]:
        command = prepared.command
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            operation=CREATE_ATTACHMENT_OPERATION,
            idempotency_key=command.idempotency_key,
            payload_sha256=prepared.payload_sha256,
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return CreateWrittenAttachmentReceipt.from_response(replay.response), None
        received_at = _timestamp(now)
        idempotency_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, ?, ?, ?, 'processing', ?) "
                "RETURNING id",
                (
                    command.account_id,
                    CREATE_ATTACHMENT_OPERATION,
                    command.idempotency_key,
                    prepared.payload_sha256,
                    received_at,
                ),
            ).fetchone()["id"]
        )
        try:
            target = _attachment_target(
                connection,
                command=command,
                now=now,
            )
            media_id = int(
                connection.execute(
                    "INSERT INTO media_assets "
                    "(public_id, sha256, storage_namespace, object_key, public_url, "
                    "media_type, byte_size, width, height, source_filename, "
                    "conversion_version, created_by_user_id, created_at) VALUES "
                    "(?, ?, 'submission', ?, ?, 'image/webp', ?, ?, ?, ?, "
                    "'pwa-written-image-v1', ?, ?) RETURNING id",
                    (
                        media_public_id,
                        asset.output_sha256,
                        asset.object_key,
                        asset.public_url,
                        asset.byte_size,
                        asset.width,
                        asset.height,
                        command.client_filename,
                        target.context.student_user_id,
                        received_at,
                    ),
                ).fetchone()["id"]
            )
            connection.execute(
                "INSERT INTO submission_attachments "
                "(public_id, entry_id, asset_id, ordinal, client_filename, "
                "upload_status, created_at) VALUES (?, ?, ?, ?, ?, 'stored', ?)",
                (
                    attachment_public_id,
                    target.entry_id,
                    media_id,
                    command.ordinal,
                    command.client_filename,
                    received_at,
                ),
            )
            entry_version = command.expected_entry_version + 1
            thread_version = command.expected_thread_version + 1
            connection.execute(
                "UPDATE submission_entries SET version = ? WHERE id = ?",
                (entry_version, target.entry_id),
            )
            connection.execute(
                "UPDATE submission_threads SET latest_entry_at = ?, updated_at = ?, "
                "version = ? WHERE id = ?",
                (received_at, received_at, thread_version, target.thread_id),
            )
            receipt = CreateWrittenAttachmentReceipt(
                thread_public_id=target.thread_public_id,
                problem_public_id=target.context.problem_public_id,
                thread_status=target.thread_status,
                thread_version=thread_version,
                entry=_entry_record(connection, entry_id=target.entry_id),
            )
        except WrittenSubmissionRejected as error:
            _complete_idempotency(
                connection,
                record_id=idempotency_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=received_at,
            )
            return None, error
        _complete_idempotency(
            connection,
            record_id=idempotency_id,
            state="completed",
            http_status=201,
            response=receipt.response_payload(),
            completed_at=received_at,
        )
        return receipt, None

    async def reorder_attachments(
        self, command: ReorderWrittenAttachmentsCommand
    ) -> MutateWrittenAttachmentsReceipt:
        payload_sha256 = _payload_hash(command.request_payload())
        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                operation=REORDER_ATTACHMENTS_OPERATION,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return MutateWrittenAttachmentsReceipt.from_response(replay.response)
        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_reorder_attachments(
                connection,
                command=command,
                payload_sha256=payload_sha256,
                now=self._clock(),
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    def _write_reorder_attachments(
        self,
        connection: sqlite3.Connection,
        *,
        command: ReorderWrittenAttachmentsCommand,
        payload_sha256: str,
        now: datetime,
    ) -> tuple[
        MutateWrittenAttachmentsReceipt | None,
        WrittenSubmissionRejected | None,
    ]:
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            operation=REORDER_ATTACHMENTS_OPERATION,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return MutateWrittenAttachmentsReceipt.from_response(replay.response), None
        changed_at = _timestamp(now)
        idempotency_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, ?, ?, ?, 'processing', ?) "
                "RETURNING id",
                (
                    command.account_id,
                    REORDER_ATTACHMENTS_OPERATION,
                    command.idempotency_key,
                    payload_sha256,
                    changed_at,
                ),
            ).fetchone()["id"]
        )
        try:
            target = _mutable_entry_target(
                connection,
                account_id=command.account_id,
                entry_public_id=command.entry_public_id,
                expected_entry_version=command.expected_entry_version,
                expected_thread_version=command.expected_thread_version,
            )
            current_ids = tuple(item.public_id for item in target.attachments)
            if set(current_ids) != set(command.attachment_public_ids) or len(
                current_ids
            ) != len(command.attachment_public_ids):
                raise WrittenSubmissionRejected(
                    code="written_attachment_set_changed",
                    message="Список фотографий изменился. Обновите страницу.",
                    http_status=409,
                )
            changed = current_ids != command.attachment_public_ids
            entry_version = target.entry_version
            thread_version = target.thread_version
            if changed:
                by_public_id = {item.public_id: item.id for item in target.attachments}
                _renumber_attachments(
                    connection,
                    entry_id=target.entry_id,
                    ordered_attachment_ids=tuple(
                        by_public_id[public_id]
                        for public_id in command.attachment_public_ids
                    ),
                )
                entry_version += 1
                thread_version += 1
                connection.execute(
                    "UPDATE submission_entries SET version = ? WHERE id = ?",
                    (entry_version, target.entry_id),
                )
                connection.execute(
                    "UPDATE submission_threads SET latest_entry_at = ?, "
                    "updated_at = ?, version = ? WHERE id = ?",
                    (changed_at, changed_at, thread_version, target.thread_id),
                )
            receipt = MutateWrittenAttachmentsReceipt(
                thread_public_id=target.thread_public_id,
                problem_public_id=target.problem_public_id,
                thread_status=target.thread_status,
                thread_version=thread_version,
                entry=_entry_record(connection, entry_id=target.entry_id),
                changed=changed,
            )
        except WrittenSubmissionRejected as error:
            _complete_idempotency(
                connection,
                record_id=idempotency_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=changed_at,
            )
            return None, error
        _complete_idempotency(
            connection,
            record_id=idempotency_id,
            state="completed",
            http_status=200,
            response=receipt.response_payload(),
            completed_at=changed_at,
        )
        return receipt, None

    async def delete_attachment(
        self, command: DeleteWrittenAttachmentCommand
    ) -> MutateWrittenAttachmentsReceipt:
        payload_sha256 = _payload_hash(command.request_payload())
        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                operation=DELETE_ATTACHMENT_OPERATION,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return MutateWrittenAttachmentsReceipt.from_response(replay.response)
        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_delete_attachment(
                connection,
                command=command,
                payload_sha256=payload_sha256,
                now=self._clock(),
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    def _write_delete_attachment(
        self,
        connection: sqlite3.Connection,
        *,
        command: DeleteWrittenAttachmentCommand,
        payload_sha256: str,
        now: datetime,
    ) -> tuple[
        MutateWrittenAttachmentsReceipt | None,
        WrittenSubmissionRejected | None,
    ]:
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            operation=DELETE_ATTACHMENT_OPERATION,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return MutateWrittenAttachmentsReceipt.from_response(replay.response), None
        changed_at = _timestamp(now)
        idempotency_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, ?, ?, ?, 'processing', ?) "
                "RETURNING id",
                (
                    command.account_id,
                    DELETE_ATTACHMENT_OPERATION,
                    command.idempotency_key,
                    payload_sha256,
                    changed_at,
                ),
            ).fetchone()["id"]
        )
        try:
            target = _mutable_entry_target(
                connection,
                account_id=command.account_id,
                entry_public_id=command.entry_public_id,
                expected_entry_version=command.expected_entry_version,
                expected_thread_version=command.expected_thread_version,
            )
            attachment = next(
                (
                    item
                    for item in target.attachments
                    if item.public_id == command.attachment_public_id
                ),
                None,
            )
            if attachment is None:
                raise WrittenSubmissionRejected(
                    code="written_attachment_not_found",
                    message="Фотография решения не найдена.",
                    http_status=404,
                )
            if (
                target.entry_state == "submitted"
                and not str(target.text or "").strip()
                and len(target.attachments) == 1
            ):
                raise WrittenSubmissionRejected(
                    code="written_entry_empty",
                    message="В отправленном решении должна остаться фотография или текст.",
                    http_status=422,
                )
            connection.execute(
                "UPDATE media_assets SET deleted_at = ? WHERE id = ?",
                (changed_at, attachment.asset_id),
            )
            connection.execute(
                "DELETE FROM submission_attachments WHERE id = ?",
                (attachment.id,),
            )
            remaining_ids = tuple(
                item.id for item in target.attachments if item.id != attachment.id
            )
            _renumber_attachments(
                connection,
                entry_id=target.entry_id,
                ordered_attachment_ids=remaining_ids,
            )
            entry_version = target.entry_version + 1
            thread_version = target.thread_version + 1
            connection.execute(
                "UPDATE submission_entries SET version = ? WHERE id = ?",
                (entry_version, target.entry_id),
            )
            connection.execute(
                "UPDATE submission_threads SET latest_entry_at = ?, updated_at = ?, "
                "version = ? WHERE id = ?",
                (changed_at, changed_at, thread_version, target.thread_id),
            )
            receipt = MutateWrittenAttachmentsReceipt(
                thread_public_id=target.thread_public_id,
                problem_public_id=target.problem_public_id,
                thread_status=target.thread_status,
                thread_version=thread_version,
                entry=_entry_record(connection, entry_id=target.entry_id),
                changed=True,
            )
        except WrittenSubmissionRejected as error:
            _complete_idempotency(
                connection,
                record_id=idempotency_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=changed_at,
            )
            return None, error
        _complete_idempotency(
            connection,
            record_id=idempotency_id,
            state="completed",
            http_status=200,
            response=receipt.response_payload(),
            completed_at=changed_at,
        )
        return receipt, None

    async def submit_entry(
        self, command: SubmitWrittenEntryCommand
    ) -> SubmitWrittenEntryReceipt:
        now = self._clock()
        request = {
            "schemaVersion": 1,
            "entryId": command.entry_public_id,
            "expectedEntryVersion": command.expected_entry_version,
            "expectedThreadVersion": command.expected_thread_version,
            "attachmentIds": list(command.attachment_public_ids),
        }
        payload_sha256 = _payload_hash(request)
        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                operation=SUBMIT_ENTRY_OPERATION,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return SubmitWrittenEntryReceipt.from_response(replay.response)
        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_submit_entry(
                connection,
                command=command,
                now=now,
                payload_sha256=payload_sha256,
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    def _write_submit_entry(
        self,
        connection: sqlite3.Connection,
        *,
        command: SubmitWrittenEntryCommand,
        now: datetime,
        payload_sha256: str,
    ) -> tuple[SubmitWrittenEntryReceipt | None, WrittenSubmissionRejected | None]:
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            operation=SUBMIT_ENTRY_OPERATION,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return SubmitWrittenEntryReceipt.from_response(replay.response), None
        received_at = _timestamp(now)
        idempotency_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, ?, ?, ?, 'processing', ?) "
                "RETURNING id",
                (
                    command.account_id,
                    SUBMIT_ENTRY_OPERATION,
                    command.idempotency_key,
                    payload_sha256,
                    received_at,
                ),
            ).fetchone()["id"]
        )
        try:
            row = connection.execute(
                "SELECT entry.id, entry.state, entry.version AS entry_version, "
                "entry.text, entry.client_created_at, entry.problem_revision_id, "
                "thread.id AS thread_id, thread.public_id AS thread_public_id, "
                "thread.version AS thread_version, thread.problem_id, "
                "problem.public_id AS problem_public_id "
                "FROM auth_accounts AS account "
                "JOIN submission_threads AS thread "
                "ON thread.student_user_id = account.linked_user_id "
                "JOIN submission_entries AS entry ON entry.thread_id = thread.id "
                "JOIN problems AS problem ON problem.id = thread.problem_id "
                "WHERE account.id = ? AND account.audience = 'student' "
                "AND account.status = 'active' AND entry.public_id = ?",
                (command.account_id, command.entry_public_id),
            ).fetchone()
            if row is None:
                raise WrittenSubmissionRejected(
                    code="written_entry_not_found",
                    message="Черновик письменного решения не найден.",
                    http_status=404,
                )
            if row["state"] not in ("draft", "uploading"):
                raise WrittenSubmissionRejected(
                    code="written_entry_not_editable",
                    message="Эта версия решения уже отправлена.",
                    http_status=409,
                )
            if (
                int(row["entry_version"]) != command.expected_entry_version
                or int(row["thread_version"]) != command.expected_thread_version
            ):
                raise WrittenSubmissionRejected(
                    code="written_submission_version_conflict",
                    message="Решение изменилось в другом окне. Обновите страницу.",
                    http_status=409,
                )
            context = _resolve_context(
                connection,
                account_id=command.account_id,
                problem_public_id=str(row["problem_public_id"]),
                now=now,
            )
            if context.problem_revision_id != int(row["problem_revision_id"]):
                raise WrittenSubmissionRejected(
                    code="written_problem_revision_changed",
                    message="Условие задачи изменилось. Проверьте решение перед отправкой.",
                    http_status=409,
                )
            stored_attachments = connection.execute(
                "SELECT public_id, upload_status FROM submission_attachments "
                "WHERE entry_id = ? ORDER BY ordinal, id",
                (row["id"],),
            ).fetchall()
            stored_ids = tuple(str(item["public_id"]) for item in stored_attachments)
            if stored_ids != command.attachment_public_ids or any(
                item["upload_status"] != "stored" for item in stored_attachments
            ):
                raise WrittenSubmissionRejected(
                    code="written_attachments_not_ready",
                    message="Не все фотографии готовы к отправке.",
                    http_status=409,
                )
            if not str(row["text"] or "").strip() and not stored_ids:
                raise WrittenSubmissionRejected(
                    code="written_entry_empty",
                    message="Добавьте текст или фотографии решения.",
                    http_status=422,
                )
            client_created_at = _parse_timestamp(
                row["client_created_at"], label="entry creation time"
            )
            clock = assess_submission_clock(
                client_created_at=client_created_at,
                server_received_at=now,
                submission_closes_at=context.submission_closes_at,
            )
            if not clock.timely:
                raise WrittenSubmissionRejected(
                    code="submission_deadline_passed",
                    message="Срок сдачи этой задачи уже закончился.",
                    http_status=409,
                    details={
                        "submissionClosesAt": _timestamp(context.submission_closes_at)
                    },
                )
            entry_version = int(row["entry_version"]) + 1
            thread_version = int(row["thread_version"]) + 1
            connection.execute(
                "UPDATE submission_entries SET state = 'submitted', version = ? "
                "WHERE id = ?",
                (entry_version, row["id"]),
            )
            connection.execute(
                "UPDATE submission_threads SET status = 'awaiting_review', "
                "latest_entry_at = ?, updated_at = ?, version = ? WHERE id = ?",
                (received_at, received_at, thread_version, row["thread_id"]),
            )
            receipt = SubmitWrittenEntryReceipt(
                thread_public_id=str(row["thread_public_id"]),
                problem_public_id=str(row["problem_public_id"]),
                thread_status="awaiting_review",
                thread_version=thread_version,
                entry=_entry_record(connection, entry_id=int(row["id"])),
                clock_suspicious=clock.suspicious,
            )
        except WrittenSubmissionRejected as error:
            _complete_idempotency(
                connection,
                record_id=idempotency_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=received_at,
            )
            return None, error
        _complete_idempotency(
            connection,
            record_id=idempotency_id,
            state="completed",
            http_status=200,
            response=receipt.response_payload(),
            completed_at=received_at,
        )
        return receipt, None

    async def replace_entry(
        self, command: ReplaceWrittenEntryCommand
    ) -> ReplaceWrittenEntryReceipt:
        """Publish a complete draft and retire one unlocked submitted entry."""

        payload_sha256 = _payload_hash(command.request_payload())
        replay = await self._factory.run_read_async(
            lambda connection: _read_idempotency(
                connection,
                account_id=command.account_id,
                operation=REPLACE_ENTRY_OPERATION,
                idempotency_key=command.idempotency_key,
                payload_sha256=payload_sha256,
            )
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return ReplaceWrittenEntryReceipt.from_response(replay.response)
        replacement_event_public_id = self._replacement_event_public_id_factory()
        if not _PUBLIC_ID.fullmatch(replacement_event_public_id):
            raise WrittenSubmissionRepositoryError(
                "replacement event public ID factory returned an invalid value"
            )
        receipt, error = await self._factory.run_write_async(
            lambda connection: self._write_replace_entry(
                connection,
                command=command,
                payload_sha256=payload_sha256,
                replacement_event_public_id=replacement_event_public_id,
                now=self._clock(),
            )
        )
        if error is not None:
            raise error
        assert receipt is not None
        return receipt

    def _write_replace_entry(
        self,
        connection: sqlite3.Connection,
        *,
        command: ReplaceWrittenEntryCommand,
        payload_sha256: str,
        replacement_event_public_id: str,
        now: datetime,
    ) -> tuple[ReplaceWrittenEntryReceipt | None, WrittenSubmissionRejected | None]:
        replay = _read_idempotency(
            connection,
            account_id=command.account_id,
            operation=REPLACE_ENTRY_OPERATION,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
        )
        if replay is not None:
            if replay.state != "completed":
                _raise_replay_failure(replay)
            return ReplaceWrittenEntryReceipt.from_response(replay.response), None
        replaced_at = _timestamp(now)
        idempotency_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, ?, ?, ?, 'processing', ?) "
                "RETURNING id",
                (
                    command.account_id,
                    REPLACE_ENTRY_OPERATION,
                    command.idempotency_key,
                    payload_sha256,
                    replaced_at,
                ),
            ).fetchone()["id"]
        )
        try:
            row = connection.execute(
                "SELECT entry.id, entry.state, entry.version AS entry_version, "
                "entry.text, entry.client_created_at, entry.problem_revision_id, "
                "thread.id AS thread_id, thread.public_id AS thread_public_id, "
                "thread.student_user_id, thread.status AS thread_status, "
                "thread.version AS thread_version, problem.public_id AS problem_public_id "
                "FROM auth_accounts AS account "
                "JOIN submission_threads AS thread "
                "ON thread.student_user_id = account.linked_user_id "
                "JOIN submission_entries AS entry ON entry.thread_id = thread.id "
                "JOIN problems AS problem ON problem.id = thread.problem_id "
                "WHERE account.id = ? AND account.audience = 'student' "
                "AND account.status = 'active' AND entry.public_id = ?",
                (command.account_id, command.entry_public_id),
            ).fetchone()
            if row is None:
                raise WrittenSubmissionRejected(
                    code="written_entry_not_found",
                    message="Черновик замены не найден.",
                    http_status=404,
                )
            if row["state"] not in ("draft", "uploading"):
                raise WrittenSubmissionRejected(
                    code="written_entry_not_editable",
                    message="Эту версию решения уже нельзя использовать для замены.",
                    http_status=409,
                )
            if row["thread_status"] != "awaiting_review":
                raise WrittenSubmissionRejected(
                    code="written_replacement_unavailable",
                    message="Отправленное решение уже начали проверять или проверили.",
                    http_status=409,
                )
            if (
                int(row["entry_version"]) != command.expected_entry_version
                or int(row["thread_version"]) != command.expected_thread_version
            ):
                raise WrittenSubmissionRejected(
                    code="written_submission_version_conflict",
                    message="Решение изменилось в другом окне. Обновите страницу.",
                    http_status=409,
                )
            replaced = connection.execute(
                "SELECT id, state, version FROM submission_entries "
                "WHERE thread_id = ? AND public_id = ? AND author_kind = 'student' "
                "AND author_user_id = ?",
                (
                    row["thread_id"],
                    command.replaced_entry_public_id,
                    row["student_user_id"],
                ),
            ).fetchone()
            if replaced is None:
                raise WrittenSubmissionRejected(
                    code="written_replaced_entry_not_found",
                    message="Исходное отправленное решение не найдено.",
                    http_status=404,
                )
            if (
                replaced["state"] != "submitted"
                or int(replaced["version"]) != command.expected_replaced_entry_version
            ):
                raise WrittenSubmissionRejected(
                    code="written_replacement_target_changed",
                    message="Исходное решение уже изменилось или попало в проверку.",
                    http_status=409,
                )
            if connection.execute(
                "SELECT 1 FROM submission_attachments WHERE entry_id = ? "
                "AND upload_status = 'locked' LIMIT 1",
                (replaced["id"],),
            ).fetchone():
                raise WrittenSubmissionRejected(
                    code="written_attachment_locked",
                    message="Фотографии уже зафиксированы проверкой.",
                    http_status=409,
                )
            context = _resolve_context(
                connection,
                account_id=command.account_id,
                problem_public_id=str(row["problem_public_id"]),
                now=now,
            )
            if context.problem_revision_id != int(row["problem_revision_id"]):
                raise WrittenSubmissionRejected(
                    code="written_problem_revision_changed",
                    message="Условие задачи изменилось. Проверьте решение перед заменой.",
                    http_status=409,
                )
            attachments = connection.execute(
                "SELECT public_id, upload_status FROM submission_attachments "
                "WHERE entry_id = ? ORDER BY ordinal, id",
                (row["id"],),
            ).fetchall()
            stored_ids = tuple(str(item["public_id"]) for item in attachments)
            if stored_ids != command.attachment_public_ids or any(
                item["upload_status"] != "stored" for item in attachments
            ):
                raise WrittenSubmissionRejected(
                    code="written_attachments_not_ready",
                    message="Не все фотографии готовы к замене.",
                    http_status=409,
                )
            if not str(row["text"] or "").strip() and not stored_ids:
                raise WrittenSubmissionRejected(
                    code="written_entry_empty",
                    message="Добавьте текст или фотографии решения.",
                    http_status=422,
                )
            client_created_at = _parse_timestamp(
                row["client_created_at"], label="entry creation time"
            )
            clock = assess_submission_clock(
                client_created_at=client_created_at,
                server_received_at=now,
                submission_closes_at=context.submission_closes_at,
            )
            if not clock.timely:
                raise WrittenSubmissionRejected(
                    code="submission_deadline_passed",
                    message="Срок сдачи этой задачи уже закончился.",
                    http_status=409,
                    details={
                        "submissionClosesAt": _timestamp(context.submission_closes_at)
                    },
                )
            connection.execute(
                "UPDATE submission_entries SET state = 'deleted', deleted_at = ?, "
                "version = ? WHERE id = ?",
                (
                    replaced_at,
                    command.expected_replaced_entry_version + 1,
                    replaced["id"],
                ),
            )
            entry_version = int(row["entry_version"]) + 1
            thread_version = int(row["thread_version"]) + 1
            connection.execute(
                "UPDATE submission_entries SET state = 'submitted', version = ? "
                "WHERE id = ?",
                (entry_version, row["id"]),
            )
            connection.execute(
                "UPDATE submission_threads SET latest_entry_at = ?, updated_at = ?, "
                "version = ? WHERE id = ?",
                (replaced_at, replaced_at, thread_version, row["thread_id"]),
            )
            connection.execute(
                "INSERT INTO submission_entry_replacements "
                "(public_id, thread_id, student_user_id, replaced_entry_id, "
                "replacement_entry_id, idempotency_key, replaced_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    replacement_event_public_id,
                    row["thread_id"],
                    row["student_user_id"],
                    replaced["id"],
                    row["id"],
                    command.idempotency_key,
                    replaced_at,
                ),
            )
            receipt = ReplaceWrittenEntryReceipt(
                thread_public_id=str(row["thread_public_id"]),
                problem_public_id=str(row["problem_public_id"]),
                thread_status="awaiting_review",
                thread_version=thread_version,
                entry=_entry_record(connection, entry_id=int(row["id"])),
                replaced_entry_public_id=command.replaced_entry_public_id,
                replacement_event_public_id=replacement_event_public_id,
                clock_suspicious=clock.suspicious,
            )
        except WrittenSubmissionRejected as error:
            _complete_idempotency(
                connection,
                record_id=idempotency_id,
                state="failed",
                http_status=error.http_status,
                response=error.response_payload(),
                completed_at=replaced_at,
            )
            return None, error
        _complete_idempotency(
            connection,
            record_id=idempotency_id,
            state="completed",
            http_status=200,
            response=receipt.response_payload(),
            completed_at=replaced_at,
        )
        return receipt, None

    async def get_attachment_media(
        self,
        *,
        account_id: int,
        entry_public_id: str,
        attachment_public_id: str,
    ) -> WrittenAttachmentMedia:
        """Resolve only media owned by the authenticated Student account."""

        if (
            account_id < 1
            or not _PUBLIC_ID.fullmatch(entry_public_id)
            or not _PUBLIC_ID.fullmatch(attachment_public_id)
        ):
            raise ValueError("attachment media lookup arguments are invalid")

        def read(connection: sqlite3.Connection) -> WrittenAttachmentMedia:
            row = connection.execute(
                "SELECT asset.object_key, asset.sha256, asset.byte_size, "
                "asset.media_type FROM auth_accounts AS account "
                "JOIN submission_threads AS thread "
                "ON thread.student_user_id = account.linked_user_id "
                "JOIN submission_entries AS entry ON entry.thread_id = thread.id "
                "JOIN submission_attachments AS attachment "
                "ON attachment.entry_id = entry.id "
                "JOIN media_assets AS asset ON asset.id = attachment.asset_id "
                "WHERE account.id = ? AND account.audience = 'student' "
                "AND account.status = 'active' AND entry.public_id = ? "
                "AND attachment.public_id = ? AND asset.deleted_at IS NULL",
                (account_id, entry_public_id, attachment_public_id),
            ).fetchone()
            if row is None:
                raise WrittenSubmissionRejected(
                    code="written_attachment_not_found",
                    message="Фотография решения не найдена.",
                    http_status=404,
                )
            return WrittenAttachmentMedia(
                object_key=str(row["object_key"]),
                sha256=str(row["sha256"]),
                byte_size=int(row["byte_size"]),
                media_type=str(row["media_type"]),
            )

        return await self._factory.run_read_async(read)

    async def get_thread(
        self, *, account_id: int, problem_public_id: str
    ) -> WrittenThreadRecord | None:
        if account_id < 1 or not _PUBLIC_ID.fullmatch(problem_public_id):
            raise ValueError("thread lookup arguments are invalid")
        now = self._clock()

        def read(connection: sqlite3.Connection) -> WrittenThreadRecord | None:
            row = connection.execute(
                "SELECT thread.*, problem.public_id AS problem_public_id, "
                "revision.public_id AS condition_revision_public_id "
                "FROM auth_accounts AS account "
                "JOIN submission_threads AS thread "
                "ON thread.student_user_id = account.linked_user_id "
                "JOIN problems AS problem ON problem.id = thread.problem_id "
                "JOIN content_revisions AS revision "
                "ON revision.id = thread.condition_revision_id "
                "WHERE account.id = ? AND account.audience = 'student' "
                "AND account.status = 'active' AND problem.public_id = ? "
                "ORDER BY (thread.status = 'closed'), thread.updated_at DESC, "
                "thread.id DESC LIMIT 1",
                (account_id, problem_public_id),
            ).fetchone()
            if row is None:
                # Do not reveal whether a foreign problem exists. A student with
                # no own history must still have current published access.
                _resolve_context(
                    connection,
                    account_id=account_id,
                    problem_public_id=problem_public_id,
                    now=now,
                )
                return None
            entry_rows = connection.execute(
                "SELECT id FROM submission_entries WHERE thread_id = ? "
                "ORDER BY server_received_at, id",
                (row["id"],),
            ).fetchall()
            return WrittenThreadRecord(
                public_id=str(row["public_id"]),
                problem_public_id=str(row["problem_public_id"]),
                status=str(row["status"]),
                condition_revision_public_id=str(row["condition_revision_public_id"]),
                version=int(row["version"]),
                latest_entry_at=str(row["latest_entry_at"]),
                entries=tuple(
                    _entry_record(connection, entry_id=int(entry["id"]))
                    for entry in entry_rows
                ),
            )

        return await self._factory.run_read_async(read)


__all__ = [
    "CREATE_ATTACHMENT_OPERATION",
    "CREATE_ENTRY_OPERATION",
    "DELETE_ATTACHMENT_OPERATION",
    "REORDER_ATTACHMENTS_OPERATION",
    "REPLACE_ENTRY_OPERATION",
    "SUBMIT_ENTRY_OPERATION",
    "CreateWrittenAttachmentCommand",
    "CreateWrittenAttachmentReceipt",
    "CreateWrittenEntryCommand",
    "CreateWrittenEntryReceipt",
    "DeleteWrittenAttachmentCommand",
    "MutateWrittenAttachmentsReceipt",
    "PersistWrittenAttachment",
    "PreparedWrittenAttachmentUpload",
    "ProblemRevisionRef",
    "PwaWrittenSubmissionRepository",
    "ReorderWrittenAttachmentsCommand",
    "ReplaceWrittenEntryCommand",
    "ReplaceWrittenEntryReceipt",
    "SubmitWrittenEntryCommand",
    "SubmitWrittenEntryReceipt",
    "WrittenAttachmentRecord",
    "WrittenAttachmentMedia",
    "WrittenAttachmentUploadScope",
    "WrittenEntryRecord",
    "WrittenIdempotencyPayloadMismatch",
    "WrittenSubmissionRejected",
    "WrittenSubmissionRepositoryError",
    "WrittenThreadRecord",
]
