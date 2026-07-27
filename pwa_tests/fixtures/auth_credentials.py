"""Synthetic credentials available only to the PWA test/dev harness."""

from __future__ import annotations

from types import MappingProxyType

from pwa_tests.fixtures.seed import FIXTURES_ROOT, load_json_fixture


AUTH_CREDENTIALS_V1_PATH = FIXTURES_ROOT / "auth-credentials-v1.json"


def _load_synthetic_auth_credentials_v1() -> MappingProxyType[str, str]:
    """Load the single test-only credential source shared with browser E2E."""

    payload = load_json_fixture(AUTH_CREDENTIALS_V1_PATH)
    if (
        payload.get("fixture") != "synthetic-auth-credentials-v1"
        or payload.get("fixtureVersion") != 1
    ):
        raise ValueError("Unknown synthetic auth credential fixture")
    accounts = payload.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise ValueError("Synthetic auth credential fixture has no accounts")

    credentials: dict[str, str] = {}
    for account in accounts:
        if not isinstance(account, dict):
            raise ValueError("Synthetic auth credential account must be an object")
        public_id = account.get("accountPublicId")
        credential = account.get("credential")
        if (
            not isinstance(public_id, str)
            or not public_id
            or not isinstance(credential, str)
            or not credential.endswith("-not-a-secret")
            or public_id in credentials
        ):
            raise ValueError("Invalid synthetic auth credential account")
        credentials[public_id] = credential
    return MappingProxyType(credentials)


# The runtime seeder deliberately does not import this module: production code
# gets neither plaintext credentials nor a mock-auth path. Browser E2E imports
# the same JSON fixture directly; the focused seed test verifies every hash.
SYNTHETIC_AUTH_CREDENTIALS_V1 = _load_synthetic_auth_credentials_v1()
