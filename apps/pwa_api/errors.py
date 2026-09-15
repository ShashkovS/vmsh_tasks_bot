"""Stable PWA HTTP errors independent from aiohttp reason phrases."""

from __future__ import annotations

from collections.abc import Mapping


class PwaApiError(Exception):
    """An expected API failure rendered by the outer PWA middleware."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if not 400 <= status <= 599:
            raise ValueError("PWA API error status must be between 400 and 599")
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}
        super().__init__(message)


__all__ = ["PwaApiError"]
