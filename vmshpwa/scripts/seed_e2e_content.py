"""Seed mutable content lessons exclusively for production-build E2E.

The baseline-v1 seed remains a stable Phase-1 artifact. This bounded follow-up
adds independent publication and test-submission lessons per Playwright project
so three browsers can mutate real SQLite concurrently without sharing revisions,
publications or attempts. See development-plan phases 2 and 4.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from db_methods.pwa import PwaConnectionFactory, maintenance_database_lock
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPOSITORY_ROOT / "pwa_tests/fixtures/content/e2e-content-v1.json"
EXPECTED_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"
EXPECTED_PROJECTS = frozenset({"chromium", "webkit", "firefox"})
TIMESTAMP = "2026-07-28T00:00:00Z"


def _load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate key {key!r} in {path.name}")
            result[key] = value
        return result

    payload = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
    )
    _validate_fixture(payload)
    return payload


def _validate_fixture(payload: Mapping[str, Any]) -> None:
    if payload.get("fixture") != "phase2-content-e2e-v1":
        raise ValueError("Unknown Phase-2 E2E content fixture")
    if payload.get("fixtureVersion") != 1:
        raise ValueError("Unsupported Phase-2 E2E content fixture version")
    target_collections = {
        "targets": "Phase-2 publication",
        "submissionTargets": "Phase-4 submission",
    }
    all_targets: list[Mapping[str, Any]] = []
    for key, label in target_collections.items():
        targets = payload.get(key)
        if not isinstance(targets, list) or len(targets) != len(EXPECTED_PROJECTS):
            raise ValueError(f"{label} E2E fixture must define exactly three targets")
        if any(not isinstance(target, dict) for target in targets):
            raise ValueError(f"{label} E2E targets must be objects")
        projects = {target.get("project") for target in targets}
        if projects != EXPECTED_PROJECTS:
            raise ValueError(
                f"{label} E2E targets must cover every browser exactly once"
            )
        all_targets.extend(targets)

    lesson_numbers = [target.get("lessonNumber") for target in all_targets]
    course_lessons = [target.get("courseLessonPublicId") for target in all_targets]
    group_lessons = [target.get("groupLessonPublicId") for target in all_targets]
    if (
        any(not isinstance(value, int) or value < 1 for value in lesson_numbers)
        or len(lesson_numbers) != len(set(lesson_numbers))
        or any(not isinstance(value, str) or not value for value in course_lessons)
        or len(course_lessons) != len(set(course_lessons))
        or any(not isinstance(value, str) or not value for value in group_lessons)
        or len(group_lessons) != len(set(group_lessons))
    ):
        raise ValueError("E2E content lesson identities must be non-empty and unique")


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("Phase-2 content seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("Phase-2 content seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("Phase-2 content seed refuses an unknown SQLite target")
    return database_path


def _lookup_owner(
    connection: sqlite3.Connection,
    payload: Mapping[str, Any],
) -> tuple[int, int, str]:
    course = connection.execute(
        "SELECT id FROM courses WHERE public_id = ?",
        (payload["coursePublicId"],),
    ).fetchone()
    actor = connection.execute(
        "SELECT id FROM users WHERE public_id = ?",
        (payload["actorUserPublicId"],),
    ).fetchone()
    group = connection.execute(
        "SELECT group_id, course_id FROM groups WHERE public_id = ?",
        (payload["groupPublicId"],),
    ).fetchone()
    if course is None or actor is None or group is None:
        raise RuntimeError(
            "Phase-2 E2E fixture owner rows are missing from baseline-v1"
        )
    if int(group["course_id"]) != int(course["id"]):
        raise RuntimeError("Phase-2 E2E fixture group belongs to another course")
    return int(course["id"]), int(actor["id"]), str(group["group_id"])


def _insert_content_fixture(
    connection: sqlite3.Connection,
    payload: Mapping[str, Any],
) -> int:
    course_id, actor_user_id, group_id = _lookup_owner(connection, payload)
    targets = [*payload["targets"], *payload["submissionTargets"]]
    submission_group_lessons = {
        target["groupLessonPublicId"] for target in payload["submissionTargets"]
    }
    public_ids = [
        value
        for target in targets
        for value in (
            target["courseLessonPublicId"],
            target["groupLessonPublicId"],
        )
    ]
    placeholders = ", ".join("?" for _value in public_ids)
    existing = connection.execute(
        "SELECT public_id FROM course_lessons WHERE public_id IN "
        f"({placeholders}) UNION ALL "
        "SELECT public_id FROM group_lessons WHERE public_id IN "
        f"({placeholders})",
        (*public_ids, *public_ids),
    ).fetchall()
    if existing:
        existing_ids = {str(row["public_id"]) for row in existing}
        if existing_ids == set(public_ids):
            return 0
        raise RuntimeError("Phase-2 E2E fixture is only partially present")

    inserted = 0
    for target in targets:
        course_lesson_id = connection.execute(
            "INSERT INTO course_lessons "
            "(public_id, course_id, lesson_number, title, created_by_user_id, "
            "updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                target["courseLessonPublicId"],
                course_id,
                target["lessonNumber"],
                target["title"],
                actor_user_id,
                actor_user_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        ).fetchone()["id"]
        group_lesson_id = connection.execute(
            "INSERT INTO group_lessons "
            "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_by_user_id, updated_by_user_id, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?) RETURNING id",
            (
                target["groupLessonPublicId"],
                course_lesson_id,
                course_id,
                group_id,
                payload["cycleAnchorDate"],
                payload["businessTimezone"],
                actor_user_id,
                actor_user_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        ).fetchone()["id"]
        if target["groupLessonPublicId"] in submission_group_lessons:
            connection.execute(
                "INSERT INTO lesson_windows "
                "(public_id, group_lesson_id, opens_at, submission_closes_at, "
                "timezone, source, created_by_user_id, updated_by_user_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'native', ?, ?, ?, ?)",
                (
                    f"window-{target['groupLessonPublicId']}",
                    group_lesson_id,
                    "2026-07-01T00:00:00Z",
                    "2099-12-31T23:59:59Z",
                    payload["businessTimezone"],
                    actor_user_id,
                    actor_user_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            )
        inserted += 1
    return inserted


def seed_e2e_content(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    payload = _load_fixture()
    with maintenance_database_lock(database_path):
        database = PwaConnectionFactory(database_path)
        inserted = database.run_write(
            lambda connection: _insert_content_fixture(connection, payload)
        )
    print(
        "Seeded E2E content: "
        f"targets={len(payload['targets']) + len(payload['submissionTargets'])} "
        f"inserted={inserted}"
    )
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_content accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Phase-2 E2E content seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Phase-2 content seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_content(config)


if __name__ == "__main__":
    main()
