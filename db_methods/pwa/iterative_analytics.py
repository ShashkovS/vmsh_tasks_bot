"""Atomic publication and bounded retention for the a53 step (lesson-statistics.md)."""

import json

from db_methods.pwa.course_analytics import save_completed_course_metrics

ALGORITHM = "a53-iterative"


def read_state(connection, course_id):
    difficulty = {
        r["logical_key"]: (r["for_weak"], r["for_strong"])
        for r in connection.execute(
            "SELECT * FROM course_problem_difficulty WHERE course_id = ?", (course_id,)
        )
    }
    strength = {
        r["student_user_id"]: (r["simple"], r["complex"])
        for r in connection.execute(
            "SELECT * FROM course_student_strength WHERE course_id = ?", (course_id,)
        )
    }
    return difficulty, strength


def publish_step(
    connection,
    course_id,
    difficulty,
    strength,
    metrics,
    diagnostics,
    timestamp,
    result_id,
):
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM course_problem_difficulty WHERE course_id = ?", (course_id,)
        )
        connection.execute(
            "DELETE FROM course_student_strength WHERE course_id = ?", (course_id,)
        )
        connection.executemany(
            "INSERT INTO course_problem_difficulty VALUES (?, ?, ?, ?)",
            [(course_id, key, *values) for key, values in difficulty.items()],
        )
        connection.executemany(
            "INSERT INTO course_student_strength VALUES (?, ?, ?, ?)",
            [(course_id, student, *values) for student, values in strength.items()],
        )
        run_id = save_completed_course_metrics(
            connection,
            course_id=course_id,
            algorithm=ALGORITHM,
            algorithm_version="2",
            input_through_result_id=result_id,
            completed_at=timestamp,
            metrics=metrics,
            commit=False,
        )
        connection.executemany(
            "UPDATE student_lesson_metrics SET simple_smooth = ?, complex_smooth = ? WHERE run_id = ? AND student_user_id = ? AND lesson_number = ?",
            [
                (
                    m["simple_smooth"],
                    m["complex_smooth"],
                    run_id,
                    m["student_user_id"],
                    m["lesson_number"],
                )
                for m in metrics
            ],
        )
        connection.execute(
            "UPDATE analytics_runs SET diagnostics_json = ? WHERE id = ?",
            (json.dumps([diagnostics]), run_id),
        )
        connection.execute(
            "DELETE FROM analytics_runs WHERE course_id = ? AND algorithm = ? AND id NOT IN (SELECT id FROM analytics_runs WHERE course_id = ? AND algorithm = ? ORDER BY id DESC LIMIT 2)",
            (course_id, ALGORITHM, course_id, ALGORITHM),
        )
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
