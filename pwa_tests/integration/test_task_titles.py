"""Visible task names use reviewed revision metadata (vmshpwa/docs/task-titles.md)."""

import pytest

from pwa_tests.integration.test_content_http_api import (
    _cookie,
    _headers,
    _publish,
    _student_read,
    _upload_and_compile,
    content_http,  # noqa: F401
)


@pytest.mark.parametrize("source_title", ["", "[title=Старое название]"])
async def test_task_titles_in_published_documents_and_staff_preview(
    content_http,  # noqa: F811
    source_title,
):
    fixture = content_http
    revision, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="titles/condition.tex",
        source=f"\\задача{source_title} Найдите периметр. \\кзадача",
    )
    grid_url = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/metadata-grid"
    response = await fixture.client.get(
        grid_url,
        params={"revisionId": revision["revisionId"]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    grid = await response.json()
    row = grid["rows"][0]
    row.pop("reviewed")
    row["title"] = "Два квадрата и прямоугольник"
    row["problemType"] = 2
    saved = await fixture.client.put(
        grid_url,
        json={"revisionId": revision["revisionId"], "rows": [row]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=response.headers["ETag"]),
    )
    assert saved.status == 200, await saved.text()
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    assert published.status == 201, await published.text()

    # A newer unpublished revision must not replace the published title.
    draft, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="titles/draft.tex",
        source="\\задача[title=Название черновика] Новый текст. \\кзадача",
        review=False,
    )
    for audience, url, title in (
        (
            "student",
            f"/student/api/v1/group-lessons/{fixture.group_lesson_a}/content/condition",
            row["title"],
        ),
        (
            "family",
            f"/family/api/v1/children/u-903101/group-lessons/{fixture.group_lesson_a}/content/condition",
            row["title"],
        ),
        (
            "admin",
            f"/staff/api/v1/content/revisions/{revision['revisionId']}/previews/web",
            row["title"],
        ),
        (
            "admin",
            f"/staff/api/v1/content/revisions/{draft['revisionId']}/previews/web",
            "Название черновика",
        ),
    ):
        response = await fixture.client.get(
            url, cookies=_cookie(fixture, audience), headers=_headers()
        )
        assert response.status == 200, await response.text()
        problem = (await response.json())["document"]["problems"][0]
        assert problem["title"] == title
        assert problem["taskReference"] == "41a.1"
        assert "correctAnswer" not in problem and "answerConfig" not in problem

    # Omitted mappings are not a second source of visible metadata.
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE content_problem_matches SET decision='omit', problem_id=NULL WHERE content_revision_id="
            "(SELECT id FROM content_revisions WHERE public_id=?)",
            (revision["revisionId"],),
        )
    )
    response = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="condition"
    )
    assert (await response.json())["document"]["problems"][0]["title"] == (
        "Старое название" if source_title else None
    )
