"""Pure tests for replacing teacher course/group scopes."""

from __future__ import annotations

import pytest

from models.pwa.staff_access import InvalidTeacherScopes, teacher_scope_changes


def test_teacher_scope_changes_returns_only_additions_and_removals() -> None:
    additions, removals = teacher_scope_changes(
        [("math", "beginner"), ("physics", None)],
        [("math", "advanced"), ("physics", None)],
    )

    assert additions == frozenset({("math", "advanced")})
    assert removals == frozenset({("math", "beginner")})


def test_teacher_scope_changes_rejects_duplicate_scope() -> None:
    with pytest.raises(InvalidTeacherScopes, match="duplicate_scope"):
        teacher_scope_changes([], [("math", "beginner"), ("math", "beginner")])


def test_teacher_scope_changes_rejects_redundant_course_and_group_scope() -> None:
    with pytest.raises(InvalidTeacherScopes, match="redundant_group_scope"):
        teacher_scope_changes([], [("math", None), ("math", "beginner")])
