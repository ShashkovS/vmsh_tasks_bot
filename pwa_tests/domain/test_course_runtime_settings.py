"""Pure validation for typed course runtime settings."""

from __future__ import annotations

import pytest

from models.pwa.course_runtime_settings import (
    DEFAULT_COURSE_RUNTIME_SETTINGS,
    InvalidCourseRuntimeSettings,
    normalize_course_runtime_settings,
)


def test_current_mathematics_defaults_are_a_complete_valid_v1_object() -> None:
    assert normalize_course_runtime_settings(dict(DEFAULT_COURSE_RUNTIME_SETTINGS)) == {
        "verdictMode": "verdict_plus_minus_half",
        "resultMode": "res_immed",
        "previousLessonsMode": "prev_problems_show_all",
        "testAttemptRateLimit": "rate_limit_3_and_6",
    }


@pytest.mark.parametrize(
    "values",
    [
        {},
        {**DEFAULT_COURSE_RUNTIME_SETTINGS, "saveSolMode": "save_sol_in_tg_only"},
        {**DEFAULT_COURSE_RUNTIME_SETTINGS, "resultMode": "later-maybe"},
        {**DEFAULT_COURSE_RUNTIME_SETTINGS, "verdictMode": True},
    ],
)
def test_unknown_removed_or_wrong_typed_values_fail_closed(values: object) -> None:
    with pytest.raises(
        InvalidCourseRuntimeSettings, match="invalid_course_runtime_settings"
    ):
        normalize_course_runtime_settings(values)
