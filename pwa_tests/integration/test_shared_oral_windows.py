"""Shared weekly drafts: membership, atomic receipt and legacy compatibility."""

from pathlib import Path
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience

from pwa_tests.integration.test_phase7_oral_windows import (
    NOW,
    _payload,
    _seed_group_lesson,
)
from pwa_tests.integration import test_classroom_catalog_http_api as support

classroom_http = support.classroom_http


def seed(fixture):
    _seed_group_lesson(fixture)

    def write(connection):
        connection.execute(
            "INSERT INTO groups (group_id, short_code, public_name, sort_order, is_active, is_default, allow_self_switch, is_system, score_weight, course_id, status, color_key, created_at, updated_at) SELECT 'layout-middle', 'п', 'Продолжающие', 2, 1, 0, 0, 0, 1.0, course_id, status, color_key, created_at, updated_at FROM groups WHERE group_id = 'layout-beginner'"
        )
        connection.execute(
            "INSERT INTO course_group_access (enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "SELECT enrollment_id, course_id, 'layout-middle', valid_from, created_at, updated_at "
            "FROM course_group_access WHERE group_id = 'layout-beginner'"
        )
        second = connection.execute(
            "INSERT INTO group_lessons (course_lesson_id, course_id, group_id, cycle_anchor_date, business_timezone, status, created_at, updated_at) SELECT course_lesson_id, course_id, 'layout-middle', cycle_anchor_date, business_timezone, status, created_at, updated_at FROM group_lessons WHERE public_id = 'gl-1' RETURNING public_id"
        ).fetchone()["public_id"]
        number = connection.execute(
            "INSERT INTO course_lessons (course_id, lesson_number, created_at, updated_at) SELECT course_id, 42, created_at, updated_at FROM group_lessons WHERE public_id = 'gl-1' RETURNING id"
        ).fetchone()["id"]
        future = connection.execute(
            "INSERT INTO group_lessons (course_lesson_id, course_id, group_id, cycle_anchor_date, business_timezone, status, created_at, updated_at) SELECT ?, course_id, group_id, cycle_anchor_date, business_timezone, status, created_at, updated_at FROM group_lessons WHERE public_id = 'gl-1' RETURNING public_id",
            (number,),
        ).fetchone()["public_id"]
        return second, future

    return fixture.factory.run_write(write)


async def test_shared_batch_update_replay_permissions_and_next_week(classroom_http):
    fixture = classroom_http
    second, future = seed(fixture)
    base = "/staff/api/v1/group-lessons/gl-1/oral-windows"
    headers = support._headers(unsafe=True)
    cookies = support._cookies(fixture, "admin")
    body = dict(
        schemaVersion=1,
        idempotencyKey="weekly-1",
        entries=[dict(groupLessonIds=["gl-1", second], window=_payload())],
    )
    forbidden = await fixture.client.post(
        base + "/batch",
        json=body,
        headers=headers,
        cookies=support._cookies(fixture, "teacher"),
    )
    assert forbidden.status == 403
    created = await fixture.client.post(
        base + "/batch", json=body, headers=headers, cookies=cookies
    )
    assert created.status == 201, await created.text()
    window = (await created.json())["items"][0]
    assert len(window["groups"]) == 2
    again = await fixture.client.post(
        base + "/batch", json=body, headers=headers, cookies=cookies
    )
    assert (await again.json())["items"][0]["windowId"] == window["windowId"]
    changed = await fixture.client.put(
        "/staff/api/v1/oral-windows/" + window["windowId"],
        json=_payload(joinUrl="https://zoom.example.test/new"),
        headers={**headers, "If-Match": f'"{window["windowId"]}:v1"'},
        cookies=cookies,
    )
    assert changed.status == 200, await changed.text()
    for lesson in ["gl-1", second]:
        listed = await fixture.client.get(
            f"/staff/api/v1/group-lessons/{lesson}/oral-windows",
            headers=support._headers(),
            cookies=cookies,
        )
        item = (await listed.json())["items"][0]
        assert item["joinUrl"] == "https://zoom.example.test/new"
        assert item["version"] == 2 and item["windowId"] == window["windowId"]
    stale = await fixture.client.put(
        "/staff/api/v1/oral-windows/" + window["windowId"],
        json=_payload(),
        headers={**headers, "If-Match": f'"{window["windowId"]}:v1"'},
        cookies=cookies,
    )
    assert stale.status == 409
    collision = await fixture.client.post(
        f"/staff/api/v1/group-lessons/{second}/oral-windows",
        json=_payload(),
        headers=headers,
        cookies=cookies,
    )
    assert collision.status == 409
    plan = await fixture.client.get(
        f"/staff/api/v1/group-lessons/{future}/oral-windows/planning",
        headers=support._headers(),
        cookies=cookies,
    )
    assert plan.status == 200, await plan.text()
    data = await plan.json()
    assert data["lessonNumber"] == 42 and data["previous"][0]["groupLessonIds"] == [
        future
    ]
    assert data["previous"][0]["window"]["joinUrl"] == "https://zoom.example.test/new"
    cancelled = await fixture.client.put(
        "/staff/api/v1/oral-windows/" + window["windowId"],
        json=_payload(status="cancelled"),
        headers={**headers, "If-Match": f'"{window["windowId"]}:v2"'},
        cookies=cookies,
    )
    assert cancelled.status == 200
    listed = await fixture.client.get(
        f"/staff/api/v1/group-lessons/{second}/oral-windows",
        headers=support._headers(),
        cookies=cookies,
    )
    assert (await listed.json())["items"][0]["status"] == "cancelled"


async def test_atomic_validation_and_changed_idempotency_key(classroom_http):
    fixture = classroom_http
    second, future = seed(fixture)
    base = "/staff/api/v1/group-lessons/gl-1/oral-windows"
    headers, cookies = support._headers(unsafe=True), support._cookies(fixture, "admin")
    entry = dict(groupLessonIds=["gl-1", second], window=_payload())
    body = dict(
        schemaVersion=1,
        idempotencyKey="atomic",
        entries=[entry, dict(groupLessonIds=[future], window=_payload())],
    )
    invalid = await fixture.client.post(
        base + "/batch", json=body, headers=headers, cookies=cookies
    )
    assert invalid.status == 422, await invalid.text()
    listed = await fixture.client.get(base, headers=support._headers(), cookies=cookies)
    assert (await listed.json())["items"] == []
    body["entries"] = [entry]
    good = await fixture.client.post(
        base + "/batch", json=body, headers=headers, cookies=cookies
    )
    assert good.status == 201
    body["entries"][0]["window"] = _payload(joinLabel="Changed")
    conflict = await fixture.client.post(
        base + "/batch", json=body, headers=headers, cookies=cookies
    )
    assert conflict.status == 409


async def test_membership_backfill_and_secondary_group_student_join(
    classroom_http, monkeypatch
):
    from apps.pwa_api import oral_window_routes

    fixture = classroom_http
    second, _ = seed(fixture)
    monkeypatch.setattr(oral_window_routes, "_now", lambda: NOW)
    cookies, headers = support._cookies(fixture, "admin"), support._headers(unsafe=True)
    created = await fixture.client.post(
        "/staff/api/v1/group-lessons/gl-1/oral-windows/batch",
        json=dict(
            schemaVersion=1,
            idempotencyKey="join",
            entries=[dict(groupLessonIds=["gl-1", second], window=_payload())],
        ),
        headers=headers,
        cookies=cookies,
    )
    window = (await created.json())["items"][0]
    fixture.factory.run_write(
        lambda c: c.execute(
            "UPDATE course_enrollments SET active_group_id = 'layout-middle' WHERE public_id = 'en-1'"
        )
    )
    joined = await fixture.client.get(
        f"/student/api/v1/courses/c-1/lessons/{second}/oral-windows/{window['windowId']}/join",
        headers=support._headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.STUDENT].access_name: fixture.student_cookie
        },
    )
    assert joined.status == 200, await joined.text()

    def rehearse(connection):
        root = Path(__file__).resolve().parents[2] / "migrations"
        existing_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        # Rehearse on the same isolated fixture; legacy primary window IDs survive.
        connection.executescript(
            (root / "0094.pwa_shared_oral_windows.rollback.sql").read_text()
        )
        connection.executescript(
            (root / "0094.pwa_shared_oral_windows.sql").read_text()
        )
        assert (
            connection.execute("SELECT count(*) n FROM oral_window_lessons").fetchone()[
                "n"
            ]
            == 1
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == existing_violations
        assert connection.execute("PRAGMA foreign_key_check(oral_window_lessons)").fetchall() == []

    fixture.factory.run_write(rehearse)
