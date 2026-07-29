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
    ("chromium", "group-lesson-content-e2e-chromium"),
    ("webkit", "group-lesson-content-e2e-webkit"),
    ("firefox", "group-lesson-content-e2e-firefox"),
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
        "SELECT id FROM users WHERE public_id = 'user-admin-fixture'"
    ).fetchone()
    season = connection.execute(
        "SELECT id FROM seasons WHERE public_id = 'season-fixture-2025-26'"
    ).fetchone()
    group_lessons = {
        row["public_id"]: row
        for row in connection.execute(
            "SELECT id, public_id, course_id, group_id FROM group_lessons "
            "WHERE public_id IN (?, ?, ?)",
            tuple(group_lesson for _project, group_lesson in TARGETS),
        )
    }
    if actor is None or season is None or len(group_lessons) != len(TARGETS):
        raise RuntimeError("Classroom E2E seed requires the baseline and content seeds")

    event_ids = [f"in-person-classrooms-e2e-{project}" for project, _lesson in TARGETS]
    room_ids = [f"classroom-e2e-{project}" for project, _lesson in TARGETS]
    existing_events = {
        row[0]
        for row in connection.execute(
            "SELECT public_id FROM in_person_events WHERE public_id IN (?, ?, ?)",
            event_ids,
        )
    }
    existing_rooms = {
        row[0]
        for row in connection.execute(
            "SELECT public_id FROM classrooms WHERE public_id IN (?, ?, ?)",
            room_ids,
        )
    }
    if existing_events or existing_rooms:
        if existing_events == set(event_ids) and existing_rooms == set(room_ids):
            return 0
        raise RuntimeError("Classroom E2E fixture is only partially present")

    actor_id = int(actor["id"])
    season_id = int(season["id"])
    for ordinal, (project, group_lesson_public_id) in enumerate(TARGETS, start=1):
        group_lesson = group_lessons[group_lesson_public_id]
        room_public_id = f"classroom-e2e-{project}"
        room_name = f"20{ordinal} E2E {project}"
        room_id = int(
            connection.execute(
                "INSERT INTO classrooms "
                "(public_id, name, normalized_name, status, created_by_user_id, "
                "updated_by_user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', ?, ?, ?, ?) RETURNING id",
                (
                    room_public_id,
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
            "(public_id, classroom_id, action, after_name, after_normalized_name, "
            "after_status, version_after, actor_user_id, request_id, created_at) "
            "VALUES (?, ?, 'created', ?, ?, 'active', 1, ?, ?, ?)",
            (
                f"classroom-event-e2e-{project}",
                room_id,
                room_name,
                room_name.casefold(),
                actor_id,
                f"e2e.seed.classroom.{project}",
                TIMESTAMP,
            ),
        )
        event_id = int(
            connection.execute(
                "INSERT INTO in_person_events "
                "(public_id, season_id, name, starts_at, ends_at, status, "
                "created_by_user_id, updated_by_user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'scheduled', ?, ?, ?, ?) RETURNING id",
                (
                    f"in-person-classrooms-e2e-{project}",
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
            (event_id, int(group_lesson["id"]), actor_id, TIMESTAMP),
        )
        student_id = int(
            connection.execute(
                "INSERT INTO users "
                "(public_id, type, name, surname, grade, birthday) "
                "VALUES (?, 1, 'Ученик', ?, 7, '2013-01-01') RETURNING id",
                (f"student-classroom-e2e-{project}", f"Тестов {project}"),
            ).fetchone()["id"]
        )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(public_id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'in_person', 'active', ?, ?) RETURNING id",
                (
                    f"enrollment-classroom-e2e-{project}",
                    student_id,
                    int(group_lesson["course_id"]),
                    str(group_lesson["group_id"]),
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
                int(group_lesson["course_id"]),
                str(group_lesson["group_id"]),
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
