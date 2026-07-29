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
    assert body["courses"][0]["progress"]["courseId"] == "course-content-http"
    assert body["courses"][0]["progress"]["summary"] == {
        "attempted": 1,
        "accepted": 1,
        "partial": 0,
        "needsWork": 0,
        "awaitingReview": 0,
    }

    hidden = await fixture.client.get(
        "/family/api/v1/children/unlinked-student/home",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert hidden.status == 403


async def test_student_progress_is_course_scoped_and_collapses_retries(content_http):
    fixture = content_http
    (
        problem_public_id,
        _revision_id,
    ) = await content_support._prepare_published_test_problem(fixture, problem_type=1)

    def seed_results(connection):
        problem_id = connection.execute(
            "SELECT id FROM problems WHERE public_id = ?", (problem_public_id,)
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, res_type) "
            "VALUES (?, ?, 'content-a', 41, NULL, ?, ?, 1)",
            (
                (
                    content_support.STUDENT_USER_ID,
                    problem_id,
                    "2026-09-15T10:00:00",
                    14,
                ),
                (
                    content_support.STUDENT_USER_ID,
                    problem_id,
                    "2026-09-16T10:00:00",
                    17,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO written_tasks_queue "
            "(ts, student_id, problem_id, cur_status) VALUES (?, ?, ?, 0)",
            ("2026-09-16T11:00:00", content_support.STUDENT_USER_ID, problem_id),
        )

    fixture.factory.run_write(seed_results)
    response = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/progress",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "student"),
    )
    assert response.status == 200, await response.text()
    assert await response.json() == {
        "courseId": "course-content-http",
        "summary": {
            "attempted": 1,
            "accepted": 1,
            "partial": 0,
            "needsWork": 0,
            "awaitingReview": 1,
        },
        "lessons": [
            {
                "lessonNumber": 41,
                "attempted": 1,
                "accepted": 1,
                "partial": 0,
                "needsWork": 0,
                "awaitingReview": 1,
            }
        ],
        "activity": [
            {"date": "2026-09-15", "problemCount": 1},
            {"date": "2026-09-16", "problemCount": 1},
        ],
        "analytics": None,
        "achievements": [],
    }

    forbidden = await fixture.client.get(
        "/student/api/v1/courses/not-allowed/progress",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "student"),
    )
    assert forbidden.status == 403

    invalid_query = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/progress?group=anything",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "student"),
    )
    assert invalid_query.status == 422


async def test_family_changes_an_allowed_group_and_mode_with_one_versioned_write(
    content_http,
):
    fixture = content_http

    def grant_second_group(connection):
        enrollment = connection.execute(
            "SELECT id, course_id FROM course_enrollments "
            "WHERE public_id = 'enrollment-content-http'"
        ).fetchone()
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'content-b', '2026-09-01T00:00:00Z', "
            "'2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')",
            (enrollment["id"], enrollment["course_id"]),
        )

    fixture.factory.run_write(grant_second_group)
    path = (
        "/family/api/v1/children/user-content-student/courses/"
        "course-content-http/enrollment"
    )
    changed = await fixture.client.patch(
        path,
        json={
            "activeGroupId": "group-content-http-b",
            "attendanceMode": "in_person",
            "version": 1,
        },
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert changed.status == 200, await changed.text()
    assert (await changed.json())["activeGroupId"] == "group-content-http-b"
    assert (await changed.json())["attendanceMode"] == "in_person"
    assert (await changed.json())["version"] == 2

    def read_changes(connection):
        enrollment = connection.execute(
            "SELECT active_group_id, attendance_mode, version "
            "FROM course_enrollments WHERE public_id = 'enrollment-content-http'"
        ).fetchone()
        events = connection.execute(
            "SELECT event_type, source FROM course_enrollment_events "
            "WHERE enrollment_id = (SELECT id FROM course_enrollments "
            "WHERE public_id = 'enrollment-content-http') ORDER BY id"
        ).fetchall()
        legacy = connection.execute(
            "SELECT group_id, online FROM users WHERE id = ?",
            (content_support.STUDENT_USER_ID,),
        ).fetchone()
        return dict(enrollment), [dict(row) for row in events], dict(legacy)

    enrollment, events, legacy = fixture.factory.run_read(read_changes)
    assert enrollment == {
        "active_group_id": "content-b",
        "attendance_mode": "in_person",
        "version": 2,
    }
    assert events[-2:] == [
        {"event_type": "active_group_changed", "source": "pwa"},
        {"event_type": "attendance_mode_changed", "source": "pwa"},
    ]
    assert legacy == {"group_id": "content-b", "online": 2}

    stale = await fixture.client.patch(
        path,
        json={
            "activeGroupId": "group-content-http-a",
            "attendanceMode": "online",
            "version": 1,
        },
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert stale.status == 409

    refreshed = await fixture.client.get(
        "/family/api/v1/children/user-content-student/home",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert refreshed.status == 200
    current = (await refreshed.json())["courses"][0]["enrollment"]
    assert current["activeGroupId"] == "group-content-http-b"
    assert current["attendanceMode"] == "in_person"


async def test_family_enrollment_change_rejects_unlinked_or_unavailable_data(
    content_http,
):
    fixture = content_http
    body = {
        "activeGroupId": "group-content-http-b",
        "attendanceMode": "in_person",
        "version": 1,
    }
    linked_path = (
        "/family/api/v1/children/user-content-student/courses/"
        "course-content-http/enrollment"
    )

    unavailable_group = await fixture.client.patch(
        linked_path,
        json=body,
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert unavailable_group.status == 403
    assert (await unavailable_group.json())["error"]["code"] == "forbidden"

    unlinked_child = await fixture.client.patch(
        "/family/api/v1/children/someone-else/courses/"
        "course-content-http/enrollment",
        json=body,
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert unlinked_child.status == 403

    missing_origin = await fixture.client.patch(
        linked_path,
        json=body,
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert missing_origin.status == 403
    assert (await missing_origin.json())["error"]["code"] == "request_source_missing"

    unexpected_query = await fixture.client.patch(
        f"{linked_path}?unexpected=1",
        json=body,
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "family"),
    )
    assert unexpected_query.status == 422
