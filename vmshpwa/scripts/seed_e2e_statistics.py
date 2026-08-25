"""Seed one immutable Staff statistics snapshot in the guarded E2E SQLite."""

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
RUN_ID = 9601
RUN_PUBLIC_ID = f"ar-{RUN_ID}"
COMPLETED_AT = "2026-08-02T12:15:00Z"


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("Statistics E2E seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("Statistics E2E seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("Statistics E2E seed refuses an unknown SQLite target")
    return database_path


def _seed(connection: sqlite3.Connection) -> int:
    existing = connection.execute(
        "SELECT id FROM analytics_runs WHERE public_id = ?", (RUN_PUBLIC_ID,)
    ).fetchone()
    if existing is not None:
        count = connection.execute(
            "SELECT count(*) FROM student_lesson_metrics WHERE run_id = ?",
            (existing["id"],),
        ).fetchone()[0]
        if count != 4:
            raise RuntimeError("Statistics E2E fixture is only partially present")
        return 0

    course = connection.execute(
        "SELECT id FROM courses WHERE public_id = 'c-1'"
    ).fetchone()
    students = connection.execute(
        "SELECT id, group_id FROM users WHERE public_id IN "
        "('u-101', 'u-102') "
        "ORDER BY id"
    ).fetchall()
    if course is None or len(students) != 2:
        raise RuntimeError("Statistics E2E seed requires baseline course and students")

    run_id = connection.execute(
        "INSERT INTO analytics_runs "
        "(id, course_id, algorithm, algorithm_version, input_through_result_id, "
        "state, started_at, completed_at) "
        "VALUES (?, ?, 'a53-compatible', '1', 179, 'completed', ?, ?) RETURNING id",
        (RUN_ID, int(course["id"]), COMPLETED_AT, COMPLETED_AT),
    ).fetchone()["id"]
    rows = []
    for lesson_number, solved_by_student in ((40, (2, 3)), (41, (4, 5))):
        for student, solved in zip(students, solved_by_student, strict=True):
            rows.append(
                (
                    run_id,
                    int(student["id"]),
                    lesson_number,
                    str(student["group_id"]),
                    5.5 + solved / 2,
                    3.0 + solved / 3,
                    8.0,
                    solved,
                    6,
                )
            )
    connection.executemany(
        "INSERT INTO student_lesson_metrics "
        "(run_id, student_user_id, lesson_number, group_id, simple_strength, "
        "complex_strength, max_complex_strength, solved_items, total_items) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def seed_e2e_statistics(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with maintenance_database_lock(database_path):
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            inserted = _seed(connection)
    print(f"Seeded Staff statistics E2E snapshot: inserted={inserted}")
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_statistics accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Statistics E2E seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Statistics E2E seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_statistics(config)


if __name__ == "__main__":
    main()
