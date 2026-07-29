"""Phase-9 family child/course authorization boundary."""

from __future__ import annotations

from pwa_tests.integration import test_content_http_api as content_support


content_http = content_support.content_http


async def test_family_reads_only_a_linked_childs_courses(content_http):
    fixture = content_http
    response = await fixture.client.get(
        "/family/api/v1/children/user-content-student/courses",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert response.status == 200, await response.text()
    assert response.headers["Cache-Control"] == "no-store"
    body = await response.json()
    assert body["student"] == {
        "studentId": "user-content-student",
        "displayName": "Ирина Тестова",
        "grade": None,
        "birthday": None,
        "relationshipLabel": "родитель",
        "isPrimary": True,
    }
    assert len(body["enrollments"]) == 1
    assert body["enrollments"][0]["studentId"] == "user-content-student"
    assert body["enrollments"][0]["course"]["courseId"] == "course-content-http"
    assert body["enrollments"][0]["activeGroupId"] == "group-content-http-a"


async def test_family_child_courses_hide_unlinked_and_reject_other_audiences(
    content_http,
):
    fixture = content_http
    for child_id in ("someone-else", "INVALID"):
        hidden = await fixture.client.get(
            f"/family/api/v1/children/{child_id}/courses",
            headers=content_support._headers(),
            cookies=content_support._cookie(fixture, "family"),
        )
        assert hidden.status == 403
        assert (await hidden.json())["error"]["code"] == "forbidden"

    student = await fixture.client.get(
        "/family/api/v1/children/user-content-student/courses",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "student"),
    )
    # The Student cookie has Path=/student and therefore cannot authenticate a
    # request under /family at all.
    assert student.status == 401

    with_query = await fixture.client.get(
        "/family/api/v1/children/user-content-student/courses?extra=1",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert with_query.status == 422


async def test_family_home_returns_only_browser_ready_current_lessons(content_http):
    fixture = content_http
    empty = await fixture.client.get(
        "/family/api/v1/children/user-content-student/home",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert empty.status == 200
    assert (await empty.json())["courses"][0]["currentLesson"] is None

    await content_support._prepare_published_test_problem(fixture, problem_type=1)
    response = await fixture.client.get(
        "/family/api/v1/children/user-content-student/home",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert response.status == 200, await response.text()
    body = await response.json()
    assert body["student"]["studentId"] == "user-content-student"
    assert body["courses"][0]["enrollment"]["activeGroupId"] == "group-content-http-a"
    assert body["courses"][0]["currentLesson"] == {
        "groupLessonId": fixture.group_lesson_a,
        "courseLessonId": "course-lesson-content-http",
        "lessonNumber": 41,
        "title": "Занятие 41",
        "cycleAnchorDate": "2026-09-14",
        "businessTimezone": "Europe/Moscow",
        "problemCount": 1,
    }

    hidden = await fixture.client.get(
        "/family/api/v1/children/unlinked-student/home",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert hidden.status == 403
