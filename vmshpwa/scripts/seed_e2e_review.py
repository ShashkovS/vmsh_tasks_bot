"""Seed one independent live Staff review case per Playwright browser."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path

from db_methods.pwa import PwaConnectionFactory, maintenance_database_lock
from helpers.object_storage import LocalObjectStorage
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"
EXPECTED_MEDIA_ROOT = REPOSITORY_ROOT / ".runtime/vmshpwa/e2e"
TIMESTAMP = "2026-07-28T12:00:00Z"
REVIEW_WEBP = base64.b64decode(
    "UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEALmk0mk0iIiIiIgBoSywA"
)
TARGETS = (
    ("chromium", 9701),
    ("webkit", 9702),
    ("firefox", 9703),
)


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("Phase-6 review seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("Phase-6 review seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("Phase-6 review seed refuses an unknown SQLite target")
    media_root = Path(runtime_config.pwa_media_root)
    if not media_root.is_absolute():
        media_root = REPOSITORY_ROOT / media_root
    if media_root.absolute() != EXPECTED_MEDIA_ROOT:
        raise RuntimeError("Phase-6 review seed refuses an unknown media target")
    return database_path


async def _put_review_media(media_root: Path) -> None:
    storage = LocalObjectStorage(media_root)
    for project, _lesson_number in TARGETS:
        await storage.put(
            f"submission/e2e-review-{project}.webp",
            REVIEW_WEBP,
            "image/webp",
        )


def _insert_review_cases(connection) -> int:
    course = connection.execute(
        "SELECT id FROM courses WHERE code = 'math-5-7'"
    ).fetchone()
    student = connection.execute(
        "SELECT linked_user_id FROM auth_accounts "
        "WHERE audience = 'student' AND username_normalized = 'testovyy-onlayn-14'"
    ).fetchone()
    teacher = connection.execute(
        "SELECT linked_user_id FROM auth_accounts "
        "WHERE audience = 'staff' AND username_normalized = 'synthetic-teacher'"
    ).fetchone()
    if course is None or student is None or teacher is None:
        raise RuntimeError("Phase-6 E2E review seed requires the baseline accounts")
    course_id = int(course["id"])
    group_id = str(
        connection.execute(
            "SELECT group_id FROM groups WHERE group_id = 'н'"
        ).fetchone()["group_id"]
    )
    student_id = int(student["linked_user_id"])
    teacher_id = int(teacher["linked_user_id"])
    connection.execute(
        "INSERT INTO course_runtime_settings "
        "(course_id, schema_version, values_json, updated_by_user_id, updated_at) "
        "VALUES (?, 1, ?, ?, ?) "
        "ON CONFLICT(course_id) DO UPDATE SET values_json = excluded.values_json, "
        "updated_by_user_id = excluded.updated_by_user_id, updated_at = excluded.updated_at",
        (
            course_id,
            json.dumps(
                {
                    "verdictMode": "verdict_plus_steps",
                    "resultMode": "res_immed",
                    "previousLessonsMode": "prev_problems_show_all",
                    "testAttemptRateLimit": "rate_limit_3_and_6",
                },
                separators=(",", ":"),
            ),
            teacher_id,
            TIMESTAMP,
        ),
    )

    existing = connection.execute(
        "SELECT id FROM written_tasks_queue WHERE id BETWEEN 9701 AND 9703"
    ).fetchall()
    expected_queue_ids = {fixture_id for _project, fixture_id in TARGETS}
    if existing:
        existing_ids = {int(row["id"]) for row in existing}
        if existing_ids == expected_queue_ids:
            return 0
        raise RuntimeError("Phase-6 E2E review fixture is only partially present")

    inserted = 0
    for ordinal, (project, fixture_id) in enumerate(TARGETS, start=1):
        lesson_number = fixture_id
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(id, course_id, lesson_number, title, created_by_user_id, "
                "updated_by_user_id, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    fixture_id,
                    course_id,
                    lesson_number,
                    f"E2E проверка {project}",
                    teacher_id,
                    teacher_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        group_lesson_id = int(
            connection.execute(
                "INSERT INTO group_lessons "
                "(id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
                "business_timezone, status, created_by_user_id, updated_by_user_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, '2026-07-28', "
                "'Europe/Moscow', 'active', ?, ?, ?, ?) RETURNING id",
                (
                    fixture_id,
                    course_lesson_id,
                    course_id,
                    group_id,
                    teacher_id,
                    teacher_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        source_id = int(
            connection.execute(
                "INSERT INTO content_sources "
                "(id, group_lesson_id, kind, logical_filename, source_encoding, "
                "created_by_user_id, created_at) VALUES (?, ?, 'condition', ?, 'utf-8', "
                "?, ?) RETURNING id",
                (
                    fixture_id,
                    group_lesson_id,
                    f"e2e-review-{project}.tex",
                    teacher_id,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        revision_id = int(
            connection.execute(
                "INSERT INTO content_revisions "
                "(id, source_id, revision_number, source_sha256, latex_text, "
                "parser_version, status, canonical_json, diagnostics_json, "
                "provenance_json, created_by_user_id, created_at) VALUES "
                "(?, ?, 1, ?, 'Тестовая задача', 'review-e2e-v1', 'ready', '{}', "
                "'[]', '{}', ?, ?) RETURNING id",
                (
                    fixture_id,
                    source_id,
                    f"{ordinal}" * 64,
                    teacher_id,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(id, group_id, lesson, prob, item, title, prob_text, prob_type, ans_type, "
                "ans_validation, validation_error, cor_ans, wrong_ans, congrat, synonyms) "
                "VALUES (?, ?, ?, 1, '', ?, '', 2, 0, '', '', '', '', '', '') "
                "RETURNING id",
                (
                    fixture_id,
                    group_id,
                    lesson_number,
                    f"E2E проверка {project}",
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, decision, "
            "resolved_by_user_id, resolved_at, diagnostics_json, created_at) VALUES "
            "(?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
            (revision_id, problem_id, teacher_id, TIMESTAMP, TIMESTAMP),
        )
        problem_revision_id = int(
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, answer_type, "
                "answer_config_json, attempt_policy_json, config_version, created_at) "
                "VALUES (?, ?, 1, '1', ?, ?, ?, 2, 0, '{}', '{}', 1, ?) RETURNING id",
                (
                    problem_id,
                    revision_id,
                    f"{lesson_number}н.1",
                    f"E2E проверка {project}",
                    f"e2e проверка {project}",
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        thread_id = int(
            connection.execute(
                "INSERT INTO submission_threads "
                "(id, student_user_id, problem_id, condition_revision_id, status, "
                "latest_entry_at, created_at, updated_at, version) VALUES "
                "(?, ?, ?, ?, 'awaiting_review', ?, ?, ?, 3) RETURNING id",
                (
                    fixture_id,
                    student_id,
                    problem_id,
                    revision_id,
                    "2026-07-28T12:02:00Z",
                    TIMESTAMP,
                    "2026-07-28T12:02:00Z",
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO submission_entries "
            "(id, thread_id, problem_revision_id, author_kind, author_user_id, "
            "channel, entry_kind, state, text, client_created_at, server_received_at, "
            "locked_at, version) VALUES (?, ?, ?, 'teacher', ?, 'pwa', "
            "'teacher_comment', 'locked', 'Поясните, почему этот переход верен.', ?, ?, ?, 1)",
            (
                fixture_id * 10 + 1,
                thread_id,
                problem_revision_id,
                teacher_id,
                TIMESTAMP,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        student_entry_id = int(
            connection.execute(
                "INSERT INTO submission_entries "
                "(id, thread_id, problem_revision_id, author_kind, author_user_id, "
                "channel, entry_kind, state, text, client_created_at, server_received_at, "
                "version) VALUES (?, ?, ?, 'student', ?, 'pwa', 'submission', 'submitted', "
                "'Я дописал объяснение перехода и проверил крайний случай.', ?, ?, 2) "
                "RETURNING id",
                (
                    fixture_id * 10 + 2,
                    thread_id,
                    problem_revision_id,
                    student_id,
                    "2026-07-28T12:02:00Z",
                    "2026-07-28T12:02:00Z",
                ),
            ).fetchone()["id"]
        )
        asset_id = int(
            connection.execute(
                "INSERT INTO media_assets "
                "(id, sha256, storage_namespace, object_key, media_type, "
                "byte_size, width, height, source_filename, conversion_version, "
                "created_by_user_id, created_at) VALUES (?, ?, 'submission', ?, "
                "'image/webp', ?, 1, 1, 'e2e-review.webp', "
                "'pwa-written-image-v1', ?, ?) RETURNING id",
                (
                    fixture_id,
                    hashlib.sha256(REVIEW_WEBP).hexdigest(),
                    f"submission/e2e-review-{project}.webp",
                    len(REVIEW_WEBP),
                    student_id,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO submission_attachments "
            "(id, entry_id, asset_id, ordinal, client_filename, upload_status, "
            "created_at) VALUES (?, ?, ?, 0, 'e2e-review.webp', 'stored', ?)",
            (
                fixture_id,
                student_entry_id,
                asset_id,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "INSERT INTO written_tasks_queue "
            "(id, ts, student_id, problem_id, cur_status, updated_at) VALUES "
            "(?, '2026-07-28T12:02:00Z', ?, ?, 0, ?)",
            (fixture_id, student_id, problem_id, TIMESTAMP),
        )
        inserted += 1
    return inserted


def seed_e2e_review(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with maintenance_database_lock(database_path):
        asyncio.run(_put_review_media(EXPECTED_MEDIA_ROOT))
        database = PwaConnectionFactory(database_path)
        inserted = database.run_write(_insert_review_cases)
    print(f"Seeded E2E review cases: targets={len(TARGETS)} inserted={inserted}")
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_review accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Phase-6 E2E review seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Phase-6 review seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_review(config)


if __name__ == "__main__":
    main()
