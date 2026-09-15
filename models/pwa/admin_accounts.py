"""Small domain rules for Staff-managed Student and Family accounts.

The storage module only applies already validated state.  Credential text is
normalized here and is never returned by an API or written to an audit event.
See Phase 10 in ``vmshpwa/dev/development-plan/14-phase-10-admin-and-google-exit.md``.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from models.pwa.auth import (
    AuthAudience,
    legacy_telegram_token_risk_shapes,
    normalize_login,
    normalize_student_login,
    normalize_telegram_token,
)


class ManagedAccountStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class InvalidManagedAccountChange(ValueError):
    pass


def prepare_replacement_credential(audience: AuthAudience, raw_credential: str) -> str:
    """Validate one admin-entered replacement without retaining a second form."""

    if audience is AuthAudience.STUDENT:
        credential = normalize_telegram_token(raw_credential)
        if not credential or legacy_telegram_token_risk_shapes(credential, None):
            raise InvalidManagedAccountChange("unsafe_student_credential")
        return credential
    if audience is AuthAudience.FAMILY:
        if not 8 <= len(raw_credential) <= 256 or not raw_credential.strip():
            raise InvalidManagedAccountChange("unsafe_family_credential")
        return raw_credential
    raise InvalidManagedAccountChange("unsupported_audience")


def validate_status_change(
    *,
    current: ManagedAccountStatus,
    requested: ManagedAccountStatus,
    has_credential: bool,
) -> bool:
    """Return whether storage must change, rejecting activation without a secret."""

    if requested is ManagedAccountStatus.ACTIVE and not has_credential:
        raise InvalidManagedAccountChange("missing_credential")
    return current is not requested


def prepare_family_link_identity(
    *, username: str, relationship_label: str
) -> tuple[str, str, str]:
    """Normalize a Family login and one child relationship label."""

    stored_username = " ".join(unicodedata.normalize("NFKC", username).strip().split())
    normalized_username = normalize_login(stored_username)
    stored_relationship = " ".join(
        unicodedata.normalize("NFKC", relationship_label).strip().split()
    )
    if not 1 <= len(stored_username) <= 100 or not normalized_username:
        raise InvalidManagedAccountChange("invalid_family_username")
    if not 1 <= len(stored_relationship) <= 100:
        raise InvalidManagedAccountChange("invalid_family_relationship")
    return stored_username, normalized_username, stored_relationship


def prepare_family_identity(
    *, username: str, display_name: str, relationship_label: str
) -> tuple[str, str, str, str]:
    """Normalize the non-secret fields used to create a Family account."""

    stored_username, normalized_username, stored_relationship = (
        prepare_family_link_identity(
            username=username, relationship_label=relationship_label
        )
    )
    stored_display_name = " ".join(
        unicodedata.normalize("NFKC", display_name).strip().split()
    )
    if not 1 <= len(stored_display_name) <= 200:
        raise InvalidManagedAccountChange("invalid_family_display_name")
    return (
        stored_username,
        normalized_username,
        stored_display_name,
        stored_relationship,
    )


def prepare_student_identity(
    *, username: str, telegram_token: str, chat_id: object
) -> tuple[str, str, str]:
    """Validate a Staff-selected login against the Student's current bot token."""

    stored_username = " ".join(unicodedata.normalize("NFKC", username).strip().split())
    normalized_username = normalize_student_login(stored_username)
    if not 1 <= len(stored_username) <= 100 or not normalized_username:
        raise InvalidManagedAccountChange("invalid_student_username")
    credential = normalize_telegram_token(telegram_token)
    if not credential or legacy_telegram_token_risk_shapes(credential, chat_id):
        raise InvalidManagedAccountChange("unsafe_student_credential")
    return stored_username, normalized_username, credential


__all__ = [
    "InvalidManagedAccountChange",
    "ManagedAccountStatus",
    "prepare_family_identity",
    "prepare_family_link_identity",
    "prepare_replacement_credential",
    "prepare_student_identity",
    "validate_status_change",
]
