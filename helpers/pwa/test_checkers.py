"""Compatibility executor for trusted-admin test answer checkers.

The historical Telegram handler accepts a small Python ``def`` from the task
metadata and executes it with an allowlisted globals dictionary.  This remains
a trusted-administrator compatibility boundary, not a security sandbox.  The
PWA submission domain uses the structured result below so malformed checker
configuration fails closed without exposing source code or a traceback to a
student.

See ``vmshpwa/dev/development-plan/08-phase-4-test-submissions.md`` and the
characterization tests in ``pwa_tests/domain/test_pwa_test_submissions.py``.
"""

from __future__ import annotations

import re
from ast import literal_eval
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


TRUSTED_CHECKER_PATTERN = re.compile(r"^\s*def \w+\s*\(")

# Keep this list byte-for-byte equivalent in meaning to the historical
# ``GLOBALS_FOR_TEST_FUNCTION_CREATION`` dictionary.  Expanding it is a
# security-sensitive product decision even though the caller is trusted.
TRUSTED_CHECKER_GLOBALS: dict[str, object] = {
    "__builtins__": None,
    "re": re,
    "bool": bool,
    "float": float,
    "int": int,
    "list": list,
    "range": range,
    "set": set,
    "str": str,
    "tuple": tuple,
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "enumerate": enumerate,
    "format": format,
    "len": len,
    "max": max,
    "min": min,
    "round": round,
    "sorted": sorted,
    "sum": sum,
    "map": map,
    "literal_eval": literal_eval,
}


class TrustedCheckerStatus(StrEnum):
    CHECKED = "checked"
    INVALID_CONFIGURATION = "invalid_configuration"


@dataclass(frozen=True, slots=True)
class TrustedCheckerExecution:
    status: TrustedCheckerStatus
    correct: bool | None = None
    message: str | None = None
    diagnostic_code: str | None = None


def _invalid_configuration(code: str) -> TrustedCheckerExecution:
    return TrustedCheckerExecution(
        status=TrustedCheckerStatus.INVALID_CONFIGURATION,
        diagnostic_code=code,
    )


class TrustedCheckerExecutor:
    """Compile and cache exact trusted checker strings like the legacy path."""

    def __init__(self) -> None:
        self._cache: dict[str, Callable[[str], object]] = {}

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def execute(
        self, checker_source: str, student_answer: str
    ) -> TrustedCheckerExecution:
        source = checker_source.strip()
        if not TRUSTED_CHECKER_PATTERN.match(source):
            return _invalid_configuration("not_a_function")

        checker = self._cache.get(source)
        if checker is None:
            locals_: dict[str, object] = {}
            try:
                exec(source, TRUSTED_CHECKER_GLOBALS, locals_)
            except BaseException:
                return _invalid_configuration("compile_or_exec_failed")
            if not locals_:
                return _invalid_configuration("no_created_value")
            # ``dict.popitem`` matches the historical handler: the last value
            # created by the snippet is selected.  Tests pin this odd but real
            # compatibility behavior before any future cleanup.
            _, candidate = locals_.popitem()
            if not callable(candidate):
                return _invalid_configuration("created_value_not_callable")
            checker = candidate
            self._cache[source] = checker

        try:
            result = checker(student_answer)
        except BaseException:
            return _invalid_configuration("call_failed")
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], bool)
            or (result[1] is not None and not isinstance(result[1], str))
        ):
            return _invalid_configuration("invalid_result_shape")
        return TrustedCheckerExecution(
            status=TrustedCheckerStatus.CHECKED,
            correct=result[0],
            message=result[1],
        )


__all__ = [
    "TRUSTED_CHECKER_GLOBALS",
    "TRUSTED_CHECKER_PATTERN",
    "TrustedCheckerExecution",
    "TrustedCheckerExecutor",
    "TrustedCheckerStatus",
]
