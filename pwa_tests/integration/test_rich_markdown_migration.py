"""Schema boundary for Phase 8 Rich Markdown v1 (migration 0081)."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0081.pwa_rich_markdown"


def _columns(database_path, table: str) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _objects(database_path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name IN "
                "('group_banner_media', 'group_banner_media_banner_idx')"
            )
        }


def test_rich_markdown_migration_up_down_up_on_clean_sqlite(tmp_path) -> None:
    database_path = tmp_path / "rich-markdown.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0080.pwa_submission_paste_evidence"
    }

    _apply(database_path, set(migrations) - {MIGRATION_ID})
    assert {"content_format", "markdown_source", "rich_document_json"}.isdisjoint(
        _columns(database_path, "news_revisions")
    )
    assert {"content_format", "markdown_source", "rich_document_json"}.isdisjoint(
        _columns(database_path, "group_banners")
    )
    assert _objects(database_path) == set()

    _apply(database_path, {MIGRATION_ID})
    assert {"content_format", "markdown_source", "rich_document_json"}.issubset(
        _columns(database_path, "news_revisions")
    )
    assert {"content_format", "markdown_source", "rich_document_json"}.issubset(
        _columns(database_path, "group_banners")
    )
    assert "source_url" in _columns(database_path, "news_media")
    assert _objects(database_path) == {
        "group_banner_media",
        "group_banner_media_banner_idx",
    }
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
