from __future__ import annotations

import json
import sqlite3

import pytest

from db_methods.pwa.group_banners import list_current_group_banners
from models.pwa.group_banners import (
    GroupBannerConflict,
    cancel_banner,
    create_group_banner,
    edit_group_banner,
)
from models.pwa.group_banner_notifications import sync_group_banner_notifications
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    NOW,
    _insert_parents,
)
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
    _seed_account,
)


MIGRATION_ID = "0068.pwa_group_banners"
RICH_MARKDOWN_MIGRATION_ID = "0081.pwa_rich_markdown"
COMMUNICATION_TARGETING_MIGRATION_ID = "0089.pwa_communication_targeting"


def test_group_banner_migration_roundtrip(tmp_path):
    database_path = tmp_path / "banners.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    # Rich Markdown extends this table and is covered by its own migration
    # round-trip. Exclude it while proving the historical 0068 boundary.
    _apply(
        database_path,
        set(migrations)
        - {
            MIGRATION_ID,
            RICH_MARKDOWN_MIGRATION_ID,
            COMMUNICATION_TARGETING_MIGRATION_ID,
        },
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM sqlite_schema WHERE name = 'group_banners'"
        ).fetchone() == (0,)
    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    _rollback(database_path, {MIGRATION_ID})
    _apply(database_path, {MIGRATION_ID})


def test_banner_sanitizing_window_and_optimistic_cancel(tmp_path):
    database_path = tmp_path / "banners.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _insert_parents(connection)
    course_id = int(
        connection.execute(
            "SELECT course_id FROM groups WHERE group_id = 'assignment-n'"
        ).fetchone()[0]
    )

    item = create_group_banner(
        connection,
        course_id=course_id,
        group_id="assignment-n",
        audience="both",
        attendance_mode="all",
        html_source=(
            '<b>Разбор в 17:00</b> · <a href="javascript:alert(1)">войти</a>'
            "<script>bad()</script>"
        ),
        starts_at="2026-10-05T12:00:00Z",
        ends_at="2026-10-05T18:00:00Z",
        priority=10,
        dismissible=True,
        actor_user_id=2,
        now="2026-10-05T11:00:00Z",
    )
    assert "javascript" not in item["html_sanitized"]
    assert "<script" not in item["html_sanitized"]
    assert (
        len(
            list_current_group_banners(
                connection,
                enrollment_targets=((course_id, "assignment-n", "online"),),
                audience="student",
                now="2026-10-05T13:00:00Z",
            )
        )
        == 1
    )
    assert (
        list_current_group_banners(
            connection,
            enrollment_targets=((course_id, "assignment-n", "online"),),
            audience="student",
            now="2026-10-05T18:00:00Z",
        )
        == []
    )

    updated = edit_group_banner(
        connection,
        public_id="bn-1",
        expected_version=1,
        course_id=course_id,
        group_id="assignment-n",
        audience="student",
        attendance_mode="all",
        html_source="<i>Новое время</i>",
        starts_at="2026-10-05T12:30:00Z",
        ends_at="2026-10-05T19:00:00Z",
        priority=20,
        dismissible=False,
        actor_user_id=2,
        now="2026-10-05T11:05:00Z",
    )
    assert updated["version"] == 2
    with pytest.raises(GroupBannerConflict):
        cancel_banner(
            connection,
            public_id="bn-1",
            expected_version=1,
            actor_user_id=2,
            now="2026-10-05T11:06:00Z",
        )
    cancelled = cancel_banner(
        connection,
        public_id="bn-1",
        expected_version=2,
        actor_user_id=2,
        now="2026-10-05T11:07:00Z",
    )
    assert (cancelled["status"], cancelled["version"]) == ("cancelled", 3)
    connection.close()


def test_banner_visibility_matches_course_group_audience_and_attendance(tmp_path):
    database_path = tmp_path / "banner-targeting.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _insert_parents(connection)
    course_id = int(
        connection.execute(
            "SELECT course_id FROM groups WHERE group_id = 'assignment-n'"
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, course_id, status, color_key, "
        "created_at, updated_at) VALUES "
        "('assignment-p', 'ап', 'Продолжающие', 2, 1, 0, 1, 0, 1.0, "
        "?, 'active', 'level-2', ?, ?)",
        (course_id, NOW, NOW),
    )

    for group_id, audience, attendance_mode, text in (
        (None, "both", "all", "course-all"),
        ("assignment-n", "student", "in_person", "student-active"),
        ("assignment-n", "family", "in_person", "family-active"),
        ("assignment-n", "both", "online", "wrong-attendance"),
        ("assignment-p", "both", "all", "wrong-group"),
    ):
        create_group_banner(
            connection,
            course_id=course_id,
            group_id=group_id,
            audience=audience,
            attendance_mode=attendance_mode,
            html_source=f"<p>{text}</p>",
            starts_at="2026-10-05T12:00:00Z",
            ends_at="2026-10-05T18:00:00Z",
            priority=0,
            dismissible=True,
            actor_user_id=2,
            now="2026-10-05T11:00:00Z",
        )

    target = ((course_id, "assignment-n", "in_person"),)
    student = list_current_group_banners(
        connection,
        enrollment_targets=target,
        audience="student",
        now="2026-10-05T13:00:00Z",
    )
    family = list_current_group_banners(
        connection,
        enrollment_targets=target,
        audience="family",
        now="2026-10-05T13:00:00Z",
    )
    assert {str(item["html_sanitized"]) for item in student} == {
        "course-all",
        "student-active",
    }
    assert {str(item["html_sanitized"]) for item in family} == {
        "course-all",
        "family-active",
    }
    connection.close()


def test_future_banner_schedules_and_replaces_group_notifications(tmp_path):
    database_path = tmp_path / "banner-notifications.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        account_id, _session_id = _seed_account(connection)
        course_id = int(
            connection.execute(
                "SELECT course_id FROM groups WHERE group_id = 'assignment-n'"
            ).fetchone()[0]
        )
        created = create_group_banner(
            connection,
            course_id=course_id,
            group_id="assignment-n",
            audience="student",
            attendance_mode="all",
            html_source="<b>Встречаемся у входа</b>",
            starts_at="2026-10-05T12:00:00Z",
            ends_at="2026-10-05T18:00:00Z",
            priority=0,
            dismissible=True,
            actor_user_id=2,
            now="2026-10-05T11:00:00Z",
        )
        assert (
            sync_group_banner_notifications(
                connection, banner=created, now="2026-10-05T11:00:00Z"
            )
            == 1
        )
        scheduled = connection.execute(
            "SELECT account_id, category, route, payload_json, deliver_after "
            "FROM notification_events"
        ).fetchone()
        assert dict(scheduled) | {"payload_json": None} == {
            "account_id": account_id,
            "category": "group_announcement",
            "route": "/student/",
            "payload_json": None,
            "deliver_after": "2026-10-05T12:00:00Z",
        }
        assert json.loads(str(scheduled["payload_json"])) == {
            "bannerId": "bn-1",
            "courseId": "c-1",
            "groupId": created["group_public_id"],
            "groupName": "Начинающие",
            "text": "Встречаемся у входа",
        }

        updated = edit_group_banner(
            connection,
            public_id="bn-1",
            expected_version=1,
            course_id=course_id,
            group_id="assignment-n",
            audience="student",
            attendance_mode="all",
            html_source="<i>Встречаемся у второго входа</i>",
            starts_at="2026-10-05T12:30:00Z",
            ends_at="2026-10-05T18:00:00Z",
            priority=0,
            dismissible=True,
            actor_user_id=2,
            now="2026-10-05T11:05:00Z",
        )
        assert (
            sync_group_banner_notifications(
                connection, banner=updated, now="2026-10-05T11:05:00Z"
            )
            == 1
        )
        replacement = connection.execute(
            "SELECT payload_json, deliver_after FROM notification_events"
        ).fetchone()
        assert replacement["deliver_after"] == "2026-10-05T12:30:00Z"
        assert json.loads(str(replacement["payload_json"]))["text"] == "Встречаемся у второго входа"

        cancelled = cancel_banner(
            connection,
            public_id="bn-1",
            expected_version=2,
            actor_user_id=2,
            now="2026-10-05T11:10:00Z",
        )
        assert sync_group_banner_notifications(connection, banner=cancelled, now="2026-10-05T11:10:00Z") == 0
        assert connection.execute("SELECT count(*) FROM notification_events").fetchone()[0] == 0
