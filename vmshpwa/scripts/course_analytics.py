"""Calculate and publish one analytics snapshot for every active course."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from db_methods.pwa.course_analytics import (
    list_course_group_access_rows,
    list_course_problem_rows,
    list_course_result_rows,
    save_completed_course_metrics,
)
from db_methods.pwa.course_achievements import (
    list_course_achievement_facts,
    list_course_student_ids,
    save_course_achievements,
)
from db_methods.pwa.migrations import require_current_schema
from models.pwa.course_analytics import calculate_course_lesson_metrics
from models.pwa.course_achievements import calculate_initial_course_achievements
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


ALGORITHM = "a53-course"
ALGORITHM_VERSION = "1"


def calculate_active_courses(
    connection: sqlite3.Connection,
    *,
    completed_at: str,
    run_token: str,
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
        metrics = calculate_course_lesson_metrics(
            list_course_problem_rows(connection, course_id=course_id),
            list_course_result_rows(connection, course_id=course_id),
            list_course_group_access_rows(connection, course_id=course_id),
        )
        save_completed_course_metrics(
            connection,
            public_id=f"analytics-{course_public_id}-{run_token}",
            course_id=course_id,
            algorithm=ALGORITHM,
            algorithm_version=ALGORITHM_VERSION,
            input_through_result_id=input_through_result_id,
            completed_at=completed_at,
            metrics=metrics,
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
        calculated.append((course_public_id, len(metrics)))

    return calculated


def run(runtime_config: PwaMaintenanceConfig) -> list[tuple[str, int]]:
    require_pwa_maintenance_profile(runtime_config)
    require_current_schema(runtime_config.db_filename)
    completed_at = (
        datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )
    run_token = uuid.uuid4().hex
    with sqlite3.connect(runtime_config.db_filename, timeout=5) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return calculate_active_courses(
            connection,
            completed_at=completed_at,
            run_token=run_token,
        )


def main() -> None:
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
