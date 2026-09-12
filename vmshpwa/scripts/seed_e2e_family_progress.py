"""Add independent two-child Family personas for the Phase-9 browser proof."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from db_methods.pwa import maintenance_database_lock
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"
TIMESTAMP = "2026-07-30T12:00:00Z"
TARGETS = (
    ("chromium", 10404, 10601),
    ("webkit", 10405, 10602),
    ("firefox", 10406, 10603),
)


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("Family E2E seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("Family E2E seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("Family E2E seed refuses an unknown SQLite target")
    return database_path


def _seed(connection: sqlite3.Connection) -> int:
    course = connection.execute(
        "SELECT id FROM courses WHERE id = 1"
    ).fetchone()
    groups = {
        int(row["id"]): str(row["group_id"])
        for row in connection.execute(
            "SELECT id, group_id FROM groups WHERE id IN (1, 2)"
        )
    }
    admin = connection.execute(
        "SELECT id FROM users WHERE id = 301"
    ).fetchone()
    if course is None or admin is None or len(groups) != 2:
        raise RuntimeError("Family E2E seed requires baseline course and groups")

    expected_students = {student_id for _project, student_id, _enrollment_id in TARGETS}
    existing_students = {
        int(row[0])
        for row in connection.execute(
            "SELECT id FROM users WHERE id IN (?, ?, ?)",
            tuple(sorted(expected_students)),
        )
    }
    if existing_students:
        if existing_students == expected_students:
            return 0
        raise RuntimeError("Family E2E fixture is only partially present")

    course_id = int(course["id"])
    admin_id = int(admin["id"])
    beginner = groups[1]
    continuing = groups[2]

    for project, second_student_id, second_enrollment_id in TARGETS:
        first_student = connection.execute(
            "SELECT linked_user_id AS id FROM auth_accounts "
            "WHERE audience = 'student' AND username_normalized = ?",
            (f"classroom-e2e-{project}",),
        ).fetchone()
        family_account = connection.execute(
            "SELECT id FROM auth_accounts "
            "WHERE audience = 'family' AND username_normalized = ?",
            (f"classroom-family-e2e-{project}",),
        ).fetchone()
        first_enrollment = connection.execute(
            "SELECT id FROM course_enrollments "
            "WHERE student_user_id = ? AND course_id = ?",
            (int(first_student["id"]) if first_student is not None else None, course_id),
        ).fetchone()
        if first_student is None or family_account is None or first_enrollment is None:
            raise RuntimeError("Family E2E seed requires classroom personas")

        connection.executemany(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, granted_by, reason, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'e2e_family_seed', ?, ?)",
            [
                (
                    int(first_enrollment["id"]),
                    course_id,
                    group_id,
                    TIMESTAMP,
                    admin_id,
                    TIMESTAMP,
                    TIMESTAMP,
                )
                for group_id in (beginner, continuing)
            ],
        )

        connection.execute(
            "INSERT INTO users "
            "(id, type, group_id, name, surname, online, grade, birthday, "
            "allowed_groups) VALUES (?, 1, ?, 'Второй', ?, 1, 5, '2015-05-05', ?)",
            (
                second_student_id,
                continuing,
                f"Ребёнок {project}",
                f";{beginner};{continuing};",
            ),
        )
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at) VALUES (?, ?, 'родитель', 0, ?, ?)",
            (int(family_account["id"]), second_student_id, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO course_enrollments "
            "(id, student_user_id, course_id, active_group_id, attendance_mode, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, 'online', 'active', ?, ?)",
            (
                second_enrollment_id,
                second_student_id,
                course_id,
                continuing,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.executemany(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, granted_by, reason, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'e2e_family_seed', ?, ?)",
            [
                (
                    second_enrollment_id,
                    course_id,
                    group_id,
                    TIMESTAMP,
                    admin_id,
                    TIMESTAMP,
                    TIMESTAMP,
                )
                for group_id in (beginner, continuing)
            ],
        )
    return len(TARGETS)


def seed_e2e_family_progress(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with maintenance_database_lock(database_path):
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            inserted = _seed(connection)
    print(f"Seeded Phase-9 Family E2E personas: inserted={inserted}")
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_family_progress accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Family E2E seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Family E2E seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_family_progress(config)


if __name__ == "__main__":
    main()
