"""Authentication orchestration over the shared SQLite repository.

This module owns credential verification, throttle composition, session token
rotation and construction of a server-authoritative principal. It has no
aiohttp dependency, which keeps security transitions executable in focused
unit/integration tests. Governing decisions: ADR 0003 and Phase 1 in
``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from db_methods.pwa.auth import (
    AccountStateConflict,
    AccountUnavailableError,
    AuthAccountCredential,
    AuthEventType,
    AuthSessionRecord,
    CourseEnrollmentRecord,
    CurrentAuthSession,
    FamilyChildRecord,
    PrincipalDataIntegrityError,
    PwaAuthRepository,
    RefreshRotationOutcome,
    RevokedSessionTarget,
    SessionRevokeReason,
    StaffScopeRecord,
    ThrottleBucketKind,
    ThrottleState,
    make_throttle_bucket_key,
)
from helpers.pwa.auth_config import AuthRuntimeConfig
from helpers.pwa.permissions import (
    AuthorizationPrincipal,
    PrincipalIntegrityError,
    build_authorization_principal,
    enrollment_grant_from_record,
    staff_scope_grant_from_record,
)
from models.pwa.auth import (
    AuthAudience,
    AuthPrincipal,
    CredentialHasher,
    SessionTokenPair,
    create_session_token_pair,
    hash_refresh_secret,
    next_session_expiry,
    normalize_login,
    normalize_student_login,
    normalize_telegram_token,
    parse_refresh_cookie,
)


SUPPORT_EMAIL = "vmsh@179.ru"
_MAX_SESSION_ID_ATTEMPTS = 3
_UA_RULES = (
    (re.compile(r"Edg(?:A|iOS)?/", re.IGNORECASE), "Edge"),
    (re.compile(r"(?:Firefox|FxiOS)/", re.IGNORECASE), "Firefox"),
    (re.compile(r"(?:Chrome|CriOS)/", re.IGNORECASE), "Chrome"),
    (re.compile(r"Safari/", re.IGNORECASE), "Safari"),
)


class AuthFailureCode(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_UNAVAILABLE = "account_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_REQUIRED = "authentication_required"
    SESSION_EXPIRED = "session_expired"
    SESSION_REVOKED = "session_revoked"


class AuthServiceError(RuntimeError):
    """Expected secret-free auth failure mapped by the HTTP adapter."""

    def __init__(
        self,
        code: AuthFailureCode,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """One fully revalidated session and its API projection inputs."""

    current: CurrentAuthSession
    principal: AuthorizationPrincipal
    family_children: tuple[FamilyChildRecord, ...] = ()
    course_enrollments: tuple[CourseEnrollmentRecord, ...] = ()
    staff_scopes: tuple[StaffScopeRecord, ...] = ()
    access_expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class IssuedSession:
    authenticated: AuthenticatedSession
    access_cookie_value: str
    refresh_cookie_value: str
    access_expires_at: datetime


def coarse_ip_prefix(client_address: str) -> str:
    """Return a privacy-bounded prefix suitable for audit/throttle buckets.

    IPv4 /24 and IPv6 /64 avoid retaining a full client address and make IPv6
    privacy-address rotation less useful for bypassing the SQLite throttle.
    nginx still enforces its independent per-source limit (ADR 0003).
    """

    address = ipaddress.ip_address(client_address)
    prefix_length = 24 if address.version == 4 else 64
    return ipaddress.ip_network(
        f"{address}/{prefix_length}", strict=False
    ).with_prefixlen


def user_agent_family(raw_user_agent: str | None) -> str | None:
    """Keep only a coarse browser/platform label, never the raw UA string."""

    if not raw_user_agent:
        return None
    browser = next(
        (label for pattern, label in _UA_RULES if pattern.search(raw_user_agent)),
        "Браузер",
    )
    if re.search(r"iPhone|iPad|iPod", raw_user_agent, re.IGNORECASE):
        platform = "iOS"
    elif re.search(r"Android", raw_user_agent, re.IGNORECASE):
        platform = "Android"
    elif re.search(r"Macintosh|Mac OS X", raw_user_agent, re.IGNORECASE):
        platform = "macOS"
    elif re.search(r"Windows", raw_user_agent, re.IGNORECASE):
        platform = "Windows"
    elif re.search(r"Linux", raw_user_agent, re.IGNORECASE):
        platform = "Linux"
    else:
        platform = None
    return browser if platform is None else f"{browser} · {platform}"


class PwaAuthService:
    """Fail-closed auth/session service shared by all audience routes."""

    def __init__(
        self,
        repository: PwaAuthRepository,
        runtime_config: AuthRuntimeConfig,
        *,
        credential_hasher: CredentialHasher,
        dummy_credential_hash: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.runtime_config = runtime_config
        self.credential_hasher = credential_hasher
        self._dummy_credential_hash = dummy_credential_hash
        self._clock = clock or (lambda: datetime.now(UTC))
        self._access_codec = runtime_config.access_codec()

    @classmethod
    async def create(
        cls,
        repository: PwaAuthRepository,
        runtime_config: AuthRuntimeConfig,
        *,
        credential_hasher: CredentialHasher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> "PwaAuthService":
        hasher = credential_hasher or CredentialHasher()
        # Argon2 belongs off the event loop even at startup. The synthetic input
        # is process-local timing camouflage and is never accepted by an account.
        dummy_hash = await asyncio.to_thread(
            hasher.hash,
            "vmsh-pwa-dummy-credential-never-valid",
        )
        return cls(
            repository,
            runtime_config,
            credential_hasher=hasher,
            dummy_credential_hash=dummy_hash,
            clock=clock,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Auth service clock must be timezone-aware")
        return value.astimezone(UTC)

    def _throttle_key(self, audience, kind, value):
        return make_throttle_bucket_key(
            audience=audience,
            kind=kind,
            value=value,
            pepper=self.runtime_config.throttle_pepper,
        )

    async def login(
        self,
        *,
        audience: AuthAudience,
        username: str,
        credential: str,
        request_id: str,
        client_address: str,
        device_label: str | None = None,
        raw_user_agent: str | None = None,
    ) -> IssuedSession:
        normalized_login = (
            normalize_student_login(username)
            if audience is AuthAudience.STUDENT
            else normalize_login(username)
        )
        ip_prefix = coarse_ip_prefix(client_address)
        login_key = self._throttle_key(
            audience,
            ThrottleBucketKind.NORMALIZED_LOGIN,
            normalized_login or "<empty>",
        )
        ip_key = self._throttle_key(audience, ThrottleBucketKind.IP, ip_prefix)

        try:
            account = await self.repository.find_account_for_login(
                audience,
                normalized_login,
            )
        except AccountUnavailableError:
            # Corrupt/ineligible provisioned identities have the same public
            # shape and one Argon verification as an unknown username.
            account = None

        account_key = (
            self._throttle_key(
                audience,
                ThrottleBucketKind.ACCOUNT,
                account.public_id,
            )
            if account is not None
            else None
        )
        keys = tuple(key for key in (login_key, account_key, ip_key) if key is not None)
        existing_throttle = await self.repository.check_throttle(keys)
        self._raise_if_locked(existing_throttle)

        normalized_credential = (
            normalize_telegram_token(credential)
            if audience is AuthAudience.STUDENT
            else credential
        )
        expected_kind = (
            "telegram_token" if audience is AuthAudience.STUDENT else "password"
        )
        account_hash_is_verifiable = (
            account is not None
            and account.credential_kind == expected_kind
            and self.credential_hasher.is_verifiable_hash(account.credential_hash)
        )
        selected_hash = (
            account.credential_hash
            if account_hash_is_verifiable
            else self._dummy_credential_hash
        )
        verification = await asyncio.to_thread(
            self.credential_hasher.verify,
            selected_hash,
            normalized_credential,
        )
        if (
            account is None
            or account.credential_kind != expected_kind
            or not account_hash_is_verifiable
            or not verification.valid
        ):
            failed_states = await self.repository.record_throttle_failure(keys)
            await self.repository.record_auth_event(
                event_type=AuthEventType.LOGIN_FAILED,
                request_id=request_id,
                account_id=None if account is None else account.id,
                ip_prefix=ip_prefix,
            )
            # The threshold-triggering attempt gets the same 429 for known and
            # unknown accounts because login/IP buckets exist in both paths.
            self._raise_if_locked(failed_states)
            raise AuthServiceError(AuthFailureCode.INVALID_CREDENTIALS)

        issued = await self._create_verified_session(
            account=account,
            replacement_credential_hash=verification.replacement_hash,
            request_id=request_id,
            ip_prefix=ip_prefix,
            device_label=device_label,
            raw_user_agent=raw_user_agent,
        )
        await self.repository.clear_throttle(
            tuple(key for key in (login_key, account_key) if key is not None)
        )
        return issued

    async def authenticate_access(
        self,
        *,
        audience: AuthAudience,
        access_cookie_value: str | None,
        request_id: str,
        client_address: str,
    ) -> AuthenticatedSession | None:
        if not access_cookie_value:
            return None
        loaded = self._access_codec.loads_with_timestamp(
            access_cookie_value,
            audience,
        )
        if loaded is None:
            return None
        claims, signed_at = loaded
        current = await self.repository.get_current_session(
            audience=audience,
            account_public_id=str(claims["aid"]),
            session_public_id=str(claims["sid"]),
            credential_version=int(claims["cv"]),
            session_version=int(claims["sv"]),
        )
        if current is None:
            return None
        try:
            return await self._build_authenticated_session(
                current,
                access_expires_at=min(
                    signed_at
                    + timedelta(seconds=self.runtime_config.access_ttl_seconds),
                    current.session.expires_at,
                ),
            )
        except PrincipalDataIntegrityError, PrincipalIntegrityError:
            # Corrupt grants must not remain usable through another worker.
            await self.repository.revoke_session(
                account_id=current.session.account_id,
                session_public_id=current.session.public_id,
                reason=SessionRevokeReason.ACCOUNT_UNAVAILABLE,
                request_id=request_id,
                ip_prefix=coarse_ip_prefix(client_address),
            )
            return None

    async def is_websocket_session_active(
        self,
        *,
        audience: AuthAudience,
        account_public_id: str,
        session_public_id: str,
    ) -> bool:
        """Revalidate a socket identity against current SQLite authority.

        The identity is captured only after a valid access cookie and exact
        browser Origin pass the upgrade boundary.  Current versions are read
        afresh on every pass; the complete principal is then rebuilt so an
        inactive account, changed credential, revoked/expired session or
        corrupt grant closes the socket.  Storage failures propagate to the
        registry, whose policy is fail-closed.
        """

        versions = await self.repository.get_session_authority_versions(
            audience=audience,
            account_public_id=account_public_id,
            session_public_id=session_public_id,
        )
        if versions is None:
            return False
        credential_version, session_version = versions
        current = await self.repository.get_current_session(
            audience=audience,
            account_public_id=account_public_id,
            session_public_id=session_public_id,
            credential_version=credential_version,
            session_version=session_version,
        )
        if current is None:
            return False
        try:
            await self._build_authenticated_session(current)
        except PrincipalDataIntegrityError, PrincipalIntegrityError:
            return False
        return True

    async def refresh(
        self,
        *,
        audience: AuthAudience,
        refresh_cookie_value: str | None,
        request_id: str,
        client_address: str,
    ) -> IssuedSession:
        presented = parse_refresh_cookie(refresh_cookie_value)
        if presented is None:
            raise AuthServiceError(AuthFailureCode.AUTHENTICATION_REQUIRED)
        replacement = SessionTokenPair(
            public_id=presented.public_id,
            raw_refresh_secret=secrets.token_urlsafe(32),
        )
        ip_prefix = coarse_ip_prefix(client_address)
        rotated = await self.repository.rotate_refresh_secret(
            audience=audience,
            session_public_id=presented.public_id,
            presented_secret_hash=hash_refresh_secret(
                presented.raw_refresh_secret,
                self.runtime_config.refresh_pepper,
            ),
            replacement_secret_hash=hash_refresh_secret(
                replacement.raw_refresh_secret,
                self.runtime_config.refresh_pepper,
            ),
            request_id=request_id,
            ip_prefix=ip_prefix,
        )
        if rotated.outcome is not RefreshRotationOutcome.ROTATED:
            raise AuthServiceError(self._refresh_failure_code(rotated.outcome))
        if rotated.session is None or rotated.account_public_id is None:
            raise RuntimeError("Rotated refresh result has no authoritative identity")
        current = await self.repository.get_current_session(
            audience=audience,
            account_public_id=rotated.account_public_id,
            session_public_id=rotated.session.public_id,
            credential_version=rotated.session.credential_version,
            session_version=rotated.session.version,
        )
        if current is None:
            raise AuthServiceError(AuthFailureCode.SESSION_REVOKED)
        try:
            authenticated = await self._build_authenticated_session(current)
        except (PrincipalDataIntegrityError, PrincipalIntegrityError) as error:
            # Rotation already changed the single-use refresh secret. Revoke
            # the now-corrupt lineage in the same request instead of leaving a
            # valid but unusable session for another worker to rediscover.
            await self.repository.revoke_session(
                account_id=current.session.account_id,
                session_public_id=current.session.public_id,
                reason=SessionRevokeReason.ACCOUNT_UNAVAILABLE,
                request_id=request_id,
                ip_prefix=ip_prefix,
            )
            raise AuthServiceError(AuthFailureCode.ACCOUNT_UNAVAILABLE) from error
        return self._issue(authenticated, replacement)

    async def logout_by_refresh(
        self,
        *,
        audience: AuthAudience,
        refresh_cookie_value: str | None,
        request_id: str,
        client_address: str,
    ) -> RevokedSessionTarget | None:
        presented = parse_refresh_cookie(refresh_cookie_value)
        if presented is None:
            return None
        return await self.repository.revoke_session_with_refresh_secret(
            audience=audience,
            session_public_id=presented.public_id,
            presented_secret_hash=hash_refresh_secret(
                presented.raw_refresh_secret,
                self.runtime_config.refresh_pepper,
            ),
            request_id=request_id,
            ip_prefix=coarse_ip_prefix(client_address),
        )

    async def list_active_sessions(
        self,
        authenticated: AuthenticatedSession,
    ) -> tuple[AuthSessionRecord, ...]:
        sessions = await self.repository.list_sessions(
            account_id=authenticated.current.session.account_id,
            include_revoked=False,
        )
        now = self._now()
        active = tuple(session for session in sessions if session.active_at(now))
        if authenticated.current.session.public_id not in {
            session.public_id for session in active
        }:
            raise AuthServiceError(AuthFailureCode.SESSION_REVOKED)
        return active

    async def revoke_session(
        self,
        authenticated: AuthenticatedSession,
        *,
        session_public_id: str,
        request_id: str,
        client_address: str,
    ) -> bool:
        return await self.repository.revoke_session(
            account_id=authenticated.current.session.account_id,
            session_public_id=session_public_id,
            reason=SessionRevokeReason.MANUAL,
            request_id=request_id,
            ip_prefix=coarse_ip_prefix(client_address),
        )

    async def logout_all(
        self,
        authenticated: AuthenticatedSession,
        *,
        request_id: str,
        client_address: str,
    ) -> int:
        return await self.repository.revoke_all_sessions(
            account_id=authenticated.current.session.account_id,
            reason=SessionRevokeReason.LOGOUT_ALL,
            request_id=request_id,
            ip_prefix=coarse_ip_prefix(client_address),
        )

    async def _create_verified_session(
        self,
        *,
        account: AuthAccountCredential,
        replacement_credential_hash: str | None,
        request_id: str,
        ip_prefix: str,
        device_label: str | None,
        raw_user_agent: str | None,
    ) -> IssuedSession:
        session_expiry = next_session_expiry(self._now())
        for attempt in range(_MAX_SESSION_ID_ATTEMPTS):
            pair = create_session_token_pair()
            try:
                session = await self.repository.create_session(
                    verified_account=account,
                    session_public_id=pair.public_id,
                    refresh_secret_hash=hash_refresh_secret(
                        pair.raw_refresh_secret,
                        self.runtime_config.refresh_pepper,
                    ),
                    expires_at=session_expiry,
                    request_id=request_id,
                    replacement_credential_hash=replacement_credential_hash,
                    device_label=device_label,
                    user_agent_family=user_agent_family(raw_user_agent),
                    ip_prefix=ip_prefix,
                )
                break
            except AccountStateConflict:
                # Identity/credential drift is not a token collision and must
                # not be retried with a now-stale verified snapshot.
                raise AuthServiceError(AuthFailureCode.ACCOUNT_UNAVAILABLE) from None
            except AccountUnavailableError:
                raise AuthServiceError(AuthFailureCode.ACCOUNT_UNAVAILABLE) from None
            except Exception as error:
                # Public-id/digest collisions are cryptographically negligible.
                # Retry only SQLite uniqueness failures without widening the
                # repository API to expose database exception details.
                if (
                    "UNIQUE constraint failed" not in str(error)
                    or attempt + 1 == _MAX_SESSION_ID_ATTEMPTS
                ):
                    raise
        else:  # pragma: no cover - loop either returns or raises
            raise RuntimeError("Session identifier generation exhausted")

        current = await self.repository.get_current_session(
            audience=account.audience,
            account_public_id=account.public_id,
            session_public_id=session.public_id,
            credential_version=session.credential_version,
            session_version=session.version,
        )
        if current is None:
            raise AuthServiceError(AuthFailureCode.ACCOUNT_UNAVAILABLE)
        try:
            authenticated = await self._build_authenticated_session(current)
        except (PrincipalDataIntegrityError, PrincipalIntegrityError) as error:
            await self.repository.revoke_session(
                account_id=session.account_id,
                session_public_id=session.public_id,
                reason=SessionRevokeReason.ACCOUNT_UNAVAILABLE,
                request_id=request_id,
                ip_prefix=ip_prefix,
            )
            raise AuthServiceError(AuthFailureCode.ACCOUNT_UNAVAILABLE) from error
        return self._issue(authenticated, pair)

    async def _build_authenticated_session(
        self,
        current: CurrentAuthSession,
        *,
        access_expires_at: datetime | None = None,
    ) -> AuthenticatedSession:
        family_children: tuple[FamilyChildRecord, ...] = ()
        enrollments: list[CourseEnrollmentRecord] = []
        staff_scopes: tuple[StaffScopeRecord, ...] = ()
        enrollment_grants = []
        staff_scope_grants = []

        if current.session.audience is AuthAudience.STUDENT:
            assert current.linked_user_id is not None
            student_enrollments = await self.repository.list_course_enrollments(
                student_user_id=current.linked_user_id,
            )
            enrollments.extend(student_enrollments)
            enrollment_grants.extend(
                enrollment_grant_from_record(
                    student_user_id=current.linked_user_id,
                    record=record,
                )
                for record in student_enrollments
            )
            family_child_ids: tuple[int, ...] = ()
        elif current.session.audience is AuthAudience.FAMILY:
            family_children = await self.repository.list_family_children(
                family_account_id=current.session.account_id,
            )
            family_child_ids = tuple(child.student_user_id for child in family_children)
            for child in family_children:
                child_enrollments = await self.repository.list_course_enrollments(
                    student_user_id=child.student_user_id,
                )
                enrollments.extend(child_enrollments)
                enrollment_grants.extend(
                    enrollment_grant_from_record(
                        student_user_id=child.student_user_id,
                        record=record,
                    )
                    for record in child_enrollments
                )
        else:
            assert current.linked_user_id is not None
            family_child_ids = ()
            staff_scopes = await self.repository.list_staff_scopes(
                staff_user_id=current.linked_user_id,
            )
            staff_scope_grants.extend(
                staff_scope_grant_from_record(record) for record in staff_scopes
            )

        principal = build_authorization_principal(
            account_public_id=current.account_public_id,
            session_public_id=current.session.public_id,
            session_version=current.session.version,
            credential_version=current.session.credential_version,
            audience=current.session.audience,
            linked_user_id=current.linked_user_id,
            linked_user_type=current.linked_user_type,
            family_child_user_ids=family_child_ids,
            enrollment_grants=enrollment_grants,
            staff_scope_grants=staff_scope_grants,
        )
        return AuthenticatedSession(
            current=current,
            principal=principal,
            family_children=family_children,
            course_enrollments=tuple(enrollments),
            staff_scopes=staff_scopes,
            access_expires_at=access_expires_at,
        )

    def _issue(
        self,
        authenticated: AuthenticatedSession,
        refresh_pair: SessionTokenPair,
    ) -> IssuedSession:
        session = authenticated.current.session
        signed_principal = AuthPrincipal(
            account_public_id=authenticated.principal.account_public_id,
            session_public_id=authenticated.principal.session_public_id,
            audience=authenticated.principal.audience,
            linked_user_id=authenticated.principal.linked_user_id,
            role=authenticated.principal.role.value,
            capabilities=frozenset(authenticated.principal.capability_names),
            credential_version=authenticated.principal.credential_version,
            session_version=authenticated.principal.session_version,
        )
        access_expires_at = min(
            self._now() + timedelta(seconds=self.runtime_config.access_ttl_seconds),
            session.expires_at,
        )
        return IssuedSession(
            authenticated=authenticated,
            access_cookie_value=self._access_codec.dumps(signed_principal),
            refresh_cookie_value=refresh_pair.cookie_value,
            access_expires_at=access_expires_at,
        )

    @staticmethod
    def _raise_if_locked(states: tuple[ThrottleState, ...]) -> None:
        retry_after = max(
            (state.retry_after_seconds for state in states),
            default=0,
        )
        if retry_after > 0:
            raise AuthServiceError(
                AuthFailureCode.RATE_LIMITED,
                retry_after_seconds=retry_after,
            )

    @staticmethod
    def _refresh_failure_code(outcome: RefreshRotationOutcome) -> AuthFailureCode:
        if outcome is RefreshRotationOutcome.EXPIRED:
            return AuthFailureCode.SESSION_EXPIRED
        if outcome in {
            RefreshRotationOutcome.INACTIVE,
            RefreshRotationOutcome.ACCOUNT_UNAVAILABLE,
            RefreshRotationOutcome.CREDENTIAL_CHANGED,
            RefreshRotationOutcome.REPLAY_REVOKED,
        }:
            return AuthFailureCode.SESSION_REVOKED
        return AuthFailureCode.AUTHENTICATION_REQUIRED


__all__ = [
    "AuthenticatedSession",
    "AuthFailureCode",
    "AuthServiceError",
    "IssuedSession",
    "PwaAuthService",
    "SUPPORT_EMAIL",
    "coarse_ip_prefix",
    "user_agent_family",
]
