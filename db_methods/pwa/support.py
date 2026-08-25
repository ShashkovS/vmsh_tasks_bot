"""Private Student/Staff support threads for the PWA contour.

This first Phase-6 slice deliberately keeps Telegram dual-write and HTTP/UI
composition outside the repository. It establishes the durable invariant that
one Student owns a chronological question thread while any authorized Teacher
may answer it without claiming the conversation. See
``vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from helpers.consts import USER_TYPE

from .connection import PwaConnectionFactory


_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")
SupportThreadKind = Literal["problem_question", "general", "sos"]
SupportAuthorKind = Literal["student", "teacher", "admin", "system"]
SupportReplyState = Literal["awaiting_staff", "awaiting_student", "activity"]
SupportStaffListState = Literal["all", "awaiting_staff", "awaiting_student"]


class SupportRepositoryError(RuntimeError):
    """Base class for support persistence failures."""


class SupportNotFound(SupportRepositoryError):
    """The thread or requested lesson/problem target does not exist."""


class SupportForbidden(SupportRepositoryError):
    """The actor cannot read or append to this private thread."""


class SupportIdempotencyConflict(SupportRepositoryError):
    """An idempotency key was reused for a different support payload."""


@dataclass(frozen=True, slots=True)
class SupportStaffScope:
    """Server-resolved Staff scope expressed only through opaque public IDs."""

    global_access: bool = False
    course_public_ids: frozenset[str] = frozenset()
    group_public_ids: frozenset[str] = frozenset()

    def allows(self, row: dict[str, object]) -> bool:
        if self.global_access:
            return True
        course_public_id = row.get("course_public_id")
        group_public_id = row.get("group_public_id")
        return (
            isinstance(course_public_id, str)
            and course_public_id in self.course_public_ids
        ) or (
            isinstance(group_public_id, str)
            and group_public_id in self.group_public_ids
        )


@dataclass(frozen=True, slots=True)
class CreateSupportThreadCommand:
    student_user_id: int
    kind: Literal["problem_question", "general"]
    group_lesson_public_id: str
    problem_public_id: str | None
    text: str
    client_created_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        _validate_user_id(self.student_user_id)
        _validate_public_id(self.group_lesson_public_id, "group lesson")
        if self.kind == "problem_question":
            if self.problem_public_id is None:
                raise ValueError("problem question requires a problem")
            _validate_public_id(self.problem_public_id, "problem")
        elif self.problem_public_id is not None:
            raise ValueError("general question cannot reference a problem")
        _validate_text(self.text)
        _validate_client_time(self.client_created_at)
        _validate_idempotency_key(self.idempotency_key)


@dataclass(frozen=True, slots=True)
class AppendStudentSupportEntryCommand:
    student_user_id: int
    thread_public_id: str
    text: str
    client_created_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        _validate_user_id(self.student_user_id)
        _validate_public_id(self.thread_public_id, "support thread")
        _validate_text(self.text)
        _validate_client_time(self.client_created_at)
        _validate_idempotency_key(self.idempotency_key)


@dataclass(frozen=True, slots=True)
class AppendStaffSupportEntryCommand:
    staff_user_id: int
    author_kind: Literal["teacher", "admin"]
    thread_public_id: str
    text: str
    client_created_at: datetime
    idempotency_key: str
    scope: SupportStaffScope

    def __post_init__(self) -> None:
        _validate_user_id(self.staff_user_id)
        _validate_public_id(self.thread_public_id, "support thread")
        _validate_text(self.text)
        _validate_client_time(self.client_created_at)
        _validate_idempotency_key(self.idempotency_key)


@dataclass(frozen=True, slots=True)
class SupportEntryRecord:
    entry_public_id: str
    author_kind: SupportAuthorKind
    author_public_id: str | None
    author_display_name: str
    text: str | None
    asset_public_id: str | None
    channel: str
    client_created_at: datetime | None
    server_received_at: datetime


@dataclass(frozen=True, slots=True)
class SupportThreadRecord:
    thread_public_id: str
    kind: SupportThreadKind
    student_public_id: str
    student_display_name: str
    course_public_id: str | None
    course_name: str | None
    group_public_id: str | None
    group_name: str | None
    group_lesson_public_id: str | None
    problem_public_id: str | None
    problem_title: str | None
    latest_entry_at: datetime
    version: int
    entries: tuple[SupportEntryRecord, ...]


@dataclass(frozen=True, slots=True)
class SupportThreadSummaryRecord:
    thread_public_id: str
    kind: SupportThreadKind
    student_public_id: str
    student_display_name: str
    course_public_id: str | None
    course_name: str | None
    group_public_id: str | None
    group_name: str | None
    group_lesson_public_id: str | None
    problem_public_id: str | None
    problem_title: str | None
    latest_entry_at: datetime
    latest_author_kind: SupportAuthorKind
    latest_text_excerpt: str | None
    reply_state: SupportReplyState
    entry_count: int
    version: int


@dataclass(frozen=True, slots=True)
class SupportThreadPage:
    items: tuple[SupportThreadSummaryRecord, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class SupportInvalidationTargets:
    thread_public_id: str
    student_account_public_ids: tuple[str, ...]
    staff_account_public_ids: tuple[str, ...]


def _validate_user_id(value: int) -> None:
    if type(value) is not int or value == 0:
        raise ValueError("user ID must be a non-zero integer")


def _validate_public_id(value: str, label: str) -> None:
    if not isinstance(value, str) or _PUBLIC_ID.fullmatch(value) is None:
        raise ValueError(f"{label} public ID is invalid")


def _validate_text(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 100_000:
        raise ValueError("support entry text is invalid")


def _validate_client_time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("client creation time must be timezone-aware")


def _validate_idempotency_key(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 200
    ):
        raise ValueError("idempotency key is invalid")


def _validate_list_page(*, cursor: str | None, page_size: int) -> None:
    if cursor is not None:
        _validate_public_id(cursor, "support list cursor")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("support page size must be between 1 and 100")


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise SupportRepositoryError(f"stored {label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SupportRepositoryError(f"stored {label} is invalid") from error
    if parsed.tzinfo is None:
        raise SupportRepositoryError(f"stored {label} is not timezone-aware")
    return parsed.astimezone(UTC)


def _display_name(row: dict[str, object], *, prefix: str) -> str:
    name = row.get(f"{prefix}_name")
    surname = row.get(f"{prefix}_surname")
    value = " ".join(
        part.strip()
        for part in (name, surname)
        if isinstance(part, str) and part.strip()
    )
    return value or "Неизвестный пользователь"


def _payload_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _reply_state(author_kind: object) -> SupportReplyState:
    if author_kind == "student":
        return "awaiting_staff"
    if author_kind in {"teacher", "admin"}:
        return "awaiting_student"
    return "activity"


def _summary_record(row: dict[str, object]) -> SupportThreadSummaryRecord:
    student_public_id = row["student_public_id"]
    if not isinstance(student_public_id, str) or not student_public_id:
        raise SupportRepositoryError("support Student has no public identity")
    latest_author_kind = str(row["latest_author_kind"])
    entry_count = int(row["entry_count"])
    if entry_count < 1:
        raise SupportRepositoryError("support thread summary has no entries")
    return SupportThreadSummaryRecord(
        thread_public_id=str(row["public_id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        student_public_id=student_public_id,
        student_display_name=_display_name(row, prefix="student"),
        course_public_id=(
            None if row["course_public_id"] is None else str(row["course_public_id"])
        ),
        course_name=None if row["course_name"] is None else str(row["course_name"]),
        group_public_id=(
            None if row["group_public_id"] is None else str(row["group_public_id"])
        ),
        group_name=None if row["group_name"] is None else str(row["group_name"]),
        group_lesson_public_id=(
            None
            if row["group_lesson_public_id"] is None
            else str(row["group_lesson_public_id"])
        ),
        problem_public_id=(
            None if row["problem_public_id"] is None else str(row["problem_public_id"])
        ),
        problem_title=(
            None if row["problem_title"] is None else str(row["problem_title"])
        ),
        latest_entry_at=_parse_timestamp(
            row["latest_entry_at"], label="support latest entry time"
        ),
        latest_author_kind=latest_author_kind,  # type: ignore[arg-type]
        latest_text_excerpt=(
            None
            if row["latest_text_excerpt"] is None
            else str(row["latest_text_excerpt"])
        ),
        reply_state=_reply_state(latest_author_kind),
        entry_count=entry_count,
        version=int(row["version"]),
    )


class PwaSupportThreadRepository:
    """Transactional repository for private, unassigned support conversations."""

    def __init__(
        self,
        connection_factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._factory = connection_factory
        self._clock = clock

    async def create_student_thread(
        self, command: CreateSupportThreadCommand
    ) -> SupportThreadRecord:
        payload_hash = _payload_hash(
            {
                "operation": "support-thread:create",
                "kind": command.kind,
                "groupLessonId": command.group_lesson_public_id,
                "problemId": command.problem_public_id,
                "text": command.text,
                "clientCreatedAt": _timestamp(command.client_created_at),
            }
        )
        now = self._clock()
        if now.tzinfo is None:
            raise SupportRepositoryError("repository clock must be timezone-aware")
        received_at = _timestamp(now)

        def operation(connection: sqlite3.Connection) -> SupportThreadRecord:
            replay = self._idempotent_entry(
                connection,
                actor_user_id=command.student_user_id,
                idempotency_key=command.idempotency_key,
                payload_hash=payload_hash,
            )
            if replay is not None:
                return self._load_thread(connection, thread_id=replay)

            target = self._student_target(
                connection,
                student_user_id=command.student_user_id,
                group_lesson_public_id=command.group_lesson_public_id,
                problem_public_id=command.problem_public_id,
                kind=command.kind,
                now=received_at,
            )
            if command.kind == "problem_question":
                existing = connection.execute(
                    "SELECT id FROM support_threads WHERE student_user_id = ? "
                    "AND group_lesson_id = ? AND problem_id = ? "
                    "AND kind = 'problem_question'",
                    (
                        command.student_user_id,
                        target["group_lesson_id"],
                        target["problem_id"],
                    ),
                ).fetchone()
            else:
                existing = connection.execute(
                    "SELECT id FROM support_threads WHERE student_user_id = ? "
                    "AND group_lesson_id = ? AND kind = 'general'",
                    (command.student_user_id, target["group_lesson_id"]),
                ).fetchone()

            if existing is None:
                thread_id = int(
                    connection.execute(
                        "INSERT INTO support_threads "
                        "(student_user_id, problem_id, group_lesson_id, kind, "
                        "latest_entry_at, created_at, updated_at, version) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, 1) RETURNING id",
                        (
                            command.student_user_id,
                            target["problem_id"],
                            target["group_lesson_id"],
                            command.kind,
                            received_at,
                            received_at,
                            received_at,
                        ),
                    ).fetchone()["id"]
                )
                touch_thread = False
            else:
                thread_id = int(existing["id"])
                touch_thread = True

            self._insert_entry(
                connection,
                thread_id=thread_id,
                author_kind="student",
                author_user_id=command.student_user_id,
                channel="pwa",
                text=command.text,
                client_created_at=command.client_created_at,
                server_received_at=received_at,
                idempotency_key=command.idempotency_key,
                payload_hash=payload_hash,
            )
            if touch_thread:
                self._touch_thread(connection, thread_id=thread_id, now=received_at)
            return self._load_thread(connection, thread_id=thread_id)

        return await self._factory.run_write_async(operation)

    async def append_student_entry(
        self, command: AppendStudentSupportEntryCommand
    ) -> SupportThreadRecord:
        return await self._append_entry(
            actor_user_id=command.student_user_id,
            author_kind="student",
            thread_public_id=command.thread_public_id,
            text=command.text,
            client_created_at=command.client_created_at,
            idempotency_key=command.idempotency_key,
            scope=None,
        )

    async def append_staff_entry(
        self, command: AppendStaffSupportEntryCommand
    ) -> SupportThreadRecord:
        return await self._append_entry(
            actor_user_id=command.staff_user_id,
            author_kind=command.author_kind,
            thread_public_id=command.thread_public_id,
            text=command.text,
            client_created_at=command.client_created_at,
            idempotency_key=command.idempotency_key,
            scope=command.scope,
        )

    async def get_student_thread(
        self, *, student_user_id: int, thread_public_id: str
    ) -> SupportThreadRecord:
        _validate_user_id(student_user_id)
        _validate_public_id(thread_public_id, "support thread")

        def operation(connection: sqlite3.Connection) -> SupportThreadRecord:
            row = self._thread_row(connection, thread_public_id=thread_public_id)
            if row is None:
                raise SupportNotFound("support thread was not found")
            if int(row["student_user_id"]) != student_user_id:
                raise SupportForbidden("support thread belongs to another Student")
            return self._load_thread(connection, thread_id=int(row["id"]), row=row)

        return await self._factory.run_read_async(operation)

    async def get_staff_thread(
        self, *, thread_public_id: str, scope: SupportStaffScope
    ) -> SupportThreadRecord:
        _validate_public_id(thread_public_id, "support thread")

        def operation(connection: sqlite3.Connection) -> SupportThreadRecord:
            row = self._thread_row(connection, thread_public_id=thread_public_id)
            if row is None:
                raise SupportNotFound("support thread was not found")
            if not scope.allows(row):
                raise SupportForbidden("support thread is outside Staff scope")
            return self._load_thread(connection, thread_id=int(row["id"]), row=row)

        return await self._factory.run_read_async(operation)

    async def list_student_threads(
        self,
        *,
        student_user_id: int,
        cursor: str | None = None,
        page_size: int = 50,
    ) -> SupportThreadPage:
        """Return one Student's historical threads, newest activity first."""

        _validate_user_id(student_user_id)
        _validate_list_page(cursor=cursor, page_size=page_size)

        def operation(connection: sqlite3.Connection) -> SupportThreadPage:
            rows = self._summary_rows(
                connection,
                where_sql="thread.student_user_id = ?",
                parameters=(student_user_id,),
            )
            return self._summary_page(rows, cursor=cursor, page_size=page_size)

        return await self._factory.run_read_async(operation)

    async def list_staff_threads(
        self,
        *,
        scope: SupportStaffScope,
        state: SupportStaffListState = "awaiting_staff",
        kind: SupportThreadKind | None = None,
        course_public_id: str | None = None,
        group_public_id: str | None = None,
        cursor: str | None = None,
        page_size: int = 50,
    ) -> SupportThreadPage:
        """Return the current Staff inbox projection without assigning threads."""

        if state not in {"all", "awaiting_staff", "awaiting_student"}:
            raise ValueError("support list state is invalid")
        if kind is not None and kind not in {"problem_question", "general", "sos"}:
            raise ValueError("support thread kind is invalid")
        if course_public_id is not None:
            _validate_public_id(course_public_id, "course")
        if group_public_id is not None:
            _validate_public_id(group_public_id, "group")
        _validate_list_page(cursor=cursor, page_size=page_size)

        def operation(connection: sqlite3.Connection) -> SupportThreadPage:
            conditions: list[str] = []
            parameters: list[object] = []
            if not scope.global_access:
                scope_conditions: list[str] = []
                course_ids = sorted(scope.course_public_ids)
                if course_ids:
                    scope_conditions.append(
                        f"course.public_id IN ({','.join('?' for _ in course_ids)})"
                    )
                    parameters.extend(course_ids)
                group_ids = sorted(scope.group_public_ids)
                if group_ids:
                    scope_conditions.append(
                        f"group_row.public_id IN ({','.join('?' for _ in group_ids)})"
                    )
                    parameters.extend(group_ids)
                if not scope_conditions:
                    return SupportThreadPage(items=(), next_cursor=None)
                conditions.append(f"({' OR '.join(scope_conditions)})")
            if state == "awaiting_staff":
                conditions.append("latest_entry.author_kind = 'student'")
            elif state == "awaiting_student":
                conditions.append("latest_entry.author_kind IN ('teacher', 'admin')")
            if kind is not None:
                conditions.append("thread.kind = ?")
                parameters.append(kind)
            if course_public_id is not None:
                conditions.append("course.public_id = ?")
                parameters.append(course_public_id)
            if group_public_id is not None:
                conditions.append("group_row.public_id = ?")
                parameters.append(group_public_id)
            rows = self._summary_rows(
                connection,
                where_sql=" AND ".join(conditions),
                parameters=tuple(parameters),
            )
            return self._summary_page(rows, cursor=cursor, page_size=page_size)

        return await self._factory.run_read_async(operation)

    async def invalidation_targets(
        self, *, thread_public_id: str
    ) -> SupportInvalidationTargets:
        """Resolve current account recipients after an authoritative commit."""

        _validate_public_id(thread_public_id, "support thread")
        now = self._clock()
        if now.tzinfo is None:
            raise SupportRepositoryError("repository clock must be timezone-aware")
        current_time = _timestamp(now)

        def operation(connection: sqlite3.Connection) -> SupportInvalidationTargets:
            row = self._thread_row(connection, thread_public_id=thread_public_id)
            if row is None:
                raise SupportNotFound("support thread was not found")
            student_accounts = connection.execute(
                "SELECT public_id FROM auth_accounts WHERE linked_user_id = ? "
                "AND audience = 'student' AND status = 'active' ORDER BY id",
                (row["student_user_id"],),
            ).fetchall()
            staff_accounts = connection.execute(
                "SELECT DISTINCT account.id, account.public_id "
                "FROM auth_accounts AS account "
                "JOIN users AS staff_user ON staff_user.id = account.linked_user_id "
                "WHERE account.audience = 'staff' AND account.status = 'active' AND ("
                "staff_user.type = ? OR EXISTS ("
                "SELECT 1 FROM staff_scopes AS staff_scope "
                "WHERE staff_scope.staff_user_id = staff_user.id "
                "AND staff_scope.course_id = ? "
                "AND (staff_scope.group_id IS NULL OR staff_scope.group_id = ?) "
                "AND staff_scope.valid_from <= ? "
                "AND (staff_scope.valid_to IS NULL OR staff_scope.valid_to > ?)"
                ")) ORDER BY account.id",
                (
                    int(USER_TYPE.ADMIN),
                    row["course_internal_id"],
                    row["group_internal_id"],
                    current_time,
                    current_time,
                ),
            ).fetchall()
            return SupportInvalidationTargets(
                thread_public_id=thread_public_id,
                student_account_public_ids=tuple(
                    str(account["public_id"]) for account in student_accounts
                ),
                staff_account_public_ids=tuple(
                    str(account["public_id"]) for account in staff_accounts
                ),
            )

        return await self._factory.run_read_async(operation)

    async def _append_entry(
        self,
        *,
        actor_user_id: int,
        author_kind: Literal["student", "teacher", "admin"],
        thread_public_id: str,
        text: str,
        client_created_at: datetime,
        idempotency_key: str,
        scope: SupportStaffScope | None,
    ) -> SupportThreadRecord:
        payload_hash = _payload_hash(
            {
                "operation": "support-entry:append",
                "threadId": thread_public_id,
                "authorKind": author_kind,
                "text": text,
                "clientCreatedAt": _timestamp(client_created_at),
            }
        )
        now = self._clock()
        if now.tzinfo is None:
            raise SupportRepositoryError("repository clock must be timezone-aware")
        received_at = _timestamp(now)

        def operation(connection: sqlite3.Connection) -> SupportThreadRecord:
            replay = self._idempotent_entry(
                connection,
                actor_user_id=actor_user_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
            )
            if replay is not None:
                replay_public_id = connection.execute(
                    "SELECT public_id FROM support_threads WHERE id = ?", (replay,)
                ).fetchone()
                if replay_public_id is None:
                    raise SupportNotFound("support thread was not found")
                replay_row = self._thread_row(
                    connection,
                    thread_public_id=str(replay_public_id["public_id"]),
                )
                if replay_row is None:
                    raise SupportNotFound("support thread was not found")
                if author_kind == "student":
                    if int(replay_row["student_user_id"]) != actor_user_id:
                        raise SupportForbidden(
                            "support thread belongs to another Student"
                        )
                elif scope is None or not scope.allows(replay_row):
                    # Idempotent replay must not become a capability token after
                    # the Teacher's course/group scope has been revoked.
                    raise SupportForbidden("support thread is outside Staff scope")
                return self._load_thread(
                    connection,
                    thread_id=replay,
                    row=replay_row,
                )

            row = self._thread_row(connection, thread_public_id=thread_public_id)
            if row is None:
                raise SupportNotFound("support thread was not found")
            if author_kind == "student":
                if int(row["student_user_id"]) != actor_user_id:
                    raise SupportForbidden("support thread belongs to another Student")
                channel = "pwa"
            else:
                if scope is None or not scope.allows(row):
                    raise SupportForbidden("support thread is outside Staff scope")
                channel = "staff"

            thread_id = int(row["id"])
            self._insert_entry(
                connection,
                thread_id=thread_id,
                author_kind=author_kind,
                author_user_id=actor_user_id,
                channel=channel,
                text=text,
                client_created_at=client_created_at,
                server_received_at=received_at,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
            )
            self._touch_thread(connection, thread_id=thread_id, now=received_at)
            return self._load_thread(connection, thread_id=thread_id)

        return await self._factory.run_write_async(operation)

    @staticmethod
    def _student_target(
        connection: sqlite3.Connection,
        *,
        student_user_id: int,
        group_lesson_public_id: str,
        problem_public_id: str | None,
        kind: str,
        now: str,
    ) -> dict[str, object]:
        target = connection.execute(
            "SELECT group_lesson.id AS group_lesson_id, group_lesson.course_id, "
            "group_lesson.group_id FROM group_lessons AS group_lesson "
            "JOIN courses AS course ON course.id = group_lesson.course_id "
            "WHERE group_lesson.public_id = ? AND group_lesson.status = 'active' "
            "AND course.status = 'active' AND EXISTS ("
            "SELECT 1 FROM course_enrollments AS enrollment "
            "WHERE enrollment.student_user_id = ? "
            "AND enrollment.course_id = group_lesson.course_id "
            "AND enrollment.status = 'active' AND ("
            "enrollment.active_group_id = group_lesson.group_id OR EXISTS ("
            "SELECT 1 FROM course_group_access AS access "
            "WHERE access.enrollment_id = enrollment.id "
            "AND access.group_id = group_lesson.group_id "
            "AND access.valid_from <= ? "
            "AND (access.valid_to IS NULL OR access.valid_to > ?)"
            "))) LIMIT 1",
            (group_lesson_public_id, student_user_id, now, now),
        ).fetchone()
        if target is None:
            raise SupportForbidden("group lesson is outside current Student access")

        result = dict(target)
        result["problem_id"] = None
        if kind == "problem_question":
            problem = connection.execute(
                "SELECT problem.id FROM problems AS problem "
                "WHERE problem.public_id = ? AND EXISTS ("
                "SELECT 1 FROM problem_revisions AS problem_revision "
                "JOIN content_revisions AS revision "
                "ON revision.id = problem_revision.content_revision_id "
                "JOIN content_sources AS source ON source.id = revision.source_id "
                "WHERE problem_revision.problem_id = problem.id "
                "AND source.group_lesson_id = ?) LIMIT 1",
                (problem_public_id, target["group_lesson_id"]),
            ).fetchone()
            if problem is None:
                raise SupportNotFound("problem is outside the selected group lesson")
            result["problem_id"] = int(problem["id"])
        return result

    @staticmethod
    def _thread_row(
        connection: sqlite3.Connection, *, thread_public_id: str
    ) -> dict[str, object] | None:
        return connection.execute(
            "SELECT thread.*, student.public_id AS student_public_id, "
            "student.name AS student_name, student.surname AS student_surname, "
            "group_lesson.public_id AS group_lesson_public_id, "
            "group_lesson.course_id AS course_internal_id, "
            "group_lesson.group_id AS group_internal_id, "
            "course.public_id AS course_public_id, course.name AS course_name, "
            "group_row.public_id AS group_public_id, "
            "group_row.public_name AS group_name, problem.public_id AS problem_public_id, "
            "problem.title AS problem_title "
            "FROM support_threads AS thread "
            "JOIN users AS student ON student.id = thread.student_user_id "
            "LEFT JOIN group_lessons AS group_lesson ON group_lesson.id = thread.group_lesson_id "
            "LEFT JOIN courses AS course ON course.id = group_lesson.course_id "
            "LEFT JOIN groups AS group_row ON group_row.course_id = group_lesson.course_id "
            "AND group_row.group_id = group_lesson.group_id "
            "LEFT JOIN problems AS problem ON problem.id = thread.problem_id "
            "WHERE thread.public_id = ?",
            (thread_public_id,),
        ).fetchone()

    def _load_thread(
        self,
        connection: sqlite3.Connection,
        *,
        thread_id: int,
        row: dict[str, object] | None = None,
    ) -> SupportThreadRecord:
        if row is None:
            public_id_row = connection.execute(
                "SELECT public_id FROM support_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if public_id_row is None:
                raise SupportNotFound("support thread was not found")
            row = self._thread_row(
                connection, thread_public_id=str(public_id_row["public_id"])
            )
        if row is None:
            raise SupportNotFound("support thread was not found")
        student_public_id = row["student_public_id"]
        if not isinstance(student_public_id, str) or not student_public_id:
            raise SupportRepositoryError("support Student has no public identity")

        entries = tuple(
            SupportEntryRecord(
                entry_public_id=str(entry["public_id"]),
                author_kind=str(entry["author_kind"]),  # type: ignore[arg-type]
                author_public_id=(
                    None
                    if entry["author_public_id"] is None
                    else str(entry["author_public_id"])
                ),
                author_display_name=(
                    "Система"
                    if entry["author_kind"] == "system"
                    else _display_name(entry, prefix="author")
                ),
                text=None if entry["text"] is None else str(entry["text"]),
                asset_public_id=(
                    None
                    if entry["asset_public_id"] is None
                    else str(entry["asset_public_id"])
                ),
                channel=str(entry["channel"]),
                client_created_at=(
                    None
                    if entry["client_created_at"] is None
                    else _parse_timestamp(
                        entry["client_created_at"], label="support client creation time"
                    )
                ),
                server_received_at=_parse_timestamp(
                    entry["server_received_at"], label="support receive time"
                ),
            )
            for entry in connection.execute(
                "SELECT entry.*, author.public_id AS author_public_id, "
                "author.name AS author_name, author.surname AS author_surname, "
                "asset.public_id AS asset_public_id "
                "FROM support_entries AS entry "
                "LEFT JOIN users AS author ON author.id = entry.author_user_id "
                "LEFT JOIN media_assets AS asset ON asset.id = entry.asset_id "
                "WHERE entry.thread_id = ? "
                "ORDER BY entry.server_received_at, entry.id",
                (thread_id,),
            ).fetchall()
        )
        return SupportThreadRecord(
            thread_public_id=str(row["public_id"]),
            kind=str(row["kind"]),  # type: ignore[arg-type]
            student_public_id=student_public_id,
            student_display_name=_display_name(row, prefix="student"),
            course_public_id=(
                None
                if row["course_public_id"] is None
                else str(row["course_public_id"])
            ),
            course_name=None if row["course_name"] is None else str(row["course_name"]),
            group_public_id=(
                None if row["group_public_id"] is None else str(row["group_public_id"])
            ),
            group_name=None if row["group_name"] is None else str(row["group_name"]),
            group_lesson_public_id=(
                None
                if row["group_lesson_public_id"] is None
                else str(row["group_lesson_public_id"])
            ),
            problem_public_id=(
                None
                if row["problem_public_id"] is None
                else str(row["problem_public_id"])
            ),
            problem_title=(
                None if row["problem_title"] is None else str(row["problem_title"])
            ),
            latest_entry_at=_parse_timestamp(
                row["latest_entry_at"], label="support latest entry time"
            ),
            version=int(row["version"]),
            entries=entries,
        )

    @staticmethod
    def _summary_rows(
        connection: sqlite3.Connection,
        *,
        where_sql: str,
        parameters: tuple[object, ...],
    ) -> list[dict[str, object]]:
        return connection.execute(
            "SELECT thread.*, student.public_id AS student_public_id, "
            "student.name AS student_name, student.surname AS student_surname, "
            "group_lesson.public_id AS group_lesson_public_id, "
            "course.public_id AS course_public_id, course.name AS course_name, "
            "group_row.public_id AS group_public_id, "
            "group_row.public_name AS group_name, "
            "problem.public_id AS problem_public_id, problem.title AS problem_title, "
            "latest_entry.author_kind AS latest_author_kind, "
            "substr(latest_entry.text, 1, 280) AS latest_text_excerpt, "
            "(SELECT count(*) FROM support_entries AS counted_entry "
            "WHERE counted_entry.thread_id = thread.id) AS entry_count "
            "FROM support_threads AS thread "
            "JOIN users AS student ON student.id = thread.student_user_id "
            "LEFT JOIN group_lessons AS group_lesson "
            "ON group_lesson.id = thread.group_lesson_id "
            "LEFT JOIN courses AS course ON course.id = group_lesson.course_id "
            "LEFT JOIN groups AS group_row "
            "ON group_row.course_id = group_lesson.course_id "
            "AND group_row.group_id = group_lesson.group_id "
            "LEFT JOIN problems AS problem ON problem.id = thread.problem_id "
            "JOIN support_entries AS latest_entry ON latest_entry.id = ("
            "SELECT candidate.id FROM support_entries AS candidate "
            "WHERE candidate.thread_id = thread.id "
            "ORDER BY candidate.server_received_at DESC, candidate.id DESC LIMIT 1"
            ") WHERE "
            + (where_sql or "1 = 1")
            + " ORDER BY thread.latest_entry_at DESC, thread.id DESC",
            parameters,
        ).fetchall()

    @staticmethod
    def _summary_page(
        rows: list[dict[str, object]], *, cursor: str | None, page_size: int
    ) -> SupportThreadPage:
        start = 0
        if cursor is not None:
            for index, row in enumerate(rows):
                if row["public_id"] == cursor:
                    start = index + 1
                    break
            else:
                raise SupportNotFound("support list cursor was not found")
        selected = rows[start : start + page_size + 1]
        visible = selected[:page_size]
        items = tuple(_summary_record(row) for row in visible)
        return SupportThreadPage(
            items=items,
            next_cursor=(
                items[-1].thread_public_id
                if len(selected) > page_size and items
                else None
            ),
        )

    @staticmethod
    def _idempotent_entry(
        connection: sqlite3.Connection,
        *,
        actor_user_id: int,
        idempotency_key: str,
        payload_hash: str,
    ) -> int | None:
        row = connection.execute(
            "SELECT thread_id, payload_sha256 FROM support_entries "
            "WHERE author_user_id = ? AND idempotency_key = ?",
            (actor_user_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if row["payload_sha256"] != payload_hash:
            raise SupportIdempotencyConflict(
                "support idempotency key was reused for another payload"
            )
        return int(row["thread_id"])

    def _insert_entry(
        self,
        connection: sqlite3.Connection,
        *,
        thread_id: int,
        author_kind: str,
        author_user_id: int,
        channel: str,
        text: str,
        client_created_at: datetime,
        server_received_at: str,
        idempotency_key: str,
        payload_hash: str,
    ) -> None:
        connection.execute(
            "INSERT INTO support_entries "
            "(thread_id, author_kind, author_user_id, text, channel, "
            "client_created_at, server_received_at, idempotency_key, payload_sha256, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                thread_id,
                author_kind,
                author_user_id,
                text,
                channel,
                _timestamp(client_created_at),
                server_received_at,
                idempotency_key,
                payload_hash,
                server_received_at,
            ),
        )

    @staticmethod
    def _touch_thread(
        connection: sqlite3.Connection, *, thread_id: int, now: str
    ) -> None:
        connection.execute(
            "UPDATE support_threads SET latest_entry_at = ?, updated_at = ?, "
            "version = version + 1 WHERE id = ?",
            (now, now, thread_id),
        )

    @staticmethod
    def _new_public_id(factory: Callable[[], str], label: str) -> str:
        value = factory().strip()
        if _PUBLIC_ID.fullmatch(value) is None:
            raise SupportRepositoryError(
                f"{label} public ID factory returned invalid value"
            )
        return value


__all__ = [
    "AppendStaffSupportEntryCommand",
    "AppendStudentSupportEntryCommand",
    "CreateSupportThreadCommand",
    "PwaSupportThreadRepository",
    "SupportEntryRecord",
    "SupportForbidden",
    "SupportIdempotencyConflict",
    "SupportInvalidationTargets",
    "SupportNotFound",
    "SupportRepositoryError",
    "SupportReplyState",
    "SupportStaffScope",
    "SupportStaffListState",
    "SupportThreadPage",
    "SupportThreadRecord",
    "SupportThreadSummaryRecord",
]
