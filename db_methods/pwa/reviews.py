"""Lease-safe written review queue primitives for the Staff adapter."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from helpers.consts import WRITTEN_STATUS

from .connection import PwaConnectionFactory


REVIEW_LEASE_DURATION = timedelta(minutes=30)


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
class ReviewLease:
    claim_token: str
    teacher_user_id: int
    claimed_at: datetime
    expires_at: datetime
    logical_case_public_id: str
    items: tuple[ReviewLeaseItem, ...]


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


def _lease_from_rows(
    rows: list[dict[str, object]], *, logical_case_public_id: str
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
    )


class PwaWrittenReviewQueueRepository:
    """Claim/heartbeat/release one Student + synonym-group logical case."""

    def __init__(
        self,
        connection_factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] = _utc_now,
        claim_token_factory: Callable[[], str] = lambda: f"review-claim-{uuid.uuid4()}",
    ) -> None:
        self._factory = connection_factory
        self._clock = clock
        self._claim_token_factory = claim_token_factory

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
                list(refreshed), logical_case_public_id=logical_case_public_id
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
                list(refreshed), logical_case_public_id=logical_case_public_id
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
    "PwaWrittenReviewQueueRepository",
    "REVIEW_LEASE_DURATION",
    "ReviewLease",
    "ReviewLeaseConflict",
    "ReviewLeaseItem",
    "ReviewLeaseLost",
    "ReviewQueueCase",
    "ReviewQueueError",
    "ReviewQueueForbidden",
    "ReviewQueueLock",
    "ReviewQueueNotFound",
    "ReviewQueuePage",
    "ReviewStaffScope",
]
