"""Acceptance for vmshpwa/docs/course-attendance-settings.md."""

import json

import pytest

from models.pwa.family_enrollment import (
    AttendanceModeUnavailable,
    change_family_enrollment,
)
from db_methods.pwa.classroom_assignments import (
    list_eligible_students,
    list_student_classroom_events,
)
from db_methods.pwa.classroom_layouts import (
    list_group_lesson_candidates,
    resolve_group_lesson_ids,
)
from db_methods.pwa.notifications import list_events
from models.pwa.notifications import read_preferences
from pwa_tests.integration.test_classroom_catalog_http_api import (
    _cookies,
    _headers,
    _seed_layout_scope,
)
from pwa_tests.integration.test_phase10_course_catalog import _course

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


async def test_admin_setting_defaults_versions_audit_and_legacy_edits(classroom_http):
    f = classroom_http
    created = await f.client.post(
        "/staff/api/v1/courses",
        json=_course(season_id="s-1"),
        headers=_headers(unsafe=True),
        cookies=_cookies(f, "admin"),
    )
    assert created.status == 201, await created.text()
    body = (await created.json())["course"]
    assert body["hasInPersonClasses"] is True
    course_id = body["courseId"]
    data = _course(season_id="s-1")
    data.pop("seasonId")
    data["hasInPersonClasses"] = False
    for identity, expected in [("teacher", 403), ("admin", 200)]:
        result = await f.client.put(
            f"/staff/api/v1/courses/{course_id}",
            json=data,
            headers=_headers(unsafe=True, if_match=f'"{course_id}:v1"'),
            cookies=_cookies(f, identity),
        )
        assert result.status == expected, await result.text()
    assert (await result.json())["course"]["hasInPersonClasses"] is False
    stale = await f.client.put(
        f"/staff/api/v1/courses/{course_id}",
        json=data,
        headers=_headers(unsafe=True, if_match=f'"{course_id}:v1"'),
        cookies=_cookies(f, "admin"),
    )
    assert stale.status == 409
    data.pop("hasInPersonClasses")
    data["name"] = "Renamed"
    legacy = await f.client.put(
        f"/staff/api/v1/courses/{course_id}",
        json=data,
        headers=_headers(unsafe=True, if_match=f'"{course_id}:v2"'),
        cookies=_cookies(f, "admin"),
    )
    assert legacy.status == 200
    assert (await legacy.json())["course"]["hasInPersonClasses"] is False
    rows = f.factory.run_read(
        lambda c: c.execute(
            "SELECT before_json,after_json FROM audit_events WHERE object_id=? AND action='course.updated' ORDER BY id",
            (course_id,),
        ).fetchall()
    )
    assert json.loads(rows[0]["before_json"])["hasInPersonClasses"] is True
    assert json.loads(rows[0]["after_json"])["hasInPersonClasses"] is False


async def test_disabled_course_preserves_preference_and_blocks_new_operations(
    classroom_http,
):
    f = classroom_http
    _seed_layout_scope(f.factory)

    def check(c):
        enrollment = dict(
            c.execute("SELECT * FROM course_enrollments LIMIT 1").fetchone()
        )
        course_id = enrollment["course_id"]
        c.execute("UPDATE courses SET has_in_person_classes=0 WHERE id=?", (course_id,))
        kwargs = dict(
            enrollment_id=enrollment["id"],
            course_id=course_id,
            student_user_id=enrollment["student_user_id"],
            expected_version=enrollment["version"],
            previous_group_id=enrollment["active_group_id"],
            active_group_id=enrollment["active_group_id"],
            previous_attendance_mode=enrollment["attendance_mode"],
            request_id="setting-check",
            now="2026-10-01T00:00:00Z",
        )
        with pytest.raises(AttendanceModeUnavailable):
            change_family_enrollment(
                c,
                attendance_mode="online"
                if enrollment["attendance_mode"] == "in_person"
                else "in_person",
                **kwargs,
            )
        assert (
            change_family_enrollment(c, attendance_mode=None, **kwargs)
            == enrollment["version"]
        )
        assert (
            c.execute(
                "SELECT attendance_mode FROM course_enrollments WHERE id=?",
                (enrollment["id"],),
            ).fetchone()["attendance_mode"]
            == enrollment["attendance_mode"]
        )
        assert list_eligible_students(c, 1) == []
        assert list_student_classroom_events(c, enrollment["student_user_id"]) == []
        assert list_group_lesson_candidates(c, season_id=1) == []
        assert resolve_group_lesson_ids(c, season_id=1, public_ids=("gl-1",)) == []
        c.execute("UPDATE courses SET has_in_person_classes=1 WHERE id=?", (course_id,))
        assert list_eligible_students(c, 1)

    f.factory.run_write(check)


async def test_disabled_notification_history_is_hidden_and_restored(classroom_http):
    f = classroom_http
    _seed_layout_scope(f.factory)

    def check(c):
        account = c.execute(
            "SELECT id FROM auth_accounts WHERE audience='student' LIMIT 1"
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO notification_events(account_id,category,route,payload_json,occurred_at,deliver_after,created_at,dedupe_key) VALUES(?,'classroom_assignment','/student/',?, '2026-09-01T00:00:00Z','2026-09-01T00:00:00Z','2026-09-01T00:00:00Z','attendance-setting-test')",
            (account, json.dumps({"courseId": "c-1"})),
        )
        assert "classroom_assignment" in {
            p["category"] for p in read_preferences(c, account)
        }
        c.execute("UPDATE courses SET has_in_person_classes=0")
        assert (
            list_events(
                c,
                account_id=account,
                limit=100,
                unread_only=True,
                now="2026-10-01T00:00:00Z",
            )
            == []
        )
        assert "classroom_assignment" not in {
            p["category"] for p in read_preferences(c, account)
        }
        assert (
            c.execute("SELECT count(*) AS n FROM notification_events").fetchone()["n"]
            == 1
        )
        c.execute("UPDATE courses SET has_in_person_classes=1")
        assert (
            len(
                list_events(
                    c,
                    account_id=account,
                    limit=100,
                    unread_only=True,
                    now="2026-10-01T00:00:00Z",
                )
            )
            == 1
        )

    f.factory.run_write(check)


async def test_mixed_course_membership_and_family_projection(classroom_http):
    from models.pwa.auth import AuthAudience
    from helpers.pwa.auth_config import COOKIE_POLICY

    f = classroom_http
    _seed_layout_scope(f.factory)
    for enabled in (False, True):
        f.factory.run_write(
            lambda c: c.execute(
                "UPDATE courses SET has_in_person_classes=?", (int(enabled),)
            )
        )
        for path, cookie in [
            (
                "/student/api/v1/classroom-assignments",
                {COOKIE_POLICY[AuthAudience.STUDENT].access_name: f.student_cookie},
            ),
            (
                "/family/api/v1/children/u-958003/classroom-assignments",
                {COOKIE_POLICY[AuthAudience.FAMILY].access_name: f.family_cookie},
            ),
        ]:
            response = await f.client.get(path, headers=_headers(), cookies=cookie)
            assert response.status == 200
            body = await response.json()
            assert body["hasInPersonCourses"] is enabled
            assert bool(body["items"]) is enabled


async def test_mixed_courses_filter_room_items_and_each_courses_preferences(
    classroom_http,
):
    from db_methods.pwa.classroom_assignments import has_student_in_person_courses
    from models.pwa.notifications import read_course_preferences

    f = classroom_http
    _seed_layout_scope(f.factory)

    def check(c):
        student = c.execute(
            "SELECT student_user_id FROM course_enrollments LIMIT 1"
        ).fetchone()["student_user_id"]
        course = c.execute(
            "INSERT INTO courses(season_id,code,name,subject_code,status,sort_order,accent_key,created_at,updated_at) SELECT season_id,'second-course','Second course',subject_code,status,sort_order,accent_key,created_at,updated_at FROM courses WHERE id=1 RETURNING id,public_id"
        ).fetchone()
        cid = course["id"]
        c.execute(
            "INSERT INTO groups(group_id,short_code,public_name,sort_order,is_active,is_default,allow_self_switch,is_system,score_weight,course_id,status,color_key,created_at,updated_at) SELECT 'second-group',short_code,public_name,sort_order,is_active,is_default,allow_self_switch,is_system,score_weight,?,status,color_key,created_at,updated_at FROM groups WHERE course_id=1",
            (cid,),
        )
        c.execute(
            "INSERT INTO course_enrollments(student_user_id,course_id,active_group_id,attendance_mode,status,created_at,updated_at) SELECT student_user_id,?,'second-group',attendance_mode,status,created_at,updated_at FROM course_enrollments WHERE course_id=1",
            (cid,),
        )
        lesson = c.execute(
            "INSERT INTO course_lessons(course_id,lesson_number,created_at,updated_at) SELECT ?,lesson_number,created_at,updated_at FROM course_lessons LIMIT 1 RETURNING id",
            (cid,),
        ).fetchone()["id"]
        gl = c.execute(
            "INSERT INTO group_lessons(course_lesson_id,course_id,group_id,cycle_anchor_date,business_timezone,status,created_at,updated_at) SELECT ?,?,'second-group',cycle_anchor_date,business_timezone,status,created_at,updated_at FROM group_lessons LIMIT 1 RETURNING id",
            (lesson, cid),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO in_person_event_group_lessons(in_person_event_id,group_lesson_id,added_by_user_id,created_at) SELECT in_person_event_id,?,added_by_user_id,created_at FROM in_person_event_group_lessons LIMIT 1",
            (gl,),
        )
        c.execute("UPDATE courses SET has_in_person_classes=0 WHERE id=1")
        assert has_student_in_person_courses(c, student)
        items = list_student_classroom_events(c, student)
        assert {item["course_public_id"] for item in items} == {course["public_id"]}
        account = c.execute(
            "SELECT id FROM auth_accounts WHERE audience='student' LIMIT 1"
        ).fetchone()["id"]
        assert "classroom_assignment" in {
            item["category"] for item in read_preferences(c, account)
        }
        assert "classroom_assignment" not in {
            item["category"]
            for item in read_course_preferences(
                c, account_id=account, course_public_id="c-1"
            )[1]
        }
        assert "classroom_assignment" in {
            item["category"]
            for item in read_course_preferences(
                c, account_id=account, course_public_id=course["public_id"]
            )[1]
        }

    f.factory.run_write(check)


def test_migration_keeps_existing_courses_and_rolls_back(tmp_path):
    import sqlite3
    from pwa_tests.integration.test_phase8_notification_core import (
        _apply,
        _migrations,
        _rollback,
    )
    from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
        _insert_parents,
    )

    path = tmp_path / "course-attendance.sqlite3"
    migration_id = "0103.course_in_person_classes"
    _apply(path, {m.id for m in _migrations()} - {migration_id})
    with sqlite3.connect(path) as c:
        c.row_factory = sqlite3.Row
        _insert_parents(c)
        before = [tuple(row) for row in c.execute("SELECT * FROM course_enrollments")]
    _apply(path, {migration_id})
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT has_in_person_classes FROM courses").fetchall() == [
            (1,)
        ]
        assert [
            tuple(row) for row in c.execute("SELECT * FROM course_enrollments")
        ] == before
        assert c.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    _rollback(path, {migration_id})
    _apply(path, {migration_id})
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT has_in_person_classes FROM courses").fetchall() == [
            (1,)
        ]


async def test_disabled_course_retains_online_targets_and_saved_preference(
    classroom_http,
):
    from db_methods.pwa.notifications import (
        active_online_student_accounts_for_group,
        targeted_notification_accounts,
    )
    from db_methods.pwa.news import list_news_recipient_accounts
    from db_methods.pwa.oral_results import online_students

    f = classroom_http
    _seed_layout_scope(f.factory)

    def check(c):
        e = c.execute("SELECT * FROM course_enrollments LIMIT 1").fetchone()
        c.execute(
            "UPDATE course_enrollments SET attendance_mode='in_person' WHERE id=?",
            (e["id"],),
        )
        c.execute(
            "UPDATE courses SET has_in_person_classes=0 WHERE id=?", (e["course_id"],)
        )
        assert active_online_student_accounts_for_group(
            c, course_id=e["course_id"], group_id=e["active_group_id"]
        )
        group = c.execute(
            "SELECT public_id FROM groups WHERE group_id=?", (e["active_group_id"],)
        ).fetchone()["public_id"]
        assert online_students(c, course_public_id="c-1", group_public_id=group)
        for mode in ("online", "in_person"):
            targets = targeted_notification_accounts(
                c, course_id=e["course_id"], group_id=None, attendance_mode=mode
            )
            news = list_news_recipient_accounts(
                c,
                owner_course_id=e["course_id"],
                owner_group_id=None,
                audience="both",
                attendance_mode=mode,
            )
            assert bool(targets) is (mode == "online")
            assert bool(news) is (mode == "online")
        assert (
            c.execute(
                "SELECT attendance_mode FROM course_enrollments WHERE id=?", (e["id"],)
            ).fetchone()["attendance_mode"]
            == "in_person"
        )

    f.factory.run_write(check)


async def test_pending_layout_confirmation_rechecks_course_setting(classroom_http):
    f = classroom_http
    _seed_layout_scope(f.factory)
    path = "/staff/api/v1/in-person-events/ipe-1/classroom-layout"
    response = await f.client.post(
        path + "/materialize",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(f, "admin"),
    )
    assert response.status == 200, await response.text()
    layout = (await response.json())["layout"]
    lid = layout["publicId"]
    response = await f.client.put(
        path + f"/{lid}/rooms",
        json={
            "schemaVersion": 1,
            "mappings": [
                {"classroomPublicId": "room-1", "groupLessonPublicId": "gl-1"}
            ],
        },
        headers=_headers(unsafe=True, if_match=f'"{lid}:v1"'),
        cookies=_cookies(f, "admin"),
    )
    assert response.status == 200, await response.text()
    f.factory.run_write(
        lambda c: c.execute("UPDATE courses SET has_in_person_classes=0")
    )
    response = await f.client.post(
        path + f"/{lid}/confirm",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{lid}:v2"'),
        cookies=_cookies(f, "admin"),
    )
    assert response.status == 422, await response.text()
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT state FROM classroom_layout_versions WHERE public_id=?", (lid,)
            ).fetchone()["state"]
        )
        == "draft"
    )
