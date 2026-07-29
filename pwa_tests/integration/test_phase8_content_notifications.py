"""Phase-8 proof for notifications created by published lesson materials."""

from __future__ import annotations

import json

from db_methods.pwa.notifications import active_group_notification_accounts
from pwa_tests.integration import test_content_http_api as content_http_support


# Re-export the established fixture so this focused proof uses the same real
# aiohttp/SQLite publication path.
content_http = content_http_support.content_http


async def test_condition_publication_notifies_active_group_student_and_family(
    content_http: content_http_support.ContentHttpFixture,
):
    fixture = content_http
    await content_http_support._prepare_published_test_problem(fixture)

    rows = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.public_id AS account_public_id, account.audience, "
            "event.category, event.dedupe_key, event.route, event.payload_json "
            "FROM notification_events AS event "
            "JOIN auth_accounts AS account ON account.id = event.account_id "
            "WHERE event.category = 'lesson_published' ORDER BY account.audience DESC"
        ).fetchall()
    )

    assert [row["account_public_id"] for row in rows] == [
        "account-content-student",
        "account-content-family",
    ]
    assert len({row["dedupe_key"] for row in rows}) == 1
    assert rows[0]["route"] == (
        "/student/tasks?course=course-content-http&group=group-content-http-a&lesson=41"
    )
    assert rows[1]["route"] == "/family/children/user-content-student"
    for row in rows:
        assert json.loads(row["payload_json"]) == {
            "publicationId": row["dedupe_key"],
            "courseId": "course-content-http",
            "groupId": "group-content-http-a",
            "groupLessonId": "group-lesson-content-http-a",
            "lessonNumber": 41,
            "kind": "condition",
            "studentIds": ["user-content-student"],
        }
    assert (
        fixture.factory.run_read(
            lambda connection: active_group_notification_accounts(
                connection,
                course_id=int(
                    connection.execute(
                        "SELECT id FROM courses WHERE public_id = 'course-content-http'"
                    ).fetchone()["id"]
                ),
                group_id="content-b",
            )
        )
        == []
    )
