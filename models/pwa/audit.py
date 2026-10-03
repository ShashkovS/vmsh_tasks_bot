"""Safe projection rules for the compact Staff audit timeline."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping


_SAFE_DIFF_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,63}$")
_SECRET_KEY_PARTS = ("credential", "hash", "password", "secret", "token")


class InvalidAuditEvent(ValueError):
    pass


def _diff(value: object) -> dict[str, str | int | float | bool | None] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, RecursionError) as error:
        raise InvalidAuditEvent("invalid audit JSON") from error
    if not isinstance(parsed, dict):
        raise InvalidAuditEvent("audit diff must be an object")
    result: dict[str, str | int | float | bool | None] = {}
    for key, item in parsed.items():
        normalized_key = str(key)
        if (
            _SAFE_DIFF_KEY.fullmatch(normalized_key) is None
            or any(part in normalized_key.casefold() for part in _SECRET_KEY_PARTS)
            or not isinstance(item, (str, int, float, bool, type(None)))
        ):
            raise InvalidAuditEvent("unsafe audit diff")
        result[normalized_key] = item
    return result


def audit_event_payload(row: Mapping[str, object]) -> dict[str, object]:
    display_name = " ".join(
        part
        for part in (
            str(row.get("actor_surname") or "").strip(),
            str(row.get("actor_name") or "").strip(),
        )
        if part
    )
    return {
        "eventId": row["public_id"],
        "occurredAt": row["occurred_at"],
        "audience": row["audience"],
        "action": row["action"],
        "objectType": row["object_type"],
        "objectId": row["object_id"],
        "requestId": row["request_id"],
        "actor": {
            "userId": row.get("actor_user_public_id"),
            "accountId": row.get("actor_account_public_id"),
            "displayName": display_name or "Система",
        },
        "before": _diff(row.get("before_json")),
        "after": _diff(row.get("after_json")),
    }


__all__ = ["InvalidAuditEvent", "audit_event_payload"]
