"""Seed one independent live Staff review case per Playwright browser."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from db_methods.pwa import PwaConnectionFactory, maintenance_database_lock
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"
TIMESTAMP = "2026-07-28T12:00:00Z"
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
    return database_path


def _required_id(connection, table: str, public_id: str) -> int:
    if table not in {"courses", "users"}:
        raise ValueError("unsupported E2E review owner table")
    row = connection.execute(
        f"SELECT id FROM {table} WHERE public_id = ?",  # noqa: S608 - allowlisted table
        (public_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Phase-6 E2E review owner is missing: {public_id}")
    return int(row["id"])


def _insert_review_cases(connection) -> int:
    existing = connection.execute(
        "SELECT public_id FROM written_tasks_queue WHERE public_id LIKE 'e2e-review-queue-%'"
    ).fetchall()
    expected_queue_ids = {f"e2e-review-queue-{project}" for project, _lesson in TARGETS}
    if existing:
        existing_ids = {str(row["public_id"]) for row in existing}
        if existing_ids == expected_queue_ids:
            return 0
        raise RuntimeError("Phase-6 E2E review fixture is only partially present")

    course_id = _required_id(connection, "courses", "course-fixture-math-5-7")
    group_id = str(
        connection.execute(
            "SELECT group_id FROM groups WHERE public_id = 'group-fixture-beginner'"
        ).fetchone()["group_id"]
    )
    student_id = _required_id(connection, "users", "user-student-online-fixture")
    teacher_id = _required_id(connection, "users", "user-staff-fixture")

    inserted = 0
    for ordinal, (project, lesson_number) in enumerate(TARGETS, start=1):
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(public_id, course_id, lesson_number, title, created_by_user_id, "
                "updated_by_user_id, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    f"e2e-review-course-lesson-{project}",
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
                "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
                "business_timezone, status, created_by_user_id, updated_by_user_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, '2026-07-28', "
                "'Europe/Moscow', 'active', ?, ?, ?, ?) RETURNING id",
                (
                    f"e2e-review-group-lesson-{project}",
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
                "(public_id, group_lesson_id, kind, logical_filename, source_encoding, "
                "created_by_user_id, created_at) VALUES (?, ?, 'condition', ?, 'utf-8', "
                "?, ?) RETURNING id",
                (
                    f"e2e-review-source-{project}",
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
                "(public_id, source_id, revision_number, source_sha256, latex_text, "
                "parser_version, status, canonical_json, diagnostics_json, "
                "provenance_json, created_by_user_id, created_at) VALUES "
                "(?, ?, 1, ?, 'Тестовая задача', 'review-e2e-v1', 'ready', '{}', "
                "'[]', '{}', ?, ?) RETURNING id",
                (
                    f"e2e-review-revision-{project}",
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
                "(group_id, lesson, prob, item, title, prob_text, prob_type, ans_type, "
                "ans_validation, validation_error, cor_ans, wrong_ans, congrat, synonyms, "
                "public_id) VALUES (?, ?, 1, '', ?, '', 2, 0, '', '', '', '', '', '', ?) "
                "RETURNING id",
                (
                    group_id,
                    lesson_number,
                    f"E2E проверка {project}",
                    f"e2e-review-problem-{project}",
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
                "(public_id, student_user_id, problem_id, condition_revision_id, status, "
                "latest_entry_at, created_at, updated_at, version) VALUES "
                "(?, ?, ?, ?, 'awaiting_review', ?, ?, ?, 3) RETURNING id",
                (
                    f"e2e-review-thread-{project}",
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
            "(public_id, thread_id, problem_revision_id, author_kind, author_user_id, "
            "channel, entry_kind, state, text, client_created_at, server_received_at, "
            "locked_at, version) VALUES (?, ?, ?, 'teacher', ?, 'pwa', "
            "'teacher_comment', 'locked', 'Поясните, почему этот переход верен.', ?, ?, ?, 1)",
            (
                f"e2e-review-teacher-entry-{project}",
                thread_id,
                problem_revision_id,
                teacher_id,
                TIMESTAMP,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "INSERT INTO submission_entries "
            "(public_id, thread_id, problem_revision_id, author_kind, author_user_id, "
            "channel, entry_kind, state, text, client_created_at, server_received_at, "
            "version) VALUES (?, ?, ?, 'student', ?, 'pwa', 'submission', 'submitted', "
            "'Я дописал объяснение перехода и проверил крайний случай.', ?, ?, 2)",
            (
                f"e2e-review-student-entry-{project}",
                thread_id,
                problem_revision_id,
                student_id,
                "2026-07-28T12:02:00Z",
                "2026-07-28T12:02:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO written_tasks_queue "
            "(public_id, ts, student_id, problem_id, cur_status, updated_at) VALUES "
            "(?, '2026-07-28T12:02:00Z', ?, ?, 0, ?)",
            (f"e2e-review-queue-{project}", student_id, problem_id, TIMESTAMP),
        )
        inserted += 1
    return inserted


def seed_e2e_review(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with maintenance_database_lock(database_path):
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
