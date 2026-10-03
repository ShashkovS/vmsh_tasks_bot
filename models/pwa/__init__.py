"""Pure domain models used by the PWA adapters."""

from .auth import (
    ACCESS_TOKEN_VERSION,
    STUDENT_USERNAME_ALGORITHM_VERSION,
    AccessTokenCodec,
    AuthAudience,
    AuthPrincipal,
    CredentialHasher,
    CredentialVerification,
    SessionTokenPair,
    build_student_username,
    create_session_token_pair,
    next_session_expiry,
    normalize_login,
    normalize_student_login,
    normalize_telegram_token,
)

__all__ = [
    "ACCESS_TOKEN_VERSION",
    "STUDENT_USERNAME_ALGORITHM_VERSION",
    "AccessTokenCodec",
    "AuthAudience",
    "AuthPrincipal",
    "CredentialHasher",
    "CredentialVerification",
    "SessionTokenPair",
    "build_student_username",
    "create_session_token_pair",
    "next_session_expiry",
    "normalize_login",
    "normalize_student_login",
    "normalize_telegram_token",
]
