"""One course model step shared by CLI and Staff; docs/lesson-statistics.md."""

import logging
import time
from datetime import UTC, datetime

from db_methods.pwa.lesson_statistics import course_facts
from db_methods.pwa.iterative_analytics import read_state, publish_step
from models.pwa.iterative_analytics import calculate_step


def timestamp():
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def calculate_course(connection, course_id, *, completed_at=None, operation_id=None):
    started = time.monotonic()
    connection.execute("BEGIN")
    try:
        input_through_result_id = connection.execute(
            "SELECT coalesce(max(id), 0) AS boundary FROM results"
        ).fetchone()["boundary"]
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
        completed_at or timestamp(),
        input_through_result_id,
        operation_id=operation_id,
    )
    logging.getLogger(__name__).info(
        "Analytics course=%s duration=%.3fs diagnostics=%s",
        course_id,
        time.monotonic() - started,
        diagnostics,
    )
    return len(metrics)
