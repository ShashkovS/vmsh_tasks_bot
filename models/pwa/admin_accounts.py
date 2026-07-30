"""Small domain rules for Staff-managed Student and Family accounts.

The storage module only applies already validated state.  Credential text is
normalized here and is never returned by an API or written to an audit event.
See Phase 10 in ``vmshpwa/dev/development-plan/14-phase-10-admin-and-google-exit.md``.
"""

from __future__ import annotations

from enum import StrEnum

from models.pwa.auth import (
    AuthAudience,
    legacy_telegram_token_risk_shapes,
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


__all__ = [
    "InvalidManagedAccountChange",
    "ManagedAccountStatus",
    "prepare_replacement_credential",
    "validate_status_change",
]
