"""Seed one independent oral lesson for each Playwright browser."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"
TIMESTAMP = "2026-07-29T12:00:00Z"
TARGETS = (("chromium", 921), ("webkit", 922), ("firefox", 923))


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("Oral E2E seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("Oral E2E seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("Oral E2E seed refuses an unknown SQLite target")
    return database_path


def _web_document(*, revision_id: str, source_sha256: str, title: str) -> str:
    return json.dumps(
        {
            "contractVersion": 1,
            "revisionId": revision_id,
            "sourceSha256": source_sha256,
            "materialKind": "condition",
            "title": None,
            "introduction": [],
            "problems": [
                {
                    "ordinal": 1,
                    "sourceItem": "1",
                    "title": title,
                    "blocks": [
                        {
                            "type": "paragraph",
                            "children": [
                                {
                                    "type": "text",
                                    "value": "Расскажите решение преподавателю или отправьте его письменно.",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _seed(connection: sqlite3.Connection) -> int:
    existing_lessons = {
        row["public_id"]
        for row in connection.execute(
            "SELECT public_id FROM group_lessons WHERE public_id IN (?, ?, ?)",
            tuple(f"e2e-oral-group-lesson-{project}" for project, _number in TARGETS),
        )
    }
    existing_windows = {
        row["public_id"]
        for row in connection.execute(
            "SELECT public_id FROM oral_windows WHERE public_id IN (?, ?, ?)",
            tuple(f"e2e-oral-window-{project}" for project, _number in TARGETS),
        )
    }
    expected_lessons = {
        f"e2e-oral-group-lesson-{project}" for project, _number in TARGETS
    }
    expected_windows = {f"e2e-oral-window-{project}" for project, _number in TARGETS}
    if existing_lessons or existing_windows:
        if (
            existing_lessons == expected_lessons
            and existing_windows == expected_windows
        ):
            return 0
        raise RuntimeError("Oral E2E fixture is only partially present")

    course = connection.execute(
        "SELECT id FROM courses WHERE public_id = 'course-fixture-math-5-7'"
    ).fetchone()
    admin = connection.execute(
        "SELECT id FROM users WHERE public_id = 'user-admin-fixture'"
    ).fetchone()
    group = connection.execute(
        "SELECT group_id, course_id FROM groups "
        "WHERE public_id = 'group-fixture-beginner'"
    ).fetchone()
    if course is None or admin is None or group is None:
        raise RuntimeError("Oral E2E seed requires baseline course, group and admin")
    course_id = int(course["id"])
    admin_id = int(admin["id"])
    if int(group["course_id"]) != course_id:
        raise RuntimeError("Oral E2E group belongs to another course")
    group_id = str(group["group_id"])

    for ordinal, (project, lesson_number) in enumerate(TARGETS, start=1):
        title = f"Устная E2E {project}"
        source = f"{title}: расскажите решение преподавателю."
        source_sha256 = hashlib.sha256(source.encode()).hexdigest()
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(public_id, course_id, lesson_number, title, created_by_user_id, "
                "updated_by_user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "RETURNING id",
                (
                    f"e2e-oral-course-lesson-{project}",
                    course_id,
                    lesson_number,
                    title,
                    admin_id,
                    admin_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        group_lesson_id = int(
            connection.execute(
                "INSERT INTO group_lessons "
                "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
                "business_timezone, status, created_by_user_id, updated_by_user_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, '2026-07-29', "
                "'Europe/Moscow', 'active', ?, ?, ?, ?) RETURNING id",
                (
                    f"e2e-oral-group-lesson-{project}",
                    course_lesson_id,
                    course_id,
                    group_id,
                    admin_id,
                    admin_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        source_id = int(
            connection.execute(
                "INSERT INTO content_sources "
                "(public_id, group_lesson_id, kind, logical_filename, source_encoding, "
                "created_by_user_id, created_at) VALUES (?, ?, 'condition', ?, 'utf-8', ?, ?) "
                "RETURNING id",
                (
                    f"e2e-oral-source-{project}",
                    group_lesson_id,
                    f"e2e-oral-{project}.tex",
                    admin_id,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        revision_public_id = f"e2e-oral-revision-{project}"
        revision_id = int(
            connection.execute(
                "INSERT INTO content_revisions "
                "(public_id, source_id, revision_number, source_sha256, latex_text, "
                "parser_version, status, canonical_json, diagnostics_json, provenance_json, "
                "created_by_user_id, created_at) VALUES (?, ?, 1, ?, ?, 'oral-e2e-v1', "
                "'ready', ?, '[]', '{}', ?, ?) RETURNING id",
                (
                    revision_public_id,
                    source_id,
                    source_sha256,
                    source,
                    _web_document(
                        revision_id=revision_public_id,
                        source_sha256=source_sha256,
                        title=title,
                    ),
                    admin_id,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        web_document = _web_document(
            revision_id=revision_public_id,
            source_sha256=source_sha256,
            title=title,
        )
        connection.execute(
            "INSERT INTO content_derivatives "
            "(revision_id, kind, renderer_version, content_text, sha256, "
            "diagnostics_json, provenance_json, created_at) "
            "VALUES (?, 'web_ast', 'oral-e2e-v1', ?, ?, '[]', '{}', ?)",
            (
                revision_id,
                web_document,
                hashlib.sha256(web_document.encode()).hexdigest(),
                TIMESTAMP,
            ),
        )
        problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, ans_type, "
                "ans_validation, validation_error, cor_ans, wrong_ans, congrat, synonyms, "
                "public_id) VALUES (?, ?, 1, '', ?, ?, 3, 0, '', '', '', '', '', '', ?) "
                "RETURNING id",
                (
                    group_id,
                    lesson_number,
                    title,
                    source,
                    f"e2e-oral-problem-{project}",
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, decision, "
            "resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
            "VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
            (revision_id, problem_id, admin_id, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, display_number, "
            "title, normalized_title, problem_type, answer_type, answer_config_json, "
            "attempt_policy_json, config_version, created_at) "
            "VALUES (?, ?, 1, '1', '1', ?, ?, 3, NULL, '{}', '{}', 1, ?)",
            (problem_id, revision_id, title, title.casefold(), TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO lesson_windows "
            "(public_id, group_lesson_id, opens_at, submission_closes_at, timezone, source, "
            "created_by_user_id, updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, '2026-01-01T00:00:00Z', '2027-08-10T00:00:00Z', "
            "'Europe/Moscow', 'native', ?, ?, ?, ?)",
            (
                f"e2e-oral-lesson-window-{project}",
                group_lesson_id,
                admin_id,
                admin_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "INSERT INTO lesson_publications "
            "(public_id, group_lesson_id, kind, revision_id, state, published_at, "
            "created_by_user_id, published_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, 'condition', ?, 'published', ?, ?, ?, ?, ?)",
            (
                f"e2e-oral-publication-{project}",
                group_lesson_id,
                revision_id,
                TIMESTAMP,
                admin_id,
                admin_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "INSERT INTO oral_windows "
            "(public_id, group_lesson_id, sequence_number, opens_at, closes_at, join_label, "
            "join_url, join_code, status, created_by_user_id, updated_by_user_id, "
            "created_at, updated_at) VALUES (?, ?, 1, '2026-01-01T00:00:00Z', "
            "'2027-08-10T00:00:00Z', 'Подключиться к Zoom', ?, ?, 'active', ?, ?, ?, ?)",
            (
                f"e2e-oral-window-{project}",
                group_lesson_id,
                f"https://zoom.example.test/j/{ordinal}",
                f"17990{ordinal}",
                admin_id,
                admin_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
    return len(TARGETS)


def seed_e2e_oral(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        inserted = _seed(connection)
    print(f"Seeded E2E oral lessons: inserted={inserted}")
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_oral accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Oral E2E seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Oral E2E seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_oral(config)


if __name__ == "__main__":
    main()
