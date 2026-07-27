"""Real aiohttp/SQLite tests for the bounded Phase-2 content API slice."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType, SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from aiohttp import FormData, web
from argon2 import PasswordHasher

from apps import pwa_app
from apps.pwa_api import content_routes as content_routes_module
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from db_methods.pwa.content import PwaContentRepository
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from models.pwa.auth import AuthAudience, CredentialHasher
from models.pwa.content import ProblemMatchDecision, ProblemRevisionDraft


ORIGIN = "http://127.0.0.1:5380"
HOST = "127.0.0.1:5380"
NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)
TEST_HASHER = PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)
STUDENT_USER_ID = 903_101
TEACHER_USER_ID = 903_102
ADMIN_USER_ID = 903_103


@dataclass(frozen=True, slots=True)
class ContentHttpFixture:
    client: object
    factory: PwaConnectionFactory
    group_lesson_a: str
    group_lesson_b: str
    cookies: MappingProxyType


def _timestamp(value: datetime = NOW) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _local_time(value: datetime) -> str:
    return value.astimezone(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%dT%H:%M")


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


def _seed_content_accounts(factory: PwaConnectionFactory) -> int:
    now = _timestamp()

    def seed(connection):
        connection.execute("DELETE FROM kv_logins")
        connection.executemany(
            "INSERT INTO users (id, public_id, type, name, surname, group_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                (
                    STUDENT_USER_ID,
                    "user-content-student",
                    int(USER_TYPE.STUDENT),
                    "Ирина",
                    "Тестова",
                    None,
                ),
                (
                    TEACHER_USER_ID,
                    "user-content-teacher",
                    int(USER_TYPE.TEACHER),
                    "Тестовый",
                    "Учитель",
                    None,
                ),
                (
                    ADMIN_USER_ID,
                    "user-content-admin",
                    int(USER_TYPE.ADMIN),
                    "Тестовый",
                    "Администратор",
                    None,
                ),
            ),
        )
        season_id = connection.execute(
            "INSERT INTO seasons "
            "(public_id, code, title, starts_on, ends_on, session_expires_on, "
            "status, created_at, updated_at) VALUES "
            "('season-content-http', 'content-http', 'Content HTTP', "
            "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) "
            "RETURNING id",
            (now, now),
        ).fetchone()["id"]
        course_id = connection.execute(
            "INSERT INTO courses "
            "(public_id, season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "('course-content-http', ?, 'math', 'Математика', 'math', 'active', "
            "1, 'math', ?, ?) RETURNING id",
            (season_id, now, now),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, public_id, course_id, status, "
            "created_at, updated_at) VALUES "
            "(?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, ?, 'active', ?, ?)",
            (
                (
                    "content-a",
                    "a",
                    "A",
                    1,
                    "group-content-http-a",
                    course_id,
                    now,
                    now,
                ),
                (
                    "content-b",
                    "b",
                    "B",
                    2,
                    "group-content-http-b",
                    course_id,
                    now,
                    now,
                ),
            ),
        )
        accounts = connection.executemany(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, display_name, "
            "credential_kind, credential_hash, linked_user_id, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'synthetic-test', "
            "?, ?, ?, ?, 'active', ?, ?)",
            (
                (
                    "account-content-student",
                    "student",
                    "content-student",
                    "content-student",
                    1,
                    None,
                    "telegram_token",
                    TEST_HASHER.hash("student-token"),
                    STUDENT_USER_ID,
                    now,
                    now,
                ),
                (
                    "account-content-family",
                    "family",
                    "content-family",
                    "content-family",
                    None,
                    "Синтетическая семья",
                    "password",
                    TEST_HASHER.hash("family-password"),
                    None,
                    now,
                    now,
                ),
                (
                    "account-content-teacher",
                    "staff",
                    "content-teacher",
                    "content-teacher",
                    None,
                    None,
                    "password",
                    TEST_HASHER.hash("teacher-password"),
                    TEACHER_USER_ID,
                    now,
                    now,
                ),
                (
                    "account-content-admin",
                    "staff",
                    "content-admin",
                    "content-admin",
                    None,
                    None,
                    "password",
                    TEST_HASHER.hash("admin-password"),
                    ADMIN_USER_ID,
                    now,
                    now,
                ),
            ),
        )
        del accounts
        family_account_id = connection.execute(
            "SELECT id FROM auth_accounts WHERE public_id = 'account-content-family'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, "
            "is_primary, created_at, updated_at) VALUES (?, ?, 'родитель', 1, ?, ?)",
            (family_account_id, STUDENT_USER_ID, now, now),
        )
        enrollment_id = connection.execute(
            "INSERT INTO course_enrollments "
            "(public_id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) VALUES "
            "('enrollment-content-http', ?, ?, 'content-a', 'online', "
            "'active', ?, ?) RETURNING id",
            (STUDENT_USER_ID, course_id, now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'content-a', ?, ?, ?)",
            (enrollment_id, course_id, now, now, now),
        )
        connection.execute(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'content-a', 'teacher', ?, ?, ?)",
            (TEACHER_USER_ID, course_id, now, now, now),
        )
        return int(course_id)

    return factory.run_write(seed)


@pytest.fixture()
async def content_http(tmp_path, aiohttp_client) -> ContentHttpFixture:
    database_path = tmp_path / "content-http.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    course_id = _seed_content_accounts(factory)
    content_repository = PwaContentRepository(factory, clock=lambda: NOW)
    course_lesson = await content_repository.create_course_lesson(
        public_id="course-lesson-content-http",
        course_id=course_id,
        lesson_number=41,
        title="Занятие 41",
        actor_user_id=ADMIN_USER_ID,
    )
    group_lesson_a = await content_repository.create_group_lesson(
        public_id="group-lesson-content-http-a",
        course_lesson_id=course_lesson.id,
        course_id=course_id,
        group_id="content-a",
        cycle_anchor_date=date(2026, 9, 14),
        business_timezone="Europe/Moscow",
        actor_user_id=ADMIN_USER_ID,
        status="active",
    )
    group_lesson_b = await content_repository.create_group_lesson(
        public_id="group-lesson-content-http-b",
        course_lesson_id=course_lesson.id,
        course_id=course_id,
        group_id="content-b",
        cycle_anchor_date=date(2026, 9, 14),
        business_timezone="Europe/Moscow",
        actor_user_id=ADMIN_USER_ID,
        status="active",
    )
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
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="content-http-test",
        config_name="content_http_test",
        pwa_prototype=True,
        nats_server=None,
    )
    pwa_app.configure(
        app,
        broker=InProcessBroker("content_http_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
        content_repository=content_repository,
    )
    client = await aiohttp_client(app)

    async def login(audience: AuthAudience, username: str, credential: str) -> str:
        field = "telegramToken" if audience is AuthAudience.STUDENT else "password"
        response = await client.post(
            f"/{audience.value}/api/v1/auth/login",
            json={"username": username, field: credential},
            headers=_headers(unsafe=True),
        )
        assert response.status == 200, await response.text()
        cookie = response.cookies[COOKIE_POLICY[audience].access_name].value
        client.session.cookie_jar.clear()
        return cookie

    cookies = {
        "student": await login(
            AuthAudience.STUDENT, "content-student", "student-token"
        ),
        "family": await login(AuthAudience.FAMILY, "content-family", "family-password"),
        "teacher": await login(
            AuthAudience.STAFF, "content-teacher", "teacher-password"
        ),
        "admin": await login(AuthAudience.STAFF, "content-admin", "admin-password"),
    }
    return ContentHttpFixture(
        client=client,
        factory=factory,
        group_lesson_a=group_lesson_a.public_id,
        group_lesson_b=group_lesson_b.public_id,
        cookies=MappingProxyType(cookies),
    )


def _headers(*, unsafe: bool = False, if_match: str | None = None):
    headers = {"Host": HOST, "X-Request-ID": "content.http.test"}
    if unsafe:
        headers.update({"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"})
    if if_match is not None:
        headers["If-Match"] = if_match
    return headers


def _cookie(fixture: ContentHttpFixture, audience: str):
    policy_audience = (
        AuthAudience.STAFF
        if audience in {"admin", "teacher"}
        else AuthAudience(audience)
    )
    return {COOKIE_POLICY[policy_audience].access_name: fixture.cookies[audience]}


async def _upload(
    fixture: ContentHttpFixture,
    *,
    group_lesson: str,
    kind: str,
    filename: str,
    source: bytes,
    identity: str = "admin",
):
    form = FormData()
    form.add_field("groupLessonId", group_lesson)
    form.add_field("kind", kind)
    form.add_field("logicalFilename", filename)
    form.add_field(
        "source",
        source,
        filename=filename,
        content_type="application/x-tex",
    )
    return await fixture.client.post(
        "/staff/api/v1/content/uploads",
        data=form,
        cookies=_cookie(fixture, identity),
        headers=_headers(unsafe=True),
    )


async def _upload_and_compile(
    fixture: ContentHttpFixture,
    *,
    group_lesson: str,
    kind: str,
    filename: str,
    source: str,
):
    uploaded = await _upload(
        fixture,
        group_lesson=group_lesson,
        kind=kind,
        filename=filename,
        source=source.encode(),
    )
    assert uploaded.status == 201, await uploaded.text()
    upload_payload = await uploaded.json()
    compiled = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{upload_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=uploaded.headers["ETag"]),
    )
    assert compiled.status == 200, await compiled.text()
    compiled_payload = await compiled.json()
    await _review_compiled_problem_metadata(
        fixture, revision_public_id=compiled_payload["revisionId"]
    )
    return compiled_payload, compiled.headers["ETag"]


async def _review_compiled_problem_metadata(
    fixture: ContentHttpFixture, *, revision_public_id: str
) -> None:
    """Record the explicit admin review required before a test publication."""

    def create_legacy_problems(connection):
        revision = connection.execute(
            "SELECT revision.id, revision.canonical_json, source.group_lesson_id, "
            "group_lesson.group_id, course_lesson.lesson_number "
            "FROM content_revisions AS revision "
            "JOIN content_sources AS source ON source.id = revision.source_id "
            "JOIN group_lessons AS group_lesson "
            "  ON group_lesson.id = source.group_lesson_id "
            "JOIN course_lessons AS course_lesson "
            "  ON course_lesson.id = group_lesson.course_lesson_id "
            "WHERE revision.public_id = ?",
            (revision_public_id,),
        ).fetchone()
        document = json.loads(revision["canonical_json"])
        rows = []
        for problem in document["problems"]:
            next_problem = connection.execute(
                "SELECT coalesce(max(prob), 0) + 1 AS value FROM problems "
                "WHERE group_id = ? AND lesson = ?",
                (revision["group_id"], revision["lesson_number"]),
            ).fetchone()["value"]
            source_item = problem["source_item"] or str(problem["ordinal"])
            title = problem["source_title"] or f"Задача {problem['ordinal']}"
            problem_id = connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, synonyms) VALUES (?, ?, ?, ?, ?, '', 1, NULL, '') "
                "RETURNING id",
                (
                    revision["group_id"],
                    revision["lesson_number"],
                    next_problem,
                    source_item,
                    title,
                ),
            ).fetchone()["id"]
            rows.append(
                (
                    int(revision["id"]),
                    int(problem_id),
                    int(problem["ordinal"]),
                    source_item,
                    title,
                )
            )
        return rows

    rows = fixture.factory.run_write(create_legacy_problems)
    repository = PwaContentRepository(fixture.factory, clock=lambda: NOW)
    for revision_id, problem_id, ordinal, source_item, title in rows:
        await repository.add_problem_revision(
            content_revision_id=revision_id,
            draft=ProblemRevisionDraft(
                problem_id=problem_id,
                source_ordinal=ordinal,
                source_item=source_item,
                display_number=str(ordinal),
                title=title,
                problem_type=1,
                answer_type=None,
                answer_config={},
                attempt_policy={},
            ),
            decision=ProblemMatchDecision.MANUAL_MATCH,
            actor_user_id=ADMIN_USER_ID,
        )


async def _publish(
    fixture: ContentHttpFixture,
    *,
    group_lesson: str,
    kind: str,
    revision_id: str,
    mode: str = "publish",
    scheduled_local_time: str | None = None,
    expected_id: str | None = None,
    expected_version: int | None = None,
    expected_scheduled_id: str | None = None,
    expected_scheduled_version: int | None = None,
    if_match: str = '"none"',
):
    return await fixture.client.post(
        "/staff/api/v1/publications",
        json={
            "groupLessonId": group_lesson,
            "kind": kind,
            "revisionId": revision_id,
            "mode": mode,
            "scheduledLocalTime": scheduled_local_time,
            "businessTimezone": (
                "Europe/Moscow" if scheduled_local_time is not None else None
            ),
            "expectedCurrentPublicationId": expected_id,
            "expectedCurrentVersion": expected_version,
            "expectedScheduledPublicationId": expected_scheduled_id,
            "expectedScheduledVersion": expected_scheduled_version,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=if_match),
    )


async def _student_read(fixture: ContentHttpFixture, *, group_lesson: str, kind: str):
    return await fixture.client.get(
        f"/student/api/v1/group-lessons/{group_lesson}/content/{kind}",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )


async def _create_lesson_window(
    fixture: ContentHttpFixture,
    *,
    group_lesson: str,
    cutoff: datetime = NOW + timedelta(days=4),
):
    return await fixture.client.post(
        f"/staff/api/v1/group-lessons/{group_lesson}/lesson-window",
        json={
            "opensLocalTime": _local_time(NOW),
            "submissionClosesLocalTime": _local_time(cutoff),
            "hintScheduledLocalTime": None,
            "solutionScheduledLocalTime": _local_time(cutoff),
            "businessTimezone": "Europe/Moscow",
            "confirmSubmissionCutoff": True,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match='"none"'),
    )


async def test_publication_requires_problem_matching_and_reviewed_metadata(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    uploaded = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="review/condition.tex",
        source="\\задача НУЖНА ПРОВЕРКА \\кзадача".encode(),
    )
    assert uploaded.status == 201
    uploaded_payload = await uploaded.json()
    compiled = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{uploaded_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=uploaded.headers["ETag"]),
    )
    assert compiled.status == 200, await compiled.text()
    revision = await compiled.json()

    blocked = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    assert blocked.status == 422
    blocked_error = (await blocked.json())["error"]
    assert blocked_error["code"] == "problem_review_incomplete"
    assert blocked_error["details"] == {
        "expectedProblems": 1,
        "resolvedMatches": 0,
        "reviewedProblems": 0,
        "omittedProblems": 0,
        "structureMatches": False,
    }

    def resolve_match_without_metadata(connection):
        revision_row = connection.execute(
            "SELECT revision.id, source.group_lesson_id, group_lesson.group_id, "
            "course_lesson.lesson_number "
            "FROM content_revisions AS revision "
            "JOIN content_sources AS source ON source.id = revision.source_id "
            "JOIN group_lessons AS group_lesson "
            "  ON group_lesson.id = source.group_lesson_id "
            "JOIN course_lessons AS course_lesson "
            "  ON course_lesson.id = group_lesson.course_lesson_id "
            "WHERE revision.public_id = ?",
            (revision["revisionId"],),
        ).fetchone()
        problem_id = connection.execute(
            "INSERT INTO problems "
            "(group_id, lesson, prob, item, title, prob_text, prob_type, "
            "ans_type, synonyms) VALUES (?, ?, 1, '1', 'Нужна проверка', '', "
            "1, NULL, '') RETURNING id",
            (revision_row["group_id"], revision_row["lesson_number"]),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, "
            "decision, resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
            "VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
            (
                revision_row["id"],
                problem_id,
                ADMIN_USER_ID,
                _timestamp(),
                _timestamp(),
            ),
        )
        return int(revision_row["id"]), int(problem_id)

    revision_id, problem_id = fixture.factory.run_write(
        resolve_match_without_metadata
    )
    metadata_blocked = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    assert metadata_blocked.status == 422
    assert (await metadata_blocked.json())["error"]["details"] == {
        "expectedProblems": 1,
        "resolvedMatches": 1,
        "reviewedProblems": 0,
        "omittedProblems": 0,
        "structureMatches": True,
    }
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, "
            "display_number, title, normalized_title, problem_type, answer_type, "
            "answer_config_json, attempt_policy_json, config_version, created_at, "
            "created_by_user_id) VALUES (?, ?, 1, '1', '1', 'Нужна проверка', "
            "'нужна проверка', 1, NULL, '{}', '{}', 1, ?, ?)",
            (problem_id, revision_id, _timestamp(), ADMIN_USER_ID),
        )
    )
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    assert published.status == 201, await published.text()


async def test_solution_publication_fails_closed_without_submission_cutoff(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    solution, _etag_value = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        filename="cutoff/solution.tex",
        source=("\\задача УСЛОВИЕ \\кзадача\n\\решение РЕШЕНИЕ \\крешение"),
    )
    blocked = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        revision_id=solution["revisionId"],
    )
    assert blocked.status == 422
    assert (await blocked.json())["error"]["code"] == "submission_cutoff_required"

    created = await _create_lesson_window(
        fixture, group_lesson=fixture.group_lesson_a
    )
    assert created.status == 201, await created.text()
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        revision_id=solution["revisionId"],
    )
    assert published.status == 201, await published.text()


async def test_lesson_window_cutoff_has_separate_confirmation_audit_and_etag(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    route = (
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/lesson-window"
    )
    body = {
        "opensLocalTime": _local_time(NOW),
        "submissionClosesLocalTime": _local_time(NOW + timedelta(days=4)),
        "hintScheduledLocalTime": None,
        "solutionScheduledLocalTime": _local_time(NOW + timedelta(days=4)),
        "businessTimezone": "Europe/Moscow",
        "confirmSubmissionCutoff": False,
    }
    unconfirmed = await fixture.client.post(
        route,
        json=body,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match='"none"'),
    )
    assert unconfirmed.status == 422
    assert (await unconfirmed.json())["error"]["code"] == (
        "submission_cutoff_confirmation_required"
    )

    timezone_mismatch = await fixture.client.post(
        route,
        json={
            **body,
            "businessTimezone": "Asia/Nicosia",
            "confirmSubmissionCutoff": True,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match='"none"'),
    )
    assert timezone_mismatch.status == 422
    assert (await timezone_mismatch.json())["error"]["code"] == (
        "business_timezone_mismatch"
    )

    created = await fixture.client.post(
        route,
        json={**body, "confirmSubmissionCutoff": True},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match='"none"'),
    )
    assert created.status == 201, await created.text()
    created_payload = await created.json()
    assert created_payload["businessTimezone"] == "Europe/Moscow"
    assert created_payload["submissionClosesAt"] == _timestamp(
        NOW + timedelta(days=4)
    )
    teacher_read = await fixture.client.get(
        route,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert teacher_read.status == 403

    schedule = await fixture.client.patch(
        f"{route}/schedule",
        json={
            "opensLocalTime": _local_time(NOW - timedelta(hours=1)),
            "hintScheduledLocalTime": _local_time(NOW + timedelta(days=2)),
            "solutionScheduledLocalTime": _local_time(NOW + timedelta(days=5)),
            "businessTimezone": "Europe/Moscow",
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=created.headers["ETag"]),
    )
    assert schedule.status == 200, await schedule.text()
    schedule_payload = await schedule.json()
    assert schedule_payload["submissionClosesAt"] == created_payload[
        "submissionClosesAt"
    ]

    unconfirmed_cutoff = await fixture.client.patch(
        f"{route}/submission-cutoff",
        json={
            "submissionClosesLocalTime": _local_time(NOW + timedelta(days=6)),
            "businessTimezone": "Europe/Moscow",
            "confirmChange": False,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=schedule.headers["ETag"]),
    )
    assert unconfirmed_cutoff.status == 422

    cutoff = await fixture.client.patch(
        f"{route}/submission-cutoff",
        json={
            "submissionClosesLocalTime": _local_time(NOW + timedelta(days=6)),
            "businessTimezone": "Europe/Moscow",
            "confirmChange": True,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=schedule.headers["ETag"]),
    )
    assert cutoff.status == 200, await cutoff.text()
    assert (await cutoff.json())["submissionClosesAt"] == _timestamp(
        NOW + timedelta(days=6)
    )

    stale = await fixture.client.patch(
        f"{route}/submission-cutoff",
        json={
            "submissionClosesLocalTime": _local_time(NOW + timedelta(days=7)),
            "businessTimezone": "Europe/Moscow",
            "confirmChange": True,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=schedule.headers["ETag"]),
    )
    assert stale.status == 409
    audit = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT change_kind, actor_user_id, request_id "
            "FROM lesson_window_changes ORDER BY id"
        ).fetchall()
    )
    assert audit == [
        {
            "change_kind": "created",
            "actor_user_id": ADMIN_USER_ID,
            "request_id": "content.http.test",
        },
        {
            "change_kind": "schedule_changed",
            "actor_user_id": ADMIN_USER_ID,
            "request_id": "content.http.test",
        },
        {
            "change_kind": "submission_cutoff_changed",
            "actor_user_id": ADMIN_USER_ID,
            "request_id": "content.http.test",
        },
    ]
    with pytest.raises(sqlite3.IntegrityError, match="lesson window audit is immutable"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE lesson_window_changes SET request_id = 'tampered' "
                "WHERE change_kind = 'created'"
            )
        )


async def test_staff_content_history_is_bounded_per_material_kind(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    revision, _etag_value = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="history/condition.tex",
        source="\\задача ИСТОРИЯ \\кзадача",
    )

    def append_history(connection):
        source_id = connection.execute(
            "SELECT source_id FROM content_revisions WHERE public_id = ?",
            (revision["revisionId"],),
        ).fetchone()["source_id"]
        connection.executemany(
            "INSERT INTO content_revisions "
            "(public_id, source_id, revision_number, source_sha256, latex_text, "
            "parser_version, status, diagnostics_json, provenance_json, "
            "created_by_user_id, created_at) "
            "VALUES (?, ?, ?, ?, 'invalid', 'test', 'invalid', '[]', '{}', ?, ?)",
            (
                (
                    f"revision-history-{number}",
                    source_id,
                    number,
                    f"{number:064x}",
                    ADMIN_USER_ID,
                    _timestamp(),
                )
                for number in range(2, 262)
            ),
        )

    fixture.factory.run_write(append_history)
    history = await fixture.client.get(
        "/staff/api/v1/publications",
        params={"groupLesson": fixture.group_lesson_a},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert history.status == 200, await history.text()
    revisions = (await history.json())["materials"][0]["revisions"]
    assert len(revisions) == 250
    assert revisions[0]["revisionNumber"] == 261
    assert revisions[-1]["revisionNumber"] == 12


async def test_upload_compile_preview_and_three_material_publications_are_independent(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    source = (
        "\\задача УСЛОВИЕ_ТОЛЬКО \\кзадача\n"
        "\\ответ ОТВЕТ_ТОЛЬКО \\кответ\n"
        "\\подсказка ПОДСКАЗКА_ТОЛЬКО \\кподсказка\n"
        "\\решение РЕШЕНИЕ_ТОЛЬКО \\крешение"
    )
    condition, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="lesson/condition.tex",
        source=source,
    )
    hint, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        filename="lesson/hint.tex",
        source=source,
    )
    solution, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        filename="lesson/solution.tex",
        source=source,
    )
    window = await _create_lesson_window(
        fixture, group_lesson=fixture.group_lesson_a
    )
    assert window.status == 201, await window.text()

    condition_preview = await fixture.client.get(
        f"/staff/api/v1/content/revisions/{condition['revisionId']}/previews/web",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert condition_preview.status == 200
    preview_text = json.dumps(await condition_preview.json(), ensure_ascii=False)
    assert "УСЛОВИЕ_ТОЛЬКО" in preview_text
    assert all(
        secret not in preview_text
        for secret in ("ОТВЕТ_ТОЛЬКО", "ПОДСКАЗКА_ТОЛЬКО", "РЕШЕНИЕ_ТОЛЬКО")
    )
    telegram_preview = await fixture.client.get(
        f"/staff/api/v1/content/revisions/{condition['revisionId']}/previews/telegram",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert telegram_preview.status == 200
    assert "УСЛОВИЕ_ТОЛЬКО" in (await telegram_preview.json())["html"]

    published_condition = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=condition["revisionId"],
    )
    published_hint = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        revision_id=hint["revisionId"],
    )
    scheduled_solution = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        revision_id=solution["revisionId"],
        mode="schedule",
        scheduled_local_time=_local_time(NOW + timedelta(days=5)),
    )
    assert published_condition.status == published_hint.status == 201
    assert scheduled_solution.status == 201
    scheduled_solution_payload = await scheduled_solution.json()
    assert scheduled_solution_payload["state"] == "scheduled"

    student_condition = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="condition"
    )
    student_hint = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="hint"
    )
    student_solution_before_publish = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="solution"
    )
    assert student_condition.status == student_hint.status == 200
    assert student_solution_before_publish.status == 404
    condition_wire = json.dumps(await student_condition.json(), ensure_ascii=False)
    hint_wire = json.dumps(await student_hint.json(), ensure_ascii=False)
    assert "УСЛОВИЕ_ТОЛЬКО" in condition_wire
    assert "ПОДСКАЗКА_ТОЛЬКО" in hint_wire
    assert "РЕШЕНИЕ_ТОЛЬКО" not in condition_wire
    assert "РЕШЕНИЕ_ТОЛЬКО" not in hint_wire
    assert "diagnostics" not in condition_wire
    assert "canonical" not in condition_wire
    assert "telegram" not in condition_wire.casefold()

    family = await fixture.client.get(
        f"/family/api/v1/children/user-content-student/group-lessons/"
        f"{fixture.group_lesson_a}/content/condition",
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert family.status == 200
    assert (await family.json())["revisionId"] == condition["revisionId"]

    published_solution = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        revision_id=solution["revisionId"],
        expected_scheduled_id=scheduled_solution_payload["publicationId"],
        expected_scheduled_version=scheduled_solution_payload["version"],
    )
    assert published_solution.status == 201
    scheduled_state = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT state FROM lesson_publications WHERE public_id = ?",
            (scheduled_solution_payload["publicationId"],),
        ).fetchone()["state"]
    )
    assert scheduled_state == "superseded"
    student_solution = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="solution"
    )
    solution_wire = json.dumps(await student_solution.json(), ensure_ascii=False)
    assert all(
        value in solution_wire
        for value in ("УСЛОВИЕ_ТОЛЬКО", "ОТВЕТ_ТОЛЬКО", "РЕШЕНИЕ_ТОЛЬКО")
    )
    assert "ПОДСКАЗКА_ТОЛЬКО" not in solution_wire

    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT kind, count(*) AS count FROM content_derivatives "
            "WHERE invalidated_at IS NULL GROUP BY kind ORDER BY kind"
        ).fetchall()
    )
    assert counts == [
        {"kind": "telegram_html", "count": 3},
        {"kind": "web_ast", "count": 3},
        {"kind": "web_html", "count": 3},
    ]
    actor_ids = fixture.factory.run_read(
        lambda connection: {
            "sources": connection.execute(
                "SELECT DISTINCT created_by_user_id AS actor FROM content_sources"
            ).fetchall(),
            "revisions": connection.execute(
                "SELECT DISTINCT created_by_user_id AS actor FROM content_revisions"
            ).fetchall(),
            "publications": connection.execute(
                "SELECT DISTINCT created_by_user_id AS actor FROM lesson_publications"
            ).fetchall(),
        }
    )
    assert actor_ids == {
        "sources": [{"actor": ADMIN_USER_ID}],
        "revisions": [{"actor": ADMIN_USER_ID}],
        "publications": [{"actor": ADMIN_USER_ID}],
    }


async def test_publish_current_conflict_and_exact_revision_rollback(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    first, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="rollback/first.tex",
        source="\\задача ПЕРВАЯ_ВЕРСИЯ \\кзадача",
    )
    second, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="rollback/first.tex",
        source="\\задача ВТОРАЯ_ВЕРСИЯ \\кзадача",
    )
    assert second["sourceId"] == first["sourceId"]
    assert (first["revisionNumber"], second["revisionNumber"]) == (1, 2)

    split_lineage = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="rollback/different-name.tex",
        source="\\задача ТРЕТЬЯ_ВЕРСИЯ \\кзадача".encode(),
    )
    assert split_lineage.status == 409
    assert (await split_lineage.json())["error"]["code"] == "source_lineage_conflict"
    first_publication = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=first["revisionId"],
    )
    first_publication_payload = await first_publication.json()
    second_publication = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=second["revisionId"],
        expected_id=first_publication_payload["publicationId"],
        expected_version=first_publication_payload["version"],
        if_match=first_publication.headers["ETag"],
    )
    assert second_publication.status == 201, await second_publication.text()
    second_publication_payload = await second_publication.json()

    stale = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=first["revisionId"],
        expected_id=first_publication_payload["publicationId"],
        expected_version=first_publication_payload["version"],
        if_match=first_publication.headers["ETag"],
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"

    current = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="condition"
    )
    assert "ВТОРАЯ_ВЕРСИЯ" in json.dumps(await current.json(), ensure_ascii=False)

    rollback = await fixture.client.post(
        f"/staff/api/v1/publications/{second_publication_payload['publicationId']}/rollback",
        json={
            "revisionId": first["revisionId"],
            "expectedScheduledPublicationId": None,
            "expectedScheduledVersion": None,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=second_publication.headers["ETag"]),
    )
    assert rollback.status == 201, await rollback.text()
    rolled_back = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="condition"
    )
    rolled_back_payload = await rolled_back.json()
    assert rolled_back_payload["revisionId"] == first["revisionId"]
    assert "ПЕРВАЯ_ВЕРСИЯ" in json.dumps(rolled_back_payload, ensure_ascii=False)

    stale_rollback = await fixture.client.post(
        f"/staff/api/v1/publications/{second_publication_payload['publicationId']}/rollback",
        json={
            "revisionId": first["revisionId"],
            "expectedScheduledPublicationId": None,
            "expectedScheduledVersion": None,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=second_publication.headers["ETag"]),
    )
    assert stale_rollback.status == 409

    history = await fixture.client.get(
        "/staff/api/v1/publications",
        params={"groupLesson": fixture.group_lesson_a},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert history.status == 200, await history.text()
    history_payload = await history.json()
    assert "InternalId" not in json.dumps(history_payload, ensure_ascii=False)
    assert history_payload["businessTimezone"] == "Europe/Moscow"
    condition_state = history_payload["materials"][0]
    assert [item["revisionNumber"] for item in condition_state["revisions"]] == [2, 1]
    assert condition_state["currentPublished"]["revisionId"] == first["revisionId"]
    assert len(condition_state["publicationHistory"]) == 3


async def test_schedule_can_be_cancelled_explicitly(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    revision, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        filename="schedule/hint.tex",
        source=("\\задача УСЛОВИЕ \\кзадача\n\\подсказка ОТЛОЖЕННАЯ \\кподсказка"),
    )
    scheduled = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        revision_id=revision["revisionId"],
        mode="schedule",
        scheduled_local_time=_local_time(NOW + timedelta(days=1)),
    )
    assert scheduled.status == 201
    scheduled_payload = await scheduled.json()
    cancelled = await fixture.client.post(
        f"/staff/api/v1/publications/{scheduled_payload['publicationId']}/cancel",
        json={},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=scheduled.headers["ETag"]),
    )
    assert cancelled.status == 200, await cancelled.text()
    assert (await cancelled.json())["action"] == "cancelled"

    history = await fixture.client.get(
        "/staff/api/v1/publications",
        params={"groupLesson": fixture.group_lesson_a},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    hint_state = (await history.json())["materials"][1]
    assert hint_state["currentScheduled"] is None
    assert hint_state["publicationHistory"][0]["state"] == "superseded"


async def test_unexpected_compiler_failure_is_redacted_and_terminal(
    content_http: ContentHttpFixture,
    monkeypatch,
):
    fixture = content_http
    uploaded = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="internal-error/condition.tex",
        source=b"\\problem harmless \\endproblem",
    )
    assert uploaded.status == 201
    uploaded_payload = await uploaded.json()

    def fail_compiler(*_args, **_kwargs):
        raise RuntimeError("SECRET_INTERNAL_COMPILER_DETAIL")

    monkeypatch.setattr(content_routes_module, "compile_latex", fail_compiler)
    compiled = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{uploaded_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=uploaded.headers["ETag"]),
    )
    assert compiled.status == 422
    payload = await compiled.json()
    assert payload["error"]["details"]["status"] == "invalid"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "compiler.internal_error" in serialized
    assert "SECRET_INTERNAL_COMPILER_DETAIL" not in serialized


async def test_invalid_compile_is_terminal_and_cannot_publish_or_mutate(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    uploaded = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="invalid/condition.tex",
        source=b"\\problem UNKNOWN \\endproblem",
    )
    assert uploaded.status == 201
    uploaded_payload = await uploaded.json()
    stale_compile = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{uploaded_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match='"wrong:v1"'),
    )
    assert stale_compile.status == 409

    compiled = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{uploaded_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=uploaded.headers["ETag"]),
    )
    assert compiled.status == 422
    compile_error = await compiled.json()
    assert compile_error["error"]["code"] == "content_compile_invalid"
    assert compile_error["error"]["details"]["status"] == "invalid"
    invalid_etag = compiled.headers["ETag"]

    publication = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=uploaded_payload["revisionId"],
    )
    assert publication.status == 422
    assert (await publication.json())["error"]["code"] == "revision_not_publishable"

    compile_again = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{uploaded_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=invalid_etag),
    )
    assert compile_again.status == 409
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE content_revisions SET latex_text = 'changed' "
                "WHERE public_id = ?",
                (uploaded_payload["revisionId"],),
            )
        )


async def test_teacher_wrong_audience_group_scope_and_request_limit_fail_closed(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    teacher = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="forbidden/teacher.tex",
        source="\\задача teacher \\кзадача".encode(),
        identity="teacher",
    )
    assert teacher.status == 403
    assert (await teacher.json())["error"]["code"] == "forbidden"

    wrong_audience = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="forbidden/student.tex",
        source="\\задача student \\кзадача".encode(),
        identity="student",
    )
    assert wrong_audience.status == 401

    group_b, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_b,
        kind="condition",
        filename="scope/group-b.tex",
        source="\\задача ЧУЖАЯ_ГРУППА \\кзадача",
    )
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_b,
        kind="condition",
        revision_id=group_b["revisionId"],
    )
    assert published.status == 201
    student_forbidden = await _student_read(
        fixture, group_lesson=fixture.group_lesson_b, kind="condition"
    )
    assert student_forbidden.status == 403
    family_forbidden = await fixture.client.get(
        f"/family/api/v1/children/user-content-student/group-lessons/"
        f"{fixture.group_lesson_b}/content/condition",
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert family_forbidden.status == 403

    oversized = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="limits/too-large.tex",
        source=b"x" * (512 * 1024 + 1),
    )
    assert oversized.status == 413
    assert (await oversized.json())["error"]["code"] == "payload_too_large"

    forbidden_sources = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM content_sources "
            "WHERE logical_filename LIKE 'forbidden/%'"
        ).fetchone()["count"]
    )
    assert forbidden_sources == 0


async def test_invalid_trusted_compiler_result_fails_closed_as_terminal_invalid(
    content_http: ContentHttpFixture,
    monkeypatch,
):
    fixture = content_http
    uploaded = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="invalid-result/condition.tex",
        source=b"\\problem harmless \\endproblem",
    )
    assert uploaded.status == 201
    uploaded_payload = await uploaded.json()

    monkeypatch.setattr(
        content_routes_module,
        "compile_latex",
        lambda *_args, **_kwargs: SimpleNamespace(
            diagnostics=[],
            ast={"type": "document", "children": []},
            has_errors=False,
            web_document=SimpleNamespace(
                content='{"contractVersion":999}', renderer_version="invalid-v1"
            ),
            web=SimpleNamespace(content="<p>unsafe</p>", renderer_version="invalid-v1"),
            telegram=SimpleNamespace(
                content="<p>unsafe</p>", renderer_version="invalid-v1"
            ),
            ast_sha256="0" * 64,
        ),
    )
    response = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{uploaded_payload['revisionId']}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=uploaded.headers["ETag"]),
    )

    assert response.status == 422
    payload = await response.json()
    assert payload["error"]["details"]["status"] == "invalid"
    assert "compiler.internal_error" in json.dumps(payload, ensure_ascii=False)
    derivative_count = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM content_derivatives AS derivative "
            "JOIN content_revisions AS revision ON revision.id = derivative.revision_id "
            "WHERE revision.public_id = ?",
            (uploaded_payload["revisionId"],),
        ).fetchone()["count"]
    )
    assert derivative_count == 0


async def test_rollback_requires_and_atomically_cancels_exact_pending_schedule(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    first, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="rollback-schedule/condition.tex",
        source="\\задача ПЕРВАЯ \\кзадача",
    )
    second, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="rollback-schedule/condition.tex",
        source="\\задача ВТОРАЯ \\кзадача",
    )
    current = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=first["revisionId"],
    )
    current_payload = await current.json()
    scheduled = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=second["revisionId"],
        mode="schedule",
        scheduled_local_time=_local_time(NOW + timedelta(days=1)),
    )
    scheduled_payload = await scheduled.json()

    stale = await fixture.client.post(
        f"/staff/api/v1/publications/{current_payload['publicationId']}/rollback",
        json={
            "revisionId": second["revisionId"],
            "expectedScheduledPublicationId": scheduled_payload["publicationId"],
            "expectedScheduledVersion": scheduled_payload["version"] + 1,
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=current.headers["ETag"]),
    )
    assert stale.status == 409

    rollback = await fixture.client.post(
        f"/staff/api/v1/publications/{current_payload['publicationId']}/rollback",
        json={
            "revisionId": second["revisionId"],
            "expectedScheduledPublicationId": scheduled_payload["publicationId"],
            "expectedScheduledVersion": scheduled_payload["version"],
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=current.headers["ETag"]),
    )
    assert rollback.status == 201, await rollback.text()
    states = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id, state FROM lesson_publications ORDER BY id"
        ).fetchall()
    )
    assert [row["state"] for row in states] == [
        "superseded",
        "superseded",
        "published",
    ]


async def test_hide_commit_succeeds_when_live_invalidation_transport_fails(
    content_http: ContentHttpFixture,
    caplog,
):
    fixture = content_http
    revision, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="hide/condition.tex",
        source="\\задача СКРЫТЬ \\кзадача",
    )
    publication = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    publication_payload = await publication.json()

    async def fail_invalidation(_scope, _kind, _reason):
        raise RuntimeError("synthetic invalidation outage")

    with pytest.warns(DeprecationWarning):
        fixture.client.server.app[content_routes_module.PWA_CONTENT_INVALIDATOR] = (
            fail_invalidation
        )
    hidden = await fixture.client.post(
        f"/staff/api/v1/publications/{publication_payload['publicationId']}/hide",
        json={},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=publication.headers["ETag"]),
    )

    assert hidden.status == 200, await hidden.text()
    assert (await hidden.json())["action"] == "hidden"
    assert "Content invalidation failed after commit" in caplog.text
    student = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="condition"
    )
    assert student.status == 404
