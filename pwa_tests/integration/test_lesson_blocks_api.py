"""Staff block authoring and reader-safe conditionless responses."""

from __future__ import annotations

from pwa_tests.integration import test_content_http_api as content_support


content_http = content_support.content_http

DOCUMENT = {
    "schemaVersion": 1,
    "blocks": [
        {
            "type": "paragraph",
            "children": [{"type": "text", "text": "Теория до задач"}],
        }
    ],
    "media": [],
}


async def test_staff_publishes_a_block_before_conditions_without_task_leaks(content_http):
    fixture = content_http
    base = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/blocks"

    empty = await fixture.client.get(
        base,
        cookies=content_support._cookie(fixture, "admin"),
        headers=content_support._headers(),
    )
    assert empty.status == 200, await empty.text()
    assert (await empty.json())["before"] is None

    saved = await fixture.client.put(
        f"{base}/before/draft",
        json={"markdown": "Теория до задач", "document": DOCUMENT},
        cookies=content_support._cookie(fixture, "admin"),
        headers=content_support._headers(unsafe=True, if_match='"none"'),
    )
    assert saved.status == 200, await saved.text()
    saved_body = await saved.json()
    revision_id = saved_body["block"]["draft"]["revisionId"]
    etag = saved.headers["ETag"]

    published = await fixture.client.post(
        f"{base}/before/publication",
        json={"revisionId": revision_id, "mode": "now", "scheduledAt": None},
        cookies=content_support._cookie(fixture, "admin"),
        headers=content_support._headers(unsafe=True, if_match=etag),
    )
    assert published.status == 200, await published.text()

    student = await fixture.client.get(
        "/student/api/v1/courses/c-1/lessons",
        cookies=content_support._cookie(fixture, "student"),
        headers=content_support._headers(),
    )
    assert student.status == 200, await student.text()
    lessons = (await student.json())["lessons"]
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson["groupLessonId"] == fixture.group_lesson_a
    assert lesson["problemCount"] == 0
    assert lesson["materials"] == {
        "condition": {"status": "unavailable"},
        "hint": {"status": "unavailable"},
        "solution": {"status": "unavailable"},
    }
    assert lesson["blocks"]["before"]["document"] == DOCUMENT
    assert lesson["blocks"]["after"] is None

    family = await fixture.client.get(
        "/family/api/v1/children/u-903101/courses/c-1/lessons/41?group=g-1",
        cookies=content_support._cookie(fixture, "family"),
        headers=content_support._headers(),
    )
    assert family.status == 200, await family.text()
    family_body = await family.json()
    assert family_body["document"] is None
    assert family_body["problems"] is None
    assert family_body["lesson"]["blocks"]["before"]["document"] == DOCUMENT
