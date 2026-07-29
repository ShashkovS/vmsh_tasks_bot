"""Phase-9 course analytics migration lifecycle."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0072.pwa_course_analytics"


def _analytics_objects(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE name IN ('analytics_runs', 'analytics_runs_course_latest_idx', "
            "'student_lesson_metrics', 'student_lesson_metrics_student_run_idx')"
        )
    }


def test_course_analytics_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "course-analytics.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0071.pwa_oral_results_idempotency"
    }

    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _analytics_objects(connection) == set()

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert _analytics_objects(connection) == {
            "analytics_runs",
            "analytics_runs_course_latest_idx",
            "student_lesson_metrics",
            "student_lesson_metrics_student_run_idx",
        }

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _analytics_objects(connection) == set()

    _apply(database_path, {MIGRATION_ID})
