"""Small, explicit Python half of the versioned PWA wire contracts.

TypeScript performs the untrusted-client validation with Zod. These builders
keep the aiohttp responses on the same reviewed shape and are checked against
the exact JSON fixtures exported by ``@vmsh/contracts``. See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal, TypeAlias

Audience: TypeAlias = Literal["student", "family", "staff"]
RUNTIME_CONTRACT_VERSION = 1

AUDIENCE_BOUNDARIES: dict[Audience, dict[str, str]] = {
    "student": {
        "appBase": "/student",
        "apiBase": "/student/api/v1",
        "websocketPath": "/student/ws",
    },
    "family": {
        "appBase": "/family",
        "apiBase": "/family/api/v1",
        "websocketPath": "/family/ws",
    },
    "staff": {
        "appBase": "/staff",
        "apiBase": "/staff/api/v1",
        "websocketPath": "/staff/ws",
    },
}

_RUNTIME_INSTANCE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


def validate_runtime_instance(value: str) -> str:
    """Reject namespaces which cannot be used verbatim by browser storage."""

    if not isinstance(value, str) or not _RUNTIME_INSTANCE_PATTERN.fullmatch(value):
        raise ValueError(
            "PWA runtime instance must be a 1-64 character canonical "
            "lowercase ASCII namespace token"
        )
    return value


def build_runtime_payload(
    *,
    audience: Audience,
    instance: str,
    server_time: str,
    request_id: str,
    telegram: bool,
    google: bool,
    nats: bool,
    prototype: bool,
) -> dict[str, object]:
    """Build the runtime response shared by all three audience endpoints."""

    try:
        boundary = AUDIENCE_BOUNDARIES[audience]
    except KeyError as error:
        raise ValueError(f"Unknown PWA audience: {audience!r}") from error

    return {
        "contractVersion": RUNTIME_CONTRACT_VERSION,
        "audience": audience,
        **boundary,
        "instance": validate_runtime_instance(instance),
        "serverTime": server_time,
        "requestId": request_id,
        "features": {
            "telegram": bool(telegram),
            "google": bool(google),
            "nats": bool(nats),
            "prototype": bool(prototype),
        },
    }


def build_api_error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the single JSON error envelope used by PWA HTTP endpoints."""

    error: dict[str, object] = {
        "code": code,
        "message": message,
        "requestId": request_id,
    }
    if details is not None:
        error["details"] = dict(details)
    return {"error": error}


def build_realtime_error_payload(
    *,
    cursor: int,
    server_time: str,
    code: str,
    message: str,
    request_id: str,
) -> dict[str, object]:
    """Build a recoverable error event after a WebSocket was upgraded."""

    if cursor < 0:
        raise ValueError("Realtime cursor must be non-negative")
    return {
        "type": "error",
        "cursor": cursor,
        "serverTime": server_time,
        "code": code,
        "message": message,
        "requestId": request_id,
    }


__all__ = [
    "AUDIENCE_BOUNDARIES",
    "Audience",
    "RUNTIME_CONTRACT_VERSION",
    "build_api_error_payload",
    "build_realtime_error_payload",
    "build_runtime_payload",
    "validate_runtime_instance",
]
