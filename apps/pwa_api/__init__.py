"""Versioned aiohttp boundary for the three PWA audiences.

The package is an adapter over the existing SQLite/domain code. It must remain
importable without Telegram or Google configuration; see Phase 1 in
``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from .errors import PwaApiError

__all__ = ["PwaApiError"]
