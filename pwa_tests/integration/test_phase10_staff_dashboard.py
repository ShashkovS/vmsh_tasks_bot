"""Real Staff dashboard API over review, support and lesson projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from zoneinfo import ZoneInfo

import pytest
from aiohttp import web

from apps import pwa_app
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from db_methods.pwa.reviews import PwaWrittenReviewQueueRepository
from db_methods.pwa.support import PwaSupportThreadRepository
from helpers.config import Config
from helpers.consts import WRITTEN_STATUS
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience, CredentialHasher
from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    NOW as AUTH_NOW,
    STUDENT_ID,
    TEST_HASHER,
    _auth_config,
    _headers,
    _seed_auth,
)


@dataclass(frozen=True, slots=True)
class DashboardHttpFixture:
    client: object
    cookies: MappingProxyType
    student_cookie: str


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _seed_dashboard(factory: PwaConnectionFactory, *, now: datetime) -> None:
    anchor = now.astimezone(ZoneInfo("Europe/Moscow")).date().isoformat()
    opened_at = _timestamp(now - timedelta(days=1))
    closes_at = _timestamp(now + timedelta(days=1))
    old_question_at = _timestamp(now - timedelta(hours=2))
    lease_expires_at = _timestamp(now + timedelta(minutes=20))

    def seed(connection) -> None:
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
        course_lesson_id = connection.execute(
            "INSERT INTO course_lessons "
            "(public_id, course_id, lesson_number, created_at, updated_at) "
            "VALUES ('dashboard-course-lesson', ?, 41, ?, ?) RETURNING id",
            (course_id, opened_at, opened_at),
        ).fetchone()["id"]
        group_lesson_id = connection.execute(
            "INSERT INTO group_lessons "
            "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "('dashboard-group-lesson', ?, ?, 'layout-beginner', ?, "
            "'Europe/Moscow', 'active', ?, ?) RETURNING id",
            (course_lesson_id, course_id, anchor, opened_at, opened_at),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO lesson_windows "
            "(public_id, group_lesson_id, opens_at, submission_closes_at, "
            "timezone, source, created_at, updated_at) VALUES "
            "('dashboard-window', ?, ?, ?, 'Europe/Moscow', 'native', ?, ?)",
            (group_lesson_id, opened_at, closes_at, opened_at, opened_at),
        )
        source_id = connection.execute(
            "INSERT INTO content_sources "
            "(public_id, group_lesson_id, kind, logical_filename, "
            "source_encoding, created_at) VALUES "
            "('dashboard-condition-source', ?, 'condition', 'condition.tex', "
            "'utf-8', ?) RETURNING id",
            (group_lesson_id, opened_at),
        ).fetchone()["id"]
        revision_id = connection.execute(
            "INSERT INTO content_revisions "
            "(public_id, source_id, revision_number, source_sha256, latex_text, "
            "parser_version, status, canonical_json, diagnostics_json, "
            "provenance_json, created_at) VALUES "
            "('dashboard-condition-revision', ?, 1, ?, 'condition', 'test', "
            "'ready', '{}', '[]', '{}', ?) RETURNING id",
            (source_id, "a" * 64, opened_at),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO lesson_publications "
            "(public_id, group_lesson_id, kind, revision_id, state, published_at, "
            "created_at, updated_at, provenance_kind) VALUES "
            "('dashboard-condition-publication', ?, 'condition', ?, 'published', "
            "?, ?, ?, 'legacy_backfill')",
            (group_lesson_id, revision_id, opened_at, opened_at, opened_at),
        )
        connection.execute(
            "INSERT INTO oral_windows "
            "(public_id, group_lesson_id, sequence_number, opens_at, closes_at, "
            "join_label, join_url, status, created_by_user_id, updated_by_user_id, "
            "created_at, updated_at) VALUES "
            "('dashboard-oral-window', ?, 1, ?, ?, 'Zoom', "
            "'https://zoom.example.test', 'active', ?, ?, ?, ?)",
            (
                group_lesson_id,
                _timestamp(now - timedelta(hours=1)),
                _timestamp(now + timedelta(hours=1)),
                ADMIN_ID,
                ADMIN_ID,
                opened_at,
                opened_at,
            ),
        )
        problem_id = connection.execute(
            "INSERT INTO problems "
            "(group_id, lesson, prob, item, title, prob_text, prob_type, ans_type, "
            "ans_validation, validation_error, cor_ans, wrong_ans, congrat, synonyms) "
            "VALUES ('layout-beginner', 41, 1, '', 'Dashboard problem', '', 2, 0, "
            "'', '', '', '', '', '') RETURNING id"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO written_tasks_queue "
            "(public_id, ts, student_id, problem_id, cur_status, teacher_ts, "
            "teacher_id, claim_token, claimed_at, lease_expires_at, updated_at) "
            "VALUES ('dashboard-review', ?, ?, ?, ?, ?, ?, 'dashboard-claim', ?, ?, ?)",
            (
                opened_at,
                STUDENT_ID,
                problem_id,
                int(WRITTEN_STATUS.BEING_CHECKED),
                opened_at,
                ADMIN_ID,
                opened_at,
                lease_expires_at,
                opened_at,
            ),
        )
        thread_id = connection.execute(
            "INSERT INTO support_threads "
            "(public_id, student_user_id, group_lesson_id, kind, latest_entry_at, "
            "created_at, updated_at) VALUES "
            "('dashboard-question', ?, ?, 'general', ?, ?, ?) RETURNING id",
            (
                STUDENT_ID,
                group_lesson_id,
                old_question_at,
                old_question_at,
                old_question_at,
            ),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO support_entries "
            "(public_id, thread_id, author_kind, author_user_id, text, channel, "
            "client_created_at, server_received_at, created_at) VALUES "
            "('dashboard-question-entry', ?, 'student', ?, 'Нужна помощь', 'pwa', "
            "?, ?, ?)",
            (thread_id, STUDENT_ID, old_question_at, old_question_at, old_question_at),
        )

    factory.run_write(seed)


@pytest.fixture()
async def dashboard_http(tmp_path, aiohttp_client) -> DashboardHttpFixture:
    now = datetime.now(UTC)
    database_path = tmp_path / "dashboard-http.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    _seed_auth(factory)
    _seed_dashboard(factory, now=now)
    auth_config = _auth_config()
    auth_service = await PwaAuthService.create(
        PwaAuthRepository(
            factory,
            clock=lambda: AUTH_NOW,
            credential_hasher=TEST_HASHER,
        ),
        auth_config,
        credential_hasher=CredentialHasher(TEST_HASHER),
        clock=lambda: AUTH_NOW,
    )
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="dashboard-http-test",
        config_name="dashboard_http_test",
        pwa_prototype=True,
        nats_server=None,
    )
    pwa_app.configure(
        app,
        broker=InProcessBroker("dashboard_http_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
        review_queue_repository=PwaWrittenReviewQueueRepository(factory),
        support_repository=PwaSupportThreadRepository(factory),
    )
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    client = await aiohttp_client(app)

    async def login(audience: AuthAudience, username: str, password: str) -> str:
        response = await client.post(
            f"/{audience.value}/api/v1/auth/login",
            json={
                "username": username,
                "telegramToken"
                if audience is AuthAudience.STUDENT
                else "password": password,
            },
            headers=_headers(unsafe=True),
        )
        assert response.status == 200, await response.text()
        cookie = response.cookies[COOKIE_POLICY[audience].access_name].value
        client.session.cookie_jar.clear()
        return cookie

    return DashboardHttpFixture(
        client=client,
        cookies=MappingProxyType(
            {
                "admin": await login(
                    AuthAudience.STAFF, "classroom-http-admin", "admin-password"
                ),
                "teacher": await login(
                    AuthAudience.STAFF, "classroom-http-teacher", "teacher-password"
                ),
            }
        ),
        student_cookie=await login(
            AuthAudience.STUDENT, "classroom-http-student", "student-password"
        ),
    )


def _staff_cookie(fixture: DashboardHttpFixture, identity: str) -> dict[str, str]:
    return {COOKIE_POLICY[AuthAudience.STAFF].access_name: fixture.cookies[identity]}


async def test_admin_and_teacher_receive_scoped_operational_dashboard(
    dashboard_http: DashboardHttpFixture,
) -> None:
    for identity in ("admin", "teacher"):
        response = await dashboard_http.client.get(
            "/staff/api/v1/dashboard",
            headers=_headers(),
            cookies=_staff_cookie(dashboard_http, identity),
        )
        assert response.status == 200, await response.text()
        payload = await response.json()
        assert payload["summary"]["review"] == {
            "totalCases": 1,
            "claimedByOthers": 1 if identity == "teacher" else 0,
        }
        assert payload["summary"]["questions"] == {
            "awaitingStaff": 1,
            "olderThanOneHour": 1,
        }
        assert payload["summary"]["publications"] == {
            "conditionsPublished": 1,
            "groupLessons": 1,
        }
        assert payload["summary"]["oral"] == {
            "openWindows": 1,
            "upcomingWindows": 0,
        }
        assert payload["summary"]["delivery"] == (
            {"failedBatches": 0, "failedRecipients": 0} if identity == "admin" else None
        )
        assert payload["lessons"][0]["phase"] == "active"
        assert payload["lessons"][0]["group"]["groupId"] == "classroom-layout-group"
        assert "studentId" not in str(payload)


async def test_dashboard_rejects_other_audiences_and_query_parameters(
    dashboard_http: DashboardHttpFixture,
) -> None:
    student = await dashboard_http.client.get(
        "/staff/api/v1/dashboard",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[
                AuthAudience.STUDENT
            ].access_name: dashboard_http.student_cookie
        },
    )
    assert student.status == 401

    invalid = await dashboard_http.client.get(
        "/staff/api/v1/dashboard?course=unexpected",
        headers=_headers(),
        cookies=_staff_cookie(dashboard_http, "admin"),
    )
    assert invalid.status == 422
    assert (await invalid.json())["error"]["code"] == "validation_error"
