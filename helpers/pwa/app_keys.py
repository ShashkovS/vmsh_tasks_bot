"""Canonical aiohttp keys shared by every PWA startup form.

These keys must live outside :mod:`main`: when ``main.py`` is executed as a
script its module name is ``__main__``. Importing ``main`` from an adapter would
then create distinct ``AppKey`` objects and make values already stored on the
application unreachable. See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp import web

from helpers.config import Config

if TYPE_CHECKING:
    from db_methods.pwa import DatabaseLifecycleLock, PwaConnectionFactory


@dataclass(slots=True)
class PwaDatabaseState:
    """Verified PWA database runtime shared without importing ``main``.

    ``main.py`` can be executed as ``__main__``. Keeping both this value type
    and its ``AppKey`` here prevents an adapter import from creating a second,
    identity-distinct key. See ADR 0002 and Phase 1's app-factory boundary.
    """

    factory: "PwaConnectionFactory | None" = None
    lifecycle_lock: "DatabaseLifecycleLock | None" = None

RUNTIME_CONFIG = web.AppKey("runtime_config", Config)
ENABLED_ADAPTERS = web.AppKey("enabled_adapters", tuple)
PWA_DATABASE = web.AppKey("pwa_database", PwaDatabaseState)

__all__ = [
    "ENABLED_ADAPTERS",
    "PWA_DATABASE",
    "RUNTIME_CONFIG",
    "PwaDatabaseState",
]
