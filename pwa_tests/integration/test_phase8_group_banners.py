from __future__ import annotations

import sqlite3

import pytest

from db_methods.pwa.group_banners import list_current_group_banners
from models.pwa.group_banners import (
    GroupBannerConflict,
    cancel_banner,
    create_group_banner,
    edit_group_banner,
)
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    _insert_parents,
)
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0068.pwa_group_banners"
RICH_MARKDOWN_MIGRATION_ID = "0081.pwa_rich_markdown"


def test_group_banner_migration_roundtrip(tmp_path):
    database_path = tmp_path / "banners.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    # Rich Markdown extends this table and is covered by its own migration
    # round-trip. Exclude it while proving the historical 0068 boundary.
    _apply(database_path, set(migrations) - {MIGRATION_ID, RICH_MARKDOWN_MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM sqlite_schema WHERE name = 'group_banners'"
        ).fetchone() == (0,)
    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    _rollback(database_path, {MIGRATION_ID})
    _apply(database_path, {MIGRATION_ID})


def test_banner_sanitizing_window_and_optimistic_cancel(tmp_path):
    database_path = tmp_path / "banners.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _insert_parents(connection)

    item = create_group_banner(
        connection,
        public_id="banner-lesson-review",
        group_id="assignment-n",
        audience="both",
        html_source=(
            '<b>Разбор в 17:00</b> · <a href="javascript:alert(1)">войти</a>'
            "<script>bad()</script>"
        ),
        starts_at="2026-10-05T12:00:00Z",
        ends_at="2026-10-05T18:00:00Z",
        priority=10,
        dismissible=True,
        actor_user_id=2,
        now="2026-10-05T11:00:00Z",
    )
    assert "javascript" not in item["html_sanitized"]
    assert "<script" not in item["html_sanitized"]
    assert (
        len(
            list_current_group_banners(
                connection,
                group_ids=("assignment-n",),
                audience="student",
                now="2026-10-05T13:00:00Z",
            )
        )
        == 1
    )
    assert (
        list_current_group_banners(
            connection,
            group_ids=("assignment-n",),
            audience="student",
            now="2026-10-05T18:00:00Z",
        )
        == []
    )

    updated = edit_group_banner(
        connection,
        public_id="banner-lesson-review",
        expected_version=1,
        audience="student",
        html_source="<i>Новое время</i>",
        starts_at="2026-10-05T12:30:00Z",
        ends_at="2026-10-05T19:00:00Z",
        priority=20,
        dismissible=False,
        actor_user_id=2,
        now="2026-10-05T11:05:00Z",
    )
    assert updated["version"] == 2
    with pytest.raises(GroupBannerConflict):
        cancel_banner(
            connection,
            public_id="banner-lesson-review",
            expected_version=1,
            actor_user_id=2,
            now="2026-10-05T11:06:00Z",
        )
    cancelled = cancel_banner(
        connection,
        public_id="banner-lesson-review",
        expected_version=2,
        actor_user_id=2,
        now="2026-10-05T11:07:00Z",
    )
    assert (cancelled["status"], cancelled["version"]) == ("cancelled", 3)
    connection.close()
