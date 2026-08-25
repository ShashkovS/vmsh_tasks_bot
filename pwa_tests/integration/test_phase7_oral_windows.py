"""Phase-7 proof for configured oral windows and guarded join details."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from apps.pwa_api import oral_window_routes as oral_routes
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from models.pwa.oral_windows import create_due_window_notifications
from pwa_tests.integration import test_classroom_catalog_http_api as classroom_support
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0070.pwa_oral_windows"
NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
classroom_http = classroom_support.classroom_http


def test_oral_window_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "oral-windows.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0069.pwa_course_notification_preferences"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema WHERE name LIKE 'oral_windows%'"
            ).fetchone()[0]
            == 0
        )

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema WHERE name LIKE 'oral_windows%'"
            ).fetchone()[0]
            == 2
        )

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema WHERE name LIKE 'oral_windows%'"
            ).fetchone()[0]
            == 0
        )
    _apply(database_path, {MIGRATION_ID})


def _seed_group_lesson(fixture: classroom_support.ClassroomHttpFixture) -> None:
    now = NOW.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def seed(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'c-1'"
        ).fetchone()["id"]
        course_lesson_id = connection.execute(
            "INSERT INTO course_lessons "
            "(course_id, lesson_number, created_at, updated_at) "
            "VALUES (?, 41, ?, ?) RETURNING id",
            (course_id, now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO group_lessons "
            "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "(?, ?, 'layout-beginner', '2026-10-05', "
            "'Europe/Moscow', 'active', ?, ?)",
            (course_lesson_id, course_id, now, now),
        )
        connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'online' "
            "WHERE public_id = 'en-1'"
        )

    fixture.factory.run_write(seed)


def _payload(**changes) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "sequenceNumber": 1,
        "opensAt": (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "closesAt": (NOW + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "joinLabel": "Подключиться к Zoom",
        "joinUrl": "https://zoom.example.test/j/179",
        "joinCode": "179179",
        "status": "active",
    }
    payload.update(changes)
    return payload


async def test_admin_configures_and_online_student_reveals_open_join(
    classroom_http,
    monkeypatch,
):
    fixture = classroom_http
    _seed_group_lesson(fixture)
    monkeypatch.setattr(oral_routes, "_now", lambda: NOW)
    staff_path = "/staff/api/v1/group-lessons/gl-1/oral-windows"

    teacher = await fixture.client.post(
        staff_path,
        json=_payload(),
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(fixture, "teacher"),
    )
    assert teacher.status == 403

    created = await fixture.client.post(
        staff_path,
        json=_payload(),
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(fixture, "admin"),
    )
    assert created.status == 201, await created.text()
    window = (await created.json())["window"]
    assert window["state"] == "open"
    assert window["joinUrl"] == "https://zoom.example.test/j/179"

    duplicate = await fixture.client.post(
        staff_path,
        json=_payload(joinUrl="https://zoom.example.test/j/another"),
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(fixture, "admin"),
    )
    assert duplicate.status == 409

    student_cookies = {
        COOKIE_POLICY[AuthAudience.STUDENT].access_name: fixture.student_cookie
    }
    student_path = (
        "/student/api/v1/courses/c-1/lessons/"
        "gl-1/oral-windows"
    )
    listed = await fixture.client.get(
        student_path,
        headers=classroom_support._headers(),
        cookies=student_cookies,
    )
    assert listed.status == 200, await listed.text()
    listed_text = await listed.text()
    assert "zoom.example.test" not in listed_text
    assert "179179" not in listed_text
    public_window = (await listed.json())["items"][0]
    assert public_window["joinAvailable"] is True

    joined = await fixture.client.get(
        f"{student_path}/{window['windowId']}/join",
        headers=classroom_support._headers(),
        cookies=student_cookies,
    )
    assert joined.status == 200, await joined.text()
    assert joined.headers["Cache-Control"] == "no-store"
    assert (await joined.json())["join"] == {
        "windowId": window["windowId"],
        "joinLabel": "Подключиться к Zoom",
        "joinUrl": "https://zoom.example.test/j/179",
        "joinCode": "179179",
        "closesAt": "2026-10-05T13:00:00.000000Z",
    }

    stale = await fixture.client.put(
        f"/staff/api/v1/oral-windows/{window['windowId']}",
        json=_payload(status="cancelled"),
        headers={
            **classroom_support._headers(unsafe=True),
            "If-Match": f'"{window["windowId"]}:v99"',
        },
        cookies=classroom_support._cookies(fixture, "admin"),
    )
    assert stale.status == 409

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'in_person' "
            "WHERE public_id = 'en-1'"
        )
    )
    hidden = await fixture.client.get(
        student_path,
        headers=classroom_support._headers(),
        cookies=student_cookies,
    )
    assert hidden.status == 404


async def test_opening_window_notifies_current_online_student_once_without_secret(
    classroom_http,
    monkeypatch,
):
    fixture = classroom_http
    _seed_group_lesson(fixture)
    monkeypatch.setattr(oral_routes, "_now", lambda: NOW)
    created = await fixture.client.post(
        "/staff/api/v1/group-lessons/gl-1/oral-windows",
        json=_payload(),
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(fixture, "admin"),
    )
    assert created.status == 201, await created.text()
    window_id = (await created.json())["window"]["windowId"]
    through = NOW.isoformat(timespec="microseconds").replace("+00:00", "Z")

    notified = fixture.factory.run_write(
        lambda connection: create_due_window_notifications(
            connection,
            after=None,
            through=through,
        )
    )
    repeated = fixture.factory.run_write(
        lambda connection: create_due_window_notifications(
            connection,
            after=None,
            through=through,
        )
    )

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'in_person' "
            "WHERE public_id = 'en-1'"
        )
    )
    second = await fixture.client.post(
        "/staff/api/v1/group-lessons/gl-1/oral-windows",
        json=_payload(sequenceNumber=2, joinUrl="https://zoom.example.test/j/180"),
        headers=classroom_support._headers(unsafe=True),
        cookies=classroom_support._cookies(fixture, "admin"),
    )
    assert second.status == 201, await second.text()
    in_person = fixture.factory.run_write(
        lambda connection: create_due_window_notifications(
            connection,
            after=None,
            through=through,
        )
    )

    assert notified == ("a-3",)
    assert repeated == ()
    assert in_person == ()

    def notification_rows(connection):
        return connection.execute(
            "SELECT account.audience, event.category, event.dedupe_key, "
            "event.route, event.payload_json FROM notification_events AS event "
            "JOIN auth_accounts AS account ON account.id = event.account_id "
            "WHERE event.category = 'oral_window' ORDER BY event.id"
        ).fetchall()

    rows = fixture.factory.run_read(notification_rows)
    assert len(rows) == 1
    row = rows[0]
    assert row["audience"] == "student"
    assert row["dedupe_key"] == window_id
    assert row["route"] == (
        "/student/tasks?course=c-1&group="
        "g-5&lesson=41"
    )
    payload = json.loads(row["payload_json"])
    assert payload["windowId"] == window_id
    assert payload["groupLessonId"] == "gl-1"
    assert "joinUrl" not in payload
    assert "joinCode" not in payload
