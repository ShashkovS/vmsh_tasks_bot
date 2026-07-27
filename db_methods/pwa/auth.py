"""SQLite persistence for PWA authentication and principal context.

The repository is deliberately async-facing, while every database callback is
fully synchronous and runs as one connection-per-operation unit of work.  In
particular, Argon2 verification happens *before* ``create_session`` opens its
``BEGIN IMMEDIATE`` transaction.  The service boundary must also verify a
precomputed dummy Argon2 hash when ``find_account_for_login`` returns ``None``;
this storage module neither accepts a raw credential nor owns password timing.

Security and transaction decisions are governed by
``adr/0003-pwa-authentication-cryptography-and-sessions.md`` and Phase 1 in
``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type

from helpers.consts import USER_TYPE
from models.pwa.auth import AuthAudience, normalize_login, normalize_telegram_token

from .connection import PwaConnectionFactory


_HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
_SESSION_PUBLIC_ID = re.compile(r"[0-9a-f]{32}")
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_DEVICE_LABEL_MAX_LENGTH = 120
_USER_AGENT_FAMILY_MAX_LENGTH = 120
_IP_PREFIX_MAX_LENGTH = 64


class AuthRepositoryError(RuntimeError):
    """Base class for expected persistence conflicts."""


class AccountUnavailableError(AuthRepositoryError):
    """The verified account is no longer eligible for a new session."""


class AccountStateConflict(AuthRepositoryError):
    """Account credentials changed between verification and session creation."""


class PrincipalDataIntegrityError(AuthRepositoryError):
    """Stored audience/access relationships cannot form a safe principal."""


class SessionRevokeReason(StrEnum):
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    MANUAL = "manual"
    ACCOUNT_UNAVAILABLE = "account_unavailable"
    CREDENTIAL_CHANGED = "credential_changed"
    REFRESH_REPLAY = "refresh_replay"
    EXPIRED = "expired"


class AuthEventType(StrEnum):
    LOGIN_FAILED = "login.failed"
    LOGIN_THROTTLED = "login.throttled"
    SESSION_CREATED = "session.created"
    SESSION_ROTATED = "session.rotated"
    SESSION_REFRESH_REJECTED = "session.refresh_rejected"
    SESSION_REVOKED = "session.revoked"
    SESSIONS_REVOKED_ALL = "sessions.revoked_all"
    CREDENTIAL_REHASHED = "credential.rehashed"
    CREDENTIAL_CHANGED = "credential.changed"


class RefreshRotationOutcome(StrEnum):
    ROTATED = "rotated"
    NOT_FOUND = "not_found"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    ACCOUNT_UNAVAILABLE = "account_unavailable"
    CREDENTIAL_CHANGED = "credential_changed"
    REPLAY_REVOKED = "replay_revoked"
    INVALID_SECRET = "invalid_secret"


class ThrottleBucketKind(StrEnum):
    NORMALIZED_LOGIN = "normalized_login"
    ACCOUNT = "account"
    IP = "ip"


class StaffScopeRole(StrEnum):
    TEACHER = "teacher"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class AuthAccountCredential:
    """Minimum account row needed by the credential-verification service.

    The normalized login is intentionally absent, and the Argon2 hash is
    excluded from ``repr`` so exception/log formatting does not expose it.
    """

    id: int
    public_id: str
    audience: AuthAudience
    credential_kind: str
    credential_hash: str = field(repr=False)
    linked_user_id: int | None = None
    status: str = "active"
    credential_version: int = 1


@dataclass(frozen=True, slots=True)
class AuthSessionRecord:
    id: int
    public_id: str
    account_id: int
    audience: AuthAudience
    credential_version: int
    version: int
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None
    device_label: str | None
    user_agent_family: str | None
    ip_prefix: str | None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None

    def active_at(self, when: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > _as_utc(when)


@dataclass(frozen=True, slots=True)
class CurrentAuthSession:
    session: AuthSessionRecord
    account_public_id: str
    account_status: str
    display_name: str
    linked_user_id: int | None
    linked_user_public_id: str | None
    linked_user_type: int | None


@dataclass(frozen=True, slots=True)
class RefreshRotationResult:
    outcome: RefreshRotationOutcome
    session: AuthSessionRecord | None = None
    account_public_id: str | None = None


@dataclass(frozen=True, slots=True)
class RevokedSessionTarget:
    """Verified internal target returned only after refresh-secret proof."""

    audience: AuthAudience
    account_public_id: str
    session_public_id: str


@dataclass(frozen=True, slots=True)
class CredentialChangeResult:
    changed: bool
    credential_version: int | None = None
    revoked_session_count: int = 0


@dataclass(frozen=True, slots=True)
class FamilyChildRecord:
    student_user_id: int
    student_public_id: str
    name: str
    surname: str
    group_id: str | None
    grade: int | None
    birthday: str | None
    relationship_label: str | None
    is_primary: bool


@dataclass(frozen=True, slots=True)
class CourseGroupAccessRecord:
    group_id: str
    group_public_id: str
    course_public_id: str
    short_code: str
    public_name: str
    status: str
    color_key: str | None
    sort_order: int
    version: int
    valid_from: datetime
    valid_to: datetime | None


@dataclass(frozen=True, slots=True)
class CourseEnrollmentRecord:
    enrollment_id: int
    enrollment_public_id: str
    enrollment_version: int
    student_public_id: str
    course_id: int
    course_public_id: str
    course_code: str
    course_name: str
    course_subject_code: str
    course_status: str
    course_sort_order: int
    course_accent_key: str
    course_version: int
    active_group_id: str
    active_group_public_id: str
    attendance_mode: str
    enrollment_status: str
    allowed_groups: tuple[CourseGroupAccessRecord, ...]


@dataclass(frozen=True, slots=True)
class StaffScopeRecord:
    id: int
    staff_user_id: int
    course_id: int
    course_public_id: str
    course_code: str
    course_name: str
    course_status: str
    group_id: str | None
    group_public_id: str | None
    group_public_name: str | None
    role: StaffScopeRole
    valid_from: datetime
    valid_to: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class ThrottleBucketKey:
    audience: AuthAudience
    kind: ThrottleBucketKind
    digest: str = field(repr=False)
    key_version: int = 1

    def __post_init__(self) -> None:
        _require_sha256(self.digest, label="throttle bucket digest")
        if self.key_version <= 0:
            raise ValueError("Throttle key version must be positive")


@dataclass(frozen=True, slots=True)
class ThrottlePolicy:
    window: timedelta = timedelta(minutes=15)
    failures_before_lock: int = 5
    initial_lock: timedelta = timedelta(seconds=30)
    maximum_lock: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if self.window.total_seconds() <= 0:
            raise ValueError("Throttle window must be positive")
        if self.failures_before_lock <= 0:
            raise ValueError("Throttle failure threshold must be positive")
        if self.initial_lock.total_seconds() <= 0:
            raise ValueError("Initial throttle lock must be positive")
        if self.maximum_lock < self.initial_lock:
            raise ValueError("Maximum throttle lock must not be shorter than initial")

    def lock_duration(self, failure_count: int) -> timedelta | None:
        if failure_count < self.failures_before_lock:
            return None
        exponent = failure_count - self.failures_before_lock
        seconds = min(
            self.initial_lock.total_seconds() * (2**exponent),
            self.maximum_lock.total_seconds(),
        )
        return timedelta(seconds=seconds)


@dataclass(frozen=True, slots=True)
class ThrottleState:
    key: ThrottleBucketKey
    failure_count: int
    locked_until: datetime | None
    retry_after_seconds: int

    @property
    def locked(self) -> bool:
        return self.retry_after_seconds > 0


def make_throttle_bucket_key(
    *,
    audience: AuthAudience,
    kind: ThrottleBucketKind,
    value: str,
    pepper: bytes,
    key_version: int = 1,
) -> ThrottleBucketKey:
    """Turn a service input into a domain-separated opaque SQLite bucket key."""

    if len(pepper) < 32:
        raise ValueError("Throttle pepper must contain at least 32 bytes")
    if key_version <= 0:
        raise ValueError("Throttle key version must be positive")
    if kind is ThrottleBucketKind.NORMALIZED_LOGIN:
        canonical_value = normalize_login(value)
    elif kind is ThrottleBucketKind.IP:
        try:
            canonical_value = ipaddress.ip_network(
                value.strip(), strict=False
            ).with_prefixlen
        except ValueError as error:
            raise ValueError("Throttle IP key must be an address or prefix") from error
    else:
        canonical_value = value.strip()
    if not canonical_value:
        raise ValueError("Throttle key input must not be empty")
    message = "\0".join(
        (
            f"vmsh-pwa-throttle-v{key_version}",
            audience.value,
            kind.value,
            canonical_value,
        )
    ).encode()
    digest = hmac.new(pepper, message, hashlib.sha256).hexdigest()
    return ThrottleBucketKey(audience, kind, digest, key_version)


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _HEX_SHA256.fullmatch(value) is not None


def _require_sha256(value: str, *, label: str) -> None:
    if not _valid_sha256(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_argon2id(value: str, *, label: str) -> None:
    # Full cryptographic verification stays outside the transaction, but
    # argon2-cffi's parser prevents malformed/prefix-only pseudo-hashes from
    # becoming the authoritative replacement and locking out the account.
    try:
        parameters = extract_parameters(value)
    except InvalidHashError as error:
        raise ValueError(f"{label} must be a valid Argon2id encoded hash") from error
    if parameters.type is not Type.ID:
        raise ValueError(f"{label} must be a valid Argon2id encoded hash")


def _valid_session_public_id(value: object) -> bool:
    return isinstance(value, str) and _SESSION_PUBLIC_ID.fullmatch(value) is not None


def _require_session_public_id(value: str) -> None:
    if not _valid_session_public_id(value):
        raise ValueError("Session public ID must be exactly 32 lowercase hex digits")


def _valid_public_id(value: object) -> bool:
    return isinstance(value, str) and _PUBLIC_ID.fullmatch(value) is not None


def _stored_public_id(value: object, *, label: str) -> str:
    if not _valid_public_id(value):
        # Public identifiers cross SQLite, URL and Zod boundaries. Treat an
        # invalid stored value as corrupt authority rather than normalizing an
        # alias that might identify a different object (Phase 1 auth contract).
        raise PrincipalDataIntegrityError(f"Stored {label} is not canonical")
    return str(value)


def _normalize_optional_bounded_text(
    value: str | None,
    *,
    label: str,
    maximum_length: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if len(normalized) > maximum_length:
        raise ValueError(f"{label} must contain at most {maximum_length} characters")
    if not normalized.isprintable():
        raise ValueError(f"{label} must not contain control characters")
    return normalized


def _normalize_ip_prefix(value: str | None) -> str | None:
    normalized = _normalize_optional_bounded_text(
        value,
        label="IP prefix",
        maximum_length=_IP_PREFIX_MAX_LENGTH,
    )
    if normalized is None:
        return None
    try:
        return ipaddress.ip_network(normalized, strict=False).with_prefixlen
    except ValueError as error:
        raise ValueError("IP prefix must be a valid IPv4 or IPv6 network") from error


def _stored_optional_session_text(
    value: object,
    *,
    label: str,
    maximum_length: int,
) -> str | None:
    try:
        return _normalize_optional_bounded_text(
            _optional_string(value),
            label=label,
            maximum_length=maximum_length,
        )
    except ValueError as error:
        raise PrincipalDataIntegrityError(f"Stored {label} is invalid") from error


def _stored_ip_prefix(value: object) -> str | None:
    try:
        return _normalize_ip_prefix(_optional_string(value))
    except ValueError as error:
        raise PrincipalDataIntegrityError("Stored IP prefix is invalid") from error


def _require_request_id(request_id: str) -> None:
    if _REQUEST_ID.fullmatch(request_id) is None:
        raise ValueError("Request ID must be a generated opaque identifier")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Authentication timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("Stored authentication timestamp is invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _as_utc(parsed)


def _parse_optional_timestamp(value: object) -> datetime | None:
    return None if value is None else _parse_timestamp(value)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _account_from_row(row: Mapping[str, object]) -> AuthAccountCredential:
    credential_hash = row["credential_hash"]
    if not isinstance(credential_hash, str) or not credential_hash:
        raise AccountUnavailableError("Account has no active credential")
    # Do not parse an existing encoding here: CredentialHasher turns malformed
    # or legacy hashes into the same generic verification failure as a wrong
    # password. Raising from lookup would create an account-enumeration signal.
    try:
        public_id = _stored_public_id(row["public_id"], label="account public ID")
    except PrincipalDataIntegrityError as error:
        # Login must not expose a distinct response for a malformed provisioned
        # account; the service maps this to the same unavailable-account path.
        raise AccountUnavailableError("Account identity is not active") from error
    return AuthAccountCredential(
        id=int(row["id"]),
        public_id=public_id,
        audience=AuthAudience(str(row["audience"])),
        credential_kind=str(row["credential_kind"]),
        credential_hash=credential_hash,
        linked_user_id=_optional_int(row["linked_user_id"]),
        status=str(row["status"]),
        credential_version=int(row["credential_version"]),
    )


def _session_from_row(row: Mapping[str, object]) -> AuthSessionRecord:
    public_id = _optional_string(row["public_id"])
    if public_id is None or not _valid_session_public_id(public_id):
        raise PrincipalDataIntegrityError("Stored session public ID is not canonical")
    return AuthSessionRecord(
        id=int(row["id"]),
        public_id=public_id,
        account_id=int(row["account_id"]),
        audience=AuthAudience(str(row["audience"])),
        credential_version=int(row["credential_version"]),
        version=int(row["version"]),
        created_at=_parse_timestamp(row["created_at"]),
        updated_at=_parse_timestamp(row["updated_at"]),
        last_seen_at=_parse_timestamp(row["last_seen_at"]),
        expires_at=_parse_timestamp(row["expires_at"]),
        revoked_at=_parse_optional_timestamp(row["revoked_at"]),
        revoke_reason=_optional_string(row["revoke_reason"]),
        device_label=_stored_optional_session_text(
            row["device_label"],
            label="Device label",
            maximum_length=_DEVICE_LABEL_MAX_LENGTH,
        ),
        user_agent_family=_stored_optional_session_text(
            row["user_agent_family"],
            label="User-agent family",
            maximum_length=_USER_AGENT_FAMILY_MAX_LENGTH,
        ),
        ip_prefix=_stored_ip_prefix(row["ip_prefix"]),
    )


def _insert_event(
    connection,
    *,
    event_type: AuthEventType,
    occurred_at: str,
    request_id: str,
    account_id: int | None = None,
    session_id: int | None = None,
    ip_prefix: str | None = None,
) -> None:
    # Auth events intentionally have no arbitrary metadata parameter.  This is
    # a structural guard against credentials, refresh tokens and raw logins
    # entering the audit trail (ADR 0003); typed columns hold all Phase-1 data.
    connection.execute(
        "INSERT INTO auth_events "
        "(account_id, session_id, event_type, occurred_at, request_id, "
        "ip_prefix, metadata_json) VALUES (?, ?, ?, ?, ?, ?, '{}')",
        (
            account_id,
            session_id,
            event_type.value,
            occurred_at,
            request_id,
            ip_prefix,
        ),
    )


class PwaAuthRepository:
    """Connection-per-operation repository for Phase-1 authentication data."""

    def __init__(
        self,
        factory: PwaConnectionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        throttle_policy: ThrottlePolicy | None = None,
        credential_hasher: PasswordHasher | None = None,
    ) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self.throttle_policy = throttle_policy or ThrottlePolicy()
        self._credential_hasher = credential_hasher or PasswordHasher()

    def _now(self) -> datetime:
        return _as_utc(self._clock())

    async def find_account_for_login(
        self,
        audience: AuthAudience,
        login: str,
    ) -> AuthAccountCredential | None:
        """Find an active account without receiving or verifying a credential.

        The caller must perform one Argon2 verification even for ``None``, using
        its startup-precomputed dummy hash, before returning a generic failure.
        Keeping that timing rule at the service boundary avoids doing expensive
        hashing while a SQLite connection is held.
        """

        normalized = normalize_login(login)
        if not normalized:
            return None

        def read(connection):
            row = connection.execute(
                "SELECT id, public_id, audience, credential_kind, "
                "credential_hash, linked_user_id, status, credential_version "
                "FROM auth_accounts WHERE audience = ? "
                "AND username_normalized = ? AND status = 'active'",
                (audience.value, normalized),
            ).fetchone()
            return None if row is None else _account_from_row(row)

        return await self._factory.run_read_async(read)

    async def create_session(
        self,
        *,
        verified_account: AuthAccountCredential,
        session_public_id: str,
        refresh_secret_hash: str,
        expires_at: datetime,
        request_id: str,
        replacement_credential_hash: str | None = None,
        device_label: str | None = None,
        user_agent_family: str | None = None,
        ip_prefix: str | None = None,
    ) -> AuthSessionRecord:
        """Create a session only if the account still matches verified state.

        Argon2 verification and optional replacement-hash calculation happen
        before this method.  The short transaction only compares the verified
        snapshot, applies a parameter rehash if needed, and inserts the session.
        """

        _require_sha256(refresh_secret_hash, label="refresh secret hash")
        _require_request_id(request_id)
        if not _valid_public_id(verified_account.public_id):
            raise AccountUnavailableError("Account identity is not active")
        now = self._now()
        expiry = _as_utc(expires_at)
        if expiry <= now:
            raise ValueError("Session expiry must be in the future")
        _require_session_public_id(session_public_id)
        if replacement_credential_hash is not None and not replacement_credential_hash:
            raise ValueError("Replacement credential hash must not be empty")
        if replacement_credential_hash is not None:
            _require_argon2id(
                replacement_credential_hash, label="replacement credential"
            )
        device_label = _normalize_optional_bounded_text(
            device_label,
            label="Device label",
            maximum_length=_DEVICE_LABEL_MAX_LENGTH,
        )
        user_agent_family = _normalize_optional_bounded_text(
            user_agent_family,
            label="User-agent family",
            maximum_length=_USER_AGENT_FAMILY_MAX_LENGTH,
        )
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        timestamp = _format_timestamp(now)

        def write(connection):
            current = connection.execute(
                "SELECT id, public_id, audience, credential_kind, "
                "credential_hash, linked_user_id, status, credential_version "
                "FROM auth_accounts WHERE id = ?",
                (verified_account.id,),
            ).fetchone()
            if current is None or current["status"] != "active":
                raise AccountUnavailableError("Account is not active")
            if (
                current["public_id"] != verified_account.public_id
                or current["audience"] != verified_account.audience.value
                or current["credential_kind"] != verified_account.credential_kind
                or current["linked_user_id"] != verified_account.linked_user_id
                or current["credential_version"] != verified_account.credential_version
                or current["credential_hash"] != verified_account.credential_hash
            ):
                raise AccountStateConflict(
                    "Account changed after credential verification"
                )

            if replacement_credential_hash is not None:
                updated = connection.execute(
                    "UPDATE auth_accounts SET credential_hash = ?, "
                    "updated_at = ? WHERE id = ? AND credential_version = ? "
                    "AND credential_hash = ?",
                    (
                        replacement_credential_hash,
                        timestamp,
                        verified_account.id,
                        verified_account.credential_version,
                        verified_account.credential_hash,
                    ),
                )
                if updated.rowcount != 1:
                    raise AccountStateConflict(
                        "Account changed during credential parameter upgrade"
                    )
                _insert_event(
                    connection,
                    event_type=AuthEventType.CREDENTIAL_REHASHED,
                    occurred_at=timestamp,
                    request_id=request_id,
                    account_id=verified_account.id,
                    ip_prefix=ip_prefix,
                )

            row = connection.execute(
                "INSERT INTO auth_sessions "
                "(public_id, account_id, audience, refresh_secret_hash, "
                "credential_version, created_at, updated_at, last_seen_at, "
                "expires_at, device_label, user_agent_family, ip_prefix) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
                (
                    session_public_id,
                    verified_account.id,
                    verified_account.audience.value,
                    refresh_secret_hash,
                    verified_account.credential_version,
                    timestamp,
                    timestamp,
                    timestamp,
                    _format_timestamp(expiry),
                    device_label,
                    user_agent_family,
                    ip_prefix,
                ),
            ).fetchone()
            connection.execute(
                "UPDATE auth_accounts SET last_login_at = ?, updated_at = ? "
                "WHERE id = ?",
                (timestamp, timestamp, verified_account.id),
            )
            _insert_event(
                connection,
                event_type=AuthEventType.SESSION_CREATED,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=verified_account.id,
                session_id=int(row["id"]),
                ip_prefix=ip_prefix,
            )
            return _session_from_row(row)

        return await self._factory.run_write_async(write)

    async def get_session_authority_versions(
        self,
        *,
        audience: AuthAudience,
        account_public_id: str,
        session_public_id: str,
    ) -> tuple[int, int] | None:
        """Read the current signed-claim versions for WebSocket revalidation.

        The public identities came from an access cookie validated before the
        WebSocket upgrade, never from the socket client.  Returning only the
        two authority versions lets the service reuse ``get_current_session``
        for all account/session/expiry/principal checks.  A race between both
        reads fails closed instead of accepting stale state.
        """

        if not _valid_session_public_id(session_public_id) or not _valid_public_id(
            account_public_id
        ):
            return None

        def read(connection):
            row = connection.execute(
                "SELECT s.credential_version, s.version "
                "FROM auth_sessions AS s JOIN auth_accounts AS a "
                "ON a.id = s.account_id WHERE s.public_id = ? "
                "AND a.public_id = ? AND s.audience = ? AND a.audience = ?",
                (
                    session_public_id,
                    account_public_id,
                    audience.value,
                    audience.value,
                ),
            ).fetchone()
            if row is None:
                return None
            credential_version = int(row["credential_version"])
            session_version = int(row["version"])
            if credential_version <= 0 or session_version <= 0:
                return None
            return credential_version, session_version

        return await self._factory.run_read_async(read)

    async def get_current_session(
        self,
        *,
        audience: AuthAudience,
        account_public_id: str,
        session_public_id: str,
        credential_version: int,
        session_version: int,
    ) -> CurrentAuthSession | None:
        """Resolve signed access claims against authoritative session state."""

        if (
            credential_version <= 0
            or session_version <= 0
            or not _valid_session_public_id(session_public_id)
            or not _valid_public_id(account_public_id)
        ):
            return None
        now = self._now()

        def read(connection):
            row = connection.execute(
                "SELECT s.*, a.public_id AS account_public_id, "
                "a.status AS account_status, a.display_name, a.linked_user_id, "
                "a.credential_version AS account_credential_version, "
                "u.public_id AS linked_user_public_id, "
                "u.type AS linked_user_type, u.name AS linked_user_name, "
                "u.surname AS linked_user_surname "
                "FROM auth_sessions AS s JOIN auth_accounts AS a "
                "ON a.id = s.account_id LEFT JOIN users AS u "
                "ON u.id = a.linked_user_id WHERE s.public_id = ? "
                "AND a.public_id = ? AND s.audience = ? AND a.audience = ?",
                (
                    session_public_id,
                    account_public_id,
                    audience.value,
                    audience.value,
                ),
            ).fetchone()
            if row is None:
                return None
            linked_user_id = _optional_int(row["linked_user_id"])
            linked_user_public_id = _optional_string(row["linked_user_public_id"])
            linked_user_public_id_is_valid = (
                linked_user_public_id is not None
                and _valid_public_id(linked_user_public_id)
            )
            linked_user_type = _optional_int(row["linked_user_type"])
            display_name = _optional_string(row["display_name"])
            if display_name is None and linked_user_id is not None:
                display_name = " ".join(
                    part
                    for part in (
                        _optional_string(row["linked_user_name"]),
                        _optional_string(row["linked_user_surname"]),
                    )
                    if part
                ).strip()
            identity_shape_is_valid = (
                (
                    audience is AuthAudience.STUDENT
                    and linked_user_id is not None
                    and linked_user_public_id_is_valid
                    and linked_user_type == int(USER_TYPE.STUDENT)
                )
                or (
                    audience is AuthAudience.FAMILY
                    and linked_user_id is None
                    and linked_user_public_id is None
                    and linked_user_type is None
                )
                or (
                    audience is AuthAudience.STAFF
                    and linked_user_id is not None
                    and linked_user_public_id_is_valid
                    and linked_user_type
                    in {int(USER_TYPE.TEACHER), int(USER_TYPE.ADMIN)}
                )
            )
            if (
                row["account_status"] != "active"
                or not identity_shape_is_valid
                or not display_name
                or row["revoked_at"] is not None
                or _parse_timestamp(row["expires_at"]) <= now
                or int(row["credential_version"]) != credential_version
                or int(row["account_credential_version"]) != credential_version
                or int(row["version"]) != session_version
            ):
                return None
            return CurrentAuthSession(
                session=_session_from_row(row),
                account_public_id=account_public_id,
                account_status=str(row["account_status"]),
                display_name=display_name,
                linked_user_id=linked_user_id,
                linked_user_public_id=linked_user_public_id,
                linked_user_type=linked_user_type,
            )

        return await self._factory.run_read_async(read)

    async def list_sessions(
        self,
        *,
        account_id: int,
        include_revoked: bool = True,
    ) -> tuple[AuthSessionRecord, ...]:
        """List device/history rows; ``include_revoked`` does not hide expiry."""

        def read(connection):
            where = "account_id = ?"
            if not include_revoked:
                where += " AND revoked_at IS NULL"
            rows = connection.execute(
                f"SELECT * FROM auth_sessions WHERE {where} "
                "ORDER BY updated_at DESC, id DESC",
                (account_id,),
            ).fetchall()
            return tuple(_session_from_row(row) for row in rows)

        return await self._factory.run_read_async(read)

    async def revoke_session(
        self,
        *,
        account_id: int,
        session_public_id: str,
        reason: SessionRevokeReason,
        request_id: str,
        ip_prefix: str | None = None,
    ) -> bool:
        _require_request_id(request_id)
        if not _valid_session_public_id(session_public_id):
            return False
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        timestamp = _format_timestamp(self._now())

        def write(connection):
            row = connection.execute(
                "SELECT id FROM auth_sessions WHERE account_id = ? "
                "AND public_id = ? AND revoked_at IS NULL",
                (account_id, session_public_id),
            ).fetchone()
            if row is None:
                return False
            updated = connection.execute(
                "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = ?, "
                "updated_at = ?, version = version + 1 WHERE id = ? "
                "AND revoked_at IS NULL",
                (timestamp, reason.value, timestamp, row["id"]),
            )
            if updated.rowcount != 1:
                return False
            _insert_event(
                connection,
                event_type=AuthEventType.SESSION_REVOKED,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=account_id,
                session_id=int(row["id"]),
                ip_prefix=ip_prefix,
            )
            return True

        return await self._factory.run_write_async(write)

    async def revoke_all_sessions(
        self,
        *,
        account_id: int,
        reason: SessionRevokeReason,
        request_id: str,
        except_session_public_id: str | None = None,
        ip_prefix: str | None = None,
    ) -> int:
        _require_request_id(request_id)
        if except_session_public_id is not None:
            _require_session_public_id(except_session_public_id)
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        timestamp = _format_timestamp(self._now())

        def write(connection):
            parameters: list[object] = [timestamp, reason.value, timestamp, account_id]
            condition = "account_id = ? AND revoked_at IS NULL"
            if except_session_public_id is not None:
                condition += " AND public_id <> ?"
                parameters.append(except_session_public_id)
            updated = connection.execute(
                "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = ?, "
                f"updated_at = ?, version = version + 1 WHERE {condition}",
                parameters,
            )
            count = updated.rowcount
            if count:
                _insert_event(
                    connection,
                    event_type=AuthEventType.SESSIONS_REVOKED_ALL,
                    occurred_at=timestamp,
                    request_id=request_id,
                    account_id=account_id,
                    ip_prefix=ip_prefix,
                )
            return count

        return await self._factory.run_write_async(write)

    async def rotate_refresh_secret(
        self,
        *,
        audience: AuthAudience,
        session_public_id: str,
        presented_secret_hash: str,
        replacement_secret_hash: str,
        request_id: str,
        ip_prefix: str | None = None,
    ) -> RefreshRotationResult:
        """Atomically consume one refresh secret and replace it exactly once.

        A concurrent request holding the same old secret observes the rotated
        digest after acquiring SQLite's writer lock and revokes the session as a
        replay.  The optimistic ``version`` and old-digest predicates remain in
        the UPDATE as a second guard even though ``BEGIN IMMEDIATE`` serializes
        writers.
        """

        _require_sha256(presented_secret_hash, label="presented refresh hash")
        _require_sha256(replacement_secret_hash, label="replacement refresh hash")
        _require_request_id(request_id)
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        if not _valid_session_public_id(session_public_id):
            return RefreshRotationResult(RefreshRotationOutcome.NOT_FOUND)
        if hmac.compare_digest(presented_secret_hash, replacement_secret_hash):
            raise ValueError("Refresh rotation requires a new secret")
        now = self._now()
        timestamp = _format_timestamp(now)

        def write(connection):
            row = connection.execute(
                "SELECT s.*, a.status AS account_status, "
                "a.credential_version AS account_credential_version, "
                "a.public_id AS account_public_id "
                "FROM auth_sessions AS s JOIN auth_accounts AS a "
                "ON a.id = s.account_id WHERE s.public_id = ? "
                "AND s.audience = ? AND a.audience = ?",
                (session_public_id, audience.value, audience.value),
            ).fetchone()
            if row is None:
                return RefreshRotationResult(RefreshRotationOutcome.NOT_FOUND)
            if row["revoked_at"] is not None:
                return RefreshRotationResult(
                    RefreshRotationOutcome.INACTIVE, _session_from_row(row)
                )

            def revoke(
                outcome: RefreshRotationOutcome,
                reason: SessionRevokeReason,
            ) -> RefreshRotationResult:
                connection.execute(
                    "UPDATE auth_sessions SET revoked_at = ?, "
                    "revoke_reason = ?, updated_at = ?, version = version + 1 "
                    "WHERE id = ? AND revoked_at IS NULL",
                    (timestamp, reason.value, timestamp, row["id"]),
                )
                _insert_event(
                    connection,
                    event_type=AuthEventType.SESSION_REVOKED,
                    occurred_at=timestamp,
                    request_id=request_id,
                    account_id=int(row["account_id"]),
                    session_id=int(row["id"]),
                    ip_prefix=ip_prefix,
                )
                refreshed = connection.execute(
                    "SELECT * FROM auth_sessions WHERE id = ?", (row["id"],)
                ).fetchone()
                return RefreshRotationResult(outcome, _session_from_row(refreshed))

            if _parse_timestamp(row["expires_at"]) <= now:
                return revoke(
                    RefreshRotationOutcome.EXPIRED, SessionRevokeReason.EXPIRED
                )
            if row["account_status"] != "active":
                return revoke(
                    RefreshRotationOutcome.ACCOUNT_UNAVAILABLE,
                    SessionRevokeReason.ACCOUNT_UNAVAILABLE,
                )
            if int(row["credential_version"]) != int(row["account_credential_version"]):
                return revoke(
                    RefreshRotationOutcome.CREDENTIAL_CHANGED,
                    SessionRevokeReason.CREDENTIAL_CHANGED,
                )
            if not hmac.compare_digest(
                str(row["refresh_secret_hash"]), presented_secret_hash
            ):
                consumed = connection.execute(
                    "SELECT 1 FROM auth_refresh_consumed_secrets "
                    "WHERE session_id = ? AND refresh_secret_hash = ?",
                    (row["id"], presented_secret_hash),
                ).fetchone()
                if consumed is not None:
                    return revoke(
                        RefreshRotationOutcome.REPLAY_REVOKED,
                        SessionRevokeReason.REFRESH_REPLAY,
                    )
                # A mismatch is not by itself proof that this value was ever a
                # valid refresh secret. Revoking here would let a leaked public
                # session ID become a logout oracle. Only consumed-history hits
                # trigger theft/replay handling.
                _insert_event(
                    connection,
                    event_type=AuthEventType.SESSION_REFRESH_REJECTED,
                    occurred_at=timestamp,
                    request_id=request_id,
                    account_id=int(row["account_id"]),
                    session_id=int(row["id"]),
                    ip_prefix=ip_prefix,
                )
                return RefreshRotationResult(
                    RefreshRotationOutcome.INVALID_SECRET,
                    _session_from_row(row),
                )

            expected_version = int(row["version"])
            connection.execute(
                "INSERT INTO auth_refresh_consumed_secrets "
                "(session_id, refresh_secret_hash, consumed_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    row["id"],
                    presented_secret_hash,
                    timestamp,
                    row["expires_at"],
                ),
            )
            updated = connection.execute(
                "UPDATE auth_sessions SET refresh_secret_hash = ?, "
                "last_seen_at = ?, updated_at = ?, version = version + 1 "
                "WHERE id = ? AND version = ? AND refresh_secret_hash = ? "
                "AND revoked_at IS NULL",
                (
                    replacement_secret_hash,
                    timestamp,
                    timestamp,
                    row["id"],
                    expected_version,
                    presented_secret_hash,
                ),
            )
            if updated.rowcount != 1:
                # BEGIN IMMEDIATE makes this unreachable today. Raising rolls
                # back the consumed-history insert instead of misclassifying an
                # unexplained storage conflict as a proven replay.
                raise AccountStateConflict(
                    "Refresh session changed during optimistic rotation"
                )
            _insert_event(
                connection,
                event_type=AuthEventType.SESSION_ROTATED,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=int(row["account_id"]),
                session_id=int(row["id"]),
                ip_prefix=ip_prefix,
            )
            refreshed = connection.execute(
                "SELECT * FROM auth_sessions WHERE id = ?", (row["id"],)
            ).fetchone()
            return RefreshRotationResult(
                RefreshRotationOutcome.ROTATED,
                _session_from_row(refreshed),
                _stored_public_id(row["account_public_id"], label="account public ID"),
            )

        return await self._factory.run_write_async(write)

    async def revoke_session_with_refresh_secret(
        self,
        *,
        audience: AuthAudience,
        session_public_id: str,
        presented_secret_hash: str,
        request_id: str,
        ip_prefix: str | None = None,
    ) -> RevokedSessionTarget | None:
        """Soft-revoke a session using only its opaque refresh credential.

        This is the logout path for a missing or expired short-lived access
        cookie. Client-derived token failures deliberately share one ``None``
        result: malformed IDs/digests, an unknown or wrong-audience session, an
        arbitrary secret, and an already revoked session must not form a token
        oracle. A consumed secret is authenticated replay evidence and revokes
        the lineage with the replay reason, matching refresh rotation.

        The soft revoke and its secret-free audit event are committed in the
        same ``BEGIN IMMEDIATE`` transaction. Callers must always clear their
        audience cookies and return the same external logout response.
        """

        _require_request_id(request_id)
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        if not _valid_session_public_id(session_public_id) or not _valid_sha256(
            presented_secret_hash
        ):
            return None
        now = self._now()
        timestamp = _format_timestamp(now)

        def write(connection):
            row = connection.execute(
                "SELECT s.*, a.public_id AS account_public_id, "
                "a.status AS account_status, "
                "a.credential_version AS account_credential_version "
                "FROM auth_sessions AS s JOIN auth_accounts AS a "
                "ON a.id = s.account_id WHERE s.public_id = ? "
                "AND s.audience = ? AND a.audience = ?",
                (session_public_id, audience.value, audience.value),
            ).fetchone()
            if row is None or row["revoked_at"] is not None:
                return None

            secret_is_current = hmac.compare_digest(
                str(row["refresh_secret_hash"]), presented_secret_hash
            )
            secret_was_consumed = False
            if not secret_is_current:
                secret_was_consumed = (
                    connection.execute(
                        "SELECT 1 FROM auth_refresh_consumed_secrets "
                        "WHERE session_id = ? AND refresh_secret_hash = ?",
                        (row["id"], presented_secret_hash),
                    ).fetchone()
                    is not None
                )
            if not secret_is_current and not secret_was_consumed:
                return None

            if secret_was_consumed:
                reason = SessionRevokeReason.REFRESH_REPLAY
            elif _parse_timestamp(row["expires_at"]) <= now:
                reason = SessionRevokeReason.EXPIRED
            elif row["account_status"] != "active":
                reason = SessionRevokeReason.ACCOUNT_UNAVAILABLE
            elif int(row["credential_version"]) != int(
                row["account_credential_version"]
            ):
                reason = SessionRevokeReason.CREDENTIAL_CHANGED
            else:
                reason = SessionRevokeReason.LOGOUT

            updated = connection.execute(
                "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = ?, "
                "updated_at = ?, version = version + 1 "
                "WHERE id = ? AND revoked_at IS NULL",
                (timestamp, reason.value, timestamp, row["id"]),
            )
            if updated.rowcount != 1:
                # The immediate writer transaction makes a concurrent revoke
                # impossible here. Do not commit a partial or unaudited state
                # if a future storage change breaks that invariant.
                raise AccountStateConflict(
                    "Refresh-authenticated session changed during revoke"
                )
            _insert_event(
                connection,
                event_type=AuthEventType.SESSION_REVOKED,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=int(row["account_id"]),
                session_id=int(row["id"]),
                ip_prefix=ip_prefix,
            )

            return RevokedSessionTarget(
                audience=audience,
                account_public_id=_stored_public_id(
                    row["account_public_id"], label="account public ID"
                ),
                session_public_id=session_public_id,
            )

        return await self._factory.run_write_async(write)

    async def delete_expired_consumed_refresh_secrets(
        self,
        *,
        limit: int = 1_000,
    ) -> int:
        """Delete a bounded batch after its owning session expiry."""

        if limit <= 0 or limit > 10_000:
            raise ValueError("Refresh-history cleanup limit must be 1..10000")
        timestamp = _format_timestamp(self._now())

        def write(connection):
            return connection.execute(
                "DELETE FROM auth_refresh_consumed_secrets WHERE rowid IN ("
                "SELECT rowid FROM auth_refresh_consumed_secrets "
                "WHERE expires_at <= ? ORDER BY expires_at, session_id LIMIT ?"
                ")",
                (timestamp, limit),
            ).rowcount

        return await self._factory.run_write_async(write)

    async def change_credential(
        self,
        *,
        account_id: int,
        expected_credential_version: int,
        replacement_credential_hash: str,
        request_id: str,
        ip_prefix: str | None = None,
    ) -> CredentialChangeResult:
        """Replace a Family/Staff credential and invalidate prior sessions.

        Student credentials must use ``change_student_telegram_credential`` so
        the legacy Telegram adapter and PWA account cannot diverge.
        """

        if not replacement_credential_hash:
            raise ValueError("Replacement credential hash must not be empty")
        _require_argon2id(replacement_credential_hash, label="replacement credential")
        if expected_credential_version <= 0:
            raise ValueError("Expected credential version must be positive")
        _require_request_id(request_id)
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        timestamp = _format_timestamp(self._now())

        def write(connection):
            updated_account = connection.execute(
                "UPDATE auth_accounts SET credential_hash = ?, "
                "credential_version = credential_version + 1, updated_at = ? "
                "WHERE id = ? AND credential_version = ? "
                "AND audience IN ('family', 'staff')",
                (
                    replacement_credential_hash,
                    timestamp,
                    account_id,
                    expected_credential_version,
                ),
            )
            if updated_account.rowcount != 1:
                return CredentialChangeResult(changed=False)
            new_version = expected_credential_version + 1
            revoked = connection.execute(
                "UPDATE auth_sessions SET revoked_at = ?, "
                "revoke_reason = ?, updated_at = ?, version = version + 1 "
                "WHERE account_id = ? AND revoked_at IS NULL",
                (
                    timestamp,
                    SessionRevokeReason.CREDENTIAL_CHANGED.value,
                    timestamp,
                    account_id,
                ),
            ).rowcount
            _insert_event(
                connection,
                event_type=AuthEventType.CREDENTIAL_CHANGED,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=account_id,
                ip_prefix=ip_prefix,
            )
            return CredentialChangeResult(True, new_version, revoked)

        return await self._factory.run_write_async(write)

    async def change_student_telegram_credential(
        self,
        *,
        account_id: int,
        expected_credential_version: int,
        normalized_telegram_token: str,
        replacement_credential_hash: str,
        request_id: str,
        ip_prefix: str | None = None,
    ) -> CredentialChangeResult:
        """Rotate the one Student secret across Telegram and PWA atomically.

        The caller hashes and passes the *same already-normalized* value. This
        method rejects a second representation so a raw-vs-normalized hashing
        mistake cannot split Telegram and PWA login semantics. The value enters
        only legacy ``users.token``—never events, throttle data or return values.
        """

        if not normalized_telegram_token:
            raise ValueError("Telegram token must not be empty")
        if (
            normalize_telegram_token(normalized_telegram_token)
            != normalized_telegram_token
        ):
            raise ValueError(
                "Telegram token must be normalized before credential change"
            )
        _require_argon2id(replacement_credential_hash, label="replacement credential")
        try:
            credential_matches_token = bool(
                self._credential_hasher.verify(
                    replacement_credential_hash,
                    normalized_telegram_token,
                )
            )
        except InvalidHashError, VerificationError, VerifyMismatchError:
            credential_matches_token = False
        if not credential_matches_token:
            # The legacy bot and PWA intentionally share exactly one Student
            # secret. Checking the encoded value before BEGIN IMMEDIATE avoids
            # both SQLite lock inflation and a split-brain credential reset.
            raise ValueError(
                "Replacement credential must encode the normalized Telegram token"
            )
        if expected_credential_version <= 0:
            raise ValueError("Expected credential version must be positive")
        _require_request_id(request_id)
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        timestamp = _format_timestamp(self._now())

        def write(connection):
            account = connection.execute(
                "SELECT a.linked_user_id, u.public_id AS linked_user_public_id "
                "FROM auth_accounts AS a "
                "JOIN users AS u ON u.id = a.linked_user_id "
                "WHERE a.id = ? AND a.audience = 'student' "
                "AND a.credential_version = ? AND u.type = ? "
                "AND u.public_id IS NOT NULL",
                (
                    account_id,
                    expected_credential_version,
                    int(USER_TYPE.STUDENT),
                ),
            ).fetchone()
            if account is None or account["linked_user_id"] is None:
                return CredentialChangeResult(changed=False)
            _stored_public_id(
                account["linked_user_public_id"], label="Student user public ID"
            )

            # The unique users.token update may fail. BEGIN IMMEDIATE plus the
            # factory rollback guarantees the auth version and session state
            # remain untouched in that case.
            connection.execute(
                "UPDATE users SET token = ? WHERE id = ?",
                (normalized_telegram_token, account["linked_user_id"]),
            )
            updated_account = connection.execute(
                "UPDATE auth_accounts SET credential_hash = ?, "
                "credential_version = credential_version + 1, updated_at = ? "
                "WHERE id = ? AND audience = 'student' "
                "AND credential_version = ?",
                (
                    replacement_credential_hash,
                    timestamp,
                    account_id,
                    expected_credential_version,
                ),
            )
            if updated_account.rowcount != 1:
                raise AccountStateConflict(
                    "Student account changed during credential rotation"
                )
            new_version = expected_credential_version + 1
            revoked = connection.execute(
                "UPDATE auth_sessions SET revoked_at = ?, "
                "revoke_reason = ?, updated_at = ?, version = version + 1 "
                "WHERE account_id = ? AND revoked_at IS NULL",
                (
                    timestamp,
                    SessionRevokeReason.CREDENTIAL_CHANGED.value,
                    timestamp,
                    account_id,
                ),
            ).rowcount
            _insert_event(
                connection,
                event_type=AuthEventType.CREDENTIAL_CHANGED,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=account_id,
                ip_prefix=ip_prefix,
            )
            return CredentialChangeResult(True, new_version, revoked)

        return await self._factory.run_write_async(write)

    async def record_auth_event(
        self,
        *,
        event_type: AuthEventType,
        request_id: str,
        account_id: int | None = None,
        session_id: int | None = None,
        ip_prefix: str | None = None,
    ) -> None:
        """Append a typed, metadata-free event such as a generic login failure."""

        _require_request_id(request_id)
        ip_prefix = _normalize_ip_prefix(ip_prefix)
        timestamp = _format_timestamp(self._now())

        def write(connection):
            if session_id is not None:
                row = connection.execute(
                    "SELECT account_id FROM auth_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row is None or (
                    account_id is not None and int(row["account_id"]) != account_id
                ):
                    raise ValueError("Auth event session/account mismatch")
            _insert_event(
                connection,
                event_type=event_type,
                occurred_at=timestamp,
                request_id=request_id,
                account_id=account_id,
                session_id=session_id,
                ip_prefix=ip_prefix,
            )

        await self._factory.run_write_async(write)

    async def check_throttle(
        self,
        keys: Sequence[ThrottleBucketKey],
    ) -> tuple[ThrottleState, ...]:
        now = self._now()
        unique = _unique_throttle_keys(keys)

        def read(connection):
            return tuple(
                self._read_throttle_state(connection, key=key, now=now)
                for key in unique
            )

        return await self._factory.run_read_async(read)

    async def record_throttle_failure(
        self,
        keys: Sequence[ThrottleBucketKey],
    ) -> tuple[ThrottleState, ...]:
        """Increment login/account/IP buckets in one shared-worker transaction."""

        now = self._now()
        timestamp = _format_timestamp(now)
        unique = _unique_throttle_keys(keys)

        def write(connection):
            states: list[ThrottleState] = []
            for key in unique:
                existing = connection.execute(
                    "SELECT * FROM auth_throttle_buckets WHERE audience = ? "
                    "AND bucket_kind = ? AND bucket_key_hmac = ? "
                    "AND key_version = ?",
                    (
                        key.audience.value,
                        key.kind.value,
                        key.digest,
                        key.key_version,
                    ),
                ).fetchone()
                if existing is not None:
                    current = _throttle_state_from_row(key, existing, now)
                    # A request that was already locked by another worker must
                    # not extend its own lock simply by continuing to retry.
                    if current.locked:
                        states.append(current)
                        continue
                    window_start = _parse_timestamp(existing["window_started_at"])
                    if now >= window_start + self.throttle_policy.window:
                        failure_count = 1
                        window_start = now
                    else:
                        failure_count = int(existing["failure_count"]) + 1
                    lock_duration = self.throttle_policy.lock_duration(failure_count)
                    locked_until = (
                        None if lock_duration is None else now + lock_duration
                    )
                    connection.execute(
                        "UPDATE auth_throttle_buckets SET failure_count = ?, "
                        "window_started_at = ?, last_failed_at = ?, "
                        "locked_until = ?, updated_at = ?, version = version + 1 "
                        "WHERE audience = ? AND bucket_kind = ? "
                        "AND bucket_key_hmac = ? AND key_version = ?",
                        (
                            failure_count,
                            _format_timestamp(window_start),
                            timestamp,
                            None
                            if locked_until is None
                            else _format_timestamp(locked_until),
                            timestamp,
                            key.audience.value,
                            key.kind.value,
                            key.digest,
                            key.key_version,
                        ),
                    )
                else:
                    failure_count = 1
                    locked_until = None
                    lock_duration = self.throttle_policy.lock_duration(failure_count)
                    if lock_duration is not None:
                        locked_until = now + lock_duration
                    connection.execute(
                        "INSERT INTO auth_throttle_buckets "
                        "(audience, bucket_kind, bucket_key_hmac, key_version, "
                        "failure_count, window_started_at, last_failed_at, "
                        "locked_until, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            key.audience.value,
                            key.kind.value,
                            key.digest,
                            key.key_version,
                            failure_count,
                            timestamp,
                            timestamp,
                            None
                            if locked_until is None
                            else _format_timestamp(locked_until),
                            timestamp,
                            timestamp,
                        ),
                    )
                states.append(
                    ThrottleState(
                        key=key,
                        failure_count=failure_count,
                        locked_until=locked_until,
                        retry_after_seconds=_retry_after_seconds(locked_until, now),
                    )
                )
            return tuple(states)

        return await self._factory.run_write_async(write)

    async def clear_throttle(self, keys: Sequence[ThrottleBucketKey]) -> int:
        """Clear only explicitly supplied buckets after a successful login.

        The service normally clears normalized-login and account buckets, but
        not the IP bucket: a successful account must not erase network-level
        evidence for unrelated distributed attempts.
        """

        unique = _unique_throttle_keys(keys)

        def write(connection):
            deleted = 0
            for key in unique:
                deleted += connection.execute(
                    "DELETE FROM auth_throttle_buckets WHERE audience = ? "
                    "AND bucket_kind = ? AND bucket_key_hmac = ? "
                    "AND key_version = ?",
                    (
                        key.audience.value,
                        key.kind.value,
                        key.digest,
                        key.key_version,
                    ),
                ).rowcount
            return deleted

        return await self._factory.run_write_async(write)

    def _read_throttle_state(
        self,
        connection,
        *,
        key: ThrottleBucketKey,
        now: datetime,
    ) -> ThrottleState:
        row = connection.execute(
            "SELECT * FROM auth_throttle_buckets WHERE audience = ? "
            "AND bucket_kind = ? AND bucket_key_hmac = ? AND key_version = ?",
            (key.audience.value, key.kind.value, key.digest, key.key_version),
        ).fetchone()
        if row is None:
            return ThrottleState(key, 0, None, 0)
        return _throttle_state_from_row(key, row, now, self.throttle_policy)

    async def list_family_children(
        self,
        *,
        family_account_id: int,
    ) -> tuple[FamilyChildRecord, ...]:
        def read(connection):
            rows = connection.execute(
                "SELECT l.student_user_id, u.public_id AS student_public_id, "
                "u.name, u.surname, u.group_id, "
                "u.grade, u.birthday, l.relationship_label, l.is_primary "
                "FROM family_student_links AS l "
                "JOIN auth_accounts AS a ON a.id = l.family_account_id "
                "JOIN users AS u ON u.id = l.student_user_id "
                "WHERE l.family_account_id = ? AND a.audience = 'family' "
                "AND a.status = 'active' AND u.type = ? "
                "AND u.public_id IS NOT NULL "
                "AND l.revoked_at IS NULL "
                "ORDER BY l.is_primary DESC, u.surname, u.name, u.id",
                (family_account_id, int(USER_TYPE.STUDENT)),
            ).fetchall()
            children: list[FamilyChildRecord] = []
            for row in rows:
                children.append(
                    FamilyChildRecord(
                        student_user_id=int(row["student_user_id"]),
                        student_public_id=_stored_public_id(
                            row["student_public_id"], label="Student user public ID"
                        ),
                        name=str(row["name"]),
                        surname=str(row["surname"]),
                        group_id=_optional_string(row["group_id"]),
                        grade=_optional_int(row["grade"]),
                        birthday=_optional_string(row["birthday"]),
                        relationship_label=_optional_string(row["relationship_label"]),
                        is_primary=bool(row["is_primary"]),
                    )
                )
            return tuple(children)

        return await self._factory.run_read_async(read)

    async def list_course_enrollments(
        self,
        *,
        student_user_id: int,
        include_inactive: bool = False,
    ) -> tuple[CourseEnrollmentRecord, ...]:
        """Load per-course active group/mode and currently allowed groups."""

        now = self._now()

        def read(connection):
            condition = "ce.student_user_id = ?"
            if not include_inactive:
                condition += " AND ce.status = 'active'"
            enrollment_rows = connection.execute(
                "SELECT ce.id, ce.public_id, ce.version, ce.course_id, "
                "u.public_id AS student_public_id, "
                "ce.active_group_id, ce.attendance_mode, "
                "ce.status AS enrollment_status, c.public_id AS course_public_id, "
                "c.code AS course_code, c.name AS course_name, "
                "c.subject_code AS course_subject_code, "
                "c.status AS course_status, c.sort_order AS course_sort_order, "
                "c.accent_key AS course_accent_key, "
                "c.version AS course_version, "
                "g.public_id AS active_group_public_id "
                "FROM course_enrollments AS ce "
                "JOIN users AS u ON u.id = ce.student_user_id "
                "JOIN courses AS c ON c.id = ce.course_id "
                "JOIN groups AS g ON g.course_id = ce.course_id "
                f"AND g.group_id = ce.active_group_id WHERE {condition} "
                "AND u.type = ? AND u.public_id IS NOT NULL "
                "ORDER BY c.sort_order, c.id, ce.id",
                (student_user_id, int(USER_TYPE.STUDENT)),
            ).fetchall()
            if not enrollment_rows:
                return ()

            enrollment_ids = [int(row["id"]) for row in enrollment_rows]
            placeholders = ",".join("?" for _ in enrollment_ids)
            access_rows = connection.execute(
                "SELECT a.enrollment_id, a.valid_from, a.valid_to, "
                "c.public_id AS course_public_id, "
                "g.group_id, g.public_id AS group_public_id, g.short_code, "
                "g.public_name, g.status, g.color_key, "
                "coalesce(g.sort_order, 0) AS sort_order, g.version "
                "FROM course_group_access AS a "
                "JOIN courses AS c ON c.id = a.course_id "
                "JOIN groups AS g ON g.course_id = a.course_id "
                "AND g.group_id = a.group_id "
                f"WHERE a.enrollment_id IN ({placeholders}) "
                "ORDER BY a.enrollment_id, coalesce(g.sort_order, 0), g.group_id",
                enrollment_ids,
            ).fetchall()
            access_by_enrollment: dict[int, list[CourseGroupAccessRecord]] = {
                enrollment_id: [] for enrollment_id in enrollment_ids
            }
            for row in access_rows:
                valid_from = _parse_timestamp(row["valid_from"])
                valid_to = _parse_optional_timestamp(row["valid_to"])
                if valid_from > now or (valid_to is not None and valid_to <= now):
                    continue
                group_public_id = _optional_string(row["group_public_id"])
                if group_public_id is None:
                    # Transitional legacy rows without a public identifier are
                    # never valid browser authority; the active-group invariant
                    # below will surface this if the row is required.
                    continue
                group_public_id = _stored_public_id(
                    group_public_id, label="Group public ID"
                )
                access_by_enrollment[int(row["enrollment_id"])].append(
                    CourseGroupAccessRecord(
                        group_id=str(row["group_id"]),
                        group_public_id=group_public_id,
                        course_public_id=_stored_public_id(
                            row["course_public_id"], label="Course public ID"
                        ),
                        short_code=str(row["short_code"]),
                        public_name=str(row["public_name"]),
                        status=str(row["status"]),
                        color_key=_optional_string(row["color_key"]),
                        sort_order=int(row["sort_order"]),
                        version=int(row["version"]),
                        valid_from=valid_from,
                        valid_to=valid_to,
                    )
                )
            records: list[CourseEnrollmentRecord] = []
            for row in enrollment_rows:
                allowed_groups = tuple(access_by_enrollment[int(row["id"])])
                active_group_id = str(row["active_group_id"])
                active_group_public_id = _optional_string(row["active_group_public_id"])
                if str(row["enrollment_status"]) == "active" and (
                    not allowed_groups
                    or active_group_id
                    not in {group.group_id for group in allowed_groups}
                    or active_group_public_id is None
                ):
                    # The TypeScript contract requires a non-empty access set
                    # and activeGroup ∈ allowedGroups. Returning a partial row
                    # would turn corrupt import data into accidental authority.
                    raise PrincipalDataIntegrityError(
                        "Active enrollment has no authoritative active-group access"
                    )
                if active_group_public_id is None:
                    # Inactive historical rows may predate the public-ID
                    # backfill, but cannot be used for current authorization.
                    continue
                active_group_public_id = _stored_public_id(
                    active_group_public_id, label="Active group public ID"
                )
                records.append(
                    CourseEnrollmentRecord(
                        enrollment_id=int(row["id"]),
                        enrollment_public_id=_stored_public_id(
                            row["public_id"], label="Course enrollment public ID"
                        ),
                        enrollment_version=int(row["version"]),
                        student_public_id=_stored_public_id(
                            row["student_public_id"], label="Student user public ID"
                        ),
                        course_id=int(row["course_id"]),
                        course_public_id=_stored_public_id(
                            row["course_public_id"], label="Course public ID"
                        ),
                        course_code=str(row["course_code"]),
                        course_name=str(row["course_name"]),
                        course_subject_code=str(row["course_subject_code"]),
                        course_status=str(row["course_status"]),
                        course_sort_order=int(row["course_sort_order"]),
                        course_accent_key=str(row["course_accent_key"]),
                        course_version=int(row["course_version"]),
                        active_group_id=active_group_id,
                        active_group_public_id=active_group_public_id,
                        attendance_mode=str(row["attendance_mode"]),
                        enrollment_status=str(row["enrollment_status"]),
                        allowed_groups=allowed_groups,
                    )
                )
            return tuple(records)

        return await self._factory.run_read_async(read)

    async def list_staff_scopes(
        self,
        *,
        staff_user_id: int,
    ) -> tuple[StaffScopeRecord, ...]:
        """Load active course/group scopes; global-admin policy stays in service."""

        now = self._now()

        def read(connection):
            rows = connection.execute(
                "SELECT s.id, s.staff_user_id, s.course_id, s.group_id, "
                "s.role, s.valid_from, s.valid_to, s.version, "
                "c.public_id AS course_public_id, c.code AS course_code, "
                "c.name AS course_name, c.status AS course_status, "
                "g.public_id AS group_public_id, "
                "g.public_name AS group_public_name, c.sort_order "
                "FROM staff_scopes AS s "
                "JOIN courses AS c ON c.id = s.course_id "
                "JOIN users AS u ON u.id = s.staff_user_id "
                "JOIN auth_accounts AS a ON a.linked_user_id = s.staff_user_id "
                "AND a.audience = 'staff' AND a.status = 'active' "
                "LEFT JOIN groups AS g ON g.course_id = s.course_id "
                "AND g.group_id = s.group_id "
                "WHERE s.staff_user_id = ? AND u.type IN (?, ?) "
                "AND u.public_id IS NOT NULL "
                "ORDER BY c.sort_order, c.id, s.group_id, s.role, s.id",
                (
                    staff_user_id,
                    int(USER_TYPE.TEACHER),
                    int(USER_TYPE.ADMIN),
                ),
            ).fetchall()
            scopes: list[StaffScopeRecord] = []
            for row in rows:
                valid_from = _parse_timestamp(row["valid_from"])
                valid_to = _parse_optional_timestamp(row["valid_to"])
                if valid_from > now or (valid_to is not None and valid_to <= now):
                    continue
                group_id = _optional_string(row["group_id"])
                group_public_id = _optional_string(row["group_public_id"])
                if group_id is not None and group_public_id is None:
                    # ``None`` is the course-wide scope sentinel in the
                    # permission layer. A legacy/corrupt group scope without
                    # its browser-safe public ID must never be widened into
                    # course-wide authority.
                    raise PrincipalDataIntegrityError(
                        "Group-scoped staff access has no authoritative public ID"
                    )
                if group_public_id is not None:
                    group_public_id = _stored_public_id(
                        group_public_id, label="Group public ID"
                    )
                scopes.append(
                    StaffScopeRecord(
                        id=int(row["id"]),
                        staff_user_id=int(row["staff_user_id"]),
                        course_id=int(row["course_id"]),
                        course_public_id=_stored_public_id(
                            row["course_public_id"], label="Course public ID"
                        ),
                        course_code=str(row["course_code"]),
                        course_name=str(row["course_name"]),
                        course_status=str(row["course_status"]),
                        group_id=group_id,
                        group_public_id=group_public_id,
                        group_public_name=_optional_string(row["group_public_name"]),
                        role=StaffScopeRole(str(row["role"])),
                        valid_from=valid_from,
                        valid_to=valid_to,
                        version=int(row["version"]),
                    )
                )
            return tuple(scopes)

        return await self._factory.run_read_async(read)


def _unique_throttle_keys(
    keys: Iterable[ThrottleBucketKey],
) -> tuple[ThrottleBucketKey, ...]:
    unique: dict[tuple[str, str, str, int], ThrottleBucketKey] = {}
    for key in keys:
        identity = (
            key.audience.value,
            key.kind.value,
            key.digest,
            key.key_version,
        )
        unique.setdefault(identity, key)
    return tuple(unique.values())


def _retry_after_seconds(locked_until: datetime | None, now: datetime) -> int:
    if locked_until is None or locked_until <= now:
        return 0
    return math.ceil((locked_until - now).total_seconds())


def _throttle_state_from_row(
    key: ThrottleBucketKey,
    row: Mapping[str, object],
    now: datetime,
    policy: ThrottlePolicy | None = None,
) -> ThrottleState:
    locked_until = _parse_optional_timestamp(row["locked_until"])
    effective_failure_count = int(row["failure_count"])
    if policy is not None:
        window_started_at = _parse_timestamp(row["window_started_at"])
        if now >= window_started_at + policy.window and (
            locked_until is None or locked_until <= now
        ):
            effective_failure_count = 0
            locked_until = None
    return ThrottleState(
        key=key,
        failure_count=effective_failure_count,
        locked_until=locked_until,
        retry_after_seconds=_retry_after_seconds(locked_until, now),
    )


__all__ = [
    "AccountStateConflict",
    "AccountUnavailableError",
    "AuthAccountCredential",
    "AuthEventType",
    "AuthRepositoryError",
    "AuthSessionRecord",
    "CourseEnrollmentRecord",
    "CourseGroupAccessRecord",
    "CredentialChangeResult",
    "CurrentAuthSession",
    "FamilyChildRecord",
    "PrincipalDataIntegrityError",
    "PwaAuthRepository",
    "RefreshRotationOutcome",
    "RefreshRotationResult",
    "SessionRevokeReason",
    "StaffScopeRecord",
    "StaffScopeRole",
    "ThrottleBucketKey",
    "ThrottleBucketKind",
    "ThrottlePolicy",
    "ThrottleState",
    "make_throttle_bucket_key",
]
