"""Typed course-owned replacement for the relevant legacy bot settings."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping


COURSE_RUNTIME_SETTING_VALUES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "verdictMode": frozenset(
            {
                "verdict_plus_minus",
                "verdict_plus_minus_half",
                "verdict_plus_steps",
            }
        ),
        "resultMode": frozenset({"res_immed", "res_after"}),
        "previousLessonsMode": frozenset(
            {
                "prev_problems_hide",
                "prev_problems_prev",
                "prev_problems_show_all",
            }
        ),
        "testAttemptRateLimit": frozenset({"rate_limit_none", "rate_limit_3_and_6"}),
    }
)

# Defaults match the characterized current circle configuration, so the first
# explicit Staff save is a no-op for the existing mathematics course. They are
# code-owned defaults, not a runtime read from Google or z_settings.
DEFAULT_COURSE_RUNTIME_SETTINGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "verdictMode": "verdict_plus_minus_half",
        "resultMode": "res_immed",
        "previousLessonsMode": "prev_problems_show_all",
        "testAttemptRateLimit": "rate_limit_3_and_6",
    }
)


class InvalidCourseRuntimeSettings(ValueError):
    """The submitted settings object is not the complete typed v1 shape."""


def normalize_course_runtime_settings(value: object) -> dict[str, str]:
    """Validate the exact v1 object without coercing unknown legacy values."""

    if not isinstance(value, dict) or set(value) != set(COURSE_RUNTIME_SETTING_VALUES):
        raise InvalidCourseRuntimeSettings("invalid_course_runtime_settings")
    normalized: dict[str, str] = {}
    for key, allowed in COURSE_RUNTIME_SETTING_VALUES.items():
        candidate = value[key]
        if not isinstance(candidate, str) or candidate not in allowed:
            raise InvalidCourseRuntimeSettings("invalid_course_runtime_settings")
        normalized[key] = candidate
    return normalized


__all__ = [
    "COURSE_RUNTIME_SETTING_VALUES",
    "DEFAULT_COURSE_RUNTIME_SETTINGS",
    "InvalidCourseRuntimeSettings",
    "normalize_course_runtime_settings",
]
