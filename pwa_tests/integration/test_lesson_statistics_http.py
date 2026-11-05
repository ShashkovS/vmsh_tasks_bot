import sqlite3

import pytest

from db_methods.pwa.lesson_statistics import course_facts
from db_methods.pwa.iterative_analytics import publish_step, read_state
from models.pwa.lesson_statistics import summarize_lessons
from pwa_tests.integration import test_content_http_api as support
from vmshpwa.scripts.course_analytics import calculate_active_courses

content_http = support.content_http


async def test_live_statistics_works_before_first_model_and_excludes_deleted_student(
    content_http,
):
    fixture = content_http
    pid, _ = await support._prepare_published_test_problem(fixture, problem_type=2)

    def seed(db):
        problem = db.execute(
            "SELECT * FROM problems WHERE public_id = ?", (pid,)
        ).fetchone()
        db.execute(
            "INSERT INTO results (student_id, problem_id, group_id, lesson, ts, verdict, res_type) VALUES (?, ?, ?, ?, ?, 17, 2)",
            (
                support.STUDENT_USER_ID,
                problem["id"],
                problem["group_id"],
                problem["lesson"],
                "2026-09-17T10:00:00",
            ),
        )

    fixture.factory.run_write(seed)
    response = await fixture.client.get(
        "/staff/api/v1/statistics?courseId=c-1&lessonNumber=41",
        cookies=support._cookie(fixture, "admin"),
        headers=support._headers(),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["run"] is None
    assert payload["basicLesson"]["groups"][0]["problems"][0]["points"] == 1
    assert payload["basicLesson"]["groups"][0]["problems"][0]["difficultyWeak"] is None
    fixture.factory.run_write(
        lambda db: db.execute(
            "UPDATE users SET type = -1 WHERE id = ?", (support.STUDENT_USER_ID,)
        )
    )
    facts = fixture.factory.run_read(lambda db: course_facts(db, 1))
    assert summarize_lessons(*facts, {"g-1"})[0]["groups"][0]["participantCount"] == 0


async def test_corrected_test_does_not_resurrect_historical_positive(content_http):
    await support.test_staff_rechecks_all_attempts_after_published_metadata_correction(
        content_http
    )
    facts = content_http.factory.run_read(lambda db: course_facts(db, 1))
    group = summarize_lessons(*facts, {"g-1"})[0]["groups"][0]
    assert group["participantCount"] == 1
    assert group["distribution"] == [0]


async def test_current_state_retention_and_failed_publish_rollback(content_http):
    fixture = content_http
    await support._prepare_published_test_problem(fixture, problem_type=2)
    # No observations: still publish finite neutral difficulty, never NaN.
    with fixture.factory.connect() as db:
        for day in range(1, 5):
            calculate_active_courses(db, completed_at=f"2026-10-{day:02}T12:00:00Z")
        assert (
            db.execute(
                "SELECT count(*) AS n FROM analytics_runs WHERE algorithm = 'a53-iterative'"
            ).fetchone()["n"]
            == 2
        )
        previous = read_state(db, 1)
        with pytest.raises(sqlite3.IntegrityError):
            publish_step(
                db, 1, {"invalid": (2, 2)}, {}, [], {}, "2026-10-05T12:00:00Z", 0
            )
        assert read_state(db, 1) == previous
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


async def test_manual_step_matches_cli_and_operation_failure_is_atomic(
    content_http, tmp_path
):
    from db_methods.pwa.statistics_recalculations import create_operation
    from models.pwa.course_analytics_runner import calculate_course

    fixture = content_http
    pid, _ = await support._prepare_published_test_problem(fixture, problem_type=2)

    def seed(db):
        problem = db.execute(
            "SELECT * FROM problems WHERE public_id=?", (pid,)
        ).fetchone()
        db.execute(
            "INSERT INTO results(student_id,problem_id,group_id,lesson,ts,verdict,res_type) VALUES(?,?,?,?,?,17,2)",
            (
                support.STUDENT_USER_ID,
                problem["id"],
                problem["group_id"],
                problem["lesson"],
                "2026-09-17T10:00:00",
            ),
        )

    fixture.factory.run_write(seed)
    with (
        fixture.factory.connect() as source,
        sqlite3.connect(tmp_path / "cli.sqlite3") as cli,
    ):
        source.backup(cli)
        cli.row_factory = sqlite3.Row
        operation = create_operation(
            source, 1, support.STUDENT_USER_ID, "compare", "2026-09-18T00:00:00Z"
        )
        calculate_course(source, 1, operation_id=operation)
        calculate_active_courses(cli, completed_at="2026-09-18T00:00:00Z")
        assert read_state(source, 1) == read_state(cli, 1)
        metrics = "SELECT student_user_id,lesson_number,simple_strength,complex_strength,solved_items,simple_smooth,complex_smooth FROM student_lesson_metrics ORDER BY student_user_id,lesson_number"
        assert [tuple(r.values()) for r in source.execute(metrics)] == [
            tuple(r) for r in cli.execute(metrics)
        ]
        before = read_state(source, 1)
        runs = source.execute("SELECT count(*) AS n FROM analytics_runs").fetchone()[
            "n"
        ]
        with pytest.raises(ValueError, match="no longer running"):
            calculate_course(source, 1, operation_id="missing-operation")
        assert read_state(source, 1) == before
        assert (
            source.execute("SELECT count(*) AS n FROM analytics_runs").fetchone()["n"]
            == runs
        )
        assert (
            source.execute(
                "SELECT state FROM statistics_recalculations WHERE operation_id=?",
                (operation,),
            ).fetchone()["state"]
            == "completed"
        )


async def test_manual_input_boundary_uses_same_snapshot(content_http, monkeypatch):
    from models.pwa import course_analytics_runner as runner

    fixture = content_http
    pid, _ = await support._prepare_published_test_problem(fixture, problem_type=2)

    def insert_result(connection):
        problem = connection.execute(
            "SELECT * FROM problems WHERE public_id=?", (pid,)
        ).fetchone()
        connection.execute(
            "INSERT INTO results(student_id,problem_id,group_id,lesson,ts,verdict,res_type) VALUES(?,?,?,?,?,17,2)",
            (
                support.STUDENT_USER_ID,
                problem["id"],
                problem["group_id"],
                problem["lesson"],
                "2026-09-18T10:00:00",
            ),
        )

    original = runner.course_facts

    def facts_after_concurrent_check(connection, course_id):
        # The first SELECT fixed the snapshot; a check committed now is next-run input.
        fixture.factory.run_write(insert_result)
        return original(connection, course_id)

    monkeypatch.setattr(runner, "course_facts", facts_after_concurrent_check)
    with fixture.factory.connect() as connection:
        boundary = connection.execute(
            "SELECT coalesce(max(id),0) AS n FROM results"
        ).fetchone()["n"]
        runner.calculate_course(connection, 1)
        run = connection.execute(
            "SELECT * FROM analytics_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert run["input_through_result_id"] == boundary
        assert not connection.execute(
            "SELECT * FROM course_student_strength"
        ).fetchall()
        monkeypatch.setattr(runner, "course_facts", original)
        runner.calculate_course(connection, 1)
        assert connection.execute("SELECT * FROM course_student_strength").fetchall()
