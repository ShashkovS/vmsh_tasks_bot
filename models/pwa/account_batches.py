"""Pure validation for the three v1 account provisioning batches.

Storage is intentionally absent here. See Phase 10 in
``vmshpwa/dev/development-plan/14-phase-10-admin-and-google-exit.md``.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from models.pwa.auth import normalize_login, normalize_telegram_token


_EMAIL = re.compile(r"^[^\s,@]+@[^\s,@]+\.[^\s,@]+$")


class InvalidAccountBatchRow(ValueError):
    """One row cannot be provisioned; the exception text is a stable code."""


def _text(value: Any, *, code: str, maximum: int, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str):
        raise InvalidAccountBatchRow(code)
    stored = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not stored and optional:
        return ""
    if not 1 <= len(stored) <= maximum:
        raise InvalidAccountBatchRow(code)
    return stored


def _login(value: Any) -> tuple[str, str]:
    stored = _text(value, code="invalid_login", maximum=100)
    normalized = normalize_login(stored)
    if not normalized or len(normalized) > 100:
        raise InvalidAccountBatchRow("invalid_login")
    return stored, normalized


def _birth_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise InvalidAccountBatchRow("invalid_birth_date")
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as error:
        raise InvalidAccountBatchRow("invalid_birth_date") from error
    if parsed < date(1900, 1, 1) or parsed > date.today():
        raise InvalidAccountBatchRow("invalid_birth_date")
    return parsed.isoformat()


def _grade(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 11:
        raise InvalidAccountBatchRow("invalid_grade")
    return value


def normalize_student_batch_row(row: object) -> dict[str, object]:
    required = {"surname", "name", "login", "password"}
    allowed = required | {"patronymic", "birthDate", "grade"}
    if (
        not isinstance(row, dict)
        or not required.issubset(row)
        or not set(row).issubset(allowed)
    ):
        raise InvalidAccountBatchRow("invalid_student_row")
    login, normalized_login = _login(row["login"])
    raw_password = row["password"]
    if not isinstance(raw_password, str):
        raise InvalidAccountBatchRow("invalid_password")
    password = normalize_telegram_token(raw_password)
    if not 1 <= len(password) <= 256:
        raise InvalidAccountBatchRow("invalid_password")
    return {
        "surname": _text(row["surname"], code="invalid_surname", maximum=100),
        "name": _text(row["name"], code="invalid_name", maximum=100),
        "patronymic": _text(
            row.get("patronymic"),
            code="invalid_patronymic",
            maximum=100,
            optional=True,
        ),
        "birth_date": _birth_date(row.get("birthDate")),
        "grade": _grade(row.get("grade")),
        "login": login,
        "login_normalized": normalized_login,
        "password": password,
    }


def _email_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [part for part in value.split(",") if part.strip()]
    if not isinstance(value, list) or not value:
        raise InvalidAccountBatchRow("invalid_emails")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        email = _text(item, code="invalid_emails", maximum=320)
        normalized = email.casefold()
        if _EMAIL.fullmatch(email) is None or normalized in seen:
            raise InvalidAccountBatchRow("invalid_emails")
        seen.add(normalized)
        result.append(email)
    return tuple(result)


def _child_logins(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise InvalidAccountBatchRow("invalid_child_logins")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        _, normalized = _login(item)
        if normalized in seen:
            raise InvalidAccountBatchRow("invalid_child_logins")
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def normalize_family_batch_row(row: object) -> dict[str, object]:
    if not isinstance(row, dict) or set(row) != {
        "name",
        "login",
        "password",
        "emails",
        "childLogins",
    }:
        raise InvalidAccountBatchRow("invalid_family_row")
    login, normalized_login = _login(row["login"])
    password = row["password"]
    if not isinstance(password, str) or not 1 <= len(password) <= 256:
        raise InvalidAccountBatchRow("invalid_password")
    return {
        "name": _text(row["name"], code="invalid_name", maximum=200),
        "login": login,
        "login_normalized": normalized_login,
        "password": password,
        "emails": _email_list(row["emails"]),
        "child_logins": _child_logins(row["childLogins"]),
    }


def _catalog_code(value: Any, *, code: str) -> str:
    stored = _text(value, code=code, maximum=50)
    normalized = unicodedata.normalize("NFKC", stored).casefold()
    if (
        normalized.startswith("-")
        or normalized.endswith("-")
        or "--" in normalized
        or not all(character.isalnum() or character == "-" for character in normalized)
    ):
        raise InvalidAccountBatchRow(code)
    return normalized


def normalize_course_enrollment_batch_row(row: object) -> dict[str, object]:
    """Normalize the owner-confirmed ``login, course, allowed groups`` row."""

    if not isinstance(row, dict) or set(row) != {
        "login",
        "courseCode",
        "allowedGroupCodes",
    }:
        raise InvalidAccountBatchRow("invalid_enrollment_row")
    _, login_normalized = _login(row["login"])
    values = row["allowedGroupCodes"]
    if not isinstance(values, list) or not 1 <= len(values) <= 100:
        raise InvalidAccountBatchRow("invalid_allowed_groups")
    allowed: list[str] = []
    seen: set[str] = set()
    for value in values:
        group_code = _catalog_code(value, code="invalid_allowed_groups")
        if group_code in seen:
            raise InvalidAccountBatchRow("invalid_allowed_groups")
        seen.add(group_code)
        allowed.append(group_code)
    return {
        "login_normalized": login_normalized,
        "course_code": _catalog_code(row["courseCode"], code="invalid_course"),
        "allowed_group_codes": tuple(allowed),
    }


def choose_active_group(
    groups: list[dict[str, object]], allowed_group_codes: tuple[str, ...]
) -> dict[str, object]:
    """Choose the first allowed group by product order, with stable tie-breaks.

    Group order is product data, not TSV order. See
    ``accepted-technical-decisions-2026-07.md`` and Phase 10.
    """

    allowed = set(allowed_group_codes)
    candidates = [
        group for group in groups if str(group["short_code"]).casefold() in allowed
    ]
    if len(candidates) != len(allowed):
        raise InvalidAccountBatchRow("group_not_found")
    return min(
        candidates,
        key=lambda group: (
            int(group["sort_order"]),
            str(group["short_code"]).casefold(),
            str(group["group_id"]),
        ),
    )


def choose_available_login(
    login: str,
    normalized_login: str,
    used: set[str],
    suffix_candidates: list[int],
) -> tuple[str, str, bool]:
    """Return the original login or a reviewed random two-digit alternative."""

    if normalized_login not in used:
        used.add(normalized_login)
        return login, normalized_login, False
    prefix = login[:97]
    for number in suffix_candidates:
        candidate = f"{prefix}-{number:02d}"
        normalized_candidate = normalize_login(candidate)
        if normalized_candidate not in used:
            used.add(normalized_candidate)
            return candidate, normalized_candidate, True
    raise InvalidAccountBatchRow("login_suffix_exhausted")


__all__ = [
    "InvalidAccountBatchRow",
    "choose_active_group",
    "choose_available_login",
    "normalize_course_enrollment_batch_row",
    "normalize_family_batch_row",
    "normalize_student_batch_row",
]
