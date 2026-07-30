"""Small privacy filter shared by the backend Sentry integrations."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


REDACTED = "[redacted]"
_SENSITIVE_KEY = re.compile(
    r"answer|attachment|authorization|body|comment|cookie|credential|password|"
    r"photo|refresh|solution|telegram|text|token",
    re.IGNORECASE,
)


def _safe_string(value: str) -> str:
    if "/sol_imgs/" in value.casefold():
        return "[redacted-media-url]"
    if not value.casefold().startswith(("http://", "https://")):
        return value
    parsed = urlsplit(value)
    if parsed.username is not None or parsed.password is not None:
        return "[redacted-url]"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _safe_value(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, str):
        return _safe_string(value)
    if isinstance(value, dict):
        return {
            nested_key: _safe_value(nested_value, str(nested_key))
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_safe_value(item) for item in value)
    return value


def sanitize_sentry_breadcrumb(
    breadcrumb: dict[str, Any], _hint: object | None = None
) -> dict[str, Any]:
    sanitized = dict(breadcrumb)
    category = sanitized.get("category")
    message = sanitized.get("message")
    if isinstance(message, str):
        sanitized["message"] = (
            REDACTED
            if isinstance(category, str)
            and (
                category == "console" or category == "log" or category.startswith("ui.")
            )
            else _safe_string(message)
        )
    if isinstance(sanitized.get("data"), dict):
        sanitized["data"] = _safe_value(sanitized["data"])
    return sanitized


def sanitize_sentry_event(
    event: dict[str, Any], _hint: object | None = None
) -> dict[str, Any]:
    sanitized = dict(event)
    sanitized.pop("user", None)
    if isinstance(event.get("request"), dict):
        request = dict(event["request"])
        for field in ("cookies", "data", "env", "headers"):
            request.pop(field, None)
        if isinstance(request.get("url"), str):
            request["url"] = _safe_string(request["url"])
        sanitized["request"] = request
    for field in ("contexts", "extra"):
        if isinstance(event.get(field), dict):
            sanitized[field] = _safe_value(event[field])
    if isinstance(event.get("breadcrumbs"), list):
        sanitized["breadcrumbs"] = [
            sanitize_sentry_breadcrumb(item)
            for item in event["breadcrumbs"]
            if isinstance(item, dict)
        ]
    return sanitized


__all__ = ["sanitize_sentry_breadcrumb", "sanitize_sentry_event"]
