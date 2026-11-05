"""Mechanical SQLite operations for lesson blocks.

Policy and authorization live in :mod:`models.pwa.lesson_blocks`; these helpers
only persist immutable revisions and the current public/pending pointers.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


class LessonBlockStorageError(RuntimeError):
    pass


class LessonBlockStorageConflict(LessonBlockStorageError):
    pass


@dataclass(frozen=True, slots=True)
class LessonBlockRevisionRecord:
    id: int
    public_id: str
    block_id: int
    revision_number: int
    markdown: str
    document: dict[str, object] | None
    created_at: datetime
    created_by_user_id: int


@dataclass(frozen=True, slots=True)
class LessonBlockRecord:
    id: int
    public_id: str
    group_lesson_id: int
    position: str
    draft_revision_id: int | None
    published_revision_id: int | None
    published_at: datetime | None
    pending_revision_id: int | None
    pending_mode: str | None
    scheduled_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int | None
    updated_by_user_id: int | None


@dataclass(frozen=True, slots=True)
class PublishedLessonBlockRecord:
    block: LessonBlockRecord
    revision: LessonBlockRevisionRecord


@dataclass(frozen=True, slots=True)
class LessonBlockActivationRecord:
    block: LessonBlockRecord
    revision: LessonBlockRevisionRecord


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise LessonBlockStorageError("lesson block timestamp is naive")
    return parsed.astimezone(UTC)


def _document(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError, RecursionError) as error:
        raise LessonBlockStorageError("stored lesson block document is invalid") from error
    if not isinstance(parsed, dict):
        raise LessonBlockStorageError("stored lesson block document is invalid")
    return parsed


def _revision(row: sqlite3.Row) -> LessonBlockRevisionRecord:
    return LessonBlockRevisionRecord(
        id=int(row["id"]), public_id=str(row["public_id"]), block_id=int(row["block_id"]),
        revision_number=int(row["revision_number"]), markdown=str(row["markdown"]),
        document=_document(row["document_json"]), created_at=_timestamp(str(row["created_at"])) or datetime.now(UTC),
        created_by_user_id=int(row["created_by_user_id"]),
    )


def _block(row: sqlite3.Row) -> LessonBlockRecord:
    return LessonBlockRecord(
        id=int(row["id"]), public_id=str(row["public_id"]), group_lesson_id=int(row["group_lesson_id"]),
        position=str(row["position"]), draft_revision_id=None if row["draft_revision_id"] is None else int(row["draft_revision_id"]),
        published_revision_id=None if row["published_revision_id"] is None else int(row["published_revision_id"]),
        published_at=_timestamp(row["published_at"]), pending_revision_id=None if row["pending_revision_id"] is None else int(row["pending_revision_id"]),
        pending_mode=None if row["pending_mode"] is None else str(row["pending_mode"]), scheduled_at=_timestamp(row["scheduled_at"]),
        version=int(row["version"]), created_at=_timestamp(str(row["created_at"])) or datetime.now(UTC),
        updated_at=_timestamp(str(row["updated_at"])) or datetime.now(UTC),
        created_by_user_id=None if row["created_by_user_id"] is None else int(row["created_by_user_id"]),
        updated_by_user_id=None if row["updated_by_user_id"] is None else int(row["updated_by_user_id"]),
    )


def get_lesson_block(connection: sqlite3.Connection, *, group_lesson_id: int, position: str) -> LessonBlockRecord | None:
    row = connection.execute("SELECT * FROM lesson_blocks WHERE group_lesson_id = ? AND position = ?", (group_lesson_id, position)).fetchone()
    return None if row is None else _block(row)


def list_lesson_blocks(connection: sqlite3.Connection, *, group_lesson_id: int) -> tuple[LessonBlockRecord, ...]:
    return tuple(_block(row) for row in connection.execute("SELECT * FROM lesson_blocks WHERE group_lesson_id = ? ORDER BY position", (group_lesson_id,)).fetchall())


def get_lesson_block_revision(connection: sqlite3.Connection, *, revision_public_id: str) -> LessonBlockRevisionRecord | None:
    row = connection.execute("SELECT * FROM lesson_block_revisions WHERE public_id = ?", (revision_public_id,)).fetchone()
    return None if row is None else _revision(row)


def get_lesson_block_revision_by_id(connection: sqlite3.Connection, *, revision_id: int | None) -> LessonBlockRevisionRecord | None:
    if revision_id is None:
        return None
    row = connection.execute("SELECT * FROM lesson_block_revisions WHERE id = ?", (revision_id,)).fetchone()
    return None if row is None else _revision(row)


def list_lesson_block_revisions_by_ids(
    connection: sqlite3.Connection, *, revision_ids: tuple[int, ...]
) -> tuple[LessonBlockRevisionRecord, ...]:
    """Load the small set of revisions referenced by two Staff slots in one query."""

    if not revision_ids:
        return ()
    placeholders = ", ".join("?" for _item in revision_ids)
    rows = connection.execute(
        f"SELECT * FROM lesson_block_revisions WHERE id IN ({placeholders})",
        revision_ids,
    ).fetchall()
    return tuple(_revision(row) for row in rows)


def insert_lesson_block(connection: sqlite3.Connection, *, group_lesson_id: int, position: str, actor_user_id: int, timestamp: str) -> LessonBlockRecord:
    try:
        row = connection.execute(
            "INSERT INTO lesson_blocks (group_lesson_id, position, created_at, updated_at, created_by_user_id, updated_by_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING *", (group_lesson_id, position, timestamp, timestamp, actor_user_id, actor_user_id),
        ).fetchone()
    except sqlite3.IntegrityError as error:
        raise LessonBlockStorageConflict("lesson block position already exists") from error
    return _block(row)


def insert_lesson_block_revision(connection: sqlite3.Connection, *, block_id: int, markdown: str, document: dict[str, object] | None, actor_user_id: int, timestamp: str) -> LessonBlockRevisionRecord:
    revision_number = int(
        connection.execute(
            "SELECT coalesce(max(revision_number), 0) + 1 AS next_revision_number "
            "FROM lesson_block_revisions WHERE block_id = ?",
            (block_id,),
        ).fetchone()["next_revision_number"]
    )
    row = connection.execute(
        "INSERT INTO lesson_block_revisions (block_id, revision_number, markdown, document_json, created_at, created_by_user_id) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
        (block_id, revision_number, markdown, None if document is None else json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True), timestamp, actor_user_id),
    ).fetchone()
    return _revision(row)


def update_lesson_block_state(connection: sqlite3.Connection, *, block_id: int, expected_version: int, timestamp: str, actor_user_id: int | None, draft_revision_id: int | None = None, update_draft: bool = False, published_revision_id: int | None = None, published_at: str | None = None, update_published: bool = False, pending_revision_id: int | None = None, pending_mode: str | None = None, scheduled_at: str | None = None, update_pending: bool = False) -> LessonBlockRecord:
    current = connection.execute("SELECT * FROM lesson_blocks WHERE id = ?", (block_id,)).fetchone()
    if current is None:
        raise LessonBlockStorageError("lesson block does not exist")
    if int(current["version"]) != expected_version:
        raise LessonBlockStorageConflict("lesson block version changed")
    row = connection.execute(
        "UPDATE lesson_blocks SET draft_revision_id = ?, published_revision_id = ?, published_at = ?, "
        "pending_revision_id = ?, pending_mode = ?, scheduled_at = ?, updated_at = ?, updated_by_user_id = ?, version = version + 1 "
        "WHERE id = ? AND version = ? RETURNING *",
        (
            draft_revision_id if update_draft else current["draft_revision_id"],
            published_revision_id if update_published else current["published_revision_id"],
            published_at if update_published else current["published_at"],
            pending_revision_id if update_pending else current["pending_revision_id"],
            pending_mode if update_pending else current["pending_mode"],
            scheduled_at if update_pending else current["scheduled_at"],
            timestamp, actor_user_id, block_id, expected_version,
        ),
    ).fetchone()
    if row is None:
        raise LessonBlockStorageConflict("lesson block version changed")
    return _block(row)


def insert_lesson_block_event(connection: sqlite3.Connection, *, block_id: int, revision_id: int | None, action: str, actor_user_id: int | None, timestamp: str, block_version: int, details: dict[str, object] | None = None) -> None:
    connection.execute(
        "INSERT INTO lesson_block_events (block_id, revision_id, action, actor_user_id, created_at, block_version, details_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (block_id, revision_id, action, actor_user_id, timestamp, block_version, json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)),
    )


def condition_is_published(connection: sqlite3.Connection, *, group_lesson_id: int) -> bool:
    return connection.execute(
        "SELECT exists(SELECT 1 FROM lesson_publications AS publication "
        "JOIN content_revisions AS revision ON revision.id = publication.revision_id "
        "JOIN content_derivatives AS derivative ON derivative.revision_id = publication.revision_id AND derivative.kind = 'web_ast' "
        "WHERE publication.group_lesson_id = ? AND publication.kind = 'condition' AND publication.state = 'published' "
        "AND (derivative.invalidated_at IS NULL OR EXISTS (SELECT 1 FROM publication_figure_layouts frozen WHERE frozen.publication_id = publication.id AND frozen.document_json IS NOT NULL)) "
        "AND (revision.status = 'ready' OR EXISTS (SELECT 1 FROM publication_figure_layouts frozen WHERE frozen.publication_id = publication.id AND frozen.document_json IS NOT NULL))) AS is_published", (group_lesson_id,),
    ).fetchone()["is_published"] == 1


def list_published_lesson_blocks(connection: sqlite3.Connection, *, group_lesson_id: int) -> tuple[PublishedLessonBlockRecord, ...]:
    rows = connection.execute(
        "SELECT block.*, revision.id AS revision_id_value, revision.public_id AS revision_public_id, revision.block_id, revision.revision_number, revision.markdown, revision.document_json, revision.created_at AS revision_created_at, revision.created_by_user_id AS revision_created_by_user_id "
        "FROM lesson_blocks AS block JOIN lesson_block_revisions AS revision ON revision.id = block.published_revision_id "
        "WHERE block.group_lesson_id = ? ORDER BY block.position", (group_lesson_id,),
    ).fetchall()
    result: list[PublishedLessonBlockRecord] = []
    for row in rows:
        revision = LessonBlockRevisionRecord(id=int(row["revision_id_value"]), public_id=str(row["revision_public_id"]), block_id=int(row["block_id"]), revision_number=int(row["revision_number"]), markdown=str(row["markdown"]), document=_document(row["document_json"]), created_at=_timestamp(str(row["revision_created_at"])) or datetime.now(UTC), created_by_user_id=int(row["revision_created_by_user_id"]))
        result.append(PublishedLessonBlockRecord(block=_block(row), revision=revision))
    return tuple(result)


def list_published_lesson_blocks_for_lessons(connection: sqlite3.Connection, *, group_lesson_ids: tuple[int, ...]) -> dict[int, tuple[PublishedLessonBlockRecord, ...]]:
    if not group_lesson_ids:
        return {}
    output: dict[int, list[PublishedLessonBlockRecord]] = {item: [] for item in group_lesson_ids}
    placeholders = ", ".join("?" for _item in group_lesson_ids)
    rows = connection.execute(
        "SELECT block.*, revision.id AS revision_id_value, revision.public_id AS revision_public_id, "
        "revision.block_id, revision.revision_number, revision.markdown, revision.document_json, "
        "revision.created_at AS revision_created_at, revision.created_by_user_id AS revision_created_by_user_id "
        "FROM lesson_blocks AS block JOIN lesson_block_revisions AS revision ON revision.id = block.published_revision_id "
        f"WHERE block.group_lesson_id IN ({placeholders}) ORDER BY block.group_lesson_id, block.position",
        group_lesson_ids,
    ).fetchall()
    for row in rows:
        revision = LessonBlockRevisionRecord(
            id=int(row["revision_id_value"]), public_id=str(row["revision_public_id"]),
            block_id=int(row["block_id"]), revision_number=int(row["revision_number"]),
            markdown=str(row["markdown"]), document=_document(row["document_json"]),
            created_at=_timestamp(str(row["revision_created_at"])) or datetime.now(UTC),
            created_by_user_id=int(row["revision_created_by_user_id"]),
        )
        output[int(row["group_lesson_id"])].append(
            PublishedLessonBlockRecord(block=_block(row), revision=revision)
        )
    return {key: tuple(value) for key, value in output.items()}


def activate_waiting_lesson_blocks(connection: sqlite3.Connection, *, group_lesson_id: int, timestamp: str) -> tuple[LessonBlockActivationRecord, ...]:
    rows = connection.execute("SELECT * FROM lesson_blocks WHERE group_lesson_id = ? AND pending_mode = 'with_lesson'", (group_lesson_id,)).fetchall()
    activated: list[LessonBlockActivationRecord] = []
    for raw in rows:
        block = _block(raw)
        revision = get_lesson_block_revision_by_id(connection, revision_id=block.pending_revision_id)
        if revision is None or revision.document is None:
            continue
        updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=None, published_revision_id=revision.id, published_at=timestamp, update_published=True, pending_revision_id=None, pending_mode=None, scheduled_at=None, update_pending=True)
        insert_lesson_block_event(connection, block_id=updated.id, revision_id=revision.id, action="schedule_activated", actor_user_id=None, timestamp=timestamp, block_version=updated.version, details={"mode": "with_lesson"})
        activated.append(LessonBlockActivationRecord(block=updated, revision=revision))
    return tuple(activated)


__all__ = ["LessonBlockActivationRecord", "LessonBlockRecord", "LessonBlockRevisionRecord", "LessonBlockStorageConflict", "LessonBlockStorageError", "PublishedLessonBlockRecord", "activate_waiting_lesson_blocks", "condition_is_published", "get_lesson_block", "get_lesson_block_revision", "get_lesson_block_revision_by_id", "insert_lesson_block", "insert_lesson_block_event", "insert_lesson_block_revision", "list_lesson_block_revisions_by_ids", "list_lesson_blocks", "list_published_lesson_blocks", "list_published_lesson_blocks_for_lessons", "update_lesson_block_state"]
