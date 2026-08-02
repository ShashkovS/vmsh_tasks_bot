from __future__ import annotations

import pytest

from models.pwa.admin_accounts import (
    InvalidManagedAccountChange,
    ManagedAccountStatus,
    prepare_family_identity,
    prepare_family_link_identity,
    prepare_replacement_credential,
    prepare_student_identity,
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


def test_student_account_creation_normalizes_login_and_current_bot_token() -> None:
    assert prepare_student_identity(
        username="  Petrov   07  ",
        telegram_token="  Уnique-Token-2026  ",
        chat_id=9001,
    ) == ("Petrov 07", "petrov 07", "ynique-token-2026")


def test_student_account_creation_rejects_unsafe_current_bot_token() -> None:
    with pytest.raises(InvalidManagedAccountChange, match="unsafe_student_credential"):
        prepare_student_identity(username="petrov-07", telegram_token="123456", chat_id=9001)


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


def test_family_identity_normalizes_only_non_secret_fields() -> None:
    assert prepare_family_identity(
        username="  Family   Ivanov  ",
        display_name="  Семья   Ивановых  ",
        relationship_label="  родитель  ",
    ) == (
        "Family Ivanov",
        "family ivanov",
        "Семья Ивановых",
        "родитель",
    )
    assert prepare_family_link_identity(
        username="ＦＡＭＩＬＹ Иванов", relationship_label=" мама "
    ) == ("FAMILY Иванов", "family иванов", "мама")


@pytest.mark.parametrize(
    ("field", "value"),
    [("username", " "), ("display_name", " "), ("relationship_label", " ")],
)
def test_family_identity_rejects_blank_required_fields(field: str, value: str) -> None:
    values = {
        "username": "family-login",
        "display_name": "Семья",
        "relationship_label": "родитель",
    }
    values[field] = value
    with pytest.raises(InvalidManagedAccountChange):
        prepare_family_identity(**values)
