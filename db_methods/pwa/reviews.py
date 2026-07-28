"""Lease-safe written review queue primitives for the Staff adapter."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable, Collection
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
        allowed_group_ids: Collection[str],
    ) -> ReviewLease:
        if not queue_public_id.strip():
            raise ValueError("queue_public_id must not be empty")
        if teacher_user_id == 0:
            raise ValueError("teacher_user_id must not be zero")
        scope = frozenset(allowed_group_ids)
        now = _normalize_time(self._clock())
        expires_at = now + REVIEW_LEASE_DURATION

        def operation(connection: sqlite3.Connection) -> ReviewLease:
            logical_case_public_id, rows = _case_rows(
                connection, queue_public_id=queue_public_id
            )
            if not scope or any(str(row["group_id"]) not in scope for row in rows):
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

    async def heartbeat(self, *, claim_token: str, teacher_user_id: int) -> ReviewLease:
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

    async def release(self, *, claim_token: str, teacher_user_id: int) -> int:
        token = claim_token.strip()
        if not token:
            raise ValueError("claim_token must not be empty")
        now_text = _timestamp(_normalize_time(self._clock()))

        def operation(connection: sqlite3.Connection) -> int:
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
