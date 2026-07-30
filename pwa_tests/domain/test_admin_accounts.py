from __future__ import annotations

import pytest

from models.pwa.admin_accounts import (
    InvalidManagedAccountChange,
    ManagedAccountStatus,
    prepare_replacement_credential,
    validate_status_change,
)
from models.pwa.auth import AuthAudience


def test_student_replacement_uses_legacy_token_normalization() -> None:
    assert (
        prepare_replacement_credential(AuthAudience.STUDENT, "  Уnique-Token-2026  ")
        == "ynique-token-2026"
    )


@pytest.mark.parametrize("credential", ["", "123456", "password", "aaaaaaaa"])
def test_student_replacement_rejects_unsafe_token_shapes(credential: str) -> None:
    with pytest.raises(InvalidManagedAccountChange, match="unsafe_student_credential"):
        prepare_replacement_credential(AuthAudience.STUDENT, credential)


def test_family_password_is_exact_and_bounded() -> None:
    assert (
        prepare_replacement_credential(AuthAudience.FAMILY, " family passphrase ")
        == " family passphrase "
    )
    with pytest.raises(InvalidManagedAccountChange, match="unsafe_family_credential"):
        prepare_replacement_credential(AuthAudience.FAMILY, "short")


def test_account_cannot_be_activated_without_a_credential() -> None:
    with pytest.raises(InvalidManagedAccountChange, match="missing_credential"):
        validate_status_change(
            current=ManagedAccountStatus.DISABLED,
            requested=ManagedAccountStatus.ACTIVE,
            has_credential=False,
        )
    assert not validate_status_change(
        current=ManagedAccountStatus.ACTIVE,
        requested=ManagedAccountStatus.ACTIVE,
        has_credential=True,
    )
    assert validate_status_change(
        current=ManagedAccountStatus.ACTIVE,
        requested=ManagedAccountStatus.BLOCKED,
        has_credential=True,
    )
