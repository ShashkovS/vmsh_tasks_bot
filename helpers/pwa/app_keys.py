"""Canonical aiohttp keys shared by every PWA startup form.

These keys must live outside :mod:`main`: when ``main.py`` is executed as a
script its module name is ``__main__``. Importing ``main`` from an adapter would
then create distinct ``AppKey`` objects and make values already stored on the
application unreachable. See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from aiohttp import web

from helpers.config import Config

RUNTIME_CONFIG = web.AppKey("runtime_config", Config)
ENABLED_ADAPTERS = web.AppKey("enabled_adapters", tuple)

__all__ = ["ENABLED_ADAPTERS", "RUNTIME_CONFIG"]
