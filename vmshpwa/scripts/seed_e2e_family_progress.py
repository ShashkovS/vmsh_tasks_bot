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
PROJECTS = ("chromium", "webkit", "firefox")


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
        "SELECT id FROM courses WHERE public_id = 'course-fixture-math-5-7'"
    ).fetchone()
    groups = {
        str(row["public_id"]): str(row["group_id"])
        for row in connection.execute(
            "SELECT public_id, group_id FROM groups WHERE public_id IN "
            "('group-fixture-beginner', 'group-fixture-continuing')"
        )
    }
    admin = connection.execute(
        "SELECT id FROM users WHERE public_id = 'user-admin-fixture'"
    ).fetchone()
    if course is None or admin is None or len(groups) != 2:
        raise RuntimeError("Family E2E seed requires baseline course and groups")

    expected_students = {f"student-family-second-e2e-{project}" for project in PROJECTS}
    existing_students = {
        str(row[0])
        for row in connection.execute(
            "SELECT public_id FROM users WHERE public_id LIKE "
            "'student-family-second-e2e-%'"
        )
    }
    if existing_students:
        if existing_students == expected_students:
            return 0
        raise RuntimeError("Family E2E fixture is only partially present")

    course_id = int(course["id"])
    admin_id = int(admin["id"])
    beginner = groups["group-fixture-beginner"]
    continuing = groups["group-fixture-continuing"]

    for project in PROJECTS:
        first_student = connection.execute(
            "SELECT id FROM users WHERE public_id = ?",
            (f"student-classroom-e2e-{project}",),
        ).fetchone()
        family_account = connection.execute(
            "SELECT id FROM auth_accounts WHERE public_id = ?",
            (f"account-classroom-family-e2e-{project}",),
        ).fetchone()
        first_enrollment = connection.execute(
            "SELECT id FROM course_enrollments WHERE public_id = ?",
            (f"enrollment-classroom-e2e-{project}",),
        ).fetchone()
        if first_student is None or family_account is None or first_enrollment is None:
            raise RuntimeError("Family E2E seed requires classroom personas")

        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, granted_by, reason, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'e2e_family_seed', ?, ?)",
            (
                int(first_enrollment["id"]),
                course_id,
                continuing,
                TIMESTAMP,
                admin_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )

        second_student_id = int(
            connection.execute(
                "INSERT INTO users "
                "(public_id, type, group_id, name, surname, online, grade, birthday, "
                "allowed_groups) VALUES (?, 1, ?, 'Второй', ?, 1, 5, '2015-05-05', ?) "
                "RETURNING id",
                (
                    f"student-family-second-e2e-{project}",
                    continuing,
                    f"Ребёнок {project}",
                    f";{beginner};{continuing};",
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at) VALUES (?, ?, 'родитель', 0, ?, ?)",
            (int(family_account["id"]), second_student_id, TIMESTAMP, TIMESTAMP),
        )
        second_enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(public_id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'online', 'active', ?, ?) RETURNING id",
                (
                    f"enrollment-family-second-e2e-{project}",
                    second_student_id,
                    course_id,
                    continuing,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
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
    return len(PROJECTS)


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
