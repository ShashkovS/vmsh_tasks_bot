"""Phase-9 course achievement migration lifecycle."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0073.pwa_course_achievements"


def _achievement_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' "
            "AND name IN ('achievement_definitions', 'user_achievements')"
        )
    }


def test_course_achievement_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "course-achievements.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0072.pwa_course_analytics"
    }

    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _achievement_tables(connection) == set()

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert _achievement_tables(connection) == {
            "achievement_definitions",
            "user_achievements",
        }
        assert connection.execute(
            "SELECT code FROM achievement_definitions ORDER BY id"
        ).fetchall() == [
            ("first_submission",),
            ("first_accepted",),
            ("first_written_submission",),
        ]

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _achievement_tables(connection) == set()

    _apply(database_path, {MIGRATION_ID})
