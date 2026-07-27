from datetime import UTC, date, datetime

import pytest
from argon2 import PasswordHasher

from models.pwa.auth import (
    AccessTokenCodec,
    AuthAudience,
    AuthPrincipal,
    CredentialHasher,
    build_student_username,
    create_session_token_pair,
    hash_refresh_secret,
    legacy_telegram_token_risk_shapes,
    next_session_expiry,
    normalize_login,
    normalize_telegram_token,
    parse_refresh_cookie,
)


def _principal(audience: AuthAudience = AuthAudience.STUDENT) -> AuthPrincipal:
    return AuthPrincipal(
        account_public_id="account_public_test",
        session_public_id="0123456789abcdef0123456789abcdef",
        audience=audience,
        linked_user_id=101,
        role="student",
        capabilities=frozenset({"course.read"}),
        credential_version=3,
        session_version=2,
    )


def test_login_normalization_is_nfkc_trimmed_casefolded_and_space_stable():
    assert normalize_login("  ＶＭＳＨ   User  ") == "vmsh user"


@pytest.mark.parametrize(
    ("surname", "birthday", "expected"),
    [
        ("Шашков", date(2013, 3, 7), "shashkov-07"),
        ("Щербакова", date(2012, 10, 21), "shcherbakova-21"),
        ("Соловьёв", date(2011, 8, 10), "solovyov-10"),
        ("Де Ла-Крус", date(2010, 1, 2), "de-la-krus-02"),
    ],
)
def test_student_username_v1_is_deterministic(surname, birthday, expected):
    assert build_student_username(surname, birthday) == expected


def test_student_username_refuses_an_empty_transliterated_surname():
    with pytest.raises(ValueError, match="surname"):
        build_student_username("---", date(2013, 1, 1))


def test_telegram_token_normalization_matches_historical_homoglyph_behavior():
    assert normalize_telegram_token("  УКЕНХВАРОСМТ  ") == "ykehxbapocmt"


def test_legacy_telegram_token_risk_shapes_are_shared_aggregate_labels():
    assert legacy_telegram_token_risk_shapes("123456", 123456) == frozenset(
        {"shorterThan8", "digitsOnly", "commonPlaceholder", "sameAsChatId"}
    )
    assert legacy_telegram_token_risk_shapes("safeTokenA8", 123456) == frozenset()


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (
            datetime(2026, 8, 9, 20, 59, 59, tzinfo=UTC),
            datetime(2026, 8, 9, 21, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 8, 9, 21, 0, 0, tzinfo=UTC),
            datetime(2027, 8, 9, 21, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 9, 21, 0, 0, tzinfo=UTC),
        ),
    ],
)
def test_session_expiry_is_next_august_10_in_moscow(now, expected):
    assert next_session_expiry(now) == expected


def test_session_expiry_rejects_naive_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        next_session_expiry(datetime(2026, 1, 1))


def test_credential_hasher_verifies_and_rejects_without_leaking_reason():
    fast = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)
    credentials = CredentialHasher(fast)
    encoded = credentials.hash("synthetic-secret")

    assert credentials.verify(encoded, "synthetic-secret").valid
    assert not credentials.verify(encoded, "wrong-secret").valid
    assert not credentials.verify("not-an-argon2-hash", "synthetic-secret").valid
    assert not credentials.verify(None, "synthetic-secret").valid


def test_credential_hasher_returns_upgrade_hash_for_old_parameters():
    old = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)
    current = CredentialHasher(
        PasswordHasher(time_cost=2, memory_cost=8 * 1024, parallelism=1)
    )
    result = current.verify(old.hash("synthetic-secret"), "synthetic-secret")

    assert result.valid
    assert result.replacement_hash is not None
    assert current.verify(result.replacement_hash, "synthetic-secret").valid


def test_refresh_cookie_round_trip_and_hmac_is_peppered():
    pair = create_session_token_pair()
    parsed = parse_refresh_cookie(pair.cookie_value)

    assert parsed == pair
    assert len(pair.public_id) == 32
    assert set(pair.public_id) <= set("0123456789abcdef")
    assert hash_refresh_secret(
        pair.raw_refresh_secret, b"p" * 32
    ) != hash_refresh_secret(pair.raw_refresh_secret, b"q" * 32)
    assert pair.raw_refresh_secret not in hash_refresh_secret(
        pair.raw_refresh_secret, b"p" * 32
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "one-part",
        ".secret",
        "id.",
        "a.b.c",
        "0123456789ABCDEF0123456789ABCDEF.secret",
        "0123456789abcdef0123456789abcde.secret",
        "session_public_test.secret",
    ],
)
def test_refresh_cookie_rejects_malformed_values(value):
    assert parse_refresh_cookie(value) is None


def test_refresh_hash_requires_a_real_pepper():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        hash_refresh_secret("secret", b"short")


def test_access_cookie_is_audience_scoped_and_payload_is_strict():
    codec = AccessTokenCodec(["k" * 32])
    token = codec.dumps(_principal())

    assert codec.loads(token, AuthAudience.STUDENT) == {
        "v": 1,
        "sid": "0123456789abcdef0123456789abcdef",
        "aid": "account_public_test",
        "aud": "student",
        "cv": 3,
        "sv": 2,
    }
    assert codec.loads(token, AuthAudience.FAMILY) is None
    assert codec.loads(token + "tampered", AuthAudience.STUDENT) is None


def test_access_cookie_supports_old_key_verification_and_new_key_signing():
    old_codec = AccessTokenCodec(["o" * 32])
    rotated_codec = AccessTokenCodec(["o" * 32, "n" * 32])
    new_only_codec = AccessTokenCodec(["n" * 32])

    assert (
        rotated_codec.loads(old_codec.dumps(_principal()), AuthAudience.STUDENT)
        is not None
    )
    assert (
        new_only_codec.loads(rotated_codec.dumps(_principal()), AuthAudience.STUDENT)
        is not None
    )


def test_access_cookie_rejects_noncanonical_session_reference_before_signing():
    codec = AccessTokenCodec(["k" * 32])
    principal = _principal()
    invalid = AuthPrincipal(
        account_public_id=principal.account_public_id,
        session_public_id="session_public_test",
        audience=principal.audience,
        linked_user_id=principal.linked_user_id,
        role=principal.role,
        capabilities=principal.capabilities,
        credential_version=principal.credential_version,
        session_version=principal.session_version,
    )

    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        codec.dumps(invalid)


def test_access_cookie_rejects_a_valid_signature_with_noncanonical_session_id():
    codec = AccessTokenCodec(["k" * 32])
    # This represents a token emitted by an older or faulty deployment.  A
    # correct signature must not relax the canonical storage lookup boundary.
    token = codec._serializer(AuthAudience.STUDENT).dumps(
        {
            "v": 1,
            "sid": "session_public_test",
            "aid": "account_public_test",
            "aud": "student",
            "cv": 3,
            "sv": 2,
        }
    )

    assert codec.loads(token, AuthAudience.STUDENT) is None


def test_access_cookie_rejects_short_keys_and_non_positive_ttl():
    with pytest.raises(ValueError, match="32 bytes"):
        AccessTokenCodec(["short"])
    with pytest.raises(ValueError, match="positive"):
        AccessTokenCodec(["k" * 32], max_age_seconds=0)
