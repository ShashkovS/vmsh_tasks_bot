"""Publication policy for independently positioned group-lesson blocks.

The service is intentionally separate from compiled worksheet publication: a
block revision is immutable Rich Markdown, while the condition remains the
authoritative source for tasks.  See ``vmshpwa/docs/lesson-blocks.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Callable

from db_methods.pwa.connection import PwaConnectionFactory
from db_methods.pwa.lesson_blocks import (
    LessonBlockActivationRecord,
    LessonBlockRecord,
    LessonBlockRevisionRecord,
    LessonBlockStorageConflict,
    PublishedLessonBlockRecord,
    condition_is_published,
    get_lesson_block,
    get_lesson_block_revision,
    get_lesson_block_revision_by_id,
    insert_lesson_block,
    insert_lesson_block_event,
    insert_lesson_block_revision,
    list_lesson_blocks,
    list_lesson_block_revisions_by_ids,
    list_published_lesson_blocks,
    update_lesson_block_state,
)
from models.pwa.content import format_utc_timestamp
from models.pwa.lesson_rich_document import validate_lesson_rich_document


class LessonBlockPosition(StrEnum):
    BEFORE = "before"
    AFTER = "after"


class LessonBlockPublishMode(StrEnum):
    NOW = "now"
    SCHEDULED = "scheduled"
    WITH_LESSON = "with_lesson"


class LessonBlockInvariantError(ValueError):
    pass


class LessonBlockVersionConflict(LessonBlockInvariantError):
    pass


class LessonBlockNotFound(LessonBlockInvariantError):
    pass


class LessonBlockService:
    def __init__(self, factory: PwaConnectionFactory, *, clock: Callable[[], datetime] | None = None) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _timestamp(self) -> str:
        return format_utc_timestamp(self._clock())

    @staticmethod
    def _position(value: LessonBlockPosition | str) -> str:
        try:
            return LessonBlockPosition(value).value
        except (TypeError, ValueError) as error:
            raise LessonBlockInvariantError("lesson block position is invalid") from error

    @staticmethod
    def _expected(block: LessonBlockRecord | None, expected_version: int | None) -> None:
        if block is None:
            if expected_version is not None:
                raise LessonBlockVersionConflict("lesson block was created")
            return
        if expected_version != block.version:
            raise LessonBlockVersionConflict("lesson block version changed")

    async def get_staff_blocks(self, group_lesson_id: int) -> tuple[LessonBlockRecord, ...]:
        return await self._factory.run_read_async(lambda connection: list_lesson_blocks(connection, group_lesson_id=group_lesson_id))

    async def get_staff_state(
        self, group_lesson_id: int
    ) -> tuple[tuple[LessonBlockRecord, ...], tuple[LessonBlockRevisionRecord, ...]]:
        def read(connection):
            blocks = list_lesson_blocks(connection, group_lesson_id=group_lesson_id)
            ids = tuple(
                sorted(
                    {
                        revision_id
                        for block in blocks
                        for revision_id in (
                            block.draft_revision_id,
                            block.published_revision_id,
                            block.pending_revision_id,
                        )
                        if revision_id is not None
                    }
                )
            )
            return blocks, list_lesson_block_revisions_by_ids(connection, revision_ids=ids)

        return await self._factory.run_read_async(read)

    async def get_published_blocks(self, group_lesson_id: int) -> tuple[PublishedLessonBlockRecord, ...]:
        return await self._factory.run_read_async(lambda connection: list_published_lesson_blocks(connection, group_lesson_id=group_lesson_id))

    async def save_draft(self, *, group_lesson_id: int, position: LessonBlockPosition | str, expected_version: int | None, markdown: str, document: object | None, actor_user_id: int) -> tuple[LessonBlockRecord, LessonBlockRevisionRecord]:
        slot = self._position(position)
        if not isinstance(markdown, str) or len(markdown) > 32_768:
            raise LessonBlockInvariantError("lesson block Markdown is invalid")
        if markdown.strip():
            if document is None:
                raise LessonBlockInvariantError("non-empty Markdown requires a document")
            checked_document = validate_lesson_rich_document(document)
        elif document is not None:
            raise LessonBlockInvariantError("an empty draft cannot contain a document")
        else:
            checked_document = None
        timestamp = self._timestamp()

        def write(connection):
            block = get_lesson_block(connection, group_lesson_id=group_lesson_id, position=slot)
            self._expected(block, expected_version)
            if block is None:
                block = insert_lesson_block(connection, group_lesson_id=group_lesson_id, position=slot, actor_user_id=actor_user_id, timestamp=timestamp)
            revision = insert_lesson_block_revision(connection, block_id=block.id, markdown=markdown, document=checked_document, actor_user_id=actor_user_id, timestamp=timestamp)
            updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=actor_user_id, draft_revision_id=revision.id, update_draft=True)
            insert_lesson_block_event(connection, block_id=updated.id, revision_id=revision.id, action="draft_saved", actor_user_id=actor_user_id, timestamp=timestamp, block_version=updated.version)
            return updated, revision
        try:
            return await self._factory.run_write_async(write)
        except LessonBlockStorageConflict as error:
            raise LessonBlockVersionConflict(str(error)) from error

    async def publish_revision(self, *, group_lesson_id: int, position: LessonBlockPosition | str, expected_version: int, revision_public_id: str, mode: LessonBlockPublishMode | str, scheduled_at: datetime | None, actor_user_id: int) -> LessonBlockRecord:
        slot = self._position(position)
        try:
            publish_mode = LessonBlockPublishMode(mode)
        except (TypeError, ValueError) as error:
            raise LessonBlockInvariantError("lesson block publication mode is invalid") from error
        now = self._clock().astimezone(UTC)
        if publish_mode is LessonBlockPublishMode.SCHEDULED:
            if scheduled_at is None or scheduled_at.tzinfo is None or scheduled_at <= now:
                raise LessonBlockInvariantError("scheduled lesson block publication must be in the future")
        elif scheduled_at is not None:
            raise LessonBlockInvariantError("only scheduled publication accepts a timestamp")
        timestamp = format_utc_timestamp(now)
        scheduled = None if scheduled_at is None else format_utc_timestamp(scheduled_at)

        def write(connection):
            block = get_lesson_block(connection, group_lesson_id=group_lesson_id, position=slot)
            if block is None:
                raise LessonBlockNotFound("save a draft before publishing")
            self._expected(block, expected_version)
            revision = get_lesson_block_revision(connection, revision_public_id=revision_public_id)
            if revision is None or revision.block_id != block.id or revision.document is None:
                raise LessonBlockInvariantError("lesson block revision is not publishable")
            if publish_mode is LessonBlockPublishMode.NOW or (publish_mode is LessonBlockPublishMode.WITH_LESSON and condition_is_published(connection, group_lesson_id=group_lesson_id)):
                updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=actor_user_id, published_revision_id=revision.id, published_at=timestamp, update_published=True, pending_revision_id=None, pending_mode=None, scheduled_at=None, update_pending=True)
                action = "published"
            else:
                pending_mode = "scheduled" if publish_mode is LessonBlockPublishMode.SCHEDULED else "with_lesson"
                updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=actor_user_id, pending_revision_id=revision.id, pending_mode=pending_mode, scheduled_at=scheduled, update_pending=True)
                action = "scheduled" if pending_mode == "scheduled" else "with_lesson_armed"
            insert_lesson_block_event(connection, block_id=updated.id, revision_id=revision.id, action=action, actor_user_id=actor_user_id, timestamp=timestamp, block_version=updated.version, details={"mode": publish_mode.value, "scheduledAt": scheduled})
            return updated
        try:
            return await self._factory.run_write_async(write)
        except LessonBlockStorageConflict as error:
            raise LessonBlockVersionConflict(str(error)) from error

    async def cancel_pending_publication(self, *, group_lesson_id: int, position: LessonBlockPosition | str, expected_version: int, actor_user_id: int) -> LessonBlockRecord:
        return await self._clear_pending(group_lesson_id, position, expected_version, actor_user_id, action="publication_cancelled")

    async def hide_block(self, *, group_lesson_id: int, position: LessonBlockPosition | str, expected_version: int, actor_user_id: int) -> LessonBlockRecord:
        slot, timestamp = self._position(position), self._timestamp()
        def write(connection):
            block = get_lesson_block(connection, group_lesson_id=group_lesson_id, position=slot)
            if block is None:
                raise LessonBlockNotFound("lesson block does not exist")
            self._expected(block, expected_version)
            updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=actor_user_id, published_revision_id=None, published_at=None, update_published=True, pending_revision_id=None, pending_mode=None, scheduled_at=None, update_pending=True)
            insert_lesson_block_event(connection, block_id=updated.id, revision_id=block.published_revision_id, action="hidden", actor_user_id=actor_user_id, timestamp=timestamp, block_version=updated.version)
            return updated
        try:
            return await self._factory.run_write_async(write)
        except LessonBlockStorageConflict as error:
            raise LessonBlockVersionConflict(str(error)) from error

    async def _clear_pending(self, group_lesson_id: int, position: LessonBlockPosition | str, expected_version: int, actor_user_id: int, *, action: str) -> LessonBlockRecord:
        slot, timestamp = self._position(position), self._timestamp()
        def write(connection):
            block = get_lesson_block(connection, group_lesson_id=group_lesson_id, position=slot)
            if block is None:
                raise LessonBlockNotFound("lesson block does not exist")
            self._expected(block, expected_version)
            if block.pending_revision_id is None:
                raise LessonBlockInvariantError("lesson block has no pending publication")
            updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=actor_user_id, pending_revision_id=None, pending_mode=None, scheduled_at=None, update_pending=True)
            insert_lesson_block_event(connection, block_id=updated.id, revision_id=block.pending_revision_id, action=action, actor_user_id=actor_user_id, timestamp=timestamp, block_version=updated.version)
            return updated
        try:
            return await self._factory.run_write_async(write)
        except LessonBlockStorageConflict as error:
            raise LessonBlockVersionConflict(str(error)) from error

    async def activate_due_blocks(self, batch_size: int) -> tuple[LessonBlockActivationRecord, ...]:
        if batch_size < 1:
            raise LessonBlockInvariantError("lesson block activation batch must be positive")
        timestamp = self._timestamp()
        def activate(connection):
            rows = connection.execute(
                "SELECT id FROM lesson_blocks WHERE (pending_mode = 'scheduled' AND scheduled_at <= ?) "
                "OR (pending_mode = 'with_lesson' AND exists (SELECT 1 FROM lesson_publications AS publication JOIN content_revisions AS revision ON revision.id = publication.revision_id JOIN content_derivatives AS derivative ON derivative.revision_id = publication.revision_id AND derivative.kind = 'web_ast' WHERE publication.group_lesson_id = lesson_blocks.group_lesson_id AND publication.kind = 'condition' AND publication.state = 'published' AND (derivative.invalidated_at IS NULL OR EXISTS (SELECT 1 FROM publication_figure_layouts frozen WHERE frozen.publication_id = publication.id AND frozen.document_json IS NOT NULL)) AND (revision.status = 'ready' OR EXISTS (SELECT 1 FROM publication_figure_layouts frozen WHERE frozen.publication_id = publication.id AND frozen.document_json IS NOT NULL)))) "
                "ORDER BY coalesce(scheduled_at, updated_at), id LIMIT ?", (timestamp, batch_size),
            ).fetchall()
            activated: list[LessonBlockActivationRecord] = []
            for raw in rows:
                block_row = connection.execute("SELECT * FROM lesson_blocks WHERE id = ?", (raw["id"],)).fetchone()
                block = get_lesson_block(connection, group_lesson_id=int(block_row["group_lesson_id"]), position=str(block_row["position"]))
                if block is None or block.pending_revision_id is None:
                    continue
                revision = get_lesson_block_revision_by_id(connection, revision_id=block.pending_revision_id)
                if revision is None or revision.document is None:
                    continue
                updated = update_lesson_block_state(connection, block_id=block.id, expected_version=block.version, timestamp=timestamp, actor_user_id=None, published_revision_id=revision.id, published_at=timestamp, update_published=True, pending_revision_id=None, pending_mode=None, scheduled_at=None, update_pending=True)
                insert_lesson_block_event(connection, block_id=updated.id, revision_id=revision.id, action="schedule_activated", actor_user_id=None, timestamp=timestamp, block_version=updated.version, details={"mode": block.pending_mode})
                activated.append(LessonBlockActivationRecord(block=updated, revision=revision))
            return tuple(activated)
        return await self._factory.run_write_async(activate)


__all__ = ["LessonBlockInvariantError", "LessonBlockNotFound", "LessonBlockPosition", "LessonBlockPublishMode", "LessonBlockService", "LessonBlockVersionConflict"]
