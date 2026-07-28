"""Lease-safe written review queue primitives for the Staff adapter."""

from __future__ import annotations

import sqlite3
import uuid
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Mapping

from helpers.consts import RES_TYPE, USER_TYPE, VERDICT, VERDICTS_SOLVED, WRITTEN_STATUS

from .connection import PwaConnectionFactory


REVIEW_LEASE_DURATION = timedelta(minutes=30)
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_WRITTEN_REVIEW_VERDICTS = frozenset(range(11, 18))


class ReviewQueueError(RuntimeError):
    """Base class for safe Staff queue failures."""


class ReviewQueueNotFound(ReviewQueueError):
    """The opaque queue identity no longer resolves."""


class ReviewQueueForbidden(ReviewQueueError):
    """The requested logical case is outside the Staff group scope."""


class ReviewLeaseConflict(ReviewQueueError):
    """Another Staff/legacy client currently owns part of the logical case."""


class ReviewLeaseLost(ReviewQueueError):
    """A heartbeat or release no longer owns any current queue rows."""


class ReviewThreadChanged(ReviewQueueError):
    """The reviewed thread/evidence boundary changed after Staff loaded it."""


class ReviewEvidenceUnavailable(ReviewQueueError):
    """A legacy queue branch has no complete modern submission evidence."""


class ReviewIdempotencyConflict(ReviewQueueError):
    """The completion key was reused for a different review payload."""


class ReviewCompletionInvalid(ReviewQueueError):
    """The completion payload violates the written-review policy."""


@dataclass(frozen=True, slots=True)
class ReviewStaffScope:
    """Server-authoritative Staff collection scope expressed in public IDs."""

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
class ReviewLeaseItem:
    queue_public_id: str
    queue_id: int
    student_user_id: int
    student_public_id: str | None
    student_name: str
    problem_id: int
    problem_public_id: str
    problem_title: str
    group_id: str
    group_public_id: str | None
    course_public_id: str | None
    submitted_at: datetime
    lease_version: int


@dataclass(frozen=True, slots=True)
class ReviewEvidenceAttachment:
    attachment_public_id: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class ReviewEvidenceEntry:
    entry_public_id: str
    entry_version: int
    entry_kind: str
    text: str | None
    server_received_at: datetime
    attachments: tuple[ReviewEvidenceAttachment, ...]


@dataclass(frozen=True, slots=True)
class ReviewEvidenceBranch:
    queue_public_id: str
    thread_public_id: str | None
    thread_version: int | None
    entries: tuple[ReviewEvidenceEntry, ...]


@dataclass(frozen=True, slots=True)
class ReviewLease:
    claim_token: str
    teacher_user_id: int
    claimed_at: datetime
    expires_at: datetime
    logical_case_public_id: str
    items: tuple[ReviewLeaseItem, ...]
    evidence_branches: tuple[ReviewEvidenceBranch, ...]


@dataclass(frozen=True, slots=True)
class ReviewEvidenceEntryExpectation:
    entry_public_id: str
    entry_version: int

    def __post_init__(self) -> None:
        if not _PUBLIC_ID.fullmatch(self.entry_public_id):
            raise ValueError("review evidence entry public ID is invalid")
        if type(self.entry_version) is not int or self.entry_version < 1:
            raise ValueError("review evidence entry version must be positive")


@dataclass(frozen=True, slots=True)
class ReviewEvidenceBranchExpectation:
    queue_public_id: str
    lease_version: int
    thread_public_id: str
    thread_version: int
    entries: tuple[ReviewEvidenceEntryExpectation, ...]

    def __post_init__(self) -> None:
        if not _PUBLIC_ID.fullmatch(self.queue_public_id) or not _PUBLIC_ID.fullmatch(
            self.thread_public_id
        ):
            raise ValueError("review branch public ID is invalid")
        if type(self.lease_version) is not int or self.lease_version < 1:
            raise ValueError("review lease version must be positive")
        if type(self.thread_version) is not int or self.thread_version < 1:
            raise ValueError("review thread version must be positive")
        if not self.entries:
            raise ValueError("review branch must contain evidence")
        if len({entry.entry_public_id for entry in self.entries}) != len(self.entries):
            raise ValueError("review evidence entry IDs must be unique per branch")


@dataclass(frozen=True, slots=True)
class CompleteReviewCommand:
    queue_public_id: str
    claim_token: str
    teacher_user_id: int
    scope: ReviewStaffScope
    idempotency_key: str
    verdict: int
    comment: str | None
    confirm_without_comment: bool
    branches: tuple[ReviewEvidenceBranchExpectation, ...]

    def __post_init__(self) -> None:
        if not _PUBLIC_ID.fullmatch(self.queue_public_id):
            raise ValueError("review queue public ID is invalid")
        if not _PUBLIC_ID.fullmatch(self.claim_token):
            raise ValueError("review claim token is invalid")
        if self.teacher_user_id == 0:
            raise ValueError("reviewer user ID must not be zero")
        if not 1 <= len(self.idempotency_key) <= 200 or (
            self.idempotency_key != self.idempotency_key.strip()
        ):
            raise ValueError("review idempotency key must be canonical")
        if self.verdict not in _WRITTEN_REVIEW_VERDICTS:
            raise ValueError("written review verdict is not supported")
        if self.comment is not None and len(self.comment) > 100_000:
            raise ValueError("review comment is too long")
        if self.verdict != int(VERDICT.VERDICT_PLUS) and not (
            (self.comment is not None and self.comment.strip())
            or self.confirm_without_comment
        ):
            raise ReviewCompletionInvalid(
                "a non-accepted verdict without a comment requires confirmation"
            )
        if not self.branches:
            raise ValueError("review completion must contain branches")
        if len({branch.queue_public_id for branch in self.branches}) != len(
            self.branches
        ):
            raise ValueError("review branch queue IDs must be unique")

    def payload(self) -> dict[str, object]:
        return {
            "queueId": self.queue_public_id,
            "claimToken": self.claim_token,
            "verdict": self.verdict,
            "comment": self.comment,
            "confirmWithoutComment": self.confirm_without_comment,
            "branches": [
                {
                    "queueId": branch.queue_public_id,
                    "leaseVersion": branch.lease_version,
                    "threadId": branch.thread_public_id,
                    "threadVersion": branch.thread_version,
                    "evidence": [
                        {
                            "entryId": entry.entry_public_id,
                            "entryVersion": entry.entry_version,
                        }
                        for entry in branch.entries
                    ],
                }
                for branch in self.branches
            ],
        }


@dataclass(frozen=True, slots=True)
class CompleteReviewReceipt:
    review_public_id: str
    target_thread_public_id: str
    target_problem_public_id: str
    target_thread_status: str
    verdict: int
    comment_entry_public_id: str | None
    evidence_entry_public_ids: tuple[str, ...]
    completed_at: datetime
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ReviewQueueLock:
    kind: str
    teacher_user_id: int
    teacher_public_id: str | None
    teacher_name: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewQueueCase:
    queue_public_id: str
    logical_case_public_id: str
    student_public_id: str | None
    student_name: str
    submitted_at: datetime
    items: tuple[ReviewLeaseItem, ...]
    lock: ReviewQueueLock | None


@dataclass(frozen=True, slots=True)
class ReviewQueuePage:
    items: tuple[ReviewQueueCase, ...]
    next_cursor: str | None


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _normalize_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("review queue timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return (
        _normalize_time(value).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _parse_timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReviewQueueError(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReviewQueueError(f"{label} is invalid") from error
    return _normalize_time(parsed)


def _display_name(row: dict[str, object]) -> str:
    parts = [str(row.get("surname") or "").strip(), str(row.get("name") or "").strip()]
    return " ".join(part for part in parts if part) or "Без имени"


def _teacher_display_name(row: dict[str, object]) -> str:
    parts = [
        str(row.get("teacher_surname") or "").strip(),
        str(row.get("teacher_name") or "").strip(),
    ]
    return " ".join(part for part in parts if part) or "Преподаватель"


def _active_pwa_claim(row: dict[str, object], *, now: datetime) -> bool:
    return (
        int(row["cur_status"]) == int(WRITTEN_STATUS.BEING_CHECKED)
        and row["claim_token"] is not None
        and row["lease_expires_at"] is not None
        and _parse_timestamp(row["lease_expires_at"], label="lease expiry") > now
    )


def _active_legacy_claim(row: dict[str, object], *, now: datetime) -> bool:
    if (
        int(row["cur_status"]) != int(WRITTEN_STATUS.BEING_CHECKED)
        or row["claim_token"] is not None
        or row["teacher_id"] is None
        or row["teacher_ts"] is None
    ):
        return False
    claimed_at = _parse_timestamp(row["teacher_ts"], label="legacy claim time")
    return claimed_at + REVIEW_LEASE_DURATION > now


def _case_rows(
    connection: sqlite3.Connection, *, queue_public_id: str
) -> tuple[str, list[dict[str, object]]]:
    chosen = connection.execute(
        "SELECT queue.id, queue.student_id, problem.public_id AS problem_public_id, "
        "synonym.id AS synonym_group_id, synonym.public_id AS synonym_public_id "
        "FROM written_tasks_queue AS queue "
        "JOIN problems AS problem ON problem.id = queue.problem_id "
        "LEFT JOIN problem_synonym_members AS member "
        "ON member.problem_id = problem.id AND member.removed_at IS NULL "
        "LEFT JOIN problem_synonym_groups AS synonym "
        "ON synonym.id = member.synonym_group_id AND synonym.status = 'active' "
        "WHERE queue.public_id = ? AND queue.problem_id > 0",
        (queue_public_id,),
    ).fetchone()
    if chosen is None:
        raise ReviewQueueNotFound("review queue item was not found")

    base_sql = (
        "SELECT queue.*, problem.public_id AS problem_public_id, "
        "problem.title AS problem_title, problem.group_id, "
        "student.public_id AS student_public_id, student.name, student.surname, "
        "groups.public_id AS group_public_id, course.public_id AS course_public_id "
        "FROM written_tasks_queue AS queue "
        "JOIN problems AS problem ON problem.id = queue.problem_id "
        "JOIN users AS student ON student.id = queue.student_id "
        "LEFT JOIN groups ON groups.group_id = problem.group_id "
        "LEFT JOIN courses AS course ON course.id = groups.course_id "
    )
    synonym_group_id = chosen["synonym_group_id"]
    if synonym_group_id is None:
        rows = connection.execute(
            base_sql + "WHERE queue.id = ? ORDER BY queue.ts, queue.id",
            (chosen["id"],),
        ).fetchall()
        logical_case_public_id = str(chosen["problem_public_id"])
    else:
        rows = connection.execute(
            base_sql + "JOIN problem_synonym_members AS peer "
            "ON peer.problem_id = problem.id AND peer.removed_at IS NULL "
            "WHERE queue.student_id = ? AND peer.synonym_group_id = ? "
            "AND queue.problem_id > 0 ORDER BY queue.ts, queue.id",
            (chosen["student_id"], synonym_group_id),
        ).fetchall()
        logical_case_public_id = str(chosen["synonym_public_id"])
    if not rows:  # pragma: no cover - chosen row is part of its own case
        raise ReviewQueueNotFound("review logical case became empty")
    return logical_case_public_id, list(rows)


_QUEUE_ROW_SELECT = (
    "SELECT queue.*, problem.public_id AS problem_public_id, "
    "problem.title AS problem_title, problem.group_id, "
    "student.public_id AS student_public_id, student.name, student.surname, "
    "groups.public_id AS group_public_id, course.public_id AS course_public_id, "
    "synonym.id AS synonym_group_id, synonym.public_id AS synonym_public_id, "
    "teacher.public_id AS teacher_public_id, teacher.name AS teacher_name, "
    "teacher.surname AS teacher_surname "
    "FROM written_tasks_queue AS queue "
    "JOIN problems AS problem ON problem.id = queue.problem_id "
    "JOIN users AS student ON student.id = queue.student_id "
    "LEFT JOIN groups ON groups.group_id = problem.group_id "
    "LEFT JOIN courses AS course ON course.id = groups.course_id "
    "LEFT JOIN problem_synonym_members AS member "
    "ON member.problem_id = problem.id AND member.removed_at IS NULL "
    "LEFT JOIN problem_synonym_groups AS synonym "
    "ON synonym.id = member.synonym_group_id AND synonym.status = 'active' "
    "LEFT JOIN users AS teacher ON teacher.id = queue.teacher_id "
    "WHERE queue.problem_id > 0 ORDER BY queue.ts, queue.id"
)


def _logical_case_key(row: dict[str, object]) -> tuple[int, str, int]:
    synonym_group_id = row["synonym_group_id"]
    return (
        int(row["student_id"]),
        "synonym" if synonym_group_id is not None else "problem",
        int(synonym_group_id if synonym_group_id is not None else row["problem_id"]),
    )


def _queue_lock(
    rows: list[dict[str, object]], *, now: datetime
) -> ReviewQueueLock | None:
    active_pwa = [row for row in rows if _active_pwa_claim(row, now=now)]
    active_legacy = [row for row in rows if _active_legacy_claim(row, now=now)]
    active = active_pwa or active_legacy
    if not active:
        return None
    first = active[0]
    teacher_id = int(first["teacher_id"])
    if any(int(row["teacher_id"]) != teacher_id for row in active):
        raise ReviewLeaseConflict("logical case has inconsistent active owners")
    if active_pwa:
        tokens = {str(row["claim_token"]) for row in active_pwa}
        if len(tokens) != 1:
            raise ReviewLeaseConflict("logical case has inconsistent active leases")
        expires_at = min(
            _parse_timestamp(row["lease_expires_at"], label="lease expiry")
            for row in active_pwa
        )
        kind = "pwa"
    else:
        expires_at = min(
            _parse_timestamp(row["teacher_ts"], label="legacy claim time")
            + REVIEW_LEASE_DURATION
            for row in active_legacy
        )
        kind = "legacy"
    return ReviewQueueLock(
        kind=kind,
        teacher_user_id=teacher_id,
        teacher_public_id=(
            None
            if first["teacher_public_id"] is None
            else str(first["teacher_public_id"])
        ),
        teacher_name=_teacher_display_name(first),
        expires_at=expires_at,
    )


def _evidence_branches(
    connection: sqlite3.Connection, rows: list[dict[str, object]]
) -> tuple[ReviewEvidenceBranch, ...]:
    branches: list[ReviewEvidenceBranch] = []
    for queue_row in rows:
        thread = connection.execute(
            "SELECT id, public_id, version FROM submission_threads "
            "WHERE student_user_id = ? AND problem_id = ? AND status <> 'closed' "
            "ORDER BY id DESC LIMIT 1",
            (queue_row["student_id"], queue_row["problem_id"]),
        ).fetchone()
        if thread is None:
            branches.append(
                ReviewEvidenceBranch(
                    queue_public_id=str(queue_row["public_id"]),
                    thread_public_id=None,
                    thread_version=None,
                    entries=(),
                )
            )
            continue
        entry_rows = connection.execute(
            "SELECT entry.id, entry.public_id, entry.version, entry.entry_kind, "
            "entry.text, entry.server_received_at FROM submission_entries AS entry "
            "WHERE entry.thread_id = ? AND entry.author_kind = 'student' "
            "AND entry.state = 'submitted' AND NOT EXISTS ("
            "SELECT 1 FROM submission_review_evidence_entries AS evidence "
            "WHERE evidence.entry_id = entry.id"
            ") ORDER BY entry.server_received_at, entry.id",
            (thread["id"],),
        ).fetchall()
        entries: list[ReviewEvidenceEntry] = []
        for entry in entry_rows:
            attachment_rows = connection.execute(
                "SELECT public_id, ordinal FROM submission_attachments "
                "WHERE entry_id = ? AND upload_status = 'stored' "
                "ORDER BY ordinal, id",
                (entry["id"],),
            ).fetchall()
            entries.append(
                ReviewEvidenceEntry(
                    entry_public_id=str(entry["public_id"]),
                    entry_version=int(entry["version"]),
                    entry_kind=str(entry["entry_kind"]),
                    text=None if entry["text"] is None else str(entry["text"]),
                    server_received_at=_parse_timestamp(
                        entry["server_received_at"], label="evidence receive time"
                    ),
                    attachments=tuple(
                        ReviewEvidenceAttachment(
                            attachment_public_id=str(attachment["public_id"]),
                            ordinal=int(attachment["ordinal"]),
                        )
                        for attachment in attachment_rows
                    ),
                )
            )
        branches.append(
            ReviewEvidenceBranch(
                queue_public_id=str(queue_row["public_id"]),
                thread_public_id=str(thread["public_id"]),
                thread_version=int(thread["version"]),
                entries=tuple(entries),
            )
        )
    return tuple(branches)


def _lease_from_rows(
    connection: sqlite3.Connection,
    rows: list[dict[str, object]],
    *,
    logical_case_public_id: str,
) -> ReviewLease:
    first = rows[0]
    claim_token = str(first["claim_token"])
    teacher_user_id = int(first["teacher_id"])
    claimed_at = min(
        _parse_timestamp(row["claimed_at"], label="claim time") for row in rows
    )
    expires_at = min(
        _parse_timestamp(row["lease_expires_at"], label="lease expiry") for row in rows
    )
    if any(
        row["claim_token"] != claim_token or int(row["teacher_id"]) != teacher_user_id
        for row in rows
    ):
        raise ReviewLeaseConflict("logical case has inconsistent active leases")
    items = tuple(
        ReviewLeaseItem(
            queue_public_id=str(row["public_id"]),
            queue_id=int(row["id"]),
            student_user_id=int(row["student_id"]),
            student_public_id=(
                None
                if row["student_public_id"] is None
                else str(row["student_public_id"])
            ),
            student_name=_display_name(row),
            problem_id=int(row["problem_id"]),
            problem_public_id=str(row["problem_public_id"]),
            problem_title=str(row["problem_title"]),
            group_id=str(row["group_id"]),
            group_public_id=(
                None if row["group_public_id"] is None else str(row["group_public_id"])
            ),
            course_public_id=(
                None
                if row["course_public_id"] is None
                else str(row["course_public_id"])
            ),
            submitted_at=_parse_timestamp(row["ts"], label="submission time"),
            lease_version=int(row["lease_version"]),
        )
        for row in rows
    )
    return ReviewLease(
        claim_token=claim_token,
        teacher_user_id=teacher_user_id,
        claimed_at=claimed_at,
        expires_at=expires_at,
        logical_case_public_id=logical_case_public_id,
        items=items,
        evidence_branches=_evidence_branches(connection, rows),
    )


class PwaWrittenReviewQueueRepository:
    """Claim/heartbeat/release one Student + synonym-group logical case."""

    def __init__(
        self,
        connection_factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] = _utc_now,
        claim_token_factory: Callable[[], str] = lambda: f"review-claim-{uuid.uuid4()}",
        review_public_id_factory: Callable[[], str] = lambda: f"review-{uuid.uuid4()}",
        comment_public_id_factory: Callable[[], str] = lambda: f"entry-{uuid.uuid4()}",
        event_public_id_factory: Callable[[], str] = lambda: (
            f"review-event-{uuid.uuid4()}"
        ),
    ) -> None:
        self._factory = connection_factory
        self._clock = clock
        self._claim_token_factory = claim_token_factory
        self._review_public_id_factory = review_public_id_factory
        self._comment_public_id_factory = comment_public_id_factory
        self._event_public_id_factory = event_public_id_factory

    async def claim(
        self,
        *,
        queue_public_id: str,
        teacher_user_id: int,
        scope: ReviewStaffScope,
    ) -> ReviewLease:
        if not queue_public_id.strip():
            raise ValueError("queue_public_id must not be empty")
        if teacher_user_id == 0:
            raise ValueError("teacher_user_id must not be zero")
        now = _normalize_time(self._clock())
        expires_at = now + REVIEW_LEASE_DURATION

        def operation(connection: sqlite3.Connection) -> ReviewLease:
            logical_case_public_id, rows = _case_rows(
                connection, queue_public_id=queue_public_id
            )
            if any(not scope.allows(row) for row in rows):
                raise ReviewQueueForbidden("review case is outside Staff scope")
            if any(_active_legacy_claim(row, now=now) for row in rows):
                raise ReviewLeaseConflict("review case is active in legacy Telegram")
            active_rows = [row for row in rows if _active_pwa_claim(row, now=now)]
            if any(int(row["teacher_id"]) != teacher_user_id for row in active_rows):
                raise ReviewLeaseConflict("review case is already claimed")
            active_tokens = {str(row["claim_token"]) for row in active_rows}
            if len(active_tokens) > 1:
                raise ReviewLeaseConflict(
                    "review case has multiple active claim tokens"
                )

            claim_token = (
                next(iter(active_tokens))
                if active_tokens
                else self._claim_token_factory().strip()
            )
            if not claim_token:
                raise ValueError("claim token factory returned an empty token")
            now_text = _timestamp(now)
            expiry_text = _timestamp(expires_at)
            row_ids = [int(row["id"]) for row in rows]
            placeholders = ",".join("?" for _ in row_ids)
            connection.execute(
                "UPDATE written_tasks_queue SET cur_status = ?, teacher_ts = ?, "
                "teacher_id = ?, claim_token = ?, "
                "claimed_at = CASE WHEN claim_token = ? AND claimed_at IS NOT NULL "
                "THEN claimed_at ELSE ? END, lease_expires_at = ?, "
                "lease_version = lease_version + 1, updated_at = ? "
                f"WHERE id IN ({placeholders})",
                (
                    int(WRITTEN_STATUS.BEING_CHECKED),
                    now_text,
                    teacher_user_id,
                    claim_token,
                    claim_token,
                    now_text,
                    expiry_text,
                    now_text,
                    *row_ids,
                ),
            )
            refreshed = connection.execute(
                "SELECT queue.*, problem.public_id AS problem_public_id, "
                "problem.title AS problem_title, problem.group_id, "
                "student.public_id AS student_public_id, student.name, student.surname, "
                "groups.public_id AS group_public_id, course.public_id AS course_public_id "
                "FROM written_tasks_queue AS queue "
                "JOIN problems AS problem ON problem.id = queue.problem_id "
                "JOIN users AS student ON student.id = queue.student_id "
                "LEFT JOIN groups ON groups.group_id = problem.group_id "
                "LEFT JOIN courses AS course ON course.id = groups.course_id "
                f"WHERE queue.id IN ({placeholders}) ORDER BY queue.ts, queue.id",
                row_ids,
            ).fetchall()
            return _lease_from_rows(
                connection,
                list(refreshed),
                logical_case_public_id=logical_case_public_id,
            )

        return await self._factory.run_write_async(operation)

    async def list_cases(
        self,
        *,
        scope: ReviewStaffScope,
        problem_group_public_id: str | None = None,
        cursor: str | None = None,
        newest_first: bool = False,
        page_size: int = 50,
    ) -> ReviewQueuePage:
        """Return complete logical cases only; never leak an out-of-scope branch."""

        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        now = _normalize_time(self._clock())

        def operation(connection: sqlite3.Connection) -> ReviewQueuePage:
            grouped: dict[tuple[int, str, int], list[dict[str, object]]] = {}
            for row in connection.execute(_QUEUE_ROW_SELECT).fetchall():
                grouped.setdefault(_logical_case_key(row), []).append(row)

            cases: list[ReviewQueueCase] = []
            for rows in grouped.values():
                if any(not scope.allows(row) for row in rows):
                    continue
                logical_case_public_id = str(
                    rows[0]["synonym_public_id"] or rows[0]["problem_public_id"]
                )
                if (
                    problem_group_public_id is not None
                    and logical_case_public_id != problem_group_public_id
                ):
                    continue
                lease_items = tuple(
                    ReviewLeaseItem(
                        queue_public_id=str(row["public_id"]),
                        queue_id=int(row["id"]),
                        student_user_id=int(row["student_id"]),
                        student_public_id=(
                            None
                            if row["student_public_id"] is None
                            else str(row["student_public_id"])
                        ),
                        student_name=_display_name(row),
                        problem_id=int(row["problem_id"]),
                        problem_public_id=str(row["problem_public_id"]),
                        problem_title=str(row["problem_title"]),
                        group_id=str(row["group_id"]),
                        group_public_id=(
                            None
                            if row["group_public_id"] is None
                            else str(row["group_public_id"])
                        ),
                        course_public_id=(
                            None
                            if row["course_public_id"] is None
                            else str(row["course_public_id"])
                        ),
                        submitted_at=_parse_timestamp(
                            row["ts"], label="submission time"
                        ),
                        lease_version=int(row["lease_version"]),
                    )
                    for row in rows
                )
                cases.append(
                    ReviewQueueCase(
                        queue_public_id=lease_items[0].queue_public_id,
                        logical_case_public_id=logical_case_public_id,
                        student_public_id=lease_items[0].student_public_id,
                        student_name=lease_items[0].student_name,
                        submitted_at=lease_items[0].submitted_at,
                        items=lease_items,
                        lock=_queue_lock(rows, now=now),
                    )
                )
            cases.sort(
                key=lambda case: (case.submitted_at, case.queue_public_id),
                reverse=newest_first,
            )
            if cursor is not None:
                for index, case in enumerate(cases):
                    if case.queue_public_id == cursor:
                        cases = cases[index + 1 :]
                        break
                else:
                    raise ReviewQueueNotFound("review queue cursor was not found")
            page = cases[: page_size + 1]
            next_cursor = (
                page[page_size - 1].queue_public_id if len(page) > page_size else None
            )
            return ReviewQueuePage(
                items=tuple(page[:page_size]), next_cursor=next_cursor
            )

        return await self._factory.run_read_async(operation)

    async def heartbeat(
        self,
        *,
        queue_public_id: str,
        claim_token: str,
        teacher_user_id: int,
        scope: ReviewStaffScope,
    ) -> ReviewLease:
        token = claim_token.strip()
        if not token:
            raise ValueError("claim_token must not be empty")
        now = _normalize_time(self._clock())
        expires_at = now + REVIEW_LEASE_DURATION

        def operation(connection: sqlite3.Connection) -> ReviewLease:
            rows = connection.execute(
                "SELECT queue.*, problem.public_id AS problem_public_id, "
                "problem.title AS problem_title, problem.group_id, "
                "student.public_id AS student_public_id, student.name, student.surname, "
                "groups.public_id AS group_public_id, course.public_id AS course_public_id, "
                "synonym.public_id AS synonym_public_id "
                "FROM written_tasks_queue AS queue "
                "JOIN problems AS problem ON problem.id = queue.problem_id "
                "JOIN users AS student ON student.id = queue.student_id "
                "LEFT JOIN groups ON groups.group_id = problem.group_id "
                "LEFT JOIN courses AS course ON course.id = groups.course_id "
                "LEFT JOIN problem_synonym_members AS member "
                "ON member.problem_id = problem.id AND member.removed_at IS NULL "
                "LEFT JOIN problem_synonym_groups AS synonym "
                "ON synonym.id = member.synonym_group_id AND synonym.status = 'active' "
                "WHERE queue.claim_token = ? AND queue.teacher_id = ? "
                "AND queue.cur_status = ? ORDER BY queue.ts, queue.id",
                (token, teacher_user_id, int(WRITTEN_STATUS.BEING_CHECKED)),
            ).fetchall()
            if not rows or any(not _active_pwa_claim(row, now=now) for row in rows):
                raise ReviewLeaseLost("review lease expired or was released")
            if not any(str(row["public_id"]) == queue_public_id for row in rows):
                raise ReviewLeaseLost("review lease does not own this queue item")
            if any(not scope.allows(row) for row in rows):
                raise ReviewQueueForbidden("review case is outside Staff scope")
            now_text = _timestamp(now)
            connection.execute(
                "UPDATE written_tasks_queue SET teacher_ts = ?, lease_expires_at = ?, "
                "lease_version = lease_version + 1, updated_at = ? "
                "WHERE claim_token = ? AND teacher_id = ? AND cur_status = ?",
                (
                    now_text,
                    _timestamp(expires_at),
                    now_text,
                    token,
                    teacher_user_id,
                    int(WRITTEN_STATUS.BEING_CHECKED),
                ),
            )
            refreshed = connection.execute(
                "SELECT queue.*, problem.public_id AS problem_public_id, "
                "problem.title AS problem_title, problem.group_id, "
                "student.public_id AS student_public_id, student.name, student.surname, "
                "groups.public_id AS group_public_id, course.public_id AS course_public_id, "
                "synonym.public_id AS synonym_public_id "
                "FROM written_tasks_queue AS queue "
                "JOIN problems AS problem ON problem.id = queue.problem_id "
                "JOIN users AS student ON student.id = queue.student_id "
                "LEFT JOIN groups ON groups.group_id = problem.group_id "
                "LEFT JOIN courses AS course ON course.id = groups.course_id "
                "LEFT JOIN problem_synonym_members AS member "
                "ON member.problem_id = problem.id AND member.removed_at IS NULL "
                "LEFT JOIN problem_synonym_groups AS synonym "
                "ON synonym.id = member.synonym_group_id AND synonym.status = 'active' "
                "WHERE queue.claim_token = ? AND queue.teacher_id = ? "
                "ORDER BY queue.ts, queue.id",
                (token, teacher_user_id),
            ).fetchall()
            logical_case_public_id = str(
                refreshed[0]["synonym_public_id"] or refreshed[0]["problem_public_id"]
            )
            return _lease_from_rows(
                connection,
                list(refreshed),
                logical_case_public_id=logical_case_public_id,
            )

        return await self._factory.run_write_async(operation)

    async def complete(self, command: CompleteReviewCommand) -> CompleteReviewReceipt:
        """Atomically persist one review and freeze every current case entry."""

        now = _normalize_time(self._clock())
        completed_at = _timestamp(now)
        payload_sha256 = _payload_hash(command.payload())

        def receipt_from_row(
            connection: sqlite3.Connection,
            row: dict[str, object],
            *,
            replayed: bool,
        ) -> CompleteReviewReceipt:
            evidence = connection.execute(
                "SELECT entry.public_id FROM submission_review_evidence_entries AS evidence "
                "JOIN submission_entries AS entry ON entry.id = evidence.entry_id "
                "WHERE evidence.review_id = ? "
                "ORDER BY evidence.server_received_at, evidence.entry_id",
                (row["id"],),
            ).fetchall()
            return CompleteReviewReceipt(
                review_public_id=str(row["public_id"]),
                target_thread_public_id=str(row["thread_public_id"]),
                target_problem_public_id=str(row["problem_public_id"]),
                target_thread_status=(
                    "accepted"
                    if VERDICT(int(row["verdict"])) in VERDICTS_SOLVED
                    else "needs_work"
                ),
                verdict=int(row["verdict"]),
                comment_entry_public_id=(
                    None
                    if row["comment_public_id"] is None
                    else str(row["comment_public_id"])
                ),
                evidence_entry_public_ids=tuple(
                    str(item["public_id"]) for item in evidence
                ),
                completed_at=_parse_timestamp(row["created_at"], label="review time"),
                replayed=replayed,
            )

        def operation(connection: sqlite3.Connection) -> CompleteReviewReceipt:
            replay = connection.execute(
                "SELECT review.*, thread.public_id AS thread_public_id, "
                "problem.public_id AS problem_public_id, "
                "comment.public_id AS comment_public_id "
                "FROM submission_reviews AS review "
                "JOIN submission_threads AS thread ON thread.id = review.thread_id "
                "JOIN problems AS problem ON problem.id = thread.problem_id "
                "LEFT JOIN submission_entries AS comment "
                "ON comment.id = review.comment_entry_id "
                "WHERE review.reviewer_user_id = ? AND review.idempotency_key = ?",
                (command.teacher_user_id, command.idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["payload_sha256"] != payload_sha256:
                    raise ReviewIdempotencyConflict(
                        "review completion key was reused with another payload"
                    )
                replay_scopes = connection.execute(
                    "SELECT groups.public_id AS group_public_id, "
                    "course.public_id AS course_public_id "
                    "FROM submission_review_evidence_entries AS evidence "
                    "JOIN problems AS problem ON problem.id = evidence.problem_id "
                    "LEFT JOIN groups ON groups.group_id = problem.group_id "
                    "LEFT JOIN courses AS course ON course.id = groups.course_id "
                    "WHERE evidence.review_id = ?",
                    (replay["id"],),
                ).fetchall()
                if any(not command.scope.allows(row) for row in replay_scopes):
                    raise ReviewQueueForbidden("review is outside current Staff scope")
                return receipt_from_row(connection, replay, replayed=True)

            _logical_case_public_id, queue_rows = _case_rows(
                connection, queue_public_id=command.queue_public_id
            )
            if any(not command.scope.allows(row) for row in queue_rows):
                raise ReviewQueueForbidden("review case is outside Staff scope")
            if any(
                not _active_pwa_claim(row, now=now)
                or row["claim_token"] != command.claim_token
                or int(row["teacher_id"]) != command.teacher_user_id
                for row in queue_rows
            ):
                raise ReviewLeaseLost("review lease expired or changed owner")

            actual_branches = _evidence_branches(connection, queue_rows)
            if any(
                branch.thread_public_id is None or not branch.entries
                for branch in actual_branches
            ):
                raise ReviewEvidenceUnavailable(
                    "review case contains a branch without modern evidence"
                )
            expected_by_queue = {
                branch.queue_public_id: branch for branch in command.branches
            }
            if set(expected_by_queue) != {str(row["public_id"]) for row in queue_rows}:
                raise ReviewThreadChanged("review queue branches changed")
            actual_by_queue = {
                branch.queue_public_id: branch for branch in actual_branches
            }
            queue_by_public_id = {str(row["public_id"]): row for row in queue_rows}
            for queue_public_id, expected in expected_by_queue.items():
                actual = actual_by_queue[queue_public_id]
                queue_row = queue_by_public_id[queue_public_id]
                actual_entries = tuple(
                    (entry.entry_public_id, entry.entry_version)
                    for entry in actual.entries
                )
                expected_entries = tuple(
                    (entry.entry_public_id, entry.entry_version)
                    for entry in expected.entries
                )
                if (
                    expected.lease_version != int(queue_row["lease_version"])
                    or expected.thread_public_id != actual.thread_public_id
                    or expected.thread_version != actual.thread_version
                    or expected_entries != actual_entries
                ):
                    raise ReviewThreadChanged("review evidence changed")

            evidence_rows: list[dict[str, object]] = []
            thread_rows: dict[int, dict[str, object]] = {}
            for branch in actual_branches:
                thread = connection.execute(
                    "SELECT * FROM submission_threads WHERE public_id = ?",
                    (branch.thread_public_id,),
                ).fetchone()
                if thread is None or thread["status"] != "awaiting_review":
                    raise ReviewThreadChanged("review thread is no longer waiting")
                thread_rows[int(thread["id"])] = thread
                for entry in branch.entries:
                    stored = connection.execute(
                        "SELECT entry.*, thread.problem_id, problem.public_id AS problem_public_id "
                        "FROM submission_entries AS entry "
                        "JOIN submission_threads AS thread ON thread.id = entry.thread_id "
                        "JOIN problems AS problem ON problem.id = thread.problem_id "
                        "WHERE entry.public_id = ? AND entry.thread_id = ? "
                        "AND entry.state = 'submitted'",
                        (entry.entry_public_id, thread["id"]),
                    ).fetchone()
                    if stored is None:
                        raise ReviewThreadChanged("review evidence disappeared")
                    evidence_rows.append(stored)

            target_entry = max(
                evidence_rows,
                key=lambda row: (
                    _parse_timestamp(row["server_received_at"], label="evidence time"),
                    int(row["id"]),
                ),
            )
            target_thread = thread_rows[int(target_entry["thread_id"])]
            target_problem = connection.execute(
                "SELECT id, public_id, lesson, group_id FROM problems WHERE id = ?",
                (target_entry["problem_id"],),
            ).fetchone()
            if target_problem is None:  # pragma: no cover - protected by FK
                raise ReviewEvidenceUnavailable("target problem disappeared")

            teacher = connection.execute(
                "SELECT type FROM users WHERE id = ?", (command.teacher_user_id,)
            ).fetchone()
            if teacher is None:
                raise ReviewQueueForbidden("reviewer user no longer exists")
            author_kind = (
                "admin" if int(teacher["type"]) & int(USER_TYPE.ADMIN) else "teacher"
            )
            comment_text = (
                None
                if command.comment is None or not command.comment.strip()
                else command.comment.strip()
            )

            if VERDICT(command.verdict) not in VERDICTS_SOLVED:
                connection.execute(
                    "UPDATE results SET verdict = ? WHERE student_id = ? "
                    "AND problem_id = ? AND res_type = ? AND verdict > 0",
                    (
                        int(VERDICT.REJECTED_ANSWER),
                        target_thread["student_user_id"],
                        target_problem["id"],
                        int(RES_TYPE.WRITTEN),
                    ),
                )
            result_id = int(
                connection.execute(
                    "INSERT INTO results "
                    "(student_id, problem_id, group_id, lesson, teacher_id, ts, "
                    "verdict, answer, res_type) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?) "
                    "RETURNING id",
                    (
                        target_thread["student_user_id"],
                        target_problem["id"],
                        target_problem["group_id"],
                        target_problem["lesson"],
                        command.teacher_user_id,
                        completed_at,
                        command.verdict,
                        int(RES_TYPE.WRITTEN),
                    ),
                ).fetchone()["id"]
            )

            comment_entry_id: int | None = None
            comment_public_id: str | None = None
            if comment_text is not None:
                comment_public_id = self._comment_public_id_factory().strip()
                if not _PUBLIC_ID.fullmatch(comment_public_id):
                    raise ValueError(
                        "comment public ID factory returned an invalid value"
                    )
                comment_entry_id = int(
                    connection.execute(
                        "INSERT INTO submission_entries "
                        "(public_id, thread_id, author_kind, author_user_id, channel, "
                        "entry_kind, state, text, server_received_at, version, locked_at) "
                        "VALUES (?, ?, ?, ?, 'staff', 'teacher_comment', 'locked', ?, ?, 1, ?) "
                        "RETURNING id",
                        (
                            comment_public_id,
                            target_thread["id"],
                            author_kind,
                            command.teacher_user_id,
                            comment_text,
                            completed_at,
                            completed_at,
                        ),
                    ).fetchone()["id"]
                )

            review_public_id = self._review_public_id_factory().strip()
            event_public_id = self._event_public_id_factory().strip()
            if not _PUBLIC_ID.fullmatch(review_public_id) or not _PUBLIC_ID.fullmatch(
                event_public_id
            ):
                raise ValueError("review public ID factory returned an invalid value")
            anchor_queue = next(
                row
                for row in queue_rows
                if str(row["public_id"]) == command.queue_public_id
            )
            review_id = int(
                connection.execute(
                    "INSERT INTO submission_reviews "
                    "(public_id, thread_id, queue_id, queue_public_id, reviewer_user_id, "
                    "evidence_through_entry_id, expected_thread_version, verdict, "
                    "comment_entry_id, result_id, source, idempotency_key, payload_sha256, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'staff', ?, ?, ?) "
                    "RETURNING id",
                    (
                        review_public_id,
                        target_thread["id"],
                        anchor_queue["id"],
                        anchor_queue["public_id"],
                        command.teacher_user_id,
                        target_entry["id"],
                        target_thread["version"],
                        command.verdict,
                        comment_entry_id,
                        result_id,
                        command.idempotency_key,
                        payload_sha256,
                        completed_at,
                    ),
                ).fetchone()["id"]
            )

            evidence_public_ids: list[str] = []
            for entry in sorted(
                evidence_rows,
                key=lambda row: (str(row["server_received_at"]), int(row["id"])),
            ):
                connection.execute(
                    "INSERT INTO submission_review_evidence_entries "
                    "(review_id, entry_id, thread_id, problem_id, entry_version, "
                    "server_received_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        review_id,
                        entry["id"],
                        entry["thread_id"],
                        entry["problem_id"],
                        entry["version"],
                        entry["server_received_at"],
                    ),
                )
                evidence_public_ids.append(str(entry["public_id"]))
                attachments = connection.execute(
                    "SELECT id, entry_id, asset_id, ordinal FROM submission_attachments "
                    "WHERE entry_id = ? AND upload_status = 'stored' "
                    "ORDER BY ordinal, id",
                    (entry["id"],),
                ).fetchall()
                for attachment in attachments:
                    connection.execute(
                        "INSERT INTO submission_review_evidence_attachments "
                        "(review_id, attachment_id, entry_id, asset_id, ordinal) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            review_id,
                            attachment["id"],
                            attachment["entry_id"],
                            attachment["asset_id"],
                            attachment["ordinal"],
                        ),
                    )

            target_status = (
                "accepted"
                if VERDICT(command.verdict) in VERDICTS_SOLVED
                else "needs_work"
            )
            for thread_id, thread in thread_rows.items():
                is_target = thread_id == int(target_thread["id"])
                connection.execute(
                    "UPDATE submission_threads SET status = ?, latest_result_id = ?, "
                    "latest_entry_at = ?, updated_at = ?, version = ? WHERE id = ?",
                    (
                        target_status if is_target else "closed",
                        result_id if is_target else None,
                        completed_at
                        if is_target and comment_entry_id is not None
                        else thread["latest_entry_at"],
                        completed_at,
                        int(thread["version"]) + 1,
                        thread_id,
                    ),
                )

            queue_ids = [int(row["id"]) for row in queue_rows]
            placeholders = ",".join("?" for _ in queue_ids)
            connection.execute(
                f"DELETE FROM written_tasks_queue WHERE id IN ({placeholders})",
                queue_ids,
            )
            connection.execute(
                "INSERT INTO submission_review_events "
                "(public_id, review_id, event_kind, payload_json, created_at) "
                "VALUES (?, ?, 'completed', ?, ?)",
                (
                    event_public_id,
                    review_id,
                    _canonical_json(
                        {
                            "reviewPublicId": review_public_id,
                            "studentUserId": target_thread["student_user_id"],
                            "targetProblemId": target_problem["id"],
                            "evidenceEntryIds": evidence_public_ids,
                        }
                    ),
                    completed_at,
                ),
            )
            return CompleteReviewReceipt(
                review_public_id=review_public_id,
                target_thread_public_id=str(target_thread["public_id"]),
                target_problem_public_id=str(target_problem["public_id"]),
                target_thread_status=target_status,
                verdict=command.verdict,
                comment_entry_public_id=comment_public_id,
                evidence_entry_public_ids=tuple(evidence_public_ids),
                completed_at=now,
            )

        return await self._factory.run_write_async(operation)

    async def release(
        self,
        *,
        queue_public_id: str,
        claim_token: str,
        teacher_user_id: int,
        scope: ReviewStaffScope,
    ) -> int:
        token = claim_token.strip()
        if not token:
            raise ValueError("claim_token must not be empty")
        now_text = _timestamp(_normalize_time(self._clock()))

        def operation(connection: sqlite3.Connection) -> int:
            _logical_case_public_id, rows = _case_rows(
                connection, queue_public_id=queue_public_id
            )
            owned_rows = [
                row
                for row in rows
                if row["claim_token"] == token
                and row["teacher_id"] == teacher_user_id
                and int(row["cur_status"]) == int(WRITTEN_STATUS.BEING_CHECKED)
            ]
            if not owned_rows or len(owned_rows) != len(rows):
                raise ReviewLeaseLost("review lease was already released")
            if any(not scope.allows(row) for row in rows):
                raise ReviewQueueForbidden("review case is outside Staff scope")
            cursor = connection.execute(
                "UPDATE written_tasks_queue SET cur_status = ?, teacher_ts = NULL, "
                "teacher_id = NULL, claim_token = NULL, claimed_at = NULL, "
                "lease_expires_at = NULL, lease_version = lease_version + 1, "
                "updated_at = ? WHERE claim_token = ? AND teacher_id = ? "
                "AND cur_status = ?",
                (
                    int(WRITTEN_STATUS.NEW),
                    now_text,
                    token,
                    teacher_user_id,
                    int(WRITTEN_STATUS.BEING_CHECKED),
                ),
            )
            if cursor.rowcount == 0:
                raise ReviewLeaseLost("review lease was already released")
            return int(cursor.rowcount)

        return await self._factory.run_write_async(operation)


__all__ = [
    "CompleteReviewCommand",
    "CompleteReviewReceipt",
    "PwaWrittenReviewQueueRepository",
    "REVIEW_LEASE_DURATION",
    "ReviewLease",
    "ReviewLeaseConflict",
    "ReviewLeaseItem",
    "ReviewLeaseLost",
    "ReviewCompletionInvalid",
    "ReviewEvidenceAttachment",
    "ReviewEvidenceBranch",
    "ReviewEvidenceBranchExpectation",
    "ReviewEvidenceEntry",
    "ReviewEvidenceEntryExpectation",
    "ReviewEvidenceUnavailable",
    "ReviewIdempotencyConflict",
    "ReviewQueueCase",
    "ReviewQueueError",
    "ReviewQueueForbidden",
    "ReviewQueueLock",
    "ReviewQueueNotFound",
    "ReviewQueuePage",
    "ReviewStaffScope",
    "ReviewThreadChanged",
]
