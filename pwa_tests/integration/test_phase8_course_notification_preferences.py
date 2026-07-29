"""Phase-8 proof for per-course Student push overrides."""

from __future__ import annotations

import sqlite3

from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from pwa_tests.integration import test_classroom_catalog_http_api as classroom_support
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0069.pwa_course_notification_preferences"
classroom_http = classroom_support.classroom_http


def test_course_preference_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "course-notification-preferences.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0068.pwa_group_banners"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name = 'notification_course_preferences'"
            ).fetchone()[0]
            == 0
        )

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name = 'notification_course_preferences'"
            ).fetchone()[0]
            == 1
        )

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name = 'notification_course_preferences'"
            ).fetchone()[0]
            == 0
        )
    _apply(database_path, {MIGRATION_ID})


async def test_student_can_override_and_restore_course_push(classroom_http):
    path = (
        "/student/api/v1/courses/classroom-layout-course/notifications/preferences"
    )
    cookies = {
        COOKIE_POLICY[AuthAudience.STUDENT].access_name: classroom_http.student_cookie
    }

    initial = await classroom_http.client.get(
        path,
        headers=classroom_support._headers(),
        cookies=cookies,
    )
    assert initial.status == 200, await initial.text()
    items = (await initial.json())["items"]
    news = next(item for item in items if item["category"] == "news")
    assert news == {
        "category": "news",
        "pushEnabled": True,
        "inherited": True,
        "updatedAt": None,
    }

    overridden = await classroom_http.client.put(
        path,
        json={"schemaVersion": 1, "category": "news", "pushEnabled": False},
        headers=classroom_support._headers(unsafe=True),
        cookies=cookies,
    )
    assert overridden.status == 200, await overridden.text()
    overridden_preference = (await overridden.json())["preference"]
    assert overridden_preference["updatedAt"] is not None
    assert overridden_preference | {"updatedAt": None} == {
        "category": "news",
        "pushEnabled": False,
        "inherited": False,
        "updatedAt": None,
    }

    restored = await classroom_http.client.put(
        path,
        json={"schemaVersion": 1, "category": "news", "pushEnabled": None},
        headers=classroom_support._headers(unsafe=True),
        cookies=cookies,
    )
    assert restored.status == 200, await restored.text()
    assert (await restored.json())["preference"] == news

    missing = await classroom_http.client.get(
        "/student/api/v1/courses/missing-course/notifications/preferences",
        headers=classroom_support._headers(),
        cookies=cookies,
    )
    assert missing.status == 404
