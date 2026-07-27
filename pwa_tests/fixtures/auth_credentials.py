"""Synthetic credentials available only to the PWA test/dev harness."""

from __future__ import annotations

from types import MappingProxyType


# These values match the committed Argon2id hashes in baseline-v1.json. The
# runtime seeder deliberately does not import this module: production code gets
# neither a plaintext credential map nor a mock-auth path. Every string is
# unmistakably synthetic and is verified by the focused seed test.
SYNTHETIC_AUTH_CREDENTIALS_V1 = MappingProxyType(
    {
        "account-student-fixture": "synthetic-telegram-token-not-a-secret",
        "account-student-in-person-fixture": (
            "synthetic-student-two-token-not-a-secret"
        ),
        "account-family-fixture": "synthetic-family-password-not-a-secret",
        "account-staff-fixture": "synthetic-staff-password-not-a-secret",
        "account-admin-fixture": "synthetic-admin-password-not-a-secret",
    }
)
