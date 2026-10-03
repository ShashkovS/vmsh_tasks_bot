"""Domain transitions for independently published before/after blocks."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from db_methods.pwa.connection import PwaConnectionFactory
from db_methods.pwa.migrations import apply_schema_migrations
from models.pwa.lesson_blocks import LessonBlockService, LessonBlockVersionConflict


NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)
DOCUMENT = {
    "schemaVersion": 1,
    "blocks": [{"type": "paragraph", "children": [{"type": "text", "text": "Theory"}]}],
    "media": [],
}


@pytest.fixture()
def block_service(tmp_path):
    path = tmp_path / "lesson-blocks.sqlite3"
    apply_schema_migrations(path)
    # The service only needs the scoped lesson and Staff actor. These records
    # use SQLite's normal FK constraints in service transactions.
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO users (id, type, name, surname) VALUES (1, 2, 'T', 'A')")
        connection.execute(
            "INSERT INTO group_lessons "
            "(id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) "
            "VALUES (1, 1, 1, 'a', '2026-09-14', 'Europe/Moscow', 'active', ?, ?)",
            ("2026-09-20T13:00:00Z", "2026-09-20T13:00:00Z"),
        )
    return path


async def test_scheduled_snapshot_replaces_the_public_revision_only_when_due(block_service):
    service = LessonBlockService(PwaConnectionFactory(block_service), clock=lambda: NOW)
    block, first = await service.save_draft(
        group_lesson_id=1, position="before", expected_version=None,
        markdown="Theory", document=DOCUMENT, actor_user_id=1,
    )
    public = await service.publish_revision(
        group_lesson_id=1, position="before", expected_version=block.version,
        revision_public_id=first.public_id, mode="now", scheduled_at=None, actor_user_id=1,
    )
    updated, replacement = await service.save_draft(
        group_lesson_id=1, position="before", expected_version=public.version,
        markdown="New theory", document={**DOCUMENT, "blocks": [{"type": "paragraph", "children": [{"type": "text", "text": "New theory"}]}]}, actor_user_id=1,
    )
    pending = await service.publish_revision(
        group_lesson_id=1, position="before", expected_version=updated.version,
        revision_public_id=replacement.public_id, mode="scheduled",
        scheduled_at=datetime(2026, 9, 20, 14, tzinfo=UTC), actor_user_id=1,
    )
    assert pending.published_revision_id == first.id
    assert pending.pending_revision_id == replacement.id
    assert await service.activate_due_blocks(10) == ()

    later = LessonBlockService(
        PwaConnectionFactory(block_service), clock=lambda: datetime(2026, 9, 20, 15, tzinfo=UTC)
    )
    activated = await later.activate_due_blocks(10)
    assert [item.block.published_revision_id for item in activated] == [replacement.id]


async def test_hide_preserves_the_draft_and_stale_writes_conflict(block_service):
    service = LessonBlockService(PwaConnectionFactory(block_service), clock=lambda: NOW)
    block, revision = await service.save_draft(
        group_lesson_id=1, position="after", expected_version=None,
        markdown="Theory", document=DOCUMENT, actor_user_id=1,
    )
    public = await service.publish_revision(
        group_lesson_id=1, position="after", expected_version=block.version,
        revision_public_id=revision.public_id, mode="now", scheduled_at=None, actor_user_id=1,
    )
    hidden = await service.hide_block(
        group_lesson_id=1, position="after", expected_version=public.version, actor_user_id=1,
    )
    assert hidden.draft_revision_id == revision.id
    assert hidden.published_revision_id is None
    with pytest.raises(LessonBlockVersionConflict):
        await service.hide_block(
            group_lesson_id=1, position="after", expected_version=public.version, actor_user_id=1,
        )
