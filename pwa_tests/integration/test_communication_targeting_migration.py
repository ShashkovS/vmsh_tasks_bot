"""Lifecycle proof for Student/Family communication targeting."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    NOW,
    _insert_parents,
)
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0089.pwa_communication_targeting"


def _seed_legacy_communications(connection: sqlite3.Connection) -> None:
    _insert_parents(connection)
    connection.execute(
        "INSERT INTO news_posts "
        "(id, source_type, owner_course_id, published_at, created_at, updated_at) "
        "VALUES (1, 'local', 1, ?, ?, ?)",
        (NOW, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO group_banners "
        "(id, group_id, audience, html_sanitized, starts_at, ends_at, "
        "created_by_user_id, updated_by_user_id, created_at, updated_at, "
        "content_format, markdown_source, rich_document_json) "
        "VALUES (1, 'assignment-n', 'student', '<p>Важно</p>', ?, ?, "
        "2, 2, ?, ?, 'rich_markdown_v1', 'Важно', ?)",
        (
            "2026-10-05T12:00:00Z",
            "2026-10-05T18:00:00Z",
            NOW,
            NOW,
            '{"schemaVersion":1,"media":[],"blocks":[]}',
        ),
    )
    connection.execute(
        "INSERT INTO group_banner_media "
        "(id, banner_id, ordinal, media_id, source_url, storage_key, public_url, "
        "mime_type, width, height, created_at) VALUES "
        "(1, 1, 0, 'image-1', 'https://example.test/a.png', "
        "'banners/a.webp', '/media/a.webp', 'image/webp', 800, 600, ?)",
        (NOW,),
    )


def test_communication_targeting_migration_preserves_existing_rows(tmp_path) -> None:
    database_path = tmp_path / "communication-targeting.sqlite3"
    migration_ids = {item.id for item in _migrations()}
    _apply(database_path, migration_ids - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_legacy_communications(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        news = connection.execute(
            "SELECT audience, attendance_mode FROM news_posts WHERE id = 1"
        ).fetchone()
        banner = connection.execute(
            "SELECT course_id, group_id, audience, attendance_mode, content_format "
            "FROM group_banners WHERE id = 1"
        ).fetchone()
        media = connection.execute(
            "SELECT banner_id, media_id, storage_key FROM group_banner_media WHERE id = 1"
        ).fetchone()
        assert tuple(news) == ("both", "all")
        assert tuple(banner) == (
            1,
            "assignment-n",
            "student",
            "all",
            "rich_markdown_v1",
        )
        assert tuple(media) == (1, "image-1", "banners/a.webp")
        assert connection.execute(
            "PRAGMA foreign_key_check(group_banners)"
        ).fetchall() == []
        assert connection.execute(
            "PRAGMA foreign_key_check(group_banner_media)"
        ).fetchall() == []
        assert tuple(connection.execute("PRAGMA integrity_check").fetchone()) == (
            "ok",
        )

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert {
            str(row[1]) for row in connection.execute("PRAGMA table_info(news_posts)")
        }.isdisjoint({"audience", "attendance_mode"})
        assert connection.execute(
            "SELECT group_id, audience, content_format FROM group_banners WHERE id = 1"
        ).fetchone() == ("assignment-n", "student", "rich_markdown_v1")
        assert connection.execute(
            "SELECT media_id FROM group_banner_media WHERE id = 1"
        ).fetchone() == ("image-1",)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
