"""Model persistence/permissions/migration; see docs/metadata-generation.md."""

import json
import sqlite3

import pytest

from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers
from pwa_tests.integration.test_phase10_course_catalog import _course
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)

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


def test_metadata_model_migration_preserves_existing_courses_up_down_up(tmp_path):
    path = tmp_path / "metadata-model.sqlite3"
    migration = "0104.course_metadata_model"
    all_migrations = {m.id: m for m in _migrations()}
    assert {m.id for m in all_migrations[migration].depends} == {
        "0103.course_in_person_classes"
    }
    _apply(path, set(all_migrations) - {migration})
    with sqlite3.connect(path) as c:
        c.execute(
            "INSERT INTO seasons (code,title,starts_on,ends_on,session_expires_on,status,created_at,updated_at) "
            "VALUES ('test','Test','2026-09-01','2027-06-01','2027-07-01','active','2026-10-01','2026-10-01')"
        )
        c.execute(
            "INSERT INTO courses (season_id,code,name,subject_code,has_in_person_classes,status,accent_key,created_at,updated_at) "
            "VALUES (1,'test','Test','math',0,'active','math','2026-10-01','2026-10-01')"
        )
    for _ in range(2):
        _apply(path, {migration})
        with sqlite3.connect(path) as c:
            assert c.execute(
                "SELECT name,has_in_person_classes,metadata_model FROM courses"
            ).fetchone() == ("Test", 0, "openai/gpt-5.6-luna")
            assert c.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        _rollback(path, {migration})
