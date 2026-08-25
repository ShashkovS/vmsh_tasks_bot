"""Real aiohttp auth/serialization tests for private support routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from aiohttp import web
from argon2 import PasswordHasher

from apps import pwa_app
from apps.pwa_api import support_routes as support_routes_module
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from db_methods.pwa.support import (
    SupportEntryRecord,
    SupportForbidden,
    SupportIdempotencyConflict,
    SupportInvalidationTargets,
    SupportNotFound,
    SupportThreadPage,
    SupportThreadRecord,
    SupportThreadSummaryRecord,
)
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from models.pwa.auth import AuthAudience, CredentialHasher


ORIGIN = "http://127.0.0.1:5380"
HOST = "127.0.0.1:5380"
NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
STUDENT_ID = 957_001
TEACHER_ID = 957_002
PARTIAL_TEACHER_ID = 957_003
ADMIN_ID = 957_004
TEST_HASHER = PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)


def _timestamp(value: datetime = NOW) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _auth_config() -> AuthRuntimeConfig:
    return AuthRuntimeConfig(
        origins_by_audience=MappingProxyType(
            {audience: frozenset({ORIGIN}) for audience in AuthAudience}
        ),
        trusted_proxy_networks=(),
        trusted_proxy_hops=0,
        access_ttl_seconds=900,
        secure_cookies=False,
        signing_keys=("s" * 32,),
        refresh_pepper=b"r" * 32,
        throttle_pepper=b"t" * 32,
        test_only_defaults=True,
    )


class FakeSupportRepository:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.record = SupportThreadRecord(
            thread_public_id="sup-1",
            kind="problem_question",
            student_public_id="u-957001",
            student_display_name="Анна Белова",
            course_public_id="c-1",
            course_name="Математика",
            group_public_id="g-5",
            group_name="Начинающие",
            group_lesson_public_id="gl-1",
            problem_public_id="p-1",
            problem_title="Перестановки",
            latest_entry_at=NOW,
            version=1,
            entries=(
                SupportEntryRecord(
                    entry_public_id="se-1",
                    author_kind="student",
                    author_public_id="u-957001",
                    author_display_name="Анна Белова",
                    text="Почему эти случаи одинаковые?",
                    asset_public_id=None,
                    channel="pwa",
                    client_created_at=NOW,
                    server_received_at=NOW,
                ),
            ),
        )
        self.summary = SupportThreadSummaryRecord(
            thread_public_id=self.record.thread_public_id,
            kind=self.record.kind,
            student_public_id=self.record.student_public_id,
            student_display_name=self.record.student_display_name,
            course_public_id=self.record.course_public_id,
            course_name=self.record.course_name,
            group_public_id=self.record.group_public_id,
            group_name=self.record.group_name,
            group_lesson_public_id=self.record.group_lesson_public_id,
            problem_public_id=self.record.problem_public_id,
            problem_title=self.record.problem_title,
            latest_entry_at=self.record.latest_entry_at,
            latest_author_kind="student",
            latest_text_excerpt="Почему эти случаи одинаковые?",
            reply_state="awaiting_staff",
            entry_count=1,
            version=self.record.version,
        )

    async def create_student_thread(self, command):
        self.calls.append(command)
        if command.idempotency_key == "support-conflict":
            raise SupportIdempotencyConflict("conflict")
        return self.record

    async def append_student_entry(self, command):
        self.calls.append(command)
        return self.record

    async def append_staff_entry(self, command):
        self.calls.append(command)
        if not command.scope.allows(
            {
                "course_public_id": self.record.course_public_id,
                "group_public_id": self.record.group_public_id,
            }
        ):
            raise SupportForbidden("outside scope")
        return self.record

    async def get_student_thread(self, *, student_user_id, thread_public_id):
        self.calls.append(("student-get", student_user_id, thread_public_id))
        if student_user_id != STUDENT_ID:
            raise SupportForbidden("wrong owner")
        return self.record

    async def get_staff_thread(self, *, thread_public_id, scope):
        self.calls.append(("staff-get", thread_public_id, scope))
        if not scope.allows(
            {
                "course_public_id": self.record.course_public_id,
                "group_public_id": self.record.group_public_id,
            }
        ):
            raise SupportForbidden("outside scope")
        return self.record

    async def list_student_threads(self, *, student_user_id, cursor=None, page_size=50):
        self.calls.append(("student-list", student_user_id, cursor, page_size))
        if student_user_id != STUDENT_ID:
            raise SupportForbidden("wrong owner")
        if cursor == "missing-cursor":
            raise SupportNotFound("missing cursor")
        return SupportThreadPage(items=(self.summary,), next_cursor="support-http-next")

    async def list_staff_threads(self, **query):
        self.calls.append(("staff-list", query))
        if not query["scope"].allows(
            {
                "course_public_id": self.record.course_public_id,
                "group_public_id": self.record.group_public_id,
            }
        ):
            return SupportThreadPage(items=(), next_cursor=None)
        if query["cursor"] == "missing-cursor":
            raise SupportNotFound("missing cursor")
        return SupportThreadPage(items=(self.summary,), next_cursor=None)

    async def invalidation_targets(self, *, thread_public_id):
        return SupportInvalidationTargets(
            thread_public_id=thread_public_id,
            student_account_public_ids=("a-1",),
            staff_account_public_ids=("a-2",),
        )


@dataclass(frozen=True, slots=True)
class SupportHttpFixture:
    client: object
    repository: FakeSupportRepository
    cookies: MappingProxyType
    invalidations: list[tuple[SupportInvalidationTargets, str]]


def _seed_auth(factory: PwaConnectionFactory) -> None:
    now = _timestamp()

    def seed(connection) -> None:
        connection.execute("DELETE FROM kv_logins")
        connection.executemany(
            "INSERT INTO users (id, type, name, surname) VALUES (?, ?, ?, ?)",
            (
                (
                    STUDENT_ID,
                    int(USER_TYPE.STUDENT),
                    "Анна",
                    "Белова",
                ),
                (
                    TEACHER_ID,
                    int(USER_TYPE.TEACHER),
                    "Мария",
                    "Учитель",
                ),
                (
                    PARTIAL_TEACHER_ID,
                    int(USER_TYPE.TEACHER),
                    "Пётр",
                    "Другой",
                ),
                (
                    ADMIN_ID,
                    int(USER_TYPE.ADMIN),
                    "Иван",
                    "Администратор",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO auth_accounts "
            "(audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'synthetic-test', ?, ?, ?, 'active', ?, ?)",
            (
                (
                    "student",
                    "support-http-student",
                    "support-http-student",
                    1,
                    "telegram_token",
                    TEST_HASHER.hash("student-token"),
                    STUDENT_ID,
                    now,
                    now,
                ),
                (
                    "staff",
                    "support-http-teacher",
                    "support-http-teacher",
                    None,
                    "password",
                    TEST_HASHER.hash("teacher-password"),
                    TEACHER_ID,
                    now,
                    now,
                ),
                (
                    "staff",
                    "support-http-partial",
                    "support-http-partial",
                    None,
                    "password",
                    TEST_HASHER.hash("partial-password"),
                    PARTIAL_TEACHER_ID,
                    now,
                    now,
                ),
                (
                    "staff",
                    "support-http-admin",
                    "support-http-admin",
                    None,
                    "password",
                    TEST_HASHER.hash("admin-password"),
                    ADMIN_ID,
                    now,
                    now,
                ),
            ),
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) VALUES "
                "('support-http', 'Support HTTP', "
                "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) "
                "RETURNING id",
                (now, now),
            ).fetchone()["id"]
        )
        course_id = int(
            connection.execute(
                "INSERT INTO courses "
                "(season_id, code, name, subject_code, status, sort_order, "
                "accent_key, created_at, updated_at) VALUES "
                "(?, 'math', 'Математика', 'math', 'active', "
                "1, 'math', ?, ?) RETURNING id",
                (season_id, now, now),
            ).fetchone()["id"]
        )
        for group_id, code in (
            ("support-http-a", "a"),
            ("support-http-b", "b"),
        ):
            connection.execute(
                "INSERT INTO groups "
                "(group_id, short_code, public_name, sort_order, is_active, is_default, "
                "allow_self_switch, is_system, score_weight, course_id, "
                "status, created_at, updated_at) VALUES "
                "(?, ?, ?, 1, 1, 0, 1, 0, 1.0, ?, 'active', ?, ?)",
                (group_id, code, f"Группа {code}", course_id, now, now),
            )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) VALUES "
                "(?, ?, 'support-http-a', 'online', "
                "'active', ?, ?) RETURNING id",
                (STUDENT_ID, course_id, now, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'support-http-a', ?, ?, ?)",
            (enrollment_id, course_id, now, now, now),
        )
        connection.executemany(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, created_at, "
            "updated_at) VALUES (?, ?, ?, 'teacher', ?, ?, ?)",
            (
                (TEACHER_ID, course_id, "support-http-a", now, now, now),
                (
                    PARTIAL_TEACHER_ID,
                    course_id,
                    "support-http-b",
                    now,
                    now,
                    now,
                ),
            ),
        )

    factory.run_write(seed)


@pytest.fixture()
async def support_http(tmp_path, aiohttp_client) -> SupportHttpFixture:
    database_path = tmp_path / "support-http.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    _seed_auth(factory)
    auth_config = _auth_config()
    auth_service = await PwaAuthService.create(
        PwaAuthRepository(
            factory,
            clock=lambda: NOW,
            credential_hasher=TEST_HASHER,
        ),
        auth_config,
        credential_hasher=CredentialHasher(TEST_HASHER),
        clock=lambda: NOW,
    )
    repository = FakeSupportRepository()
    invalidations: list[tuple[SupportInvalidationTargets, str]] = []

    async def capture_invalidation(targets, reason):
        invalidations.append((targets, reason))

    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="support-http-test",
        config_name="support_http_test",
        pwa_prototype=True,
        nats_server=None,
    )
    pwa_app.configure(
        app,
        broker=InProcessBroker("support_http_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
        support_repository=repository,
        support_invalidator=capture_invalidation,
    )
    client = await aiohttp_client(app)

    async def login(audience: AuthAudience, username: str, password: str) -> str:
        response = await client.post(
            f"/{audience.value}/api/v1/auth/login",
            json={
                "username": username,
                (
                    "telegramToken" if audience is AuthAudience.STUDENT else "password"
                ): password,
            },
            headers=_headers(unsafe=True),
        )
        assert response.status == 200, await response.text()
        cookie = response.cookies[COOKIE_POLICY[audience].access_name].value
        client.session.cookie_jar.clear()
        return cookie

    cookies = MappingProxyType(
        {
            "student": await login(
                AuthAudience.STUDENT, "support-http-student", "student-token"
            ),
            "teacher": await login(
                AuthAudience.STAFF, "support-http-teacher", "teacher-password"
            ),
            "partial": await login(
                AuthAudience.STAFF, "support-http-partial", "partial-password"
            ),
            "admin": await login(
                AuthAudience.STAFF, "support-http-admin", "admin-password"
            ),
        }
    )
    return SupportHttpFixture(
        client=client,
        repository=repository,
        cookies=cookies,
        invalidations=invalidations,
    )


def _headers(*, unsafe: bool = False) -> dict[str, str]:
    headers = {"Host": HOST, "X-Request-ID": "support.http.test"}
    if unsafe:
        headers.update({"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"})
    return headers


def _cookie(fixture: SupportHttpFixture, identity: str, audience: AuthAudience):
    return {COOKIE_POLICY[audience].access_name: fixture.cookies[identity]}


def _create_payload(**changes) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "idempotencyKey": "support-http-create",
        "kind": "problem_question",
        "groupLessonId": "gl-1",
        "problemId": "p-1",
        "text": "Почему эти случаи одинаковые?",
        "clientCreatedAt": "2026-10-05T12:00:00Z",
    }
    payload.update(changes)
    return payload


def _append_payload(**changes) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "idempotencyKey": "support-http-append",
        "text": "Посмотрите на перестановку двух случаев.",
        "clientCreatedAt": "2026-10-05T12:01:00Z",
    }
    payload.update(changes)
    return payload


@pytest.mark.asyncio
async def test_student_create_get_and_append_use_authenticated_owner(support_http):
    fixture = support_http
    anonymous = await fixture.client.get(
        "/student/api/v1/questions/sup-1", headers=_headers()
    )
    assert anonymous.status == 401

    created = await fixture.client.post(
        "/student/api/v1/questions",
        json=_create_payload(),
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert created.status == 200, await created.text()
    payload = await created.json()
    assert payload["requestId"] == "support.http.test"
    assert payload["thread"]["student"]["studentId"] == "u-957001"
    assert payload["thread"]["entries"][0]["author"]["kind"] == "student"
    assert fixture.repository.calls[-1].student_user_id == STUDENT_ID

    fetched = await fixture.client.get(
        "/student/api/v1/questions/sup-1",
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(),
    )
    assert fetched.status == 200
    appended = await fixture.client.post(
        "/student/api/v1/questions/sup-1/entries",
        json=_append_payload(),
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert appended.status == 200
    assert fixture.repository.calls[-1].student_user_id == STUDENT_ID
    assert [reason for _, reason in fixture.invalidations] == [
        "support-thread-created",
        "support-student-entry-appended",
    ]


@pytest.mark.asyncio
async def test_staff_scope_and_server_owned_author_kind_are_enforced(support_http):
    fixture = support_http
    visible = await fixture.client.get(
        "/staff/api/v1/questions/sup-1",
        cookies=_cookie(fixture, "teacher", AuthAudience.STAFF),
        headers=_headers(),
    )
    assert visible.status == 200

    forbidden = await fixture.client.get(
        "/staff/api/v1/questions/sup-1",
        cookies=_cookie(fixture, "partial", AuthAudience.STAFF),
        headers=_headers(),
    )
    assert forbidden.status == 403

    teacher_reply = await fixture.client.post(
        "/staff/api/v1/questions/sup-1/entries",
        json=_append_payload(idempotencyKey="support-teacher-entry"),
        cookies=_cookie(fixture, "teacher", AuthAudience.STAFF),
        headers=_headers(unsafe=True),
    )
    assert teacher_reply.status == 200
    assert fixture.repository.calls[-1].staff_user_id == TEACHER_ID
    assert fixture.repository.calls[-1].author_kind == "teacher"

    admin_reply = await fixture.client.post(
        "/staff/api/v1/questions/sup-1/entries",
        json=_append_payload(idempotencyKey="support-admin-entry"),
        cookies=_cookie(fixture, "admin", AuthAudience.STAFF),
        headers=_headers(unsafe=True),
    )
    assert admin_reply.status == 200
    assert fixture.repository.calls[-1].staff_user_id == ADMIN_ID
    assert fixture.repository.calls[-1].author_kind == "admin"
    assert [reason for _, reason in fixture.invalidations] == [
        "support-staff-entry-appended",
        "support-staff-entry-appended",
    ]


@pytest.mark.asyncio
async def test_student_list_is_owner_derived_cursor_backed_and_public_id_only(
    support_http,
):
    fixture = support_http
    response = await fixture.client.get(
        "/student/api/v1/questions?cursor=support-http-before",
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["nextCursor"] == "support-http-next"
    assert payload["items"][0]["replyState"] == "awaiting_staff"
    assert payload["items"][0]["latestEntry"] == {
        "authorKind": "student",
        "textExcerpt": "Почему эти случаи одинаковые?",
        "receivedAt": "2026-10-05T12:00:00.000000Z",
    }
    assert fixture.repository.calls[-1] == (
        "student-list",
        STUDENT_ID,
        "support-http-before",
        50,
    )

    invalid = await fixture.client.get(
        "/student/api/v1/questions?cursor=../unsafe",
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(),
    )
    assert invalid.status == 422


@pytest.mark.asyncio
async def test_staff_list_passes_server_scope_and_strict_inbox_filters(support_http):
    fixture = support_http
    response = await fixture.client.get(
        "/staff/api/v1/questions"
        "?state=awaiting_student&kind=general&course=c-1"
        "&group=g-5&cursor=support-http-before",
        cookies=_cookie(fixture, "teacher", AuthAudience.STAFF),
        headers=_headers(),
    )
    assert response.status == 200, await response.text()
    query = fixture.repository.calls[-1][1]
    assert query["state"] == "awaiting_student"
    assert query["kind"] == "general"
    assert query["course_public_id"] == "c-1"
    assert query["group_public_id"] == "g-5"
    assert query["cursor"] == "support-http-before"
    assert query["scope"].group_public_ids == frozenset({"g-5"})

    forbidden_scope = await fixture.client.get(
        "/staff/api/v1/questions",
        cookies=_cookie(fixture, "partial", AuthAudience.STAFF),
        headers=_headers(),
    )
    assert forbidden_scope.status == 200
    assert (await forbidden_scope.json())["items"] == []

    duplicated = await fixture.client.get(
        "/staff/api/v1/questions?state=all&state=awaiting_staff",
        cookies=_cookie(fixture, "teacher", AuthAudience.STAFF),
        headers=_headers(),
    )
    assert duplicated.status == 422


@pytest.mark.asyncio
async def test_support_routes_reject_cross_audience_and_non_strict_payloads(
    support_http,
):
    fixture = support_http
    staff_on_student = await fixture.client.post(
        "/student/api/v1/questions",
        json=_create_payload(),
        cookies=_cookie(fixture, "teacher", AuthAudience.STAFF),
        headers=_headers(unsafe=True),
    )
    # Audience cookies are scoped by Path, so the browser does not send a
    # Staff cookie to a Student endpoint at all.
    assert staff_on_student.status == 401

    student_on_staff = await fixture.client.get(
        "/staff/api/v1/questions/sup-1",
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(),
    )
    assert student_on_staff.status == 401

    extra_identity = await fixture.client.post(
        "/student/api/v1/questions",
        json=_create_payload(studentUserId=STUDENT_ID),
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert extra_identity.status == 422
    assert (await extra_identity.json())["error"]["code"] == "validation_error"

    inconsistent = await fixture.client.post(
        "/student/api/v1/questions",
        json=_create_payload(kind="general"),
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert inconsistent.status == 422


@pytest.mark.asyncio
async def test_support_idempotency_conflict_uses_versioned_error_envelope(support_http):
    fixture = support_http
    response = await fixture.client.post(
        "/student/api/v1/questions",
        json=_create_payload(idempotencyKey="support-conflict"),
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )
    assert response.status == 409
    payload = await response.json()
    assert payload["error"] == {
        "code": "idempotency_payload_mismatch",
        "message": "Это действие уже было отправлено с другими данными",
        "requestId": "support.http.test",
    }


@pytest.mark.asyncio
async def test_committed_support_entry_survives_invalidation_failure(
    support_http, caplog
):
    fixture = support_http

    async def fail_invalidation(_targets, _reason):
        raise RuntimeError("synthetic support invalidation outage")

    with pytest.warns(DeprecationWarning):
        fixture.client.server.app[support_routes_module.PWA_SUPPORT_INVALIDATOR] = (
            fail_invalidation
        )
    response = await fixture.client.post(
        "/student/api/v1/questions/sup-1/entries",
        json=_append_payload(idempotencyKey="support-after-live-failure"),
        cookies=_cookie(fixture, "student", AuthAudience.STUDENT),
        headers=_headers(unsafe=True),
    )

    assert response.status == 200, await response.text()
    assert "Support invalidation failed after commit" in caplog.text
