"""Pure validation for replacing one teacher's course/group scopes."""

from __future__ import annotations

from collections.abc import Iterable


ScopeKey = tuple[str, str | None]


class InvalidTeacherScopes(ValueError):
    pass


def teacher_scope_changes(
    current: Iterable[ScopeKey], desired: Iterable[ScopeKey]
) -> tuple[frozenset[ScopeKey], frozenset[ScopeKey]]:
    current_set = frozenset(current)
    desired_list = list(desired)
    desired_set = frozenset(desired_list)
    if len(desired_list) != len(desired_set):
        raise InvalidTeacherScopes("duplicate_scope")
    course_wide = {course_id for course_id, group_id in desired_set if group_id is None}
    if any(
        course_id in course_wide and group_id is not None
        for course_id, group_id in desired_set
    ):
        raise InvalidTeacherScopes("redundant_group_scope")
    return desired_set - current_set, current_set - desired_set


__all__ = ["InvalidTeacherScopes", "ScopeKey", "teacher_scope_changes"]
