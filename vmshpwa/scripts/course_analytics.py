"""Calculate and publish one analytics snapshot for every active course."""

from __future__ import annotations

import sqlite3
import fcntl
import logging
import time
from datetime import UTC, datetime

from db_methods.pwa.course_achievements import (
    list_course_achievement_facts,
    list_course_student_ids,
    save_course_achievements,
)
from db_methods.pwa.migrations import require_current_schema
from db_methods.pwa.lesson_statistics import course_facts
from db_methods.pwa.iterative_analytics import read_state, publish_step
from models.pwa.iterative_analytics import calculate_step
from models.pwa.course_achievements import calculate_initial_course_achievements
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


def calculate_active_courses(
    connection: sqlite3.Connection,
    *,
    completed_at: str,
) -> list[tuple[str, int]]:
    """Calculate active courses and return ``(course public id, point count)``."""

    courses = connection.execute(
        "SELECT id, public_id FROM courses WHERE status = 'active' ORDER BY id"
    ).fetchall()
    result_row = connection.execute(
        "SELECT coalesce(max(id), 0) AS result_id FROM results"
    ).fetchone()
    input_through_result_id = int(result_row["result_id"])
    calculated: list[tuple[str, int]] = []

    for course in courses:
        course_id = int(course["id"])
        course_public_id = str(course["public_id"])
        started = time.monotonic()
        connection.execute("BEGIN")
        try:
            problems, results, _ = course_facts(connection, course_id)
            difficulty, strength = read_state(connection, course_id)
        finally:
            connection.execute("ROLLBACK")
        difficulty, strength, metrics, diagnostics = calculate_step(
            problems, results, difficulty, strength
        )
        publish_step(
            connection,
            course_id,
            difficulty,
            strength,
            metrics,
            diagnostics,
            completed_at,
            input_through_result_id,
        )
        logging.getLogger(__name__).info(
            "Analytics course=%s duration=%.3fs diagnostics=%s",
            course_public_id,
            time.monotonic() - started,
            diagnostics,
        )
        for student_user_id in list_course_student_ids(connection, course_id=course_id):
            facts = list_course_achievement_facts(
                connection,
                student_user_id=student_user_id,
                course_id=course_id,
            )
            save_course_achievements(
                connection,
                student_user_id=student_user_id,
                course_id=course_id,
                achievements=calculate_initial_course_achievements(facts),
            )
            connection.commit()
        calculated.append((course_public_id, len(metrics)))
        connection.commit()

    return calculated


def run(runtime_config: PwaMaintenanceConfig) -> list[tuple[str, int]]:
    require_pwa_maintenance_profile(runtime_config)
    require_current_schema(runtime_config.db_filename)
    completed_at = (
        datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )
    # The same lock protects timer and manual runs, including the CPU-only step.
    with open(str(runtime_config.db_filename) + ".analytics.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.getLogger(__name__).info("Analytics already running; skipped")
            return []
        with sqlite3.connect(runtime_config.db_filename, timeout=5) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            return calculate_active_courses(connection, completed_at=completed_at)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    require_pwa_profile_environment()
    from helpers.config import config

    calculated = run(config)
    if not calculated:
        print("No active courses")
        return
    for course_public_id, point_count in calculated:
        print(f"{course_public_id}: {point_count} lesson points")


if __name__ == "__main__":
    main()
