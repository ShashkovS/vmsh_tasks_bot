"""Current SQLite invariants for content and lesson scheduling."""

from __future__ import annotations

from pwa_tests.sqlite_template import create_test_database

import sqlite3
from collections.abc import Collection

import pytest


CONTENT_TABLES = {
    "course_lessons",
    "group_lessons",
    "course_schedule_rules",
    "group_schedule_overrides",
    "content_sources",
    "content_revisions",
    "media_assets",
    "content_revision_assets",
    "content_derivatives",
    "content_problem_matches",
    "problem_revisions",
    "problem_synonym_groups",
    "problem_synonym_members",
    "lesson_windows",
    "lesson_window_schedule_sources",
    "lesson_publications",
    "hint_reveals",
    "solution_reveals",
}
LEGACY_LEDGER_TABLES = {
    "users",
    "groups",
    "lessons",
    "problems",
    "results",
    "written_tasks_discussions",
    "written_tasks_queue",
}
NOW = "2026-09-20T13:00:00.000000Z"


def _schema(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    return connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE '_yoyo_%' "
        "ORDER BY type, name"
    ).fetchall()


def _counts(connection: sqlite3.Connection, tables: Collection[str]) -> dict[str, int]:
    return {
        table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        for table in tables
    }


def _seed_scope(connection: sqlite3.Connection) -> tuple[int, int, int]:
    actor_id = -920_001
    connection.execute(
        "INSERT INTO users (id, type, name, surname) VALUES (?, 2, 'Schema', 'Actor')",
        (actor_id,),
    )
    season_id = connection.execute(
        "INSERT INTO seasons "
        "(code, title, starts_on, ends_on, session_expires_on, "
        "status, created_at, updated_at) VALUES "
        "('content-schema', 'Content schema', "
        "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    course_id = connection.execute(
        "INSERT INTO courses "
        "(season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(?, 'math', 'Math', 'math', 'active', 1, "
        "'math', ?, ?) RETURNING id",
        (season_id, NOW, NOW),
    ).fetchone()[0]
    other_course_id = connection.execute(
        "INSERT INTO courses "
        "(season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(?, 'physics', 'Physics', 'physics', 'active', 2, "
        "'physics', ?, ?) RETURNING id",
        (season_id, NOW, NOW),
    ).fetchone()[0]
    connection.executemany(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, course_id, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, 'active', ?, ?)",
        (
            ("schema-a", "a", "A", 1, course_id, NOW, NOW),
            ("schema-b", "b", "B", 2, course_id, NOW, NOW),
            (
                "schema-other",
                "o",
                "Other",
                1,
                other_course_id,
                NOW,
                NOW,
            ),
        ),
    )
    return actor_id, course_id, other_course_id


def test_phase2_content_scope_uniques_and_foreign_keys(tmp_path):
    database_path = tmp_path / "phase2-constraints.sqlite3"
    create_test_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        actor_id, course_id, other_course_id = _seed_scope(connection)
        course_lesson_id = connection.execute(
            "INSERT INTO course_lessons "
            "(course_id, lesson_number, created_by_user_id, "
            "updated_by_user_id, created_at, updated_at) "
            "VALUES (?, 41, ?, ?, ?, ?) RETURNING id",
            (course_id, actor_id, actor_id, NOW, NOW),
        ).fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO course_lessons "
                "(course_id, lesson_number, created_at, updated_at) "
                "VALUES (?, 41, ?, ?)",
                (course_id, NOW, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO group_lessons "
                "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
                "business_timezone, created_at, updated_at) VALUES "
                "(?, ?, 'schema-other', "
                "'2026-09-14', 'Europe/Moscow', ?, ?)",
                (course_lesson_id, course_id, NOW, NOW),
            )

        connection.execute(
            "INSERT INTO group_lessons "
            "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, created_at, updated_at) VALUES "
            "(?, ?, 'schema-a', "
            "'2026-09-14', 'Europe/Moscow', ?, ?)",
            (course_lesson_id, course_id, NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO group_lessons "
                "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
                "business_timezone, created_at, updated_at) VALUES "
                "(?, ?, 'schema-a', "
                "'2026-09-14', 'Europe/Moscow', ?, ?)",
                (course_lesson_id, course_id, NOW, NOW),
            )

        assert other_course_id != course_id
        for table in sorted(CONTENT_TABLES):
            assert (
                connection.execute(f'PRAGMA foreign_key_check("{table}")').fetchall()
                == []
            )


def test_phase2_schedule_dates_times_and_cutoff_are_db_guarded(tmp_path):
    database_path = tmp_path / "phase2-schedule-constraints.sqlite3"
    create_test_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        actor_id, course_id, _ = _seed_scope(connection)
        course_lesson_id = connection.execute(
            "INSERT INTO course_lessons "
            "(course_id, lesson_number, created_at, updated_at) "
            "VALUES (?, 50, ?, ?) RETURNING id",
            (course_id, NOW, NOW),
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO group_lessons "
                "(course_lesson_id, course_id, group_id, "
                "cycle_anchor_date, business_timezone, created_at, updated_at) "
                "VALUES (?, ?, 'schema-a', "
                "'2026-99-99', 'Europe/Moscow', ?, ?)",
                (course_lesson_id, course_id, NOW, NOW),
            )
        group_lesson_id = connection.execute(
            "INSERT INTO group_lessons "
            "(course_lesson_id, course_id, group_id, "
            "cycle_anchor_date, business_timezone, created_at, updated_at) "
            "VALUES (?, ?, 'schema-a', "
            "'2026-09-14', 'Europe/Moscow', ?, ?) RETURNING id",
            (course_lesson_id, course_id, NOW, NOW),
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO lesson_windows "
                "(group_lesson_id, opens_at, submission_closes_at, "
                "timezone, source, created_at, updated_at) VALUES "
                "(?, '2026-09-20T13:00:00.000000Z', "
                "'2026-09-19T13:00:00.000000Z', 'Europe/Moscow', 'native', ?, ?)",
                (group_lesson_id, NOW, NOW),
            )
        for local_time in ("24:00", "12:60", "12:00:60"):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO course_schedule_rules "
                    "(course_id, schedule_field, rule_version, day_offset, "
                    "local_time, timezone, state, created_at, updated_at) VALUES "
                    "(?, 'submission_closes_at', 1, 5, ?, 'Europe/Moscow', "
                    "'draft', ?, ?)",
                    (
                        course_id,
                        local_time,
                        NOW,
                        NOW,
                    ),
                )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO course_schedule_rules "
                "(course_id, schedule_field, rule_version, day_offset, "
                "local_time, timezone, state, confirmed_at, created_at, updated_at) "
                "VALUES (?, 'submission_closes_at', "
                "1, 5, '20:50', 'Europe/Moscow', 'active', ?, ?, ?)",
                (course_id, NOW, NOW, NOW),
            )
        rule_id = connection.execute(
            "INSERT INTO course_schedule_rules "
            "(course_id, schedule_field, rule_version, day_offset, "
            "local_time, timezone, state, created_by_user_id, confirmed_by_user_id, "
            "created_at, updated_at, confirmed_at) VALUES "
            "(?, 'submission_closes_at', 1, 5, '20:50', "
            "'Europe/Moscow', 'active', ?, ?, ?, ?, ?) RETURNING id",
            (course_id, actor_id, actor_id, NOW, NOW, NOW),
        ).fetchone()[0]
        with pytest.raises(
            sqlite3.IntegrityError,
            match="invalid course schedule rule state transition",
        ):
            connection.execute(
                "UPDATE course_schedule_rules SET confirmed_at = ?, version = version + 1 "
                "WHERE id = ?",
                ("2026-09-20T14:00:00.000000Z", rule_id),
            )
        override_id = connection.execute(
            "INSERT INTO group_schedule_overrides "
            "(course_id, group_id, schedule_field, override_version, "
            "mode, based_on_schedule_rule_id, state, created_by_user_id, "
            "confirmed_by_user_id, created_at, updated_at, confirmed_at) VALUES "
            "(?, 'schema-a', 'submission_closes_at', "
            "1, 'inherit', ?, 'active', ?, ?, ?, ?, ?) RETURNING id",
            (course_id, rule_id, actor_id, actor_id, NOW, NOW, NOW),
        ).fetchone()[0]
        with pytest.raises(
            sqlite3.IntegrityError,
            match="invalid group schedule override state transition",
        ):
            connection.execute(
                "UPDATE group_schedule_overrides SET superseded_at = ?, "
                "version = version + 1 WHERE id = ?",
                (NOW, override_id),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO group_schedule_overrides "
                "(course_id, group_id, schedule_field, override_version, "
                "mode, based_on_schedule_rule_id, state, created_at, updated_at) "
                "VALUES (?, 'schema-a', "
                "'submission_closes_at', 1, 'disabled', ?, 'draft', ?, ?)",
                (course_id, rule_id, NOW, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO media_assets "
                "(sha256, storage_namespace, object_key, media_type, "
                "byte_size, width, height, created_at) VALUES "
                "(?, 'content', 'content/too-wide.webp', "
                "'image/webp', 1, 20001, 1, ?)",
                ("a" * 64, NOW),
            )
        hint_rule_id = connection.execute(
            "INSERT INTO course_schedule_rules "
            "(course_id, schedule_field, rule_version, day_offset, "
            "local_time, timezone, state, created_by_user_id, confirmed_by_user_id, "
            "created_at, updated_at, confirmed_at) VALUES "
            "(?, 'hint_scheduled_at', 1, 4, '12:00', "
            "'Europe/Moscow', 'active', ?, ?, ?, ?, ?) RETURNING id",
            (course_id, actor_id, actor_id, NOW, NOW, NOW),
        ).fetchone()[0]
        stale_override_id = connection.execute(
            "INSERT INTO group_schedule_overrides "
            "(course_id, group_id, schedule_field, override_version, "
            "mode, based_on_schedule_rule_id, state, created_at, updated_at) "
            "VALUES (?, 'schema-a', 'hint_scheduled_at', "
            "1, 'inherit', ?, 'draft', ?, ?) RETURNING id",
            (course_id, hint_rule_id, NOW, NOW),
        ).fetchone()[0]
        connection.execute(
            "UPDATE course_schedule_rules SET state = 'superseded', "
            "superseded_at = ?, updated_at = ?, version = version + 1 WHERE id = ?",
            (NOW, NOW, hint_rule_id),
        )
        with pytest.raises(
            sqlite3.IntegrityError, match="group schedule override base rule is stale"
        ):
            connection.execute(
                "UPDATE group_schedule_overrides SET state = 'active', "
                "confirmed_by_user_id = ?, confirmed_at = ?, updated_at = ?, "
                "version = version + 1 WHERE id = ?",
                (actor_id, NOW, NOW, stale_override_id),
            )
        with pytest.raises(
            sqlite3.IntegrityError,
            match="invalid course schedule rule state transition",
        ):
            connection.execute(
                "UPDATE course_schedule_rules SET superseded_at = ?, "
                "version = version + 1 WHERE id = ?",
                ("2026-09-20T15:00:00.000000Z", hint_rule_id),
            )
