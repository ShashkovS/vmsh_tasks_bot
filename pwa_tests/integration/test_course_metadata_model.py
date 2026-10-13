"""Model persistence/permissions/migration; see docs/metadata-generation.md."""

import json

import pytest

from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers
from pwa_tests.integration.test_phase10_course_catalog import _course

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_course_model_defaults_updates_conflicts_and_legacy_edits(classroom_http):
    f = classroom_http
    response = await f.client.post(
        "/staff/api/v1/courses",
        json=_course(season_id="s-1"),
        headers=_headers(unsafe=True),
        cookies=_cookies(f, "admin"),
    )
    assert response.status == 201, await response.text()
    course = (await response.json())["course"]
    assert course["metadataModel"] == "openai/gpt-5.6-luna"
    course_id = course["courseId"]
    data = _course(season_id="s-1")
    data.pop("seasonId")
    data["metadataModel"] = " provider/future-model:free "
    url = f"/staff/api/v1/courses/{course_id}"
    for identity, status in [("teacher", 403), ("admin", 200)]:
        response = await f.client.put(
            url,
            json=data,
            headers=_headers(unsafe=True, if_match=f'"{course_id}:v1"'),
            cookies=_cookies(f, identity),
        )
        assert response.status == status, await response.text()
    assert (await response.json())["course"][
        "metadataModel"
    ] == "provider/future-model:free"
    stale = await f.client.put(
        url,
        json=data,
        headers=_headers(unsafe=True, if_match=f'"{course_id}:v1"'),
        cookies=_cookies(f, "admin"),
    )
    assert stale.status == 409
    data.pop("metadataModel")
    data["name"] = "Renamed"
    response = await f.client.put(
        url,
        json=data,
        headers=_headers(unsafe=True, if_match=f'"{course_id}:v2"'),
        cookies=_cookies(f, "admin"),
    )
    assert response.status == 200
    assert (await response.json())["course"][
        "metadataModel"
    ] == "provider/future-model:free"
    catalog = await f.client.get(
        "/staff/api/v1/courses", headers=_headers(), cookies=_cookies(f, "admin")
    )
    courses = (await catalog.json())["courses"]
    assert (
        next(c for c in courses if c["courseId"] == course_id)["metadataModel"]
        == "provider/future-model:free"
    )
    assert (
        next(c for c in courses if c["courseId"] != course_id)["metadataModel"]
        == "openai/gpt-5.6-luna"
    )
    row = f.factory.run_read(
        lambda c: c.execute(
            "SELECT before_json,after_json FROM audit_events WHERE object_id=? AND action='course.updated' ORDER BY id LIMIT 1",
            (course_id,),
        ).fetchone()
    )
    assert json.loads(row["before_json"])["metadataModel"] == "openai/gpt-5.6-luna"
    assert (
        json.loads(row["after_json"])["metadataModel"] == "provider/future-model:free"
    )


@pytest.mark.parametrize(
    "model",
    ["", "gpt-6-luna", "provider/", "provider/model name", None, 3, "p/" + "x" * 200],
)
async def test_course_model_rejects_invalid_ids(classroom_http, model):
    f = classroom_http
    response = await f.client.post(
        "/staff/api/v1/courses",
        json={**_course(season_id="s-1"), "metadataModel": model},
        headers=_headers(unsafe=True),
        cookies=_cookies(f, "admin"),
    )
    assert response.status == 422, await response.text()
    assert (await response.json())["error"]["details"]["field"] == "metadataModel"
