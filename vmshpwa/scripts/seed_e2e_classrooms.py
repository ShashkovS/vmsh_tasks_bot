"""Seed independent classroom-layout events for the three Playwright browsers."""

from __future__ import annotations

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
TARGETS = (
    ("chromium", 9801),
    ("webkit", 9802),
    ("firefox", 9803),
)


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("Classroom E2E seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("Classroom E2E seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("Classroom E2E seed refuses an unknown SQLite target")
    return database_path


def _seed(connection: sqlite3.Connection) -> int:
    actor = connection.execute(
        "SELECT linked_user_id AS id FROM auth_accounts "
        "WHERE audience = 'staff' AND username_normalized = 'synthetic-admin'"
    ).fetchone()
    season = connection.execute(
        "SELECT id FROM seasons WHERE code = '2025-26'"
    ).fetchone()
    course = connection.execute(
        "SELECT id FROM courses WHERE code = 'math-5-7'"
    ).fetchone()
    if actor is None or season is None or course is None:
        raise RuntimeError("Classroom E2E seed requires the baseline seed")
    student_credential = connection.execute(
        "SELECT credential_hash FROM auth_accounts "
        "WHERE audience = 'student' AND username_normalized = 'testovyy-onlayn-14'"
    ).fetchone()
    family_credential = connection.execute(
        "SELECT credential_hash FROM auth_accounts "
        "WHERE audience = 'family' AND username_normalized = 'synthetic-family'"
    ).fetchone()
    if student_credential is None or family_credential is None:
        raise RuntimeError("Classroom E2E seed requires the baseline auth accounts")

    actor_id = int(actor["id"])
    connection.execute(
        "INSERT OR IGNORE INTO audit_events "
        "(actor_user_id, actor_account_id, audience, action, "
        "object_type, object_id, request_id, before_json, after_json, occurred_at) "
        "VALUES (?, "
        "(SELECT id FROM auth_accounts WHERE username_normalized = 'synthetic-admin'), "
        "'staff', 'account.status_changed', 'account', 'a-1001', "
        "'e2e.audit.baseline', '{\"status\":\"blocked\"}', "
        '\'{"status":"active"}\', ?)',
        (actor_id, TIMESTAMP),
    )

    event_ids = [fixture_id for _project, fixture_id in TARGETS]
    room_ids = [fixture_id for _project, fixture_id in TARGETS] + [
        fixture_id + 100 for _project, fixture_id in TARGETS
    ]
    existing_events = {
        row[0]
        for row in connection.execute(
            "SELECT id FROM in_person_events WHERE id IN (?, ?, ?)",
            event_ids,
        )
    }
    existing_rooms = {
        row[0]
        for row in connection.execute(
            f"SELECT id FROM classrooms WHERE id IN "
            f"({','.join('?' for _room_id in room_ids)})",
            tuple(room_ids),
        )
    }
    if existing_events or existing_rooms:
        if existing_events == set(event_ids) and existing_rooms == set(room_ids):
            return 0
        raise RuntimeError("Classroom E2E fixture is only partially present")

    season_id = int(season["id"])
    course_id = int(course["id"])
    for ordinal, (project, fixture_id) in enumerate(TARGETS, start=1):
        group_id = f"classroom-e2e-{project}-n"
        connection.execute(
            "INSERT INTO groups "
            "(id, group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, 1, 0, 0, 0, 1.0, ?, "
            "'active', 'beginner', ?, ?)",
            (
                fixture_id,
                group_id,
                f"e{project[0]}",
                f"Начинающие E2E {project}",
                900 + ordinal,
                course_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(id, course_id, lesson_number, title, created_by_user_id, "
                "updated_by_user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    fixture_id,
                    course_id,
                    950 + ordinal,
                    f"E2E аудитории {project}",
                    actor_id,
                    actor_id,
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
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'Europe/Moscow', 'active', ?, ?, ?, ?) "
                "RETURNING id",
                (
                    fixture_id,
                    course_lesson_id,
                    course_id,
                    group_id,
                    f"2026-08-0{ordinal}",
                    actor_id,
                    actor_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        room_specs = (
            (fixture_id, f"20{ordinal} E2E {project}", "primary"),
            (
                fixture_id + 100,
                f"Переназначение E2E {project}",
                "reassign",
            ),
        )
        for room_fixture_id, room_name, purpose in room_specs:
            room_id = int(
                connection.execute(
                    "INSERT INTO classrooms "
                    "(id, name, normalized_name, status, created_by_user_id, "
                    "updated_by_user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'active', ?, ?, ?, ?) RETURNING id",
                    (
                        room_fixture_id,
                        room_name,
                        room_name.casefold(),
                        actor_id,
                        actor_id,
                        TIMESTAMP,
                        TIMESTAMP,
                    ),
                ).fetchone()["id"]
            )
            connection.execute(
                "INSERT INTO classroom_events "
                "(id, classroom_id, action, after_name, after_normalized_name, "
                "after_status, version_after, actor_user_id, request_id, created_at) "
                "VALUES (?, ?, 'created', ?, ?, 'active', 1, ?, ?, ?)",
                (
                    room_fixture_id,
                    room_id,
                    room_name,
                    room_name.casefold(),
                    actor_id,
                    f"e2e.seed.classroom.{purpose}.{project}",
                    TIMESTAMP,
                ),
            )
        event_id = int(
            connection.execute(
                "INSERT INTO in_person_events "
                "(id, season_id, name, starts_at, ends_at, status, "
                "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'scheduled', ?, ?, ?, ?) RETURNING id",
                (
                    fixture_id,
                    season_id,
                    f"E2E схема аудиторий {project}",
                    f"2026-08-0{ordinal}T13:00:00Z",
                    f"2026-08-0{ordinal}T16:00:00Z",
                    actor_id,
                    actor_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO in_person_event_group_lessons "
            "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (event_id, group_lesson_id, actor_id, TIMESTAMP),
        )
        student_id = int(
            connection.execute(
                "INSERT INTO users "
                "(id, type, name, surname, grade, birthday) "
                "VALUES (?, 1, 'Ученик', ?, 7, '2013-01-01') RETURNING id",
                (fixture_id + 200, f"Тестов {project}"),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO auth_accounts "
            "(id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, display_name, "
            "credential_kind, credential_hash, linked_user_id, status, "
            "credential_version, created_at, updated_at) "
            "VALUES (?, 'student', ?, ?, 1, 'synthetic_e2e_classroom', ?, "
            "'telegram_token', ?, ?, 'active', 1, ?, ?)",
            (
                fixture_id + 300,
                f"classroom-e2e-{project}",
                f"classroom-e2e-{project}",
                f"Тестов {project} Ученик",
                str(student_credential["credential_hash"]),
                student_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        family_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, display_name, "
                "credential_kind, credential_hash, linked_user_id, status, "
                "credential_version, created_at, updated_at) "
                "VALUES (?, 'family', ?, ?, NULL, 'synthetic_e2e_classroom', ?, "
                "'password', ?, NULL, 'active', 1, ?, ?) RETURNING id",
                (
                    fixture_id + 400,
                    f"classroom-family-e2e-{project}",
                    f"classroom-family-e2e-{project}",
                    f"Семья classroom E2E {project}",
                    str(family_credential["credential_hash"]),
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at) VALUES (?, ?, 'родитель', 1, ?, ?)",
            (family_account_id, student_id, TIMESTAMP, TIMESTAMP),
        )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'in_person', 'active', ?, ?) RETURNING id",
                (
                    fixture_id + 500,
                    student_id,
                    course_id,
                    group_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, granted_by, "
            "reason, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                enrollment_id,
                course_id,
                group_id,
                TIMESTAMP,
                actor_id,
                "e2e_classroom_seed",
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "INSERT INTO student_strength (student_id, simple_prob, compl_prob) "
            "VALUES (?, 0.5, 1.0)",
            (student_id,),
        )
        unprovisioned_id = int(
            connection.execute(
                "INSERT INTO users "
                "(id, type, name, surname, grade, birthday, token) "
                "VALUES (?, 1, 'Новый', ?, 6, '2013-05-17', ?) RETURNING id",
                (
                    fixture_id + 600,
                    f"БезАккаунта {project}",
                    f"synthetic-provision-{project}-not-a-secret",
                ),
            ).fetchone()["id"]
        )
        unprovisioned_enrollment = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'online', 'active', ?, ?) RETURNING id",
                (
                    fixture_id + 700,
                    unprovisioned_id,
                    course_id,
                    group_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, granted_by, "
            "reason, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                unprovisioned_enrollment,
                course_id,
                group_id,
                TIMESTAMP,
                actor_id,
                "e2e_student_account_seed",
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        if project == "chromium":
            connection.executemany(
                "INSERT INTO users "
                "(id, type, name, surname, grade, birthday, token) "
                "VALUES (?, 1, ?, ?, 6, ?, ?)",
                (
                    (
                        9991,
                        "Первый",
                        "Пакет Chromium",
                        "2013-05-18",
                        "synthetic-batch-one-not-secret",
                    ),
                    (
                        9992,
                        "Второй",
                        "Пакет Chromium",
                        "2013-05-19",
                        "synthetic-batch-two-not-secret",
                    ),
                ),
            )
    return len(TARGETS)


def seed_e2e_classrooms(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        inserted = _seed(connection)
    print(f"Seeded E2E classroom events: inserted={inserted}")
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_classrooms accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Classroom E2E seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Classroom E2E seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_classrooms(config)


if __name__ == "__main__":
    main()
