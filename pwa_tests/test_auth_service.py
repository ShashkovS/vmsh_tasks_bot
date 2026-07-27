"""Focused service-boundary tests for Phase-1 HTTP authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from argon2 import PasswordHasher

from apps.pwa_api.auth_service import (
    AuthFailureCode,
    AuthServiceError,
    PwaAuthService,
)
from db_methods.pwa.auth import (
    AuthAccountCredential,
    AuthSessionRecord,
    CurrentAuthSession,
    PrincipalDataIntegrityError,
    RefreshRotationOutcome,
    RefreshRotationResult,
    RevokedSessionTarget,
    SessionRevokeReason,
)
from helpers.consts import USER_TYPE
from helpers.pwa.auth_config import AuthRuntimeConfig
from models.pwa.auth import (
    AuthAudience,
    AuthPrincipal,
    CredentialHasher,
    CredentialVerification,
    MAX_ARGON2_MEMORY_COST_KIB,
)


NOW = datetime.now(UTC).replace(microsecond=0)
SESSION_ID = "0123456789abcdef0123456789abcdef"


def _runtime_config() -> AuthRuntimeConfig:
    origins = MappingProxyType(
        {audience: frozenset({"http://127.0.0.1:5380"}) for audience in AuthAudience}
    )
    return AuthRuntimeConfig(
        origins_by_audience=origins,
        trusted_proxy_networks=(),
        trusted_proxy_hops=0,
        access_ttl_seconds=900,
        secure_cookies=False,
        signing_keys=("s" * 32,),
        refresh_pepper=b"r" * 32,
        throttle_pepper=b"t" * 32,
        test_only_defaults=True,
    )


def _session() -> AuthSessionRecord:
    return AuthSessionRecord(
        id=41,
        public_id=SESSION_ID,
        account_id=51,
        audience=AuthAudience.STUDENT,
        credential_version=1,
        version=2,
        created_at=NOW - timedelta(minutes=5),
        updated_at=NOW,
        last_seen_at=NOW,
        expires_at=NOW + timedelta(days=1),
        revoked_at=None,
        revoke_reason=None,
        device_label="Synthetic browser",
        user_agent_family="Fixture Browser",
        ip_prefix="127.0.0.0/24",
    )


def _current() -> CurrentAuthSession:
    return CurrentAuthSession(
        session=_session(),
        account_public_id="account-student",
        account_status="active",
        display_name="Синтетический ученик",
        linked_user_id=61,
        linked_user_public_id="user-student",
        linked_user_type=int(USER_TYPE.STUDENT),
    )


def _service(repository) -> PwaAuthService:
    hasher = CredentialHasher(
        PasswordHasher(
            time_cost=1,
            memory_cost=8,
            parallelism=1,
            hash_len=16,
            salt_len=8,
        )
    )
    return PwaAuthService(
        repository,
        _runtime_config(),
        credential_hasher=hasher,
        dummy_credential_hash=hasher.hash("synthetic-dummy"),
    )


def _access_cookie(service: PwaAuthService) -> str:
    return service.runtime_config.access_codec().dumps(
        AuthPrincipal(
            account_public_id="account-student",
            session_public_id=SESSION_ID,
            audience=AuthAudience.STUDENT,
            linked_user_id=61,
            role="student",
            capabilities=frozenset(),
            credential_version=1,
            session_version=2,
        )
    )


@pytest.mark.asyncio
async def test_access_corrupt_principal_revokes_with_real_request_audit_context():
    repository = SimpleNamespace(
        get_current_session=AsyncMock(return_value=_current()),
        list_course_enrollments=AsyncMock(
            side_effect=PrincipalDataIntegrityError("synthetic corrupt grant")
        ),
        revoke_session=AsyncMock(return_value=True),
    )
    service = _service(repository)

    authenticated = await service.authenticate_access(
        audience=AuthAudience.STUDENT,
        access_cookie_value=_access_cookie(service),
        request_id="request.access.corrupt",
        client_address="127.0.0.42",
    )

    assert authenticated is None
    repository.revoke_session.assert_awaited_once_with(
        account_id=51,
        session_public_id=SESSION_ID,
        reason=SessionRevokeReason.ACCOUNT_UNAVAILABLE,
        request_id="request.access.corrupt",
        ip_prefix="127.0.0.0/24",
    )


@pytest.mark.asyncio
async def test_access_cookie_audience_mismatch_never_reaches_repository():
    repository = SimpleNamespace(get_current_session=AsyncMock())
    service = _service(repository)

    authenticated = await service.authenticate_access(
        audience=AuthAudience.FAMILY,
        access_cookie_value=_access_cookie(service),
        request_id="request.audience.mismatch",
        client_address="127.0.0.42",
    )

    assert authenticated is None
    repository.get_current_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_corrupt_principal_revokes_rotated_lineage_and_fails_safely():
    session = _session()
    repository = SimpleNamespace(
        rotate_refresh_secret=AsyncMock(
            return_value=RefreshRotationResult(
                RefreshRotationOutcome.ROTATED,
                session,
                "account-student",
            )
        ),
        get_current_session=AsyncMock(return_value=_current()),
        list_course_enrollments=AsyncMock(
            side_effect=PrincipalDataIntegrityError("synthetic corrupt grant")
        ),
        revoke_session=AsyncMock(return_value=True),
    )
    service = _service(repository)

    with pytest.raises(AuthServiceError) as captured:
        await service.refresh(
            audience=AuthAudience.STUDENT,
            refresh_cookie_value=f"{SESSION_ID}.synthetic-refresh-secret",
            request_id="request.refresh.corrupt",
            client_address="127.0.0.42",
        )

    assert captured.value.code is AuthFailureCode.ACCOUNT_UNAVAILABLE
    repository.revoke_session.assert_awaited_once_with(
        account_id=51,
        session_public_id=SESSION_ID,
        reason=SessionRevokeReason.ACCOUNT_UNAVAILABLE,
        request_id="request.refresh.corrupt",
        ip_prefix="127.0.0.0/24",
    )


@pytest.mark.asyncio
async def test_logout_refresh_remains_uniform_for_missing_or_malformed_cookie():
    repository = SimpleNamespace(revoke_session_with_refresh_secret=AsyncMock())
    service = _service(repository)

    result = await service.logout_by_refresh(
        audience=AuthAudience.STUDENT,
        refresh_cookie_value="not-a-refresh-cookie",
        request_id="request.logout.uniform",
        client_address="127.0.0.42",
    )

    assert result is None
    repository.revoke_session_with_refresh_secret.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_refresh_returns_only_repository_verified_close_target():
    target = RevokedSessionTarget(
        audience=AuthAudience.STUDENT,
        account_public_id="account-student",
        session_public_id=SESSION_ID,
    )
    repository = SimpleNamespace(
        revoke_session_with_refresh_secret=AsyncMock(return_value=target)
    )
    service = _service(repository)

    result = await service.logout_by_refresh(
        audience=AuthAudience.STUDENT,
        refresh_cookie_value=f"{SESSION_ID}.synthetic-refresh-secret",
        request_id="request.logout.verified",
        client_address="127.0.0.42",
    )

    assert result is target


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account",
    [
        pytest.param(None, id="unknown-account"),
        pytest.param(
            AuthAccountCredential(
                id=71,
                public_id="account-malformed-hash",
                audience=AuthAudience.STUDENT,
                credential_kind="telegram_token",
                credential_hash="$argon2id$malformed-active-row",
                linked_user_id=81,
            ),
            id="malformed-active-hash",
        ),
    ],
)
async def test_unknown_and_malformed_hash_both_use_one_full_dummy_verification(
    account,
):
    class InstrumentedHasher:
        def __init__(self) -> None:
            self.verified_hashes: list[str] = []

        @staticmethod
        def is_verifiable_hash(encoded_hash: str | None) -> bool:
            return encoded_hash == "synthetic-valid-dummy-hash"

        def verify(
            self,
            encoded_hash: str | None,
            _credential: str,
        ) -> CredentialVerification:
            assert encoded_hash is not None
            self.verified_hashes.append(encoded_hash)
            return CredentialVerification(valid=False)

    repository = SimpleNamespace(
        find_account_for_login=AsyncMock(return_value=account),
        check_throttle=AsyncMock(return_value=()),
        record_throttle_failure=AsyncMock(return_value=()),
        record_auth_event=AsyncMock(return_value=None),
    )
    hasher = InstrumentedHasher()
    service = PwaAuthService(
        repository,
        _runtime_config(),
        credential_hasher=hasher,
        dummy_credential_hash="synthetic-valid-dummy-hash",
    )

    with pytest.raises(AuthServiceError) as captured:
        await service.login(
            audience=AuthAudience.STUDENT,
            username="known-or-unknown-14",
            credential="synthetic-wrong-token",
            request_id="request.login.uniform-hash-work",
            client_address="127.0.0.42",
        )

    assert captured.value.code is AuthFailureCode.INVALID_CREDENTIALS
    # This is deliberately an instrumented work-count assertion, not a noisy
    # wall-clock comparison: both paths select exactly one real dummy verify.
    assert hasher.verified_hashes == ["synthetic-valid-dummy-hash"]


def test_credential_hash_shape_requires_complete_argon2id_encoding():
    hasher = CredentialHasher(
        PasswordHasher(
            time_cost=1,
            memory_cost=8,
            parallelism=1,
            hash_len=16,
            salt_len=8,
        )
    )

    assert hasher.is_verifiable_hash(hasher.hash("complete-hash"))
    assert not hasher.is_verifiable_hash("$argon2id$prefix-only")
    assert not hasher.is_verifiable_hash("sha256-is-not-argon2")
    valid = hasher.hash("parameter-policy")
    assert not hasher.is_verifiable_hash(valid.replace("v=19", "v=999", 1))
    assert not hasher.is_verifiable_hash(valid.replace("t=1", "t=0", 1))


@pytest.mark.asyncio
async def test_out_of_policy_argon2_parameters_select_dummy_before_verify():
    policy_hasher = CredentialHasher(
        PasswordHasher(
            time_cost=1,
            memory_cost=8,
            parallelism=1,
            hash_len=16,
            salt_len=8,
        )
    )
    ordinary_hash = policy_hasher.hash("ordinary-account-secret")
    excessive_hash = ordinary_hash.replace(
        "m=8,",
        f"m={MAX_ARGON2_MEMORY_COST_KIB + 1},",
        1,
    )
    assert not policy_hasher.is_verifiable_hash(excessive_hash)

    class InstrumentedHasher:
        def __init__(self) -> None:
            self.verified_hashes: list[str] = []

        @staticmethod
        def is_verifiable_hash(encoded_hash: str | None) -> bool:
            return policy_hasher.is_verifiable_hash(encoded_hash)

        def verify(
            self,
            encoded_hash: str | None,
            _credential: str,
        ) -> CredentialVerification:
            assert encoded_hash is not None
            self.verified_hashes.append(encoded_hash)
            return CredentialVerification(valid=False)

    account = AuthAccountCredential(
        id=72,
        public_id="account-out-of-policy-hash",
        audience=AuthAudience.STUDENT,
        credential_kind="telegram_token",
        credential_hash=excessive_hash,
        linked_user_id=82,
    )
    repository = SimpleNamespace(
        find_account_for_login=AsyncMock(return_value=account),
        check_throttle=AsyncMock(return_value=()),
        record_throttle_failure=AsyncMock(return_value=()),
        record_auth_event=AsyncMock(return_value=None),
    )
    hasher = InstrumentedHasher()
    service = PwaAuthService(
        repository,
        _runtime_config(),
        credential_hasher=hasher,
        dummy_credential_hash="synthetic-valid-dummy-hash",
    )

    with pytest.raises(AuthServiceError):
        await service.login(
            audience=AuthAudience.STUDENT,
            username="out-of-policy-14",
            credential="synthetic-wrong-token",
            request_id="request.login.argon-policy",
            client_address="127.0.0.42",
        )

    assert hasher.verified_hashes == ["synthetic-valid-dummy-hash"]
