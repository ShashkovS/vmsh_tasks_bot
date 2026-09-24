"""Server-side translation of PWA product text.

Russian is the source language: a Russian literal is both the default text
and the catalog key (msgid), exactly like the Lingui catalogs of the
frontend. English lives in ``helpers/pwa/locales/en.po``; a missing
translation falls back to Russian. The interface language of a request comes
from the device cookie written by ``@vmsh/i18n``; texts built for another
recipient (Web Push) pass the recipient's account language explicitly.

See ``adr/0004-pwa-internationalization.md`` and ``vmshpwa/docs/i18n.md``.
Extraction and coverage checks: ``vmshpwa/scripts/backend_i18n.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from functools import cache
from pathlib import Path

from babel.messages.pofile import read_po

SUPPORTED_LOCALES = ("ru", "en")
DEFAULT_LOCALE = "ru"
LOCALE_COOKIE_NAME = "vmsh-locale"
CATALOG_DIRECTORY = Path(__file__).with_name("locales")

current_locale: ContextVar[str] = ContextVar("pwa_locale", default=DEFAULT_LOCALE)


def normalize_locale(value: object) -> str | None:
    """Return a supported locale code or ``None`` for anything else."""

    return value if isinstance(value, str) and value in SUPPORTED_LOCALES else None


def locale_from_cookies(cookies: Mapping[str, str]) -> str:
    """Interface language of the device that sent a request."""

    return normalize_locale(cookies.get(LOCALE_COOKIE_NAME)) or DEFAULT_LOCALE


@cache
def _catalog(locale: str) -> Mapping[str, str]:
    path = CATALOG_DIRECTORY / f"{locale}.po"
    if locale == DEFAULT_LOCALE or not path.exists():
        return {}
    with path.open("rb") as file:
        catalog = read_po(file, locale=locale)
    return {
        message.id: message.string
        for message in catalog
        if message.id and isinstance(message.id, str) and message.string
    }


def N_(message: str) -> str:  # noqa: N802 - gettext marker convention
    """Mark a Russian literal for extraction without translating it here.

    Use it for module-level constants and for messages created in lower
    layers; the HTTP boundary translates them with the request language.
    """

    return message


def translate(
    locale: str, message: str, params: Mapping[str, object] | None = None
) -> str:
    """Translate a marked Russian message and substitute ``{name}`` params."""

    translated = _catalog(normalize_locale(locale) or DEFAULT_LOCALE).get(
        message, message
    )
    return translated.format_map(dict(params)) if params else translated


def _(message: str, **params: object) -> str:
    """Translate a Russian literal into the language of the current request."""

    return translate(current_locale.get(), message, params)


__all__ = [
    "DEFAULT_LOCALE",
    "LOCALE_COOKIE_NAME",
    "N_",
    "SUPPORTED_LOCALES",
    "_",
    "current_locale",
    "locale_from_cookies",
    "normalize_locale",
    "translate",
]
