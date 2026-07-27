"""Pure authentication rules shared by aiohttp and migration tooling.

Storage and HTTP concerns intentionally stay outside this module.  That keeps
the security-sensitive normalization, expiry and token rules executable in
small unit tests and reusable by the future Staff account importer.

Decisions: ``vmshpwa/docs/authentication-and-security.md`` and Phase 1 in
``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadData, URLSafeTimedSerializer


STUDENT_USERNAME_ALGORITHM_VERSION = 1
ACCESS_TOKEN_VERSION = 1
DEFAULT_ACCESS_MAX_AGE_SECONDS = 15 * 60
MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")

# Historical Telegram tokens were sometimes typed with visually similar
# Cyrillic characters.  PWA login must accept exactly the same correction as
# the bot or users would have two subtly different passwords.  Keep the map
# versioned by tests before changing it.
_TOKEN_HOMOGLYPHS = str.maketrans(
    "УКЕНХВАРОСМТукехарос",
    "YKEHXBAPOCMTykexapoc",
)

# A deliberately local and frozen Russian-to-ASCII mapping avoids locale- and
# library-version-dependent login changes.  Collisions are surfaced to the
# importer; they are never silently solved with a mutable database row id.
_RUSSIAN_TRANSLITERATION = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}
_LOGIN_SEPARATOR = re.compile(r"[^a-z0-9]+")


class AuthAudience(StrEnum):
    STUDENT = "student"
    FAMILY = "family"
    STAFF = "staff"


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    """Server-authoritative identity for one authenticated request."""

    account_public_id: str
    session_public_id: str
    audience: AuthAudience
    linked_user_id: int | None
    role: str
    capabilities: frozenset[str]
    credential_version: int
    session_version: int


@dataclass(frozen=True, slots=True)
class CredentialVerification:
    valid: bool
    replacement_hash: str | None = None


@dataclass(frozen=True, slots=True)
class SessionTokenPair:
    public_id: str
    raw_refresh_secret: str

    @property
    def cookie_value(self) -> str:
        return f"{self.public_id}.{self.raw_refresh_secret}"


def normalize_login(value: str) -> str:
    """Normalize a login without applying locale-sensitive transformations."""

    return " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


def normalize_telegram_token(value: str) -> str:
    """Preserve the historical bot token-normalization contract."""

    return value.strip().translate(_TOKEN_HOMOGLYPHS).lower()


def _transliterate_surname(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    transliterated = "".join(_RUSSIAN_TRANSLITERATION.get(char, char) for char in normalized)
    # Strip remaining accents after Cyrillic transliteration, then keep only a
    # small stable alphabet suitable for login forms and support dictation.
    ascii_text = unicodedata.normalize("NFKD", transliterated).encode(
        "ascii", "ignore"
    ).decode("ascii")
    return _LOGIN_SEPARATOR.sub("-", ascii_text).strip("-")


def build_student_username(surname: str, birthday: date) -> str:
    """Build the frozen v1 login ``transliterated-surname-DD``.

    The day is zero-padded because a login is an identifier, not a number.
    Duplicate outputs are an import error requiring an explicit stored override;
    adding a row-id suffix here would make identities depend on import order.
    """

    stem = _transliterate_surname(surname)
    if not stem:
        raise ValueError("Student surname does not produce a login stem")
    return f"{stem}-{birthday.day:02d}"


def next_session_expiry(
    now: datetime,
    *,
    timezone: ZoneInfo = MOSCOW_TIMEZONE,
) -> datetime:
    """Return the next 10 August 00:00 in the season business timezone."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Session expiry requires a timezone-aware datetime")
    local_now = now.astimezone(timezone)
    year = local_now.year
    boundary = datetime(year, 8, 10, tzinfo=timezone)
    if local_now >= boundary:
        boundary = datetime(year + 1, 8, 10, tzinfo=timezone)
    return boundary.astimezone(UTC)


class CredentialHasher:
    """Argon2id credential hashing with transparent parameter upgrades.

    Production uses argon2-cffi's current RFC 9106-based defaults. Tests inject
    a deliberately cheaper ``PasswordHasher``; weakening the production object
    through an environment flag is intentionally unsupported.
    """

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher()

    def hash(self, credential: str) -> str:
        if not credential:
            raise ValueError("Credential must not be empty")
        return self._hasher.hash(credential)

    def verify(self, encoded_hash: str | None, credential: str) -> CredentialVerification:
        if not encoded_hash or not credential:
            return CredentialVerification(valid=False)
        try:
            valid = self._hasher.verify(encoded_hash, credential)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return CredentialVerification(valid=False)
        replacement = (
            self._hasher.hash(credential)
            if valid and self._hasher.check_needs_rehash(encoded_hash)
            else None
        )
        return CredentialVerification(valid=bool(valid), replacement_hash=replacement)


def create_session_token_pair() -> SessionTokenPair:
    return SessionTokenPair(
        # Public IDs follow the lowercase canonical contract consumed by Zod;
        # the refresh secret remains independent high-entropy URL-safe data.
        public_id=secrets.token_hex(16),
        raw_refresh_secret=secrets.token_urlsafe(32),
    )


def parse_refresh_cookie(value: str | None) -> SessionTokenPair | None:
    if not value or value.count(".") != 1:
        return None
    public_id, raw_refresh_secret = value.split(".", 1)
    if not public_id or not raw_refresh_secret:
        return None
    return SessionTokenPair(public_id, raw_refresh_secret)


def hash_refresh_secret(secret: str, pepper: bytes) -> str:
    if len(pepper) < 32:
        raise ValueError("Refresh-token pepper must contain at least 32 bytes")
    return hmac.new(pepper, secret.encode("utf-8"), hashlib.sha256).hexdigest()


class AccessTokenCodec:
    """Short-lived signed cookie codec with audience-separated salts."""

    def __init__(
        self,
        signing_keys: Sequence[str],
        *,
        max_age_seconds: int = DEFAULT_ACCESS_MAX_AGE_SECONDS,
    ) -> None:
        keys = tuple(key for key in signing_keys if key)
        if not keys or any(len(key.encode("utf-8")) < 32 for key in keys):
            raise ValueError("Every access signing key must contain at least 32 bytes")
        if max_age_seconds <= 0:
            raise ValueError("Access token max age must be positive")
        self._keys = keys
        self.max_age_seconds = max_age_seconds

    def _serializer(self, audience: AuthAudience) -> URLSafeTimedSerializer:
        # itsdangerous accepts oldest-to-newest keys and signs with the newest.
        # A distinct salt prevents a valid Student cookie becoming a Family one.
        return URLSafeTimedSerializer(
            list(self._keys),
            salt=f"vmsh-pwa-access-v{ACCESS_TOKEN_VERSION}:{audience.value}",
        )

    def dumps(self, principal: AuthPrincipal) -> str:
        payload = {
            "v": ACCESS_TOKEN_VERSION,
            "sid": principal.session_public_id,
            "aid": principal.account_public_id,
            "aud": principal.audience.value,
            "cv": principal.credential_version,
            "sv": principal.session_version,
        }
        return self._serializer(principal.audience).dumps(payload)

    def loads(
        self, token: str, expected_audience: AuthAudience
    ) -> Mapping[str, str | int] | None:
        try:
            payload: Any = self._serializer(expected_audience).loads(
                token,
                max_age=self.max_age_seconds,
            )
        except BadData:
            return None
        if not isinstance(payload, dict) or set(payload) != {
            "v",
            "sid",
            "aid",
            "aud",
            "cv",
            "sv",
        }:
            return None
        if payload["v"] != ACCESS_TOKEN_VERSION or payload["aud"] != expected_audience.value:
            return None
        if not isinstance(payload["sid"], str) or not payload["sid"]:
            return None
        if not isinstance(payload["aid"], str) or not payload["aid"]:
            return None
        if not isinstance(payload["cv"], int) or payload["cv"] <= 0:
            return None
        if not isinstance(payload["sv"], int) or payload["sv"] <= 0:
            return None
        return payload
