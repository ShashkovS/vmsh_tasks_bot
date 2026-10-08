"""Pure rules for Staff edits to one course enrollment."""

from __future__ import annotations

import pytest

from models.pwa.admin_enrollment import (
    InvalidAdminEnrollmentChange,
    plan_admin_enrollment_change,
)


def test_plan_requires_at_least_one_allowed_group() -> None:
    with pytest.raises(InvalidAdminEnrollmentChange, match="allowed_groups_empty"):
        plan_admin_enrollment_change(
            current_active_group_id="beginner",
            current_attendance_mode="in_person",
            current_status="active",
            current_allowed_group_ids={"beginner"},
            active_group_id="beginner",
            attendance_mode="in_person",
            status="active",
            allowed_group_ids=set(),
        )


def test_plan_requires_active_group_to_remain_available() -> None:
    with pytest.raises(InvalidAdminEnrollmentChange, match="active_group_not_allowed"):
        plan_admin_enrollment_change(
            current_active_group_id="beginner",
            current_attendance_mode="in_person",
            current_status="active",
            current_allowed_group_ids={"beginner"},
            active_group_id="advanced",
            attendance_mode="online",
            status="active",
            allowed_group_ids={"beginner"},
        )


def test_plan_returns_only_the_actual_changes() -> None:
    plan = plan_admin_enrollment_change(
        current_active_group_id="beginner",
        current_attendance_mode="in_person",
        current_status="active",
        current_allowed_group_ids={"beginner", "archive"},
        active_group_id="advanced",
        attendance_mode="online",
        status="paused",
        allowed_group_ids={"beginner", "advanced"},
    )

    assert plan.changed is True
    assert plan.group_changed is True
    assert plan.mode_changed is True
    assert plan.status_changed is True
    assert plan.grant_group_ids == frozenset({"advanced"})
    assert plan.revoke_group_ids == frozenset({"archive"})


def test_plan_recognizes_an_unchanged_enrollment() -> None:
    plan = plan_admin_enrollment_change(
        current_active_group_id="beginner",
        current_attendance_mode="in_person",
        current_status="active",
        current_allowed_group_ids={"beginner", "advanced"},
        active_group_id="beginner",
        attendance_mode="in_person",
        status="active",
        allowed_group_ids={"advanced", "beginner"},
    )

    assert plan.changed is False
    assert not plan.grant_group_ids
    assert not plan.revoke_group_ids
