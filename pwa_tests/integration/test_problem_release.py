"""Acceptance for vmshpwa/docs/problem-release.md using real aiohttp/SQLite."""

import pytest

from pwa_tests.integration import test_content_http_api as support
from models.pwa.problem_release import task_states

content_http = support.content_http


async def release_state(fixture, revision_id):
    response = await fixture.client.get(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/problem-release",
        params={"revisionId": revision_id},
        cookies=support._cookie(fixture, "admin"),
        headers=support._headers(),
    )
    assert response.status == 200, await response.text()
    return await response.json()


async def change(fixture, state, is_open):
    response = await fixture.client.put(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/problem-release",
        json={
            "conditionRevisionId": state["conditionRevisionId"],
            "changes": [
                {"sourceOrdinal": item["sourceOrdinal"], "isOpen": is_open}
                for item in state["problems"]
            ],
        },
        cookies=support._cookie(fixture, "admin"),
        headers=support._headers(unsafe=True, if_match=state["etag"]),
    )
    return response


async def test_off_keeps_lesson_but_filters_student_family_and_rejects_input(
    content_http,
):
    fixture = content_http
    problem_id, revision = await support._prepare_published_test_problem(fixture)
    hint, _ = await support._upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        filename="release/hint.tex",
        source="\\задача[title=Целое число] Введите число 7. \\кзадача\\подсказка Секретная подсказка. \\кподсказка",
    )
    assert (
        await support._publish(
            fixture,
            group_lesson=fixture.group_lesson_a,
            kind="hint",
            revision_id=hint["revisionId"],
        )
    ).status == 201
    attempt_url = f"/student/api/v1/problems/{problem_id}/test-attempts"
    attempt = {
        "schemaVersion": 1,
        "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac05",
        "problemRevision": {"conditionRevisionId": revision, "configVersion": 1},
        "displayAnswer": "7",
        "clientCreatedAt": support._timestamp(),
    }
    submitted = await fixture.client.post(
        attempt_url,
        json=attempt,
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(unsafe=True),
    )
    assert submitted.status == 201, await submitted.text()
    receipt = await submitted.json()
    initial = await release_state(fixture, revision)
    assert initial["problems"] == [{"sourceOrdinal": 1, "isOpen": True}]
    closed = await change(fixture, initial, False)
    assert closed.status == 200, await closed.text()
    closed_state = await closed.json()
    assert closed_state["version"] > initial["version"]

    student = await fixture.client.get(
        f"/student/api/v1/group-lessons/{fixture.group_lesson_a}/content/condition",
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(),
    )
    assert student.status == 200, await student.text()
    assert (await student.json())["document"]["problems"] == []
    tasks = await fixture.client.get(
        f"/student/api/v1/courses/c-1/lessons/{fixture.group_lesson_a}/problems",
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(),
    )
    assert tasks.status == 200, await tasks.text()
    assert (await tasks.json())["problems"] == []
    lessons = await fixture.client.get(
        "/student/api/v1/courses/c-1/lessons",
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(),
    )
    assert lessons.status == 200, await lessons.text()
    lesson = next(
        item
        for item in (await lessons.json())["lessons"]
        if item["groupLessonId"] == fixture.group_lesson_a
    )
    assert lesson["problemCount"] == 0
    assert lesson["materials"]["condition"]["status"] == "published"
    family = await fixture.client.get(
        "/family/api/v1/children/u-903101/courses/c-1/lessons/41?group=g-1",
        cookies=support._cookie(fixture, "family"),
        headers=support._headers(),
    )
    assert family.status == 200, await family.text()
    assert (await family.json())["document"]["problems"] == []
    input_response = await fixture.client.get(
        f"/student/api/v1/problems/{problem_id}/test-input",
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(),
    )
    assert input_response.status == 404, await input_response.text()
    reveal = await support._student_reveal(
        fixture, group_lesson=fixture.group_lesson_a, problem_id=problem_id, kind="hint"
    )
    assert reveal.status == 404, await reveal.text()
    replay = await fixture.client.post(
        attempt_url,
        json=attempt,
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(unsafe=True),
    )
    assert replay.status == 201
    assert await replay.json() == receipt
    new_attempt = await fixture.client.post(
        attempt_url,
        json={**attempt, "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac04"},
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(unsafe=True),
    )
    assert new_attempt.status == 404, await new_attempt.text()
    # Full storage projection remains available to Staff/Telegram.
    from db_methods.pwa.content import PwaContentRepository
    from models.pwa.content import ContentKind

    full = await PwaContentRepository(fixture.factory).get_published_content(
        group_lesson_public_id=fixture.group_lesson_a,
        kind=ContentKind.CONDITION,
    )
    assert len(full.document["problems"]) == 1
    opened = await change(fixture, closed_state, True)
    assert opened.status == 200, await opened.text()
    visible = await fixture.client.get(
        f"/student/api/v1/group-lessons/{fixture.group_lesson_a}/content/condition",
        cookies=support._cookie(fixture, "student"),
        headers=support._headers(),
    )
    assert len((await visible.json())["document"]["problems"]) == 1


async def test_conflict_and_revision_replacement_preserve_off(content_http):
    fixture = content_http
    problem_id, revision = await support._prepare_published_test_problem(fixture)
    state = await release_state(fixture, revision)
    assert (await change(fixture, state, False)).status == 200
    stale = await change(fixture, state, True)
    assert stale.status == 409
    repaired, _ = await support._publish_repaired_test_problem(
        fixture,
        problem_public_id=problem_id,
        correct_answer="179",
    )
    assert (await release_state(fixture, repaired))["problems"] == [
        {"sourceOrdinal": 1, "isOpen": False}
    ]
    old = await release_state(fixture, revision)
    assert not old["editable"]
    assert (await change(fixture, old, True)).status == 409


@pytest.mark.parametrize(
    ("known", "new_open", "expected"),
    [
        ([None, None], True, True),
        ([None, None], False, False),
        ([1, None], False, True),
        ([0, None], True, False),
        ([1, 0], True, False),
    ],
)
def test_whole_task_and_new_subpart_inheritance(known, new_open, expected):
    rows = [{"source_ordinal": 1, "is_open": value} for value in known]
    assert task_states(rows, new_tasks_open=new_open) == {1: expected}


async def test_prepare_off_before_first_publication_and_close_new_task(content_http):
    fixture = content_http
    first, _ = await support._upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="release/first.tex",
        source="\\задача[title=Первая] Условие. \\кзадача",
    )
    state = await release_state(fixture, first["revisionId"])
    assert state["editable"]
    assert (await change(fixture, state, False)).status == 200
    published = await support._publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=first["revisionId"],
    )
    assert published.status == 201, await published.text()
    publication = await published.json()
    second, _ = await support._upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="release/second.tex",
        source="\\задача[title=Первая] Условие. \\кзадача\n\\задача[title=Новая] Ещё условие. \\кзадача",
    )
    preview = await release_state(fixture, second["revisionId"])
    assert not preview["editable"]
    assert preview["problems"] == [
        {"sourceOrdinal": 1, "isOpen": False},
        {"sourceOrdinal": 2, "isOpen": False},
    ]
    published = await support._publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=second["revisionId"],
        expected_id=publication["publicationId"],
        expected_version=publication["version"],
        if_match=published.headers["ETag"],
    )
    assert published.status == 201, await published.text()
    state = await release_state(fixture, second["revisionId"])
    assert state["editable"]
    assert state["problems"] == preview["problems"]
    invalid = await fixture.client.put(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/problem-release",
        json={
            "conditionRevisionId": second["revisionId"],
            "changes": [
                {"sourceOrdinal": 1, "isOpen": True},
                {"sourceOrdinal": 1, "isOpen": False},
            ],
        },
        cookies=support._cookie(fixture, "admin"),
        headers=support._headers(unsafe=True, if_match=state["etag"]),
    )
    assert invalid.status == 422
    forbidden = await fixture.client.get(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_b}/problem-release",
        params={"revisionId": second["revisionId"]},
        cookies=support._cookie(fixture, "teacher"),
        headers=support._headers(),
    )
    assert forbidden.status == 403
