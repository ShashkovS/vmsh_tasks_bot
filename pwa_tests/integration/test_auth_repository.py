"""Phase-1 authentication persistence and concurrency contracts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import (
    AccountStateConflict,
    AuthEventType,
    PwaAuthRepository,
    PrincipalDataIntegrityError,
    RefreshRotationOutcome,
    SessionRevokeReason,
    ThrottleBucketKind,
    ThrottlePolicy,
    make_throttle_bucket_key,
)
from models.pwa.auth import AuthAudience


START = datetime(2026, 7, 27, 8, tzinfo=UTC)
PEPPER = b"synthetic-phase-one-throttle-pepper!!"
_TEST_HASHER = PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)
STUDENT_HASH_V1 = _TEST_HASHER.hash("synthetic-student-v1")
STUDENT_HASH_REHASHED = _TEST_HASHER.hash("synthetic-student-rehashed")
STUDENT_TOKEN_V2 = "syntheticytoken"
STUDENT_HASH_V2 = _TEST_HASHER.hash(STUDENT_TOKEN_V2)
OTHER_VALID_HASH = _TEST_HASHER.hash("synthetic-other")
FAMILY_HASH_V1 = _TEST_HASHER.hash("synthetic-family-v1")
STAFF_HASH_V1 = _TEST_HASHER.hash("synthetic-staff-v1")


@dataclass
class MutableClock:
    value: datetime = START

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **parts: float) -> None:
        self.value += timedelta(**parts)


@dataclass(frozen=True)
class AuthFixture:
    database_path: object
    factory: PwaConnectionFactory
    repository: PwaAuthRepository
    clock: MutableClock
    student_account_id: int
    family_account_id: int
    staff_account_id: int
    student_user_id: int
    second_student_user_id: int
    staff_user_id: int
    course_id: int


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _session_id(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()[:32]


@pytest.fixture()
def auth_fixture(tmp_path) -> AuthFixture:
    database_path = tmp_path / "auth-repository.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    clock = MutableClock()
    now = _timestamp(clock())

    def seed(connection):
        connection.execute("DELETE FROM kv_logins")
        connection.execute("DELETE FROM groups")
        student_user_id = -701
        second_student_user_id = -702
        staff_user_id = -703
        season_id = connection.execute(
            "INSERT INTO seasons "
            "(id, code, title, starts_on, ends_on, session_expires_on, "
            "status, created_at, updated_at) VALUES "
            "(1, '2026-27', 'Сезон 2026–27', '2026-09-01', "
            "'2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
            (now, now),
        ).fetchone()["id"]
        course_id = connection.execute(
            "INSERT INTO courses "
            "(id, season_id, code, name, subject_code, status, "
            "sort_order, accent_key, created_at, updated_at) VALUES "
            "(1, ?, 'math-5-7', 'Математика 5–7', 'math', "
            "'active', 10, 'math', ?, ?) RETURNING id",
            (season_id, now, now),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO groups "
            "(id, group_id, short_code, public_name, sort_order, is_active, "
            "is_default, allow_self_switch, is_system, score_weight, "
            "course_id, status, color_key, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, 'active', ?, ?, ?)",
            (
                (
                    1,
                    "phase-a",
                    "a",
                    "Начинающие",
                    10,
                    course_id,
                    "beginner",
                    now,
                    now,
                ),
                (
                    2,
                    "phase-b",
                    "b",
                    "Продолжающие",
                    20,
                    course_id,
                    "continuing",
                    now,
                    now,
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO users "
            "(id, type, name, surname, grade, birthday, group_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    student_user_id,
                    1,
                    "Анна",
                    "Иванова",
                    7,
                    "2012-01-07",
                    "phase-a",
                ),
                (
                    second_student_user_id,
                    1,
                    "Борис",
                    "Петров",
                    None,
                    None,
                    "phase-b",
                ),
                (
                    staff_user_id,
                    2,
                    "Тестовый",
                    "Учитель",
                    None,
                    None,
                    None,
                ),
            ),
        )
        student_account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, "
            "credential_kind, credential_hash, linked_user_id, status, "
            "created_at, updated_at) VALUES "
            "(1, 'student', 'Ivanova-07', 'ivanova-07', 1, "
            "'synthetic-test', 'telegram_token', ?, ?, "
            "'active', ?, ?) RETURNING id",
            (STUDENT_HASH_V1, student_user_id, now, now),
        ).fetchone()["id"]
        family_account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(id, audience, username, username_normalized, "
            "provisioning_source, display_name, credential_kind, "
            "credential_hash, status, created_at, updated_at) VALUES "
            "(2, 'family', 'Family Login', 'family login', "
            "'synthetic-test', 'Родитель', 'password', ?, "
            "'active', ?, ?) RETURNING id",
            (FAMILY_HASH_V1, now, now),
        ).fetchone()["id"]
        staff_account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(id, audience, username, username_normalized, "
            "provisioning_source, credential_kind, credential_hash, "
            "linked_user_id, status, created_at, updated_at) VALUES "
            "(3, 'staff', 'Teacher', 'teacher', "
            "'synthetic-test', 'password', ?, ?, 'active', ?, ?) "
            "RETURNING id",
            (STAFF_HASH_V1, staff_user_id, now, now),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, "
            "is_primary, created_at, updated_at, revoked_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    family_account_id,
                    student_user_id,
                    "мама",
                    1,
                    now,
                    now,
                    None,
                ),
                (
                    family_account_id,
                    second_student_user_id,
                    "опекун",
                    0,
                    _timestamp(START - timedelta(days=10)),
                    now,
                    _timestamp(START - timedelta(days=1)),
                ),
            ),
        )
        enrollment_id = connection.execute(
            "INSERT INTO course_enrollments "
            "(id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) VALUES "
            "(1, ?, ?, 'phase-a', 'in_person', "
            "'active', ?, ?) RETURNING id",
            (student_user_id, course_id, now, now),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, valid_to, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    enrollment_id,
                    course_id,
                    "phase-a",
                    _timestamp(START - timedelta(days=10)),
                    None,
                    now,
                    now,
                ),
                (
                    enrollment_id,
                    course_id,
                    "phase-b",
                    _timestamp(START - timedelta(days=10)),
                    _timestamp(START - timedelta(days=1)),
                    now,
                    now,
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, valid_to, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    staff_user_id,
                    course_id,
                    None,
                    "teacher",
                    _timestamp(START - timedelta(days=10)),
                    None,
                    now,
                    now,
                ),
                (
                    staff_user_id,
                    course_id,
                    "phase-a",
                    "admin",
                    _timestamp(START - timedelta(days=10)),
                    _timestamp(START - timedelta(days=1)),
                    now,
                    now,
                ),
            ),
        )
        return (
            student_account_id,
            family_account_id,
            staff_account_id,
            course_id,
        )

    student_account_id, family_account_id, staff_account_id, course_id = (
        factory.run_write(seed)
    )
    return AuthFixture(
        database_path=database_path,
        factory=factory,
        repository=PwaAuthRepository(
            factory,
            clock=clock,
            credential_hasher=_TEST_HASHER,
        ),
        clock=clock,
        student_account_id=student_account_id,
        family_account_id=family_account_id,
        staff_account_id=staff_account_id,
        student_user_id=-701,
        second_student_user_id=-702,
        staff_user_id=-703,
        course_id=course_id,
    )


async def _create_student_session(
    fixture: AuthFixture,
    *,
    suffix: str,
    refresh_hash: str,
):
    account = await fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "IVANOVA-07"
    )
    assert account is not None
    return await fixture.repository.create_session(
        verified_account=account,
        session_public_id=_session_id(suffix),
        refresh_secret_hash=refresh_hash,
        expires_at=fixture.clock() + timedelta(days=1),
        request_id=f"request-create-{suffix}",
        device_label=f"Device {suffix}",
        user_agent_family="Synthetic browser",
    )


@pytest.mark.asyncio
async def test_login_lookup_is_normalized_audience_scoped_and_credential_neutral(
    auth_fixture: AuthFixture,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.FAMILY, "  ＦＡＭＩＬＹ   LOGIN  "
    )
    wrong_audience = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "family login"
    )
    missing = await auth_fixture.repository.find_account_for_login(
        AuthAudience.FAMILY, "unknown"
    )

    assert account is not None
    assert account.public_id == "a-2"
    assert FAMILY_HASH_V1 not in repr(account)
    assert wrong_audience is None
    assert missing is None
    # A missing row deliberately returns no credential decision. The auth
    # service must verify its precomputed dummy Argon2 hash before responding.


@pytest.mark.asyncio
async def test_create_current_list_and_soft_revoke_sessions(auth_fixture: AuthFixture):
    first = await _create_student_session(
        auth_fixture, suffix="one", refresh_hash="a" * 64
    )
    second = await _create_student_session(
        auth_fixture, suffix="two", refresh_hash="b" * 64
    )

    current = await auth_fixture.repository.get_current_session(
        audience=AuthAudience.STUDENT,
        account_public_id="a-1",
        session_public_id=first.public_id,
        credential_version=1,
        session_version=1,
    )
    wrong_version = await auth_fixture.repository.get_current_session(
        audience=AuthAudience.STUDENT,
        account_public_id="a-1",
        session_public_id=first.public_id,
        credential_version=1,
        session_version=2,
    )
    sessions = await auth_fixture.repository.list_sessions(
        account_id=auth_fixture.student_account_id
    )

    assert current is not None
    assert current.display_name == "Анна Иванова"
    assert current.linked_user_id == auth_fixture.student_user_id
    assert current.linked_user_public_id == "u--701"
    assert current.linked_user_type == 1
    assert wrong_version is None
    assert {session.public_id for session in sessions} == {
        first.public_id,
        second.public_id,
    }

    assert await auth_fixture.repository.revoke_session(
        account_id=auth_fixture.student_account_id,
        session_public_id=first.public_id,
        reason=SessionRevokeReason.LOGOUT,
        request_id="request-logout-one",
    )
    assert not await auth_fixture.repository.revoke_session(
        account_id=auth_fixture.student_account_id,
        session_public_id=first.public_id,
        reason=SessionRevokeReason.LOGOUT,
        request_id="request-logout-one-again",
    )
    assert (
        await auth_fixture.repository.revoke_all_sessions(
            account_id=auth_fixture.student_account_id,
            reason=SessionRevokeReason.LOGOUT_ALL,
            request_id="request-logout-all",
        )
        == 1
    )
    assert (
        await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id, include_revoked=False
        )
        == ()
    )

    events = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT event_type, metadata_json FROM auth_events "
            "WHERE account_id = ? ORDER BY id",
            (auth_fixture.student_account_id,),
        ).fetchall()
    )
    assert [row["event_type"] for row in events] == [
        "session.created",
        "session.created",
        "session.revoked",
        "sessions.revoked_all",
    ]
    assert all(json.loads(row["metadata_json"]) == {} for row in events)


@pytest.mark.asyncio
async def test_session_creation_applies_rehash_but_rejects_stale_verified_snapshot(
    auth_fixture: AuthFixture,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None

    session = await auth_fixture.repository.create_session(
        verified_account=account,
        session_public_id=_session_id("rehash"),
        refresh_secret_hash="c" * 64,
        expires_at=auth_fixture.clock() + timedelta(days=1),
        request_id="request-rehash",
        replacement_credential_hash=STUDENT_HASH_REHASHED,
    )
    assert session.credential_version == 1
    stored_account = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT credential_hash, credential_version FROM auth_accounts "
            "WHERE id = ?",
            (auth_fixture.student_account_id,),
        ).fetchone()
    )
    assert stored_account == {
        "credential_hash": STUDENT_HASH_REHASHED,
        "credential_version": 1,
    }

    with pytest.raises(AccountStateConflict):
        await auth_fixture.repository.create_session(
            verified_account=account,
            session_public_id=_session_id("stale-verification"),
            refresh_secret_hash="d" * 64,
            expires_at=auth_fixture.clock() + timedelta(days=1),
            request_id="request-stale-verification",
        )

    fresh_account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert fresh_account is not None
    with pytest.raises(ValueError, match="32 lowercase hex"):
        await auth_fixture.repository.create_session(
            verified_account=fresh_account,
            session_public_id="session-is-not-canonical",
            refresh_secret_hash="e" * 64,
            expires_at=auth_fixture.clock() + timedelta(days=1),
            request_id="request-invalid-session-id",
        )


@pytest.mark.asyncio
async def test_session_creation_rejects_a_changed_identity_snapshot(
    auth_fixture: AuthFixture,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None

    # linked_user_id is immutable in the schema, but the repository still
    # compares the complete verified snapshot as defense against a future
    # controlled relink transition or a connection with checks disabled.
    stale_identity = replace(
        account,
        linked_user_id=auth_fixture.second_student_user_id,
    )
    with pytest.raises(AccountStateConflict, match="credential verification"):
        await auth_fixture.repository.create_session(
            verified_account=stale_identity,
            session_public_id=_session_id("stale-identity"),
            refresh_secret_hash="0" * 64,
            expires_at=auth_fixture.clock() + timedelta(days=1),
            request_id="request-stale-identity",
        )

    assert (
        await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
        == ()
    )


@pytest.mark.asyncio
async def test_session_metadata_is_bounded_printable_and_network_canonical(
    auth_fixture: AuthFixture,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None
    session = await auth_fixture.repository.create_session(
        verified_account=account,
        session_public_id=_session_id("canonical-metadata"),
        refresh_secret_hash="1" * 64,
        expires_at=auth_fixture.clock() + timedelta(days=1),
        request_id="request-canonical-metadata",
        device_label="  Личный iPhone  ",
        user_agent_family="  Mobile Safari  ",
        ip_prefix="192.0.2.179/24",
    )
    assert session.device_label == "Личный iPhone"
    assert session.user_agent_family == "Mobile Safari"
    assert session.ip_prefix == "192.0.2.0/24"

    invalid_metadata = (
        {"device_label": "x" * 121},
        {"device_label": "phone\nsecond-line"},
        {"user_agent_family": "browser\u0000family"},
        {"ip_prefix": "not-an-ip-prefix"},
    )
    for index, metadata in enumerate(invalid_metadata):
        with pytest.raises(ValueError):
            await auth_fixture.repository.create_session(
                verified_account=account,
                session_public_id=_session_id(f"invalid-metadata-{index}"),
                refresh_secret_hash=f"{index + 2:x}" * 64,
                expires_at=auth_fixture.clock() + timedelta(days=1),
                request_id=f"request-invalid-metadata-{index}",
                **metadata,
            )

    assert (
        len(
            await auth_fixture.repository.list_sessions(
                account_id=auth_fixture.student_account_id
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_session_identity_and_refresh_digest_collisions_roll_back_audit(
    auth_fixture: AuthFixture,
):
    first = await _create_student_session(
        auth_fixture, suffix="collision", refresh_hash="a" * 64
    )
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None

    for public_id, refresh_hash, request_id in (
        (first.public_id, "b" * 64, "request-duplicate-session-id"),
        (_session_id("other-collision"), "a" * 64, "request-duplicate-refresh"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            await auth_fixture.repository.create_session(
                verified_account=account,
                session_public_id=public_id,
                refresh_secret_hash=refresh_hash,
                expires_at=auth_fixture.clock() + timedelta(days=1),
                request_id=request_id,
            )

    session_count, event_count = auth_fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM auth_sessions").fetchone()[
                "n"
            ],
            connection.execute(
                "SELECT count(*) AS n FROM auth_events "
                "WHERE event_type = 'session.created'"
            ).fetchone()["n"],
        )
    )
    assert (session_count, event_count) == (1, 1)


@pytest.mark.asyncio
async def test_refresh_rotation_is_single_use_and_replay_soft_revokes(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="rotation", refresh_hash="d" * 64
    )

    rotated = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=session.public_id,
        presented_secret_hash="d" * 64,
        replacement_secret_hash="e" * 64,
        request_id="request-rotate",
    )
    arbitrary_mismatch = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=session.public_id,
        presented_secret_hash="0" * 64,
        replacement_secret_hash="f" * 64,
        request_id="request-invalid-refresh",
    )
    replayed = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=session.public_id,
        presented_secret_hash="d" * 64,
        replacement_secret_hash="f" * 64,
        request_id="request-replay",
    )

    assert rotated.outcome is RefreshRotationOutcome.ROTATED
    assert rotated.session is not None and rotated.session.version == 2
    assert rotated.account_public_id == "a-1"
    assert arbitrary_mismatch.outcome is RefreshRotationOutcome.INVALID_SECRET
    assert arbitrary_mismatch.session is not None
    assert arbitrary_mismatch.account_public_id is None
    assert not arbitrary_mismatch.session.revoked
    assert arbitrary_mismatch.session.version == 2
    assert replayed.outcome is RefreshRotationOutcome.REPLAY_REVOKED
    assert replayed.session is not None
    assert replayed.account_public_id is None
    assert replayed.session.revoke_reason == "refresh_replay"
    assert replayed.session.version == 3
    consumed = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT refresh_secret_hash, expires_at "
            "FROM auth_refresh_consumed_secrets WHERE session_id = ?",
            (session.id,),
        ).fetchall()
    )
    assert consumed == [
        {"refresh_secret_hash": "d" * 64, "expires_at": _timestamp(session.expires_at)}
    ]
    assert (
        await auth_fixture.repository.get_current_session(
            audience=AuthAudience.STUDENT,
            account_public_id="a-1",
            session_public_id=session.public_id,
            credential_version=1,
            session_version=2,
        )
        is None
    )


@pytest.mark.asyncio
async def test_refresh_rotation_uses_virtual_account_identity(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="refresh-canonical-account", refresh_hash="2" * 64
    )
    account_public_id = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id FROM auth_accounts WHERE id = ?",
            (auth_fixture.student_account_id,),
        ).fetchone()["public_id"]
    )
    assert account_public_id == "a-1"
    result = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=session.public_id,
        presented_secret_hash="2" * 64,
        replacement_secret_hash="3" * 64,
        request_id="request-refresh-virtual-account-id",
    )
    assert result.outcome is RefreshRotationOutcome.ROTATED

    stored = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT refresh_secret_hash, version FROM auth_sessions WHERE id = ?",
            (session.id,),
        ).fetchone()
    )
    assert stored == {"refresh_secret_hash": "3" * 64, "version": 2}
    consumed_count, rotation_event_count = auth_fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT count(*) AS n FROM auth_refresh_consumed_secrets "
                "WHERE session_id = ?",
                (session.id,),
            ).fetchone()["n"],
            connection.execute(
                "SELECT count(*) AS n FROM auth_events "
                "WHERE session_id = ? AND event_type = 'session.rotated'",
                (session.id,),
            ).fetchone()["n"],
        )
    )
    assert (consumed_count, rotation_event_count) == (1, 1)


@pytest.mark.asyncio
async def test_refresh_authenticated_logout_is_uniform_and_fail_closed(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="refresh-logout-uniform", refresh_hash="4" * 64
    )

    results = (
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.FAMILY,
            session_public_id=session.public_id,
            presented_secret_hash="4" * 64,
            request_id="request-refresh-logout-wrong-audience",
        ),
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=session.public_id,
            presented_secret_hash="5" * 64,
            request_id="request-refresh-logout-wrong-secret",
        ),
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id="not-a-session-id",
            presented_secret_hash="4" * 64,
            request_id="request-refresh-logout-malformed-session",
        ),
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=session.public_id,
            presented_secret_hash="not-a-digest",
            request_id="request-refresh-logout-malformed-secret",
        ),
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=_session_id("unknown-refresh-logout"),
            presented_secret_hash="4" * 64,
            request_id="request-refresh-logout-unknown-session",
        ),
    )

    # Logout never discloses whether either half of the opaque refresh pair
    # existed. The route can clear cookies and return one response in all cases.
    assert results == (None, None, None, None, None)
    stored = (
        await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
    )[0]
    assert not stored.revoked
    assert stored.version == 1
    assert (
        auth_fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS n FROM auth_events "
                "WHERE session_id = ? AND event_type = 'session.revoked'",
                (session.id,),
            ).fetchone()["n"]
        )
        == 0
    )


@pytest.mark.asyncio
async def test_refresh_authenticated_logout_revokes_and_audits_atomically(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="refresh-logout", refresh_hash="6" * 64
    )

    result = await auth_fixture.repository.revoke_session_with_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=session.public_id,
        presented_secret_hash="6" * 64,
        request_id="request-refresh-logout",
        ip_prefix="2001:db8::179/64",
    )
    repeated = await auth_fixture.repository.revoke_session_with_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=session.public_id,
        presented_secret_hash="6" * 64,
        request_id="request-refresh-logout-again",
    )

    assert result is not None
    assert result.audience is AuthAudience.STUDENT
    assert result.account_public_id == "a-1"
    assert result.session_public_id == session.public_id
    assert repeated is None
    stored = (
        await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
    )[0]
    assert stored.revoke_reason == "logout"
    assert stored.version == 2
    events = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT event_type, request_id, ip_prefix, metadata_json "
            "FROM auth_events WHERE session_id = ? "
            "AND event_type = 'session.revoked' ORDER BY id",
            (session.id,),
        ).fetchall()
    )
    assert events == [
        {
            "event_type": "session.revoked",
            "request_id": "request-refresh-logout",
            "ip_prefix": "2001:db8::/64",
            "metadata_json": "{}",
        }
    ]

    rollback_session = await _create_student_session(
        auth_fixture, suffix="refresh-logout-audit-rollback", refresh_hash="7" * 64
    )
    auth_fixture.factory.run_write(
        lambda connection: connection.execute(
            "CREATE TRIGGER reject_synthetic_refresh_logout_audit "
            "BEFORE INSERT ON auth_events FOR EACH ROW "
            "WHEN new.request_id = 'request-refresh-logout-audit-failure' "
            "BEGIN SELECT raise(abort, 'synthetic audit failure'); END"
        )
    )
    with pytest.raises(sqlite3.IntegrityError, match="synthetic audit failure"):
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=rollback_session.public_id,
            presented_secret_hash="7" * 64,
            request_id="request-refresh-logout-audit-failure",
        )
    after_rollback = next(
        item
        for item in await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
        if item.id == rollback_session.id
    )
    assert not after_rollback.revoked
    assert after_rollback.version == 1


@pytest.mark.asyncio
async def test_refresh_authenticated_logout_handles_replay_expiry_and_revocation(
    auth_fixture: AuthFixture,
):
    replayed = await _create_student_session(
        auth_fixture, suffix="refresh-logout-replay", refresh_hash="8" * 64
    )
    rotation = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=replayed.public_id,
        presented_secret_hash="8" * 64,
        replacement_secret_hash="9" * 64,
        request_id="request-refresh-logout-prior-rotation",
    )
    assert rotation.outcome is RefreshRotationOutcome.ROTATED
    replay_target = await auth_fixture.repository.revoke_session_with_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=replayed.public_id,
        presented_secret_hash="8" * 64,
        request_id="request-refresh-logout-replay",
    )
    assert replay_target is not None
    assert replay_target.session_public_id == replayed.public_id
    replayed_after = next(
        item
        for item in await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
        if item.id == replayed.id
    )
    assert replayed_after.revoke_reason == "refresh_replay"
    assert replayed_after.version == 3

    expired = await _create_student_session(
        auth_fixture, suffix="refresh-logout-expired", refresh_hash="a" * 64
    )
    auth_fixture.clock.advance(days=2)
    expired_target = await auth_fixture.repository.revoke_session_with_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=expired.public_id,
        presented_secret_hash="a" * 64,
        request_id="request-refresh-logout-expired",
    )
    assert expired_target is not None
    assert expired_target.session_public_id == expired.public_id
    expired_after = next(
        item
        for item in await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
        if item.id == expired.id
    )
    assert expired_after.revoke_reason == "expired"
    assert expired_after.version == 2

    manually_revoked = await _create_student_session(
        auth_fixture, suffix="refresh-logout-already-revoked", refresh_hash="b" * 64
    )
    assert await auth_fixture.repository.revoke_session(
        account_id=auth_fixture.student_account_id,
        session_public_id=manually_revoked.public_id,
        reason=SessionRevokeReason.MANUAL,
        request_id="request-refresh-logout-manual-revoke",
    )
    assert (
        await auth_fixture.repository.revoke_session_with_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=manually_revoked.public_id,
            presented_secret_hash="b" * 64,
            request_id="request-refresh-logout-after-revoke",
        )
        is None
    )
    manually_revoked_after = next(
        item
        for item in await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
        if item.id == manually_revoked.id
    )
    assert manually_revoked_after.revoke_reason == "manual"
    assert manually_revoked_after.version == 2
    event_requests = auth_fixture.factory.run_read(
        lambda connection: {
            row["request_id"]
            for row in connection.execute(
                "SELECT request_id FROM auth_events "
                "WHERE event_type = 'session.revoked'"
            ).fetchall()
        }
    )
    assert "request-refresh-logout-after-revoke" not in event_requests


@pytest.mark.asyncio
async def test_concurrent_refresh_replay_revokes_the_shared_session(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="concurrent", refresh_hash="1" * 64
    )
    second_repository = PwaAuthRepository(
        PwaConnectionFactory(auth_fixture.database_path), clock=auth_fixture.clock
    )

    results = await asyncio.gather(
        auth_fixture.repository.rotate_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=session.public_id,
            presented_secret_hash="1" * 64,
            replacement_secret_hash="2" * 64,
            request_id="request-concurrent-one",
        ),
        second_repository.rotate_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=session.public_id,
            presented_secret_hash="1" * 64,
            replacement_secret_hash="3" * 64,
            request_id="request-concurrent-two",
        ),
    )

    assert {result.outcome for result in results} == {
        RefreshRotationOutcome.ROTATED,
        RefreshRotationOutcome.REPLAY_REVOKED,
    }
    stored = (
        await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.student_account_id
        )
    )[0]
    assert stored.revoked_at == START
    assert stored.revoke_reason == "refresh_replay"
    assert stored.version == 3


@pytest.mark.asyncio
async def test_consumed_refresh_history_cleanup_is_expiry_bounded(
    auth_fixture: AuthFixture,
):
    first = await _create_student_session(
        auth_fixture, suffix="cleanup-one", refresh_hash="a" * 64
    )
    second = await _create_student_session(
        auth_fixture, suffix="cleanup-two", refresh_hash="b" * 64
    )
    for session, old_hash, replacement_hash, request_id in (
        (first, "a" * 64, "c" * 64, "request-cleanup-one"),
        (second, "b" * 64, "d" * 64, "request-cleanup-two"),
    ):
        result = await auth_fixture.repository.rotate_refresh_secret(
            audience=AuthAudience.STUDENT,
            session_public_id=session.public_id,
            presented_secret_hash=old_hash,
            replacement_secret_hash=replacement_hash,
            request_id=request_id,
        )
        assert result.outcome is RefreshRotationOutcome.ROTATED

    assert (
        auth_fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS count FROM auth_refresh_consumed_secrets"
            ).fetchone()["count"]
        )
        == 2
    )
    auth_fixture.clock.advance(days=2)
    assert (
        await auth_fixture.repository.delete_expired_consumed_refresh_secrets(limit=1)
        == 1
    )
    assert (
        await auth_fixture.repository.delete_expired_consumed_refresh_secrets(limit=1)
        == 1
    )
    assert await auth_fixture.repository.delete_expired_consumed_refresh_secrets() == 0
    with pytest.raises(ValueError, match="1..10000"):
        await auth_fixture.repository.delete_expired_consumed_refresh_secrets(limit=0)


@pytest.mark.asyncio
async def test_refresh_fails_closed_for_expiry_and_credential_version_drift(
    auth_fixture: AuthFixture,
):
    expired = await _create_student_session(
        auth_fixture, suffix="expires", refresh_hash="6" * 64
    )
    auth_fixture.clock.advance(days=2)
    expired_result = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=expired.public_id,
        presented_secret_hash="6" * 64,
        replacement_secret_hash="7" * 64,
        request_id="request-expired-refresh",
    )
    assert expired_result.outcome is RefreshRotationOutcome.EXPIRED
    assert expired_result.session is not None
    assert expired_result.session.revoke_reason == "expired"

    # Restore the deterministic clock, then simulate a partial legacy token
    # rotation that advanced the account version before its cleanup ran. The
    # refresh path must still detect and soft-revoke the stale session.
    auth_fixture.clock.value = START
    stale = await _create_student_session(
        auth_fixture, suffix="credential-drift", refresh_hash="8" * 64
    )
    auth_fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE auth_accounts SET credential_version = 2 WHERE id = ?",
            (auth_fixture.student_account_id,),
        )
    )
    stale_result = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=stale.public_id,
        presented_secret_hash="8" * 64,
        replacement_secret_hash="9" * 64,
        request_id="request-credential-drift",
    )
    assert stale_result.outcome is RefreshRotationOutcome.CREDENTIAL_CHANGED
    assert stale_result.session is not None
    assert stale_result.session.revoke_reason == "credential_changed"


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_revoked_and_blocked_sessions(
    auth_fixture: AuthFixture,
):
    unknown = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=_session_id("unknown-refresh-session"),
        presented_secret_hash="a" * 64,
        replacement_secret_hash="b" * 64,
        request_id="request-unknown-refresh",
    )
    assert unknown.outcome is RefreshRotationOutcome.NOT_FOUND

    revoked_session = await _create_student_session(
        auth_fixture, suffix="revoked-refresh", refresh_hash="c" * 64
    )
    assert await auth_fixture.repository.revoke_session(
        account_id=auth_fixture.student_account_id,
        session_public_id=revoked_session.public_id,
        reason=SessionRevokeReason.MANUAL,
        request_id="request-manual-revoke",
    )
    revoked = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=revoked_session.public_id,
        presented_secret_hash="c" * 64,
        replacement_secret_hash="d" * 64,
        request_id="request-refresh-after-revoke",
    )
    assert revoked.outcome is RefreshRotationOutcome.INACTIVE
    assert revoked.session is not None
    assert revoked.session.revoke_reason == "manual"

    blocked_session = await _create_student_session(
        auth_fixture, suffix="blocked-refresh", refresh_hash="e" * 64
    )
    auth_fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE auth_accounts SET status = 'blocked' WHERE id = ?",
            (auth_fixture.student_account_id,),
        )
    )
    blocked = await auth_fixture.repository.rotate_refresh_secret(
        audience=AuthAudience.STUDENT,
        session_public_id=blocked_session.public_id,
        presented_secret_hash="e" * 64,
        replacement_secret_hash="f" * 64,
        request_id="request-blocked-refresh",
    )
    assert blocked.outcome is RefreshRotationOutcome.ACCOUNT_UNAVAILABLE
    assert blocked.session is not None
    assert blocked.session.revoke_reason == "account_unavailable"


@pytest.mark.asyncio
async def test_student_credential_change_updates_telegram_and_pwa_atomically(
    auth_fixture: AuthFixture,
):
    await _create_student_session(
        auth_fixture, suffix="cred-one", refresh_hash="4" * 64
    )
    await _create_student_session(
        auth_fixture, suffix="cred-two", refresh_hash="5" * 64
    )

    generic_result = await auth_fixture.repository.change_credential(
        account_id=auth_fixture.student_account_id,
        expected_credential_version=1,
        replacement_credential_hash=STUDENT_HASH_V2,
        request_id="request-generic-student-change",
    )
    result = await auth_fixture.repository.change_student_telegram_credential(
        account_id=auth_fixture.student_account_id,
        expected_credential_version=1,
        normalized_telegram_token="syntheticytoken",
        replacement_credential_hash=STUDENT_HASH_V2,
        request_id="request-change-student-credential",
    )
    stale_repeat = await auth_fixture.repository.change_student_telegram_credential(
        account_id=auth_fixture.student_account_id,
        expected_credential_version=1,
        normalized_telegram_token="must-not-win",
        replacement_credential_hash=_TEST_HASHER.hash("must-not-win"),
        request_id="request-stale-change",
    )

    assert not generic_result.changed
    assert result.changed
    assert result.credential_version == 2
    assert result.revoked_session_count == 2
    assert not stale_repeat.changed
    sessions = await auth_fixture.repository.list_sessions(
        account_id=auth_fixture.student_account_id
    )
    assert {session.revoke_reason for session in sessions} == {"credential_changed"}
    refreshed_account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert refreshed_account is not None
    assert refreshed_account.credential_version == 2
    assert refreshed_account.credential_hash == STUDENT_HASH_V2
    stored_token = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT token FROM users WHERE id = ?", (auth_fixture.student_user_id,)
        ).fetchone()["token"]
    )
    assert stored_token == "syntheticytoken"
    audit_rows = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT event_type, request_id, metadata_json FROM auth_events "
            "WHERE account_id = ? ORDER BY id",
            (auth_fixture.student_account_id,),
        ).fetchall()
    )
    # The legacy users row necessarily holds the shared Telegram secret; the
    # new auth audit remains typed and secret-free.
    assert "syntheticytoken" not in json.dumps(audit_rows)
    assert all(row["metadata_json"] == "{}" for row in audit_rows)


@pytest.mark.asyncio
async def test_student_token_uniqueness_failure_rolls_back_auth_and_sessions(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="token-conflict", refresh_hash="f" * 64
    )
    auth_fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE users SET token = 'reservedtoken' WHERE id = ?",
            (auth_fixture.second_student_user_id,),
        )
    )

    with pytest.raises(sqlite3.IntegrityError):
        await auth_fixture.repository.change_student_telegram_credential(
            account_id=auth_fixture.student_account_id,
            expected_credential_version=1,
            normalized_telegram_token="reservedtoken",
            replacement_credential_hash=_TEST_HASHER.hash("reservedtoken"),
            request_id="request-token-conflict",
        )

    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None
    assert account.credential_version == 1
    assert account.credential_hash == STUDENT_HASH_V1
    current = await auth_fixture.repository.get_current_session(
        audience=AuthAudience.STUDENT,
        account_public_id="a-1",
        session_public_id=session.public_id,
        credential_version=1,
        session_version=1,
    )
    assert current is not None
    student_token = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT token FROM users WHERE id = ?", (auth_fixture.student_user_id,)
        ).fetchone()["token"]
    )
    assert student_token is None


@pytest.mark.asyncio
async def test_student_credential_change_requires_pre_normalized_token(
    auth_fixture: AuthFixture,
):
    with pytest.raises(ValueError, match="normalized"):
        await auth_fixture.repository.change_student_telegram_credential(
            account_id=auth_fixture.student_account_id,
            expected_credential_version=1,
            normalized_telegram_token="  SyntheticУToken  ",
            replacement_credential_hash=STUDENT_HASH_V2,
            request_id="request-unnormalized-token",
        )

    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None
    assert account.credential_version == 1
    stored_token = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT token FROM users WHERE id = ?", (auth_fixture.student_user_id,)
        ).fetchone()["token"]
    )
    assert stored_token is None


@pytest.mark.asyncio
async def test_student_credential_change_rejects_hash_for_a_different_token(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="mismatched-token-hash", refresh_hash="a" * 64
    )

    with pytest.raises(ValueError, match="normalized Telegram token"):
        await auth_fixture.repository.change_student_telegram_credential(
            account_id=auth_fixture.student_account_id,
            expected_credential_version=1,
            normalized_telegram_token=STUDENT_TOKEN_V2,
            replacement_credential_hash=OTHER_VALID_HASH,
            request_id="request-mismatched-token-hash",
        )

    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None
    assert account.credential_version == 1
    assert account.credential_hash == STUDENT_HASH_V1
    assert (
        auth_fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT token FROM users WHERE id = ?",
                (auth_fixture.student_user_id,),
            ).fetchone()["token"]
        )
        is None
    )
    assert (
        await auth_fixture.repository.get_current_session(
            audience=AuthAudience.STUDENT,
            account_public_id="a-1",
            session_public_id=session.public_id,
            credential_version=1,
            session_version=1,
        )
        is not None
    )


@pytest.mark.asyncio
async def test_family_credential_change_uses_generic_transition(
    auth_fixture: AuthFixture,
):
    result = await auth_fixture.repository.change_credential(
        account_id=auth_fixture.family_account_id,
        expected_credential_version=1,
        replacement_credential_hash=OTHER_VALID_HASH,
        request_id="request-family-credential",
    )
    assert result.changed
    assert result.credential_version == 2
    assert result.revoked_session_count == 0
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.FAMILY, "family login"
    )
    assert account is not None and account.credential_version == 2


@pytest.mark.asyncio
async def test_family_credential_change_revokes_live_sessions(
    auth_fixture: AuthFixture,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.FAMILY, "family login"
    )
    assert account is not None
    session = await auth_fixture.repository.create_session(
        verified_account=account,
        session_public_id=_session_id("family-live-session"),
        refresh_secret_hash="b" * 64,
        expires_at=auth_fixture.clock() + timedelta(days=1),
        request_id="request-create-family-session",
    )

    changed = await auth_fixture.repository.change_credential(
        account_id=auth_fixture.family_account_id,
        expected_credential_version=1,
        replacement_credential_hash=OTHER_VALID_HASH,
        request_id="request-change-family-live-session",
    )
    assert changed.changed
    assert changed.revoked_session_count == 1
    assert (
        await auth_fixture.repository.get_current_session(
            audience=AuthAudience.FAMILY,
            account_public_id="a-2",
            session_public_id=session.public_id,
            credential_version=1,
            session_version=1,
        )
        is None
    )
    stored_session = (
        await auth_fixture.repository.list_sessions(
            account_id=auth_fixture.family_account_id
        )
    )[0]
    assert stored_session.revoke_reason == "credential_changed"


@pytest.mark.asyncio
async def test_events_and_throttle_rows_never_store_raw_login_or_secret(
    auth_fixture: AuthFixture,
):
    raw_login = "  Sensitive Student Login  "
    raw_ip = "192.0.2.179/24"
    key = make_throttle_bucket_key(
        audience=AuthAudience.STUDENT,
        kind=ThrottleBucketKind.NORMALIZED_LOGIN,
        value=raw_login,
        pepper=PEPPER,
    )
    same_key = make_throttle_bucket_key(
        audience=AuthAudience.STUDENT,
        kind=ThrottleBucketKind.NORMALIZED_LOGIN,
        value="sensitive   student login",
        pepper=PEPPER,
    )
    assert key.digest == same_key.digest
    assert raw_login not in repr(key)

    await auth_fixture.repository.record_throttle_failure((key,))
    await auth_fixture.repository.record_auth_event(
        event_type=AuthEventType.LOGIN_FAILED,
        request_id="request-failed-login",
        ip_prefix=raw_ip,
    )

    throttle_row, event_row = auth_fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM auth_throttle_buckets").fetchone(),
            connection.execute(
                "SELECT event_type, request_id, metadata_json FROM auth_events "
                "WHERE event_type = 'login.failed'"
            ).fetchone(),
        )
    )
    serialized_throttle = json.dumps(throttle_row, ensure_ascii=False)
    serialized_event = json.dumps(event_row, ensure_ascii=False)
    assert "Sensitive Student Login" not in serialized_throttle
    assert "sensitive student login" not in serialized_throttle
    assert key.digest in serialized_throttle
    assert event_row == {
        "event_type": "login.failed",
        "request_id": "request-failed-login",
        "metadata_json": "{}",
    }
    assert "Sensitive Student Login" not in serialized_event


@pytest.mark.asyncio
async def test_throttle_window_backoff_cap_and_selective_clear(
    auth_fixture: AuthFixture,
):
    policy = ThrottlePolicy(
        window=timedelta(seconds=60),
        failures_before_lock=3,
        initial_lock=timedelta(seconds=10),
        maximum_lock=timedelta(seconds=20),
    )
    repository = PwaAuthRepository(
        auth_fixture.factory, clock=auth_fixture.clock, throttle_policy=policy
    )
    login_key = make_throttle_bucket_key(
        audience=AuthAudience.STUDENT,
        kind=ThrottleBucketKind.NORMALIZED_LOGIN,
        value="ivanova-07",
        pepper=PEPPER,
    )
    ip_key = make_throttle_bucket_key(
        audience=AuthAudience.STUDENT,
        kind=ThrottleBucketKind.IP,
        value="192.0.2.0/24",
        pepper=PEPPER,
    )
    assert (
        ip_key.digest
        == make_throttle_bucket_key(
            audience=AuthAudience.STUDENT,
            kind=ThrottleBucketKind.IP,
            value="192.0.2.179/24",
            pepper=PEPPER,
        ).digest
    )

    first = await repository.record_throttle_failure((login_key, ip_key))
    second = await repository.record_throttle_failure((login_key, ip_key))
    third = await repository.record_throttle_failure((login_key, ip_key))
    while_locked = await repository.record_throttle_failure((login_key, ip_key))

    assert [state.failure_count for state in first] == [1, 1]
    assert [state.failure_count for state in second] == [2, 2]
    assert all(state.locked and state.retry_after_seconds == 10 for state in third)
    assert [state.failure_count for state in while_locked] == [3, 3]

    auth_fixture.clock.advance(seconds=11)
    fourth = await repository.record_throttle_failure((login_key, ip_key))
    assert all(state.failure_count == 4 for state in fourth)
    assert all(state.retry_after_seconds == 20 for state in fourth)

    auth_fixture.clock.advance(seconds=21)
    fifth = await repository.record_throttle_failure((login_key, ip_key))
    assert all(state.failure_count == 5 for state in fifth)
    assert all(state.retry_after_seconds == 20 for state in fifth)

    auth_fixture.clock.advance(seconds=29)
    reset = await repository.check_throttle((login_key, ip_key))
    assert all(state.failure_count == 0 and not state.locked for state in reset)
    after_reset = await repository.record_throttle_failure((login_key, ip_key))
    assert [state.failure_count for state in after_reset] == [1, 1]

    assert await repository.clear_throttle((login_key,)) == 1
    login_state, ip_state = await repository.check_throttle((login_key, ip_key))
    assert login_state.failure_count == 0
    assert ip_state.failure_count == 1


@pytest.mark.asyncio
async def test_concurrent_workers_increment_one_throttle_bucket_without_lost_updates(
    auth_fixture: AuthFixture,
):
    policy = ThrottlePolicy(failures_before_lock=100)
    repositories = tuple(
        PwaAuthRepository(
            PwaConnectionFactory(auth_fixture.database_path),
            clock=auth_fixture.clock,
            throttle_policy=policy,
        )
        for _ in range(4)
    )
    key = make_throttle_bucket_key(
        audience=AuthAudience.STAFF,
        kind=ThrottleBucketKind.ACCOUNT,
        value="a-3",
        pepper=PEPPER,
    )

    await asyncio.gather(
        *(
            repositories[index % len(repositories)].record_throttle_failure((key,))
            for index in range(16)
        )
    )

    state = (await repositories[0].check_throttle((key,)))[0]
    assert state.failure_count == 16
    stored = auth_fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT failure_count, version, bucket_key_hmac "
            "FROM auth_throttle_buckets WHERE bucket_key_hmac = ?",
            (key.digest,),
        ).fetchone()
    )
    assert stored == {
        "failure_count": 16,
        "version": 16,
        "bucket_key_hmac": key.digest,
    }


@pytest.mark.asyncio
async def test_family_course_access_and_staff_scope_reads_are_current_only(
    auth_fixture: AuthFixture,
):
    children = await auth_fixture.repository.list_family_children(
        family_account_id=auth_fixture.family_account_id
    )
    enrollments = await auth_fixture.repository.list_course_enrollments(
        student_user_id=auth_fixture.student_user_id
    )
    scopes = await auth_fixture.repository.list_staff_scopes(
        staff_user_id=auth_fixture.staff_user_id
    )

    assert children == (children[0],)
    assert children[0].student_user_id == auth_fixture.student_user_id
    assert children[0].student_public_id == "u--701"
    assert children[0].is_primary
    assert children[0].grade == 7
    assert children[0].birthday == "2012-01-07"

    assert len(enrollments) == 1
    enrollment = enrollments[0]
    assert enrollment.course_id == auth_fixture.course_id
    assert enrollment.student_public_id == "u--701"
    assert enrollment.course_subject_code == "math"
    assert enrollment.course_accent_key == "math"
    assert enrollment.course_version == 1
    assert enrollment.active_group_id == "phase-a"
    assert enrollment.active_group_public_id == "g-1"
    assert enrollment.attendance_mode == "in_person"
    assert [group.group_id for group in enrollment.allowed_groups] == ["phase-a"]
    assert enrollment.allowed_groups[0].course_public_id == "c-1"
    assert enrollment.allowed_groups[0].group_public_id == "g-1"
    assert enrollment.allowed_groups[0].version == 1

    assert len(scopes) == 1
    assert scopes[0].course_id == auth_fixture.course_id
    assert scopes[0].group_id is None
    assert scopes[0].role.value == "teacher"


@pytest.mark.asyncio
async def test_active_enrollment_without_current_active_group_access_fails_closed(
    auth_fixture: AuthFixture,
):
    auth_fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_group_access SET valid_to = ? WHERE group_id = 'phase-a'",
            (_timestamp(START - timedelta(days=1)),),
        )
    )
    with pytest.raises(PrincipalDataIntegrityError, match="active-group access"):
        await auth_fixture.repository.list_course_enrollments(
            student_user_id=auth_fixture.student_user_id
        )


@pytest.mark.asyncio
async def test_principal_reads_fail_closed_on_wrong_legacy_user_types(
    auth_fixture: AuthFixture,
):
    student_session = await _create_student_session(
        auth_fixture, suffix="wrong-student-type", refresh_hash="a" * 64
    )
    staff_account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STAFF, "teacher"
    )
    assert staff_account is not None
    staff_session = await auth_fixture.repository.create_session(
        verified_account=staff_account,
        session_public_id=_session_id("wrong-staff-type"),
        refresh_secret_hash="b" * 64,
        expires_at=auth_fixture.clock() + timedelta(days=1),
        request_id="request-create-staff-type",
    )

    auth_fixture.factory.run_write(
        lambda connection: connection.executemany(
            "UPDATE users SET type = ? WHERE id = ?",
            (
                (2, auth_fixture.student_user_id),
                (1, auth_fixture.staff_user_id),
            ),
        )
    )
    student_current = await auth_fixture.repository.get_current_session(
        audience=AuthAudience.STUDENT,
        account_public_id="a-1",
        session_public_id=student_session.public_id,
        credential_version=1,
        session_version=1,
    )
    staff_current = await auth_fixture.repository.get_current_session(
        audience=AuthAudience.STAFF,
        account_public_id="a-3",
        session_public_id=staff_session.public_id,
        credential_version=1,
        session_version=1,
    )
    children = await auth_fixture.repository.list_family_children(
        family_account_id=auth_fixture.family_account_id
    )
    scopes = await auth_fixture.repository.list_staff_scopes(
        staff_user_id=auth_fixture.staff_user_id
    )

    assert student_current is None
    assert staff_current is None
    assert children == ()
    assert scopes == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_staff_type", [-1, -2, -4, 130])
async def test_staff_identity_rejects_inactive_negative_and_composite_types(
    auth_fixture: AuthFixture,
    invalid_staff_type: int,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STAFF, "teacher"
    )
    assert account is not None
    session = await auth_fixture.repository.create_session(
        verified_account=account,
        session_public_id=_session_id(f"staff-type-{invalid_staff_type}"),
        refresh_secret_hash=hashlib.sha256(
            f"refresh-{invalid_staff_type}".encode()
        ).hexdigest(),
        expires_at=auth_fixture.clock() + timedelta(days=1),
        request_id=f"request-staff-type-{abs(invalid_staff_type)}",
    )
    auth_fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE users SET type = ? WHERE id = ?",
            (invalid_staff_type, auth_fixture.staff_user_id),
        )
    )

    current = await auth_fixture.repository.get_current_session(
        audience=AuthAudience.STAFF,
        account_public_id="a-3",
        session_public_id=session.public_id,
        credential_version=1,
        session_version=1,
    )
    scopes = await auth_fixture.repository.list_staff_scopes(
        staff_user_id=auth_fixture.staff_user_id
    )
    assert current is None
    assert scopes == ()


@pytest.mark.asyncio
async def test_browser_public_ids_are_virtual_and_current_at_repository_boundary(
    auth_fixture: AuthFixture,
):
    session = await _create_student_session(
        auth_fixture, suffix="corrupt-user-public-id", refresh_hash="c" * 64
    )

    current = await auth_fixture.repository.get_current_session(
            audience=AuthAudience.STUDENT,
            account_public_id="a-1",
            session_public_id=session.public_id,
            credential_version=1,
            session_version=1,
        )
    assert current is not None and current.linked_user_public_id == "u--701"
    children = await auth_fixture.repository.list_family_children(
        family_account_id=auth_fixture.family_account_id
    )
    enrollments = await auth_fixture.repository.list_course_enrollments(
        student_user_id=auth_fixture.student_user_id
    )
    assert children[0].student_public_id == "u--701"
    assert enrollments[0].student_public_id == "u--701"


@pytest.mark.asyncio
async def test_group_staff_scope_uses_virtual_group_public_id(
    auth_fixture: AuthFixture,
):
    now = _timestamp(auth_fixture.clock())

    def add_group_scope(connection):
        connection.execute(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, "
            "created_at, updated_at) VALUES (?, ?, 'phase-a', 'teacher', ?, ?, ?)",
            (
                auth_fixture.staff_user_id,
                auth_fixture.course_id,
                _timestamp(START - timedelta(days=1)),
                now,
                now,
            ),
        )
    auth_fixture.factory.run_write(add_group_scope)

    scopes = await auth_fixture.repository.list_staff_scopes(
        staff_user_id=auth_fixture.staff_user_id
    )
    assert any(scope.group_public_id == "g-1" for scope in scopes)


def test_repository_rejects_non_digest_keys_and_weak_peppers():
    with pytest.raises(ValueError, match="32 bytes"):
        make_throttle_bucket_key(
            audience=AuthAudience.STUDENT,
            kind=ThrottleBucketKind.NORMALIZED_LOGIN,
            value="student",
            pepper=b"too-short",
        )
    with pytest.raises(ValueError, match="must not be empty"):
        make_throttle_bucket_key(
            audience=AuthAudience.STUDENT,
            kind=ThrottleBucketKind.NORMALIZED_LOGIN,
            value="   ",
            pepper=PEPPER,
        )


@pytest.mark.asyncio
async def test_new_credential_transitions_reject_non_argon2id_values(
    auth_fixture: AuthFixture,
):
    account = await auth_fixture.repository.find_account_for_login(
        AuthAudience.STUDENT, "ivanova-07"
    )
    assert account is not None
    with pytest.raises(ValueError, match="Argon2id"):
        await auth_fixture.repository.create_session(
            verified_account=account,
            session_public_id=_session_id("plaintext-rehash"),
            refresh_secret_hash="a" * 64,
            expires_at=auth_fixture.clock() + timedelta(days=1),
            request_id="request-plaintext-rehash",
            replacement_credential_hash="$argon2id$prefix-only",
        )
    with pytest.raises(ValueError, match="Argon2id"):
        await auth_fixture.repository.change_credential(
            account_id=auth_fixture.student_account_id,
            expected_credential_version=1,
            replacement_credential_hash="sha256-is-not-enough",
            request_id="request-weak-credential",
        )
