"""Course analytics uses direct facts and exposes only complete snapshots."""

from __future__ import annotations

from db_methods.pwa.course_analytics import (
    latest_student_course_metrics,
    list_course_group_access_rows,
    list_course_problem_rows,
    list_course_result_rows,
    save_completed_course_metrics,
)
from models.pwa.course_analytics import calculate_course_lesson_metrics
from pwa_tests.integration import test_content_http_api as content_support
from vmshpwa.scripts.course_analytics import calculate_active_courses


content_http = content_support.content_http


async def test_course_analytics_reads_calculates_and_publishes_one_snapshot(
    content_http,
):
    fixture = content_http
    (
        problem_public_id,
        _revision_id,
    ) = await content_support._prepare_published_test_problem(fixture, problem_type=1)

    def seed_result(connection):
        problem_id = connection.execute(
            "SELECT id FROM problems WHERE public_id = ?", (problem_public_id,)
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, res_type) "
            "VALUES (?, ?, 'content-a', 41, NULL, '2026-09-15T10:00:00', 17, 1)",
            (content_support.STUDENT_USER_ID, problem_id),
        )

    fixture.factory.run_write(seed_result)

    def calculate_and_save(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'course-content-http'"
        ).fetchone()["id"]
        metrics = calculate_course_lesson_metrics(
            list_course_problem_rows(connection, course_id=course_id),
            list_course_result_rows(connection, course_id=course_id),
            list_course_group_access_rows(connection, course_id=course_id),
        )
        save_completed_course_metrics(
            connection,
            public_id="analytics-course-content-http-v1",
            course_id=course_id,
            algorithm="a53-course",
            algorithm_version="1",
            input_through_result_id=connection.execute(
                "SELECT max(id) AS result_id FROM results"
            ).fetchone()["result_id"],
            completed_at="2026-09-15T12:00:00Z",
            metrics=metrics,
        )
        return course_id, metrics

    course_id, calculated = fixture.factory.run_write(calculate_and_save)
    assert len(calculated) == 1
    assert calculated[0]["lesson_number"] == 41
    assert calculated[0]["group_id"] == "content-a"

    def seed_incomplete_and_read(connection):
        connection.execute(
            "INSERT INTO analytics_runs "
            "(public_id, course_id, algorithm, algorithm_version, "
            "input_through_result_id, state, started_at, diagnostics_json) "
            "VALUES ('analytics-running', ?, 'a53-course', '2', 1, "
            "'running', '2026-09-16T12:00:00Z', '[]')",
            (course_id,),
        )
        return latest_student_course_metrics(
            connection,
            course_id=course_id,
            student_user_id=content_support.STUDENT_USER_ID,
        )

    stored = fixture.factory.run_write(seed_incomplete_and_read)
    assert len(stored) == 1
    assert stored[0]["run_public_id"] == "analytics-course-content-http-v1"
    assert stored[0]["algorithm_version"] == "1"
    assert stored[0]["lesson_number"] == 41
    assert stored[0]["solved_items"] == 1
    assert stored[0]["total_items"] == 1

    response = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/progress",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "student"),
    )
    assert response.status == 200, await response.text()
    analytics = (await response.json())["analytics"]
    assert analytics["runId"] == "analytics-course-content-http-v1"
    assert analytics["algorithmVersion"] == "1"
    assert analytics["lessons"][0]["lessonNumber"] == 41
    assert analytics["lessons"][0]["groupId"] == "group-content-http-a"
    assert analytics["lessons"][0]["solvedItems"] == 1


async def test_analytics_command_calculates_every_active_course(content_http):
    fixture = content_http
    (
        problem_public_id,
        _revision_id,
    ) = await content_support._prepare_published_test_problem(fixture, problem_type=2)

    def seed_and_calculate(connection):
        problem_id = connection.execute(
            "SELECT id FROM problems WHERE public_id = ?", (problem_public_id,)
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, res_type) "
            "VALUES (?, ?, 'content-a', 41, NULL, '2026-09-17T10:00:00', 17, 2)",
            (content_support.STUDENT_USER_ID, problem_id),
        )
        return calculate_active_courses(
            connection,
            completed_at="2026-09-17T12:00:00Z",
            run_token="integration",
        )

    assert fixture.factory.run_write(seed_and_calculate) == [("course-content-http", 1)]
