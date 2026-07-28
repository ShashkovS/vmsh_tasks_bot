from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from db_methods.pwa import apply_schema_migrations
from vmshpwa.scripts.seed_e2e_content import (
    EXPECTED_DATABASE,
    _insert_content_fixture,
    _load_fixture,
    _require_e2e_target,
    _validate_fixture,
)


def _seed_owners(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO users (id, public_id, type, name, surname) "
        "VALUES (301, 'user-admin-fixture', 128, 'E2E', 'Admin')"
    )
    connection.execute(
        "INSERT INTO seasons "
        "(id, public_id, code, title, starts_on, ends_on, session_expires_on, "
        "status, created_at, updated_at) VALUES "
        "(1, 'season-e2e', 'e2e', 'E2E', '2026-01-01', '2026-12-31', "
        "'2027-08-10', 'active', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    connection.execute(
        "INSERT INTO courses "
        "(id, public_id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(1, 'course-fixture-math-5-7', 1, 'math', 'Math', 'math', 'active', 1, "
        "'math', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, public_id, course_id, status, "
        "created_at, updated_at) VALUES "
        "('n', 'n', 'Beginners', 1, 1, 1, 1, 0, 1.0, "
        "'group-fixture-beginner', 1, 'active', "
        "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )


def test_fixture_has_one_independent_target_per_browser():
    fixture = _load_fixture()

    for key in ("targets", "submissionTargets"):
        assert {target["project"] for target in fixture[key]} == {
            "chromium",
            "webkit",
            "firefox",
        }
        assert len({target["lessonNumber"] for target in fixture[key]}) == 3
        assert len({target["groupLessonPublicId"] for target in fixture[key]}) == 3

    all_targets = [*fixture["targets"], *fixture["submissionTargets"]]
    assert len({target["lessonNumber"] for target in all_targets}) == 6
    assert len({target["groupLessonPublicId"] for target in all_targets}) == 6


def test_fixture_rejects_duplicate_project():
    fixture = _load_fixture()
    fixture["targets"][1]["project"] = fixture["targets"][0]["project"]

    with pytest.raises(ValueError, match="every browser exactly once"):
        _validate_fixture(fixture)


def test_fixture_rejects_identity_reused_between_phase_targets():
    fixture = _load_fixture()
    fixture["submissionTargets"][0]["groupLessonPublicId"] = fixture["targets"][0][
        "groupLessonPublicId"
    ]

    with pytest.raises(ValueError, match="non-empty and unique"):
        _validate_fixture(fixture)


def test_fixture_insert_is_atomic_and_idempotent(tmp_path):
    database_path = tmp_path / "content-e2e.sqlite3"
    apply_schema_migrations(database_path)
    connection = sqlite3.connect(database_path, autocommit=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _seed_owners(connection)
        fixture = _load_fixture()
        assert _insert_content_fixture(connection, fixture) == 6
        assert _insert_content_fixture(connection, fixture) == 0
        assert (
            connection.execute("SELECT count(*) FROM course_lessons").fetchone()[0] == 6
        )
        assert (
            connection.execute("SELECT count(*) FROM group_lessons").fetchone()[0] == 6
        )
        assert (
            connection.execute("SELECT count(*) FROM lesson_windows").fetchone()[0] == 3
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM lesson_windows AS window "
                "JOIN group_lessons AS lesson ON lesson.id = window.group_lesson_id "
                "WHERE lesson.public_id LIKE 'group-lesson-submission-e2e-%'"
            ).fetchone()[0]
            == 3
        )
        connection.commit()
    finally:
        connection.close()


def test_seed_target_rejects_every_non_e2e_profile():
    with pytest.raises(RuntimeError, match="only in pwa-e2e"):
        _require_e2e_target(
            SimpleNamespace(
                runtime_profile="pwa-agent",
                pwa_instance="agent",
                db_filename=str(EXPECTED_DATABASE),
                pwa_media_root=".runtime/vmshpwa/agent",
            )
        )
