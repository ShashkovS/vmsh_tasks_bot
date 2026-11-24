"""Pure rules for a Staff change to one course enrollment."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidAdminEnrollmentChange(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AdminEnrollmentPlan:
    active_group_id: str
    allowed_group_ids: frozenset[str]
    grant_group_ids: frozenset[str]
    revoke_group_ids: frozenset[str]
    group_changed: bool
    mode_changed: bool
    status_changed: bool

    @property
    def changed(self) -> bool:
        return bool(
            self.group_changed
            or self.mode_changed
            or self.status_changed
            or self.grant_group_ids
            or self.revoke_group_ids
        )


def plan_admin_enrollment_change(
    *,
    current_active_group_id: str,
    current_attendance_mode: str,
    current_status: str,
    current_allowed_group_ids: set[str],
    active_group_id: str,
    attendance_mode: str,
    status: str,
    allowed_group_ids: set[str],
) -> AdminEnrollmentPlan:
    """Validate the full desired state and calculate the small storage diff."""

    if not allowed_group_ids:
        raise InvalidAdminEnrollmentChange("allowed_groups_empty")
    if active_group_id not in allowed_group_ids:
        raise InvalidAdminEnrollmentChange("active_group_not_allowed")
    return AdminEnrollmentPlan(
        active_group_id=active_group_id,
        allowed_group_ids=frozenset(allowed_group_ids),
        grant_group_ids=frozenset(allowed_group_ids - current_allowed_group_ids),
        revoke_group_ids=frozenset(current_allowed_group_ids - allowed_group_ids),
        group_changed=current_active_group_id != active_group_id,
        mode_changed=current_attendance_mode != attendance_mode,
        status_changed=current_status != status,
    )


__all__ = [
    "AdminEnrollmentPlan",
    "InvalidAdminEnrollmentChange",
    "plan_admin_enrollment_change",
]
