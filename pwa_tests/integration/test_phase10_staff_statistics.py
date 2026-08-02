"""Authenticated Staff statistics over one immutable analytics snapshot."""

from __future__ import annotations

from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from pwa_tests.integration.test_classroom_catalog_http_api import (
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _seed_statistics(classroom_http: ClassroomHttpFixture) -> None:
    def write(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
        student_ids: list[int] = []
        for index in range(3):
            student_ids.append(
                connection.execute(
                    "INSERT INTO users "
                    "(public_id, type, group_id, name, surname, online) "
                    "VALUES (?, 1, 'layout-beginner', ?, 'Статистика', 1) RETURNING id",
                    (f"statistics-student-{index}", f"Ученик {index + 1}"),
                ).fetchone()["id"]
            )
        run_id = connection.execute(
            "INSERT INTO analytics_runs "
            "(public_id, course_id, algorithm, algorithm_version, "
            "input_through_result_id, state, started_at, completed_at) "
            "VALUES ('statistics-run-latest', ?, 'a53-compatible', '1', 179, "
            "'completed', '2026-08-02T10:00:00Z', '2026-08-02T10:01:00Z') "
            "RETURNING id",
            (course_id,),
        ).fetchone()["id"]
        rows = []
        for lesson, values in (
            (40, ((4.0, 2.0, 1, 4), (6.0, 3.0, 2, 4), (8.0, 4.0, 3, 4))),
            (41, ((5.0, 3.0, 2, 5), (7.0, 4.0, 3, 5), (9.0, 5.0, 5, 5))),
        ):
            rows.extend(
                (
                    run_id,
                    student_id,
                    lesson,
                    "layout-beginner",
                    simple,
                    complex_,
                    8.0,
                    solved,
                    total,
                )
                for student_id, (simple, complex_, solved, total) in zip(
                    student_ids, values, strict=True
                )
            )
        connection.executemany(
            "INSERT INTO student_lesson_metrics "
            "(run_id, student_user_id, lesson_number, group_id, simple_strength, "
            "complex_strength, max_complex_strength, solved_items, total_items) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    classroom_http.factory.run_write(write)


async def test_admin_and_scoped_teacher_read_latest_course_statistics(
    classroom_http: ClassroomHttpFixture,
) -> None:
    _seed_statistics(classroom_http)
    for persona in ("admin", "teacher"):
        response = await classroom_http.client.get(
            "/staff/api/v1/statistics?courseId=classroom-layout-course",
            headers=_headers(),
            cookies=_cookies(classroom_http, persona),
        )
        assert response.status == 200, await response.text()
        payload = await response.json()
        assert payload["selectedCourseId"] == "classroom-layout-course"
        assert payload["selectedGroupId"] is None
        assert payload["run"] == {
            "runId": "statistics-run-latest",
            "algorithm": "a53-compatible",
            "algorithmVersion": "1",
            "inputThroughResultId": 179,
            "completedAt": "2026-08-02T10:01:00Z",
        }
        assert [lesson["lessonNumber"] for lesson in payload["lessons"]] == [40, 41]
        assert payload["lessons"][1]["solvedDistribution"] == [2, 3, 5]
        assert payload["lessons"][1]["completionRate"] == 66.7
        assert payload["lessons"][1]["groups"][0]["groupId"] == "classroom-layout-group"


async def test_statistics_group_filter_and_fail_closed_scope(
    classroom_http: ClassroomHttpFixture,
) -> None:
    _seed_statistics(classroom_http)
    filtered = await classroom_http.client.get(
        "/staff/api/v1/statistics?courseId=classroom-layout-course&groupId=classroom-layout-group",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert filtered.status == 200
    assert (await filtered.json())["selectedGroupId"] == "classroom-layout-group"

    forbidden = await classroom_http.client.get(
        "/staff/api/v1/statistics?courseId=course.without-scope",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert forbidden.status == 403
    assert (await forbidden.json())["error"]["code"] == "forbidden"

    student = await classroom_http.client.get(
        "/staff/api/v1/statistics",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[
                AuthAudience.STUDENT
            ].access_name: classroom_http.student_cookie
        },
    )
    assert student.status == 401


async def test_statistics_empty_state_and_input_validation(
    classroom_http: ClassroomHttpFixture,
) -> None:
    response = await classroom_http.client.get(
        "/staff/api/v1/statistics?courseId=classroom-layout-course",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["run"] is None
    assert payload["lessons"] == []

    invalid = await classroom_http.client.get(
        "/staff/api/v1/statistics?courseId=INVALID",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert invalid.status == 422

    unknown = await classroom_http.client.get(
        "/staff/api/v1/statistics?surprise=true",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert unknown.status == 422
