"""Real aiohttp/SQLite tests for the bounded Phase-2 content API slice."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
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
from db_methods.pwa.reviews import PwaWrittenReviewQueueRepository
from db_methods.pwa.submissions import PwaTestSubmissionRepository
from db_methods.pwa.written_submissions import PwaWrittenSubmissionRepository
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.object_storage import content_addressed_key
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from helpers.pwa.content import (
    AssetConversionError,
    ContentAssetConverter,
    ContentAssetService,
    ConvertedAsset,
)
from helpers.pwa.content.pdf import PDF_RENDERER_VERSION
from helpers.pwa.content.pdf_service import (
    PDF_STORAGE_CONVERSION_VERSION,
    PDF_STORAGE_NAMESPACE,
)
from helpers.pwa.written_attachments import WrittenAttachmentService
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
SAFE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" '
    b'width="40" height="20" viewBox="0 0 40 20"/>'
)


class SyntheticAssetConverter:
    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        output = b"synthetic-webp:" + hashlib.sha256(payload).digest()
        return ConvertedAsset(
            source_sha256=hashlib.sha256(payload).hexdigest(),
            output_sha256=hashlib.sha256(output).hexdigest(),
            media_type="image/webp",
            data=output,
            width=320,
            height=240,
        )

    async def svg_to_svg(self, payload: bytes) -> ConvertedAsset:
        # Exercise the real presentation-only SVG sanitizer in HTTP tests.
        return await ContentAssetConverter.svg_to_svg(self, payload)  # type: ignore[arg-type]

    async def tikz_to_svg(self, source: str) -> ConvertedAsset:
        sanitized = await ContentAssetConverter.svg_to_svg(  # type: ignore[arg-type]
            self, SAFE_SVG
        )
        return ConvertedAsset(
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            output_sha256=sanitized.output_sha256,
            media_type="image/svg+xml",
            data=sanitized.data,
            width=sanitized.width,
            height=sanitized.height,
        )


@dataclass
class MemoryAssetStorage:
    objects: dict[str, bytes] = field(default_factory=dict)
    puts: list[str] = field(default_factory=list)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        self.puts.append(key)
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def public_url(self, key: str) -> None:
        del key
        return None


@dataclass(frozen=True, slots=True)
class ContentHttpFixture:
    client: object
    factory: PwaConnectionFactory
    group_lesson_a: str
    group_lesson_b: str
    cookies: MappingProxyType
    asset_storage: MemoryAssetStorage


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
    test_submission_repository = PwaTestSubmissionRepository(factory, clock=lambda: NOW)
    written_submission_repository = PwaWrittenSubmissionRepository(
        factory, clock=lambda: NOW
    )
    review_queue_repository = PwaWrittenReviewQueueRepository(
        factory,
        clock=lambda: NOW,
        claim_token_factory=lambda: "content-http-family-review-claim",
        review_public_id_factory=lambda: "content-http-family-review",
        annotation_public_id_factory=lambda: "content-http-family-annotation",
        comment_public_id_factory=lambda: "content-http-family-comment",
        event_public_id_factory=lambda: "content-http-family-review-event",
        internal_reaction_event_public_id_factory=(
            lambda: "content-http-family-reaction-event"
        ),
    )
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
    asset_storage = MemoryAssetStorage()
    asset_converter = SyntheticAssetConverter()
    asset_service = ContentAssetService(
        converter=asset_converter,  # type: ignore[arg-type]
        storage=asset_storage,
        repository=content_repository,
    )
    written_object_tokens = iter("23456789abcdef")
    written_attachment_service = WrittenAttachmentService(
        converter=asset_converter,  # type: ignore[arg-type]
        storage=asset_storage,
        repository=written_submission_repository,
        clock=lambda: NOW,
        object_token_factory=lambda: next(written_object_tokens) * 32,
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
        test_submission_repository=test_submission_repository,
        written_submission_repository=written_submission_repository,
        review_queue_repository=review_queue_repository,
        written_attachment_service=written_attachment_service,
        content_asset_service=asset_service,
    )
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
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
        asset_storage=asset_storage,
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
    form = FormData(default_to_multipart=True)
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


async def _upload_asset(
    fixture: ContentHttpFixture,
    *,
    revision_id: str,
    logical_name: str,
    kind: str,
    if_match: str | None,
    payload: bytes | None = None,
    filename: str | None = None,
    identity: str = "admin",
):
    form = FormData(default_to_multipart=True)
    form.add_field("logicalName", logical_name)
    form.add_field("kind", kind)
    if payload is not None:
        form.add_field(
            "asset",
            payload,
            filename=filename or logical_name.rsplit("/", 1)[-1],
            content_type=("image/svg+xml" if kind == "svg" else "image/heic"),
        )
    return await fixture.client.post(
        f"/staff/api/v1/content/revisions/{revision_id}/assets",
        data=form,
        cookies=_cookie(fixture, identity),
        headers=_headers(unsafe=True, if_match=if_match),
    )


async def _upload_and_compile(
    fixture: ContentHttpFixture,
    *,
    group_lesson: str,
    kind: str,
    filename: str,
    source: str,
    review: bool = True,
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
    if review:
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
            "source.kind, group_lesson.group_id, course_lesson.lesson_number "
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
            source_item = problem["source_item"] or str(problem["ordinal"])
            existing_condition = (
                None
                if revision["kind"] == "condition"
                else connection.execute(
                    "SELECT problem.id, problem.title "
                    "FROM problem_revisions AS problem_revision "
                    "JOIN content_revisions AS candidate_revision "
                    "  ON candidate_revision.id = problem_revision.content_revision_id "
                    "JOIN content_sources AS candidate_source "
                    "  ON candidate_source.id = candidate_revision.source_id "
                    "JOIN problems AS problem ON problem.id = problem_revision.problem_id "
                    "WHERE candidate_source.group_lesson_id = ? "
                    "  AND candidate_source.kind = 'condition' "
                    "  AND problem_revision.source_ordinal = ? "
                    "  AND problem_revision.source_item = ? "
                    "ORDER BY candidate_revision.revision_number DESC, "
                    "candidate_revision.id DESC LIMIT 1",
                    (
                        revision["group_lesson_id"],
                        problem["ordinal"],
                        source_item,
                    ),
                ).fetchone()
            )
            if existing_condition is not None:
                rows.append(
                    (
                        int(revision["id"]),
                        int(existing_condition["id"]),
                        int(problem["ordinal"]),
                        source_item,
                        str(existing_condition["title"]),
                    )
                )
                continue
            next_problem = connection.execute(
                "SELECT coalesce(max(prob), 0) + 1 AS value FROM problems "
                "WHERE group_id = ? AND lesson = ?",
                (revision["group_id"], revision["lesson_number"]),
            ).fetchone()["value"]
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


async def _student_reveal(
    fixture: ContentHttpFixture,
    *,
    group_lesson: str,
    problem_id: str,
    kind: str,
):
    return await fixture.client.post(
        f"/student/api/v1/group-lessons/{group_lesson}/problems/"
        f"{problem_id}/reveal/{kind}",
        json={},
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
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


async def _prepare_published_test_problem(
    fixture: ContentHttpFixture,
    *,
    correct_answer: str | None = "7",
    correct_answer_checker: str | None = None,
    problem_type: int = 1,
) -> tuple[str, str]:
    """Use the real Staff content API to create one submit-ready problem."""

    revision, _compile_etag = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="submissions/condition.tex",
        source="\\задача[title=Целое число] Введите число 7. \\кзадача",
        review=False,
    )
    match_url = (
        f"/staff/api/v1/content/revisions/{revision['revisionId']}/problem-matches"
    )
    initial_response = await fixture.client.get(
        match_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert initial_response.status == 200, await initial_response.text()
    initial = await initial_response.json()
    item = initial["items"][0]
    matched_response = await fixture.client.put(
        match_url,
        json={
            "matches": [
                {
                    "sourceOrdinal": item["sourceOrdinal"],
                    "sourceItem": item["sourceItem"],
                    "decision": "insert_new",
                    "problemId": None,
                }
            ]
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert matched_response.status == 200, await matched_response.text()
    problem_id = (await matched_response.json())["items"][0]["match"]["problemId"]
    problem_public_id = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id FROM problems WHERE id = ?", (problem_id,)
        ).fetchone()["public_id"]
    )

    grid_url = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/metadata-grid"
    grid_response = await fixture.client.get(
        grid_url,
        params={"revisionId": revision["revisionId"]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert grid_response.status == 200, await grid_response.text()
    grid = await grid_response.json()
    row = grid["rows"][0]
    row.update(
        {
            "title": ("Целое число" if problem_type == 1 else "Письменная задача"),
            "problemType": problem_type,
            "answerType": 3 if problem_type == 1 else None,
            "answerValidation": None,
            "validationError": (
                "Введите целое число, например -7" if problem_type == 1 else None
            ),
            "correctAnswer": correct_answer if problem_type == 1 else None,
            "correctAnswerChecker": (
                correct_answer_checker if problem_type == 1 else None
            ),
            "wrongAnswer": "Нет, это другое число." if problem_type == 1 else None,
            "congratulation": "Да, всё верно!" if problem_type == 1 else None,
        }
    )
    row.pop("reviewed")
    saved = await fixture.client.put(
        grid_url,
        json={"revisionId": revision["revisionId"], "rows": [row]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=grid_response.headers["ETag"]),
    )
    assert saved.status == 200, await saved.text()

    window = await _create_lesson_window(
        fixture,
        group_lesson=fixture.group_lesson_a,
    )
    assert window.status == 201, await window.text()
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    assert published.status == 201, await published.text()
    return str(problem_public_id), str(revision["revisionId"])


def _insert_second_written_problem(
    fixture: ContentHttpFixture,
    *,
    condition_revision_public_id: str,
) -> str:
    """Add a second concrete written task to the same published lesson."""

    now = _timestamp()

    def insert(connection):
        revision = connection.execute(
            "SELECT id FROM content_revisions WHERE public_id = ?",
            (condition_revision_public_id,),
        ).fetchone()
        problem_public_id = "problem-content-http-written-target"
        problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, ans_validation, validation_error, cor_ans, "
                "cor_ans_checker, wrong_ans, congrat, synonyms, public_id) "
                "VALUES ('content-a', 41, 2, '', 'Целевая письменная задача', "
                "'', 2, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '', ?) "
                "RETURNING id",
                (problem_public_id,),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, "
            "decision, resolved_at, diagnostics_json, created_at) "
            "VALUES (?, 2, '2', ?, 'insert_new', ?, '[]', ?)",
            (revision["id"], problem_id, now, now),
        )
        connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, "
            "display_number, title, normalized_title, problem_type, answer_type, "
            "answer_config_json, attempt_policy_json, config_version, created_at) "
            "VALUES (?, ?, 2, '2', '2', 'Целевая письменная задача', "
            "'целевая письменная задача', 2, NULL, '{}', '{}', 1, ?)",
            (problem_id, revision["id"], now),
        )
        return problem_public_id

    return str(fixture.factory.run_write(insert))


async def _publish_repaired_test_problem(
    fixture: ContentHttpFixture,
    *,
    problem_public_id: str,
    correct_answer: str | None,
    correct_answer_checker: str | None = None,
) -> tuple[str, int]:
    """Publish a new immutable condition revision for an existing problem."""

    revision, _compile_etag = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="submissions/condition.tex",
        source="\\задача[title=Целое число] Введите число 179. \\кзадача",
        review=False,
    )
    problem_id = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT id FROM problems WHERE public_id = ?", (problem_public_id,)
        ).fetchone()["id"]
    )
    match_url = (
        f"/staff/api/v1/content/revisions/{revision['revisionId']}/problem-matches"
    )
    initial_response = await fixture.client.get(
        match_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert initial_response.status == 200, await initial_response.text()
    item = (await initial_response.json())["items"][0]
    matched = await fixture.client.put(
        match_url,
        json={
            "matches": [
                {
                    "sourceOrdinal": item["sourceOrdinal"],
                    "sourceItem": item["sourceItem"],
                    "decision": "manual_match",
                    "problemId": problem_id,
                }
            ]
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert matched.status == 200, await matched.text()

    grid_url = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/metadata-grid"
    grid_response = await fixture.client.get(
        grid_url,
        params={"revisionId": revision["revisionId"]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert grid_response.status == 200, await grid_response.text()
    row = (await grid_response.json())["rows"][0]
    row.update(
        {
            "title": "Целое число",
            "problemType": 1,
            "answerType": 3,
            "answerValidation": None,
            "validationError": "Введите целое число, например -7",
            "correctAnswer": correct_answer,
            "correctAnswerChecker": correct_answer_checker,
            "wrongAnswer": "Нет, это другое число.",
            "congratulation": "Да, всё верно!",
        }
    )
    row.pop("reviewed")
    saved = await fixture.client.put(
        grid_url,
        json={"revisionId": revision["revisionId"], "rows": [row]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=grid_response.headers["ETag"]),
    )
    assert saved.status == 200, await saved.text()
    current = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id, version FROM lesson_publications "
            "WHERE group_lesson_id = (SELECT id FROM group_lessons WHERE public_id = ?) "
            "AND kind = 'condition' AND state = 'published'",
            (fixture.group_lesson_a,),
        ).fetchone()
    )
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
        expected_id=current["public_id"],
        expected_version=current["version"],
        if_match=f'"{current["public_id"]}:v{current["version"]}"',
    )
    assert published.status == 201, await published.text()
    config_version = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT config_version FROM problem_revisions "
            "WHERE content_revision_id = (SELECT id FROM content_revisions WHERE public_id = ?) "
            "AND problem_id = ?",
            (revision["revisionId"], problem_id),
        ).fetchone()["config_version"]
    )
    return str(revision["revisionId"]), int(config_version)


async def test_student_test_submission_http_is_strict_idempotent_and_readable(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture
    )
    route = f"/student/api/v1/problems/{problem_public_id}/test-attempts"
    payload = {
        "schemaVersion": 1,
        "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac05",
        "problemRevision": {
            "conditionRevisionId": condition_revision_id,
            "configVersion": 1,
        },
        "displayAnswer": " 7 ",
        "clientCreatedAt": _timestamp(),
    }

    missing_origin = await fixture.client.post(
        route,
        json=payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert missing_origin.status == 403

    invalid_identity = await fixture.client.post(
        route,
        json={**payload, "studentId": "user-content-student"},
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert invalid_identity.status == 422

    invalid_version = await fixture.client.post(
        route,
        json={**payload, "schemaVersion": True},
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert invalid_version.status == 422

    input_response = await fixture.client.get(
        f"/student/api/v1/problems/{problem_public_id}/test-input",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert input_response.status == 200, await input_response.text()
    input_payload = await input_response.json()
    assert input_payload == {
        "schemaVersion": 1,
        "problemId": problem_public_id,
        "problemRevision": {
            "conditionRevisionId": condition_revision_id,
            "configVersion": 1,
        },
        "answerType": 3,
        "validationPattern": None,
        "validationError": "Введите целое число, например -7",
        "options": [],
        "requestId": "content.http.test",
    }
    serialized_input = json.dumps(input_payload)
    assert "correctAnswer" not in serialized_input
    assert "correctAnswerChecker" not in serialized_input

    stale_revision = await fixture.client.post(
        route,
        json={
            **payload,
            "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac04",
            "problemRevision": {
                "conditionRevisionId": "revision-stale-condition",
                "configVersion": 1,
            },
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert stale_revision.status == 409
    assert (await stale_revision.json())["error"]["code"] == (
        "test_problem_revision_changed"
    )

    cursors_before = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    created = await fixture.client.post(
        route,
        json=payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created.status == 201, await created.text()
    receipt = await created.json()
    assert receipt == {
        "schemaVersion": 1,
        "attemptId": receipt["attemptId"],
        "problemId": problem_public_id,
        "problemRevision": {
            "conditionRevisionId": receipt["problemRevision"]["conditionRevisionId"],
            "configVersion": 1,
        },
        "outcome": "correct",
        "displayAnswer": "7",
        "feedback": "Да, всё верно!",
        "checkerMessage": None,
        "verdict": 18,
        "clientCreatedAt": _timestamp(),
        "serverReceivedAt": _timestamp(),
        "clockSuspicious": False,
        "attempts": {
            "usedThisHour": 0,
            "remainingThisHour": 3,
            "usedToday": 1,
            "remainingToday": 4,
            "unlimited": False,
        },
        "checkStatus": "checked",
        "resultVersion": 1,
        "threadInvalidationKey": f"problems/{problem_public_id}/test-attempts",
        "requestId": "content.http.test",
    }
    assert "correctAnswer" not in json.dumps(receipt)
    assert "correctAnswerChecker" not in json.dumps(receipt)
    cursors_after_created = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    assert cursors_after_created == {
        **cursors_before,
        "student": cursors_before["student"] + 1,
    }

    replay = await fixture.client.post(
        route,
        json=payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 201
    assert await replay.json() == receipt
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_created
    )

    mismatch = await fixture.client.post(
        route,
        json={**payload, "displayAnswer": "8"},
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert mismatch.status == 409
    assert (await mismatch.json())["error"]["code"] == "idempotency_payload_mismatch"

    invalid_format = await fixture.client.post(
        route,
        json={
            **payload,
            "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac06",
            "displayAnswer": "не число",
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert invalid_format.status == 201, await invalid_format.text()
    invalid_receipt = await invalid_format.json()
    assert invalid_receipt["outcome"] == "invalid_format"
    assert invalid_receipt["verdict"] is None
    assert invalid_receipt["attempts"]["usedThisHour"] == 0
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"] == {
        **cursors_after_created,
        "student": cursors_after_created["student"] + 1,
    }

    history_response = await fixture.client.get(
        route,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert history_response.status == 200, await history_response.text()
    history = await history_response.json()
    assert history["problemId"] == problem_public_id
    assert [attempt["outcome"] for attempt in history["attempts"]] == [
        "invalid_format",
        "correct",
    ]
    assert history["nextCursor"] is None
    assert all("attempts" not in attempt for attempt in history["attempts"])

    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM test_attempts").fetchone()[
                "n"
            ],
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            connection.execute(
                "SELECT count(*) AS n FROM idempotency_records"
            ).fetchone()["n"],
        )
    )
    assert counts == (2, 1, 2)


async def test_student_test_submission_http_rejects_unauthenticated_and_bad_cursor(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, _condition_revision_id = await _prepare_published_test_problem(
        fixture
    )
    route = f"/student/api/v1/problems/{problem_public_id}/test-attempts"

    unauthenticated = await fixture.client.get(route, headers=_headers())
    assert unauthenticated.status == 401
    invalid_cursor = await fixture.client.get(
        route,
        params={"cursor": "../foreign"},
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert invalid_cursor.status == 422


async def test_student_written_submission_http_is_strict_idempotent_and_readable(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    thread_route = f"/student/api/v1/problems/{problem_public_id}/thread"
    create_route = f"{thread_route}/entries"
    create_payload = {
        "schemaVersion": 1,
        "idempotencyKey": "d301d1d4-1a8a-4d56-9a07-a5511dc4ed2c",
        "problemRevision": {
            "conditionRevisionId": condition_revision_id,
            "configVersion": 1,
        },
        "text": "Пусть x — искомое число. Тогда x + 7 = 19.",
        "pasteEvidence": {
            "pasteCount": 2,
            "pastedCharacterCount": 37,
            "lastPastedAt": _timestamp(NOW - timedelta(seconds=10)),
        },
        "clientCreatedAt": _timestamp(),
    }

    unauthenticated = await fixture.client.get(thread_route, headers=_headers())
    assert unauthenticated.status == 401
    empty = await fixture.client.get(
        thread_route,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert empty.status == 200, await empty.text()
    assert await empty.json() == {
        "schemaVersion": 1,
        "problemId": problem_public_id,
        "thread": None,
        "requestId": "content.http.test",
    }
    invalid_identity = await fixture.client.post(
        create_route,
        json={**create_payload, "studentId": "user-content-student"},
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert invalid_identity.status == 422

    cursors_before = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    created = await fixture.client.post(
        create_route,
        json=create_payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created.status == 201, await created.text()
    draft = await created.json()
    assert draft["problemId"] == problem_public_id
    assert draft["threadStatus"] == "open"
    assert draft["threadVersion"] == 1
    assert draft["entry"]["state"] == "draft"
    assert draft["entry"]["problemRevision"] == create_payload["problemRevision"]
    assert draft["entry"]["attachments"] == []
    assert draft["requestId"] == "content.http.test"
    stored_paste_evidence = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT paste_count, pasted_character_count, last_pasted_at "
            "FROM submission_entries WHERE public_id = ?",
            (draft["entry"]["entryId"],),
        ).fetchone()
    )
    assert dict(stored_paste_evidence) == {
        "paste_count": 2,
        "pasted_character_count": 37,
        "last_pasted_at": _timestamp(NOW - timedelta(seconds=10)),
    }
    cursors_after_create = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    assert cursors_after_create == {
        **cursors_before,
        "student": cursors_before["student"] + 1,
    }

    replay = await fixture.client.post(
        create_route,
        json=create_payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 201
    assert await replay.json() == draft
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_create
    )

    submit_route = f"/student/api/v1/thread-entries/{draft['entry']['entryId']}/submit"
    submit_payload = {
        "schemaVersion": 1,
        "idempotencyKey": "05eb8741-c75e-43bd-b592-8ff7baf81cc1",
        "expectedEntryVersion": 1,
        "expectedThreadVersion": 1,
        "attachmentIds": [],
    }
    submitted = await fixture.client.post(
        submit_route,
        json=submit_payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted.status == 200, await submitted.text()
    receipt = await submitted.json()
    assert receipt["threadStatus"] == "awaiting_review"
    assert receipt["threadVersion"] == 2
    assert receipt["entry"]["state"] == "submitted"
    assert receipt["entry"]["version"] == 2
    assert receipt["clockSuspicious"] is False
    cursors_after_submit = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    assert cursors_after_submit == {
        **cursors_after_create,
        "student": cursors_after_create["student"] + 1,
        "staff": cursors_after_create["staff"] + 1,
    }

    submit_replay = await fixture.client.post(
        submit_route,
        json=submit_payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submit_replay.status == 200
    assert await submit_replay.json() == receipt
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_submit
    )

    history = await fixture.client.get(
        thread_route,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert history.status == 200, await history.text()
    thread = (await history.json())["thread"]
    assert thread["status"] == "awaiting_review"
    assert thread["version"] == 2
    assert [entry["entryId"] for entry in thread["entries"]] == [
        draft["entry"]["entryId"]
    ]

    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT count(*) AS n FROM submission_threads"
            ).fetchone()["n"],
            connection.execute(
                "SELECT count(*) AS n FROM submission_entries"
            ).fetchone()["n"],
            connection.execute(
                "SELECT count(*) AS n FROM idempotency_records "
                "WHERE operation LIKE 'written-entry:%'"
            ).fetchone()["n"],
        )
    )
    assert counts == (1, 1, 2)


async def test_family_written_thread_is_read_only_child_scoped_and_hides_staff_reaction(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    student_thread_route = f"/student/api/v1/problems/{problem_public_id}/thread"
    family_thread_route = (
        "/family/api/v1/children/user-content-student/problems/"
        f"{problem_public_id}/thread"
    )
    created_response = await fixture.client.post(
        f"{student_thread_route}/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "51029bc9-ed0e-4c1d-8a92-9acf954854aa",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "Семья увидит этот текст только после отправки.",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created_response.status == 201, await created_response.text()
    created = await created_response.json()

    family_draft = await fixture.client.get(
        family_thread_route,
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert family_draft.status == 200, await family_draft.text()
    assert (await family_draft.json())["thread"] is None

    upload_form = FormData()
    upload_form.add_field("schemaVersion", "1")
    upload_form.add_field("idempotencyKey", "f909eb0f-3d32-46ef-b001-13e8dfe3f402")
    upload_form.add_field("expectedEntryVersion", str(created["entry"]["version"]))
    upload_form.add_field("expectedThreadVersion", str(created["threadVersion"]))
    upload_form.add_field("ordinal", "0")
    upload_form.add_field(
        "asset",
        b"synthetic-family-visible-photo",
        filename="семейная-проверка.heic",
        content_type="image/heic",
    )
    uploaded_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{created['entry']['entryId']}/attachments",
        data=upload_form,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert uploaded_response.status == 201, await uploaded_response.text()
    uploaded = await uploaded_response.json()
    attachment = uploaded["entry"]["attachments"][0]
    submitted_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{created['entry']['entryId']}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "03e0d258-49b1-43a0-bad4-2823773c79b6",
            "expectedEntryVersion": uploaded["entry"]["version"],
            "expectedThreadVersion": uploaded["threadVersion"],
            "attachmentIds": [attachment["attachmentId"]],
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted_response.status == 200, await submitted_response.text()

    family_submitted_response = await fixture.client.get(
        family_thread_route,
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert family_submitted_response.status == 200, (
        await family_submitted_response.text()
    )
    family_submitted = await family_submitted_response.json()
    family_attachment = family_submitted["thread"]["entries"][0]["attachments"][0]
    assert family_submitted["studentId"] == "user-content-student"
    assert family_attachment["mediaPath"].startswith(
        "/family/api/v1/children/user-content-student/thread-entries/"
    )
    family_media = await fixture.client.get(
        family_attachment["mediaPath"],
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert family_media.status == 200
    assert family_media.content_type == "image/webp"

    forbidden_child = await fixture.client.get(
        family_thread_route.replace("user-content-student", "user-foreign-student"),
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert forbidden_child.status == 403

    queue_public_id = fixture.factory.run_read(
        lambda connection: str(
            connection.execute(
                "SELECT queue.public_id FROM written_tasks_queue AS queue "
                "JOIN problems AS problem ON problem.id = queue.problem_id "
                "WHERE queue.student_id = ? AND problem.public_id = ?",
                (STUDENT_USER_ID, problem_public_id),
            ).fetchone()["public_id"]
        )
    )
    claimed_response = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_public_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert claimed_response.status == 200, await claimed_response.text()
    lease = (await claimed_response.json())["lease"]
    evidence_by_queue = {
        branch["queueId"]: branch for branch in lease["evidenceBranches"]
    }
    cursors_before_review_complete = dict(
        fixture.client.app[pwa_app.PWA_STATE]["cursors"]
    )
    completed_response = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_public_id}/complete",
        json={
            "schemaVersion": 1,
            "claimToken": lease["claimToken"],
            "idempotencyKey": "content-http-family-review-complete",
            "verdict": 15,
            "comment": "Хорошая идея; поясните отмеченный переход.",
            "confirmWithoutComment": False,
            "branches": [
                {
                    "queueId": branch["queueId"],
                    "leaseVersion": branch["leaseVersion"],
                    "threadId": evidence_by_queue[branch["queueId"]]["thread"][
                        "threadId"
                    ],
                    "threadVersion": evidence_by_queue[branch["queueId"]]["thread"][
                        "threadVersion"
                    ],
                    "evidence": [
                        {
                            "entryId": entry["entryId"],
                            "entryVersion": entry["entryVersion"],
                        }
                        for entry in evidence_by_queue[branch["queueId"]]["thread"][
                            "entries"
                        ]
                    ],
                }
                for branch in lease["branches"]
            ],
            "annotations": [
                {
                    "attachmentId": attachment["attachmentId"],
                    "schemaVersion": 1,
                    "rotation": 90,
                    "marks": [
                        {
                            "markId": "content-http-family-mark",
                            "kind": "rectangle",
                            "data": {
                                "x": 0.1,
                                "y": 0.2,
                                "width": 0.4,
                                "height": 0.2,
                                "strokeWidth": 0.008,
                                "color": "red",
                            },
                        }
                    ],
                }
            ],
            "internalReactionId": 100,
        },
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert completed_response.status == 200, await completed_response.text()
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_before_review_complete,
        "student": cursors_before_review_complete["student"] + 1,
        "family": cursors_before_review_complete["family"] + 1,
        # The queue update is Staff-wide; the hidden-reaction inbox update is
        # separately account-scoped to admins. Both advance the audience cursor.
        "staff": cursors_before_review_complete["staff"] + 2,
    }

    reviewed_response = await fixture.client.get(
        family_thread_route,
        cookies=_cookie(fixture, "family"),
        headers=_headers(),
    )
    assert reviewed_response.status == 200, await reviewed_response.text()
    reviewed = await reviewed_response.json()
    assert reviewed["thread"]["reviews"] == [
        {
            "reviewId": "content-http-family-review",
            "targetProblemId": problem_public_id,
            "verdict": 15,
            "commentEntryId": "content-http-family-comment",
            "comment": "Хорошая идея; поясните отмеченный переход.",
            "reviewerName": "Учитель Тестовый",
            "source": "staff",
            "evidenceEntryIds": [created["entry"]["entryId"]],
            "annotations": [
                {
                    "attachmentId": attachment["attachmentId"],
                    "schemaVersion": 1,
                    "rotation": 90,
                    "marks": [
                        {
                            "markId": "content-http-family-mark",
                            "kind": "rectangle",
                            "data": {
                                "x": 0.1,
                                "y": 0.2,
                                "width": 0.4,
                                "height": 0.2,
                                "strokeWidth": 0.008,
                                "color": "red",
                            },
                        }
                    ],
                }
            ],
            "studentReaction": None,
            "completedAt": _timestamp(),
        }
    ]
    assert "internalReaction" not in reviewed["thread"]["reviews"][0]


async def test_student_written_replacement_is_one_visible_atomic_commit(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    create_route = f"/student/api/v1/problems/{problem_public_id}/thread/entries"
    original_response = await fixture.client.post(
        create_route,
        json={
            "schemaVersion": 1,
            "idempotencyKey": "05f3c912-3044-4709-902a-9a8e6c02fe81",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "Первоначальное решение.",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert original_response.status == 201, await original_response.text()
    original_draft = await original_response.json()
    submitted_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{original_draft['entry']['entryId']}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "bbde7b77-80a4-4c24-927a-b0b99ee7ca1f",
            "expectedEntryVersion": 1,
            "expectedThreadVersion": 1,
            "attachmentIds": [],
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted_response.status == 200, await submitted_response.text()
    original = await submitted_response.json()
    replacement_response = await fixture.client.post(
        create_route,
        json={
            "schemaVersion": 1,
            "idempotencyKey": "988a6fb3-99da-4f28-ac84-219dc8c30742",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "Исправленное решение.",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replacement_response.status == 201, await replacement_response.text()
    replacement_draft = await replacement_response.json()
    replace_route = f"/student/api/v1/thread-entries/{replacement_draft['entry']['entryId']}/replace"
    replace_payload = {
        "schemaVersion": 1,
        "idempotencyKey": "158564ae-56cc-446a-b1d6-12ef8cc2c71b",
        "replacedEntryId": original["entry"]["entryId"],
        "expectedEntryVersion": replacement_draft["entry"]["version"],
        "expectedReplacedEntryVersion": original["entry"]["version"],
        "expectedThreadVersion": replacement_draft["threadVersion"],
        "attachmentIds": [],
    }
    cursor_before = fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"]

    replaced_response = await fixture.client.post(
        replace_route,
        json=replace_payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replaced_response.status == 200, await replaced_response.text()
    replaced = await replaced_response.json()
    assert replaced["replacedEntryId"] == original["entry"]["entryId"]
    assert replaced["replacementEventId"].startswith("written-replacement-")
    assert replaced["entry"]["entryId"] == replacement_draft["entry"]["entryId"]
    assert replaced["entry"]["state"] == "submitted"
    assert replaced["threadStatus"] == "awaiting_review"
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before + 1
    )

    replay = await fixture.client.post(
        replace_route,
        json=replace_payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 200
    assert await replay.json() == replaced
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before + 1
    )

    history_response = await fixture.client.get(
        f"/student/api/v1/problems/{problem_public_id}/thread",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert history_response.status == 200
    history = (await history_response.json())["thread"]
    assert [(entry["entryId"], entry["state"]) for entry in history["entries"]] == [
        (original["entry"]["entryId"], "deleted"),
        (replacement_draft["entry"]["entryId"], "submitted"),
    ]
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS n FROM submission_entry_replacements"
            ).fetchone()["n"]
        )
        == 1
    )


async def test_staff_written_material_reassignment_previews_commits_and_projects(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    source_problem_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    target_problem_id = _insert_second_written_problem(
        fixture, condition_revision_public_id=condition_revision_id
    )
    created_response = await fixture.client.post(
        f"/student/api/v1/problems/{source_problem_id}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "e6d18ca4-a1b6-48e9-aea7-447b7348cb2a",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "Эта работа относится ко второй задаче.",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created_response.status == 201, await created_response.text()
    created = await created_response.json()
    upload_form = FormData()
    upload_form.add_field("schemaVersion", "1")
    upload_form.add_field("idempotencyKey", "48a3845d-f857-44d1-893e-766d6a376f46")
    upload_form.add_field("expectedEntryVersion", str(created["entry"]["version"]))
    upload_form.add_field("expectedThreadVersion", str(created["threadVersion"]))
    upload_form.add_field("ordinal", "0")
    upload_form.add_field(
        "asset",
        b"synthetic-reassignment-photo",
        filename="перенос.heic",
        content_type="image/heic",
    )
    uploaded_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{created['entry']['entryId']}/attachments",
        data=upload_form,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert uploaded_response.status == 201, await uploaded_response.text()
    uploaded = await uploaded_response.json()
    attachment = uploaded["entry"]["attachments"][0]
    submitted_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{created['entry']['entryId']}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "8911a420-bbc8-4a8d-b7da-9d8693b98652",
            "expectedEntryVersion": uploaded["entry"]["version"],
            "expectedThreadVersion": uploaded["threadVersion"],
            "attachmentIds": [attachment["attachmentId"]],
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted_response.status == 200, await submitted_response.text()
    submitted = await submitted_response.json()
    selection = [
        {
            "entryId": submitted["entry"]["entryId"],
            "itemKind": "entry_text",
            "attachmentId": None,
        },
        {
            "entryId": submitted["entry"]["entryId"],
            "itemKind": "attachment",
            "attachmentId": attachment["attachmentId"],
        },
    ]
    preview_response = await fixture.client.post(
        "/staff/api/v1/submission-material-reassignments/preview",
        json={
            "schemaVersion": 1,
            "sourceThreadId": submitted["threadId"],
            "targetProblemId": target_problem_id,
            "items": selection,
        },
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = await preview_response.json()
    assert preview["studentId"] == "user-content-student"
    assert preview["source"]["problemId"] == source_problem_id
    assert preview["target"] == {
        "threadId": None,
        "problemId": target_problem_id,
        "threadVersion": None,
        "scope": preview["source"]["scope"],
    }
    assert preview["items"][0]["text"] == "Эта работа относится ко второй задаче."
    assert preview["items"][1]["attachment"] == {
        **attachment,
        "mediaPath": attachment["mediaPath"].replace(
            "/student/api/v1/", "/staff/api/v1/", 1
        ),
    }
    assert preview["impact"] == {
        "postReview": False,
        "sourceEvidenceUnchanged": True,
        "sourceVerdictUnchanged": True,
        "targetRequiresReview": True,
        "studentLabel": "Перенесено преподавателем",
    }
    cursor_before = fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"]
    commit_payload = {
        "schemaVersion": 1,
        "idempotencyKey": "4a838c0b-9fe2-4a07-a78b-a89b9314298a",
        "sourceThreadId": submitted["threadId"],
        "targetProblemId": target_problem_id,
        "expectedSourceThreadVersion": preview["source"]["threadVersion"],
        "expectedTargetThreadVersion": None,
        "items": selection,
        "reason": "Выбрана соседняя задача.",
    }
    committed_response = await fixture.client.post(
        "/staff/api/v1/submission-material-reassignments",
        json=commit_payload,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert committed_response.status == 200, await committed_response.text()
    committed = await committed_response.json()
    assert committed["source"]["threadStatus"] == "closed"
    assert committed["target"]["threadStatus"] == "awaiting_review"
    assert committed["studentLabel"] == "Перенесено преподавателем"
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before + 2
    )

    staff_media_path = preview["items"][1]["attachment"]["mediaPath"]
    staff_media = await fixture.client.get(
        staff_media_path,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert staff_media.status == 200
    assert staff_media.headers["Content-Type"] == "image/webp"
    assert (await staff_media.read()).startswith(b"synthetic-webp:")
    assert (
        await fixture.client.get(staff_media_path, headers=_headers())
    ).status == 401
    assert (
        await fixture.client.get(
            staff_media_path,
            cookies=_cookie(fixture, "student"),
            headers=_headers(),
        )
    ).status == 401

    replay = await fixture.client.post(
        "/staff/api/v1/submission-material-reassignments",
        json=commit_payload,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 200
    assert await replay.json() == committed
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before + 2
    )

    source_history = await fixture.client.get(
        f"/student/api/v1/problems/{source_problem_id}/thread",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    target_history = await fixture.client.get(
        f"/student/api/v1/problems/{target_problem_id}/thread",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert source_history.status == 200 and target_history.status == 200
    assert (await source_history.json())["thread"]["entries"] == []
    target_thread = (await target_history.json())["thread"]
    assert target_thread["threadId"] == committed["target"]["threadId"]
    assert target_thread["entries"][0]["entryId"] == submitted["entry"]["entryId"]
    assert target_thread["entries"][0]["projection"] == {
        "kind": "staff_reassignment",
        "reassignmentIds": [committed["reassignmentId"]],
        "sourceThreadId": committed["source"]["threadId"],
        "sourceProblemId": source_problem_id,
        "targetThreadId": committed["target"]["threadId"],
        "targetProblemId": target_problem_id,
        "movedAt": committed["movedAt"],
    }

    second_created_response = await fixture.client.post(
        f"/student/api/v1/problems/{source_problem_id}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "268ea380-3048-4272-836a-18da63b7119e",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "Новый материал для проверки scope.",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert second_created_response.status == 201
    second_created = await second_created_response.json()
    second_submitted_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{second_created['entry']['entryId']}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "43409f66-f6c5-4645-8be7-dfa36692ceda",
            "expectedEntryVersion": second_created["entry"]["version"],
            "expectedThreadVersion": second_created["threadVersion"],
            "attachmentIds": [],
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert second_submitted_response.status == 200
    second_submitted = await second_submitted_response.json()
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "DELETE FROM staff_scopes WHERE staff_user_id = ?", (TEACHER_USER_ID,)
        )
    )
    forbidden_media = await fixture.client.get(
        staff_media_path,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert forbidden_media.status == 403
    forbidden = await fixture.client.post(
        "/staff/api/v1/submission-material-reassignments/preview",
        json={
            "schemaVersion": 1,
            "sourceThreadId": second_submitted["threadId"],
            "targetProblemId": target_problem_id,
            "items": [
                {
                    "entryId": second_submitted["entry"]["entryId"],
                    "itemKind": "entry_text",
                    "attachmentId": None,
                }
            ],
        },
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert forbidden.status == 403

    unauthenticated = await fixture.client.post(
        "/staff/api/v1/submission-material-reassignments/preview",
        json={
            "schemaVersion": 1,
            "sourceThreadId": submitted["threadId"],
            "targetProblemId": target_problem_id,
            "items": selection,
        },
        headers=_headers(unsafe=True),
    )
    assert unauthenticated.status == 401


async def test_student_written_photo_upload_converts_persists_replays_and_submits(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    created = await fixture.client.post(
        f"/student/api/v1/problems/{problem_public_id}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "6ea1b2ad-7dc1-49db-b27a-909f8add9955",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": None,
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created.status == 201, await created.text()
    draft = await created.json()
    upload_route = (
        f"/student/api/v1/thread-entries/{draft['entry']['entryId']}/attachments"
    )

    def upload_form(*, source: bytes = b"synthetic-heic-source") -> FormData:
        form = FormData()
        form.add_field("schemaVersion", "1")
        form.add_field("idempotencyKey", "ce55c871-d3fa-46ea-89f2-34f7e54cfa12")
        form.add_field("expectedEntryVersion", "1")
        form.add_field("expectedThreadVersion", "1")
        form.add_field("ordinal", "0")
        form.add_field(
            "asset",
            source,
            filename="страница 1.heic",
            content_type="image/heic",
        )
        return form

    cursors_before = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    uploaded = await fixture.client.post(
        upload_route,
        data=upload_form(),
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert uploaded.status == 201, await uploaded.text()
    receipt = await uploaded.json()
    assert receipt["threadVersion"] == 2
    assert receipt["entry"]["version"] == 2
    assert receipt["entry"]["state"] == "draft"
    assert len(receipt["entry"]["attachments"]) == 1
    attachment = receipt["entry"]["attachments"][0]
    assert attachment == {
        "attachmentId": attachment["attachmentId"],
        "ordinal": 0,
        "uploadStatus": "stored",
        "mediaId": attachment["mediaId"],
        "publicUrl": None,
        "mediaPath": (
            f"/student/api/v1/thread-entries/{draft['entry']['entryId']}"
            f"/attachments/{attachment['attachmentId']}/media"
        ),
        "mediaType": "image/webp",
        "width": 320,
        "height": 240,
    }
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_before,
        "student": cursors_before["student"] + 1,
    }
    submission_keys = [
        key for key in fixture.asset_storage.objects if key.startswith("sol_imgs/")
    ]
    assert len(submission_keys) == 1
    assert submission_keys[0].startswith(
        f"sol_imgs/user_{STUDENT_USER_ID}/2026/lesson_41/{problem_public_id}_"
    )
    assert submission_keys[0].endswith(f"_{'2' * 32}.webp")
    assert fixture.asset_storage.objects[submission_keys[0]].startswith(
        b"synthetic-webp:"
    )
    unauthenticated_media = await fixture.client.get(
        attachment["mediaPath"], headers=_headers()
    )
    assert unauthenticated_media.status == 401
    media = await fixture.client.get(
        attachment["mediaPath"],
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert media.status == 200
    assert media.headers["Content-Type"] == "image/webp"
    assert media.headers["Cache-Control"] == "no-store"
    assert await media.read() == fixture.asset_storage.objects[submission_keys[0]]

    replay = await fixture.client.post(
        upload_route,
        data=upload_form(),
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 201
    assert await replay.json() == receipt
    assert [
        key for key in fixture.asset_storage.objects if key.startswith("sol_imgs/")
    ] == (submission_keys)

    mismatch = await fixture.client.post(
        upload_route,
        data=upload_form(source=b"different-source"),
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert mismatch.status == 409
    assert (await mismatch.json())["error"]["code"] == "idempotency_payload_mismatch"
    assert [
        key for key in fixture.asset_storage.objects if key.startswith("sol_imgs/")
    ] == submission_keys

    submitted = await fixture.client.post(
        f"/student/api/v1/thread-entries/{draft['entry']['entryId']}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "14095dae-8eb4-40e4-b784-f7b233c26c39",
            "expectedEntryVersion": 2,
            "expectedThreadVersion": 2,
            "attachmentIds": [attachment["attachmentId"]],
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted.status == 200, await submitted.text()
    submitted_payload = await submitted.json()
    assert submitted_payload["entry"]["state"] == "submitted"
    assert submitted_payload["entry"]["attachments"] == [attachment]
    assert submitted_payload["threadVersion"] == 3

    rows = fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT storage_namespace, media_type, width, height, source_filename "
                "FROM media_assets WHERE storage_namespace = 'submission'"
            ).fetchall(),
            connection.execute(
                "SELECT ordinal, upload_status FROM submission_attachments"
            ).fetchall(),
            connection.execute(
                "SELECT state FROM idempotency_records "
                "WHERE operation = 'written-attachment:create'"
            ).fetchall(),
        )
    )
    assert rows == (
        [
            {
                "storage_namespace": "submission",
                "media_type": "image/webp",
                "width": 320,
                "height": 240,
                "source_filename": "страница 1.heic",
            }
        ],
        [{"ordinal": 0, "upload_status": "stored"}],
        [{"state": "completed"}],
    )


async def test_student_written_photo_order_delete_and_reload_contract(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    created = await fixture.client.post(
        f"/student/api/v1/problems/{problem_public_id}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "66598440-354b-48cd-9057-82928e192a17",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "Текстовая часть решения сохраняется.",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created.status == 201, await created.text()
    draft = await created.json()
    entry_id = draft["entry"]["entryId"]
    upload_route = f"/student/api/v1/thread-entries/{entry_id}/attachments"

    async def upload_page(
        *,
        key: str,
        entry_version: int,
        thread_version: int,
        ordinal: int,
        source: bytes,
    ) -> dict[str, object]:
        form = FormData()
        form.add_field("schemaVersion", "1")
        form.add_field("idempotencyKey", key)
        form.add_field("expectedEntryVersion", str(entry_version))
        form.add_field("expectedThreadVersion", str(thread_version))
        form.add_field("ordinal", str(ordinal))
        form.add_field(
            "asset",
            source,
            filename=f"страница-{ordinal + 1}.heic",
            content_type="image/heic",
        )
        response = await fixture.client.post(
            upload_route,
            data=form,
            cookies=_cookie(fixture, "student"),
            headers=_headers(unsafe=True),
        )
        assert response.status == 201, await response.text()
        return await response.json()

    first = await upload_page(
        key="8ef56c78-1be6-4ba5-9cae-e52e78a5180c",
        entry_version=1,
        thread_version=1,
        ordinal=0,
        source=b"synthetic-page-one",
    )
    second = await upload_page(
        key="4938a95c-e42a-4915-bbf7-9ad1007688de",
        entry_version=first["entry"]["version"],
        thread_version=first["threadVersion"],
        ordinal=1,
        source=b"synthetic-page-two",
    )
    first_attachment, second_attachment = second["entry"]["attachments"]
    reversed_ids = [
        second_attachment["attachmentId"],
        first_attachment["attachmentId"],
    ]
    cursor_before_reorder = fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"]
    reorder_body = {
        "schemaVersion": 1,
        "idempotencyKey": "a8c582c2-5d32-4f27-8295-0067ddaf1af0",
        "expectedEntryVersion": second["entry"]["version"],
        "expectedThreadVersion": second["threadVersion"],
        "attachmentIds": reversed_ids,
    }
    reorder_route = f"/student/api/v1/thread-entries/{entry_id}/attachments/order"
    reordered_response = await fixture.client.patch(
        reorder_route,
        json=reorder_body,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert reordered_response.status == 200, await reordered_response.text()
    reordered = await reordered_response.json()
    assert reordered["changed"] is True
    assert reordered["entry"]["version"] == second["entry"]["version"] + 1
    assert reordered["threadVersion"] == second["threadVersion"] + 1
    assert [
        attachment["attachmentId"] for attachment in reordered["entry"]["attachments"]
    ] == reversed_ids
    assert [
        attachment["ordinal"] for attachment in reordered["entry"]["attachments"]
    ] == [0, 1]
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before_reorder + 1
    )

    replay = await fixture.client.patch(
        reorder_route,
        json=reorder_body,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 200
    assert await replay.json() == reordered
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before_reorder + 1
    )

    unchanged = await fixture.client.patch(
        reorder_route,
        json={
            **reorder_body,
            "idempotencyKey": "4afe8a9c-f9b3-4506-a283-9113685ec998",
            "expectedEntryVersion": reordered["entry"]["version"],
            "expectedThreadVersion": reordered["threadVersion"],
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert unchanged.status == 200
    unchanged_payload = await unchanged.json()
    assert unchanged_payload["changed"] is False
    assert unchanged_payload["entry"]["version"] == reordered["entry"]["version"]
    assert unchanged_payload["threadVersion"] == reordered["threadVersion"]
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"]["student"] == (
        cursor_before_reorder + 1
    )

    submitted_response = await fixture.client.post(
        f"/student/api/v1/thread-entries/{entry_id}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "22891164-b2ac-4a6d-9ff3-1ed8765f99e4",
            "expectedEntryVersion": reordered["entry"]["version"],
            "expectedThreadVersion": reordered["threadVersion"],
            "attachmentIds": reversed_ids,
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted_response.status == 200, await submitted_response.text()
    submitted = await submitted_response.json()

    delete_route = (
        f"/student/api/v1/thread-entries/{entry_id}/attachments/"
        f"{second_attachment['attachmentId']}"
    )
    delete_body = {
        "schemaVersion": 1,
        "idempotencyKey": "48e02691-4eb3-4214-80fb-728fc74d3b44",
        "expectedEntryVersion": submitted["entry"]["version"],
        "expectedThreadVersion": submitted["threadVersion"],
    }
    deleted_response = await fixture.client.delete(
        delete_route,
        json=delete_body,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert deleted_response.status == 200, await deleted_response.text()
    deleted = await deleted_response.json()
    assert deleted["changed"] is True
    assert deleted["entry"]["state"] == "submitted"
    assert [
        attachment["attachmentId"] for attachment in deleted["entry"]["attachments"]
    ] == [first_attachment["attachmentId"]]
    assert deleted["entry"]["attachments"][0]["ordinal"] == 0

    delete_replay = await fixture.client.delete(
        delete_route,
        json=delete_body,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert delete_replay.status == 200
    assert await delete_replay.json() == deleted
    removed_media = await fixture.client.get(
        second_attachment["mediaPath"],
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert removed_media.status == 404
    assert (await removed_media.json())["error"]["code"] == (
        "written_attachment_not_found"
    )

    thread_response = await fixture.client.get(
        f"/student/api/v1/problems/{problem_public_id}/thread",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert thread_response.status == 200
    thread = (await thread_response.json())["thread"]
    assert thread["version"] == deleted["threadVersion"]
    assert thread["entries"][0]["attachments"] == deleted["entry"]["attachments"]

    rows = fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT attachment.public_id, attachment.ordinal "
                "FROM submission_attachments AS attachment"
            ).fetchall(),
            connection.execute(
                "SELECT deleted_at FROM media_assets "
                "WHERE storage_namespace = 'submission' ORDER BY id"
            ).fetchall(),
        )
    )
    assert rows[0] == [{"public_id": first_attachment["attachmentId"], "ordinal": 0}]
    assert rows[1][0]["deleted_at"] is None
    assert rows[1][1]["deleted_at"] is not None
    # Final WebP retention is admin-managed: logical deletion immediately
    # removes app access, while physical object cleanup remains a separate job.
    assert (
        len(
            [
                key
                for key in fixture.asset_storage.objects
                if key.startswith("sol_imgs/")
            ]
        )
        == 2
    )


async def test_student_written_submission_http_persists_safe_failures(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, condition_revision_id = await _prepare_published_test_problem(
        fixture, problem_type=2
    )
    created = await fixture.client.post(
        f"/student/api/v1/problems/{problem_public_id}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "e70bc72f-457d-4684-b748-08e1af2877b0",
            "problemRevision": {
                "conditionRevisionId": condition_revision_id,
                "configVersion": 1,
            },
            "text": "   ",
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert created.status == 201, await created.text()
    draft = await created.json()
    submit_route = f"/student/api/v1/thread-entries/{draft['entry']['entryId']}/submit"
    payload = {
        "schemaVersion": 1,
        "idempotencyKey": "7ad0d1d1-2714-4365-9b4e-91afccbe22c1",
        "expectedEntryVersion": 1,
        "expectedThreadVersion": 1,
        "attachmentIds": [],
    }

    first = await fixture.client.post(
        submit_route,
        json=payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    second = await fixture.client.post(
        submit_route,
        json=payload,
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )

    assert first.status == second.status == 422
    assert await first.json() == await second.json()
    entry, record = fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT state, version FROM submission_entries"
            ).fetchone(),
            connection.execute(
                "SELECT state, http_status FROM idempotency_records "
                "WHERE operation = 'written-entry:submit'"
            ).fetchone(),
        )
    )
    assert entry == {"state": "draft", "version": 1}
    assert record == {"state": "failed", "http_status": 422}


async def test_staff_rechecks_pending_attempts_after_publishing_repaired_config(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    problem_public_id, original_revision_id = await _prepare_published_test_problem(
        fixture,
        correct_answer=None,
    )
    student_route = f"/student/api/v1/problems/{problem_public_id}/test-attempts"
    submitted = await fixture.client.post(
        student_route,
        json={
            "schemaVersion": 1,
            "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac09",
            "problemRevision": {
                "conditionRevisionId": original_revision_id,
                "configVersion": 1,
            },
            "displayAnswer": "179",
            "clientCreatedAt": _timestamp(),
        },
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert submitted.status == 201, await submitted.text()
    assert (await submitted.json())["outcome"] == "pending_configuration"

    route = f"/staff/api/v1/problems/{problem_public_id}/recheck-test-attempts"
    unauthenticated = await fixture.client.get(route, headers=_headers())
    assert unauthenticated.status == 401
    teacher = await fixture.client.get(
        route,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert teacher.status == 403
    initial_preview_response = await fixture.client.get(
        route,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert initial_preview_response.status == 200
    initial_preview = await initial_preview_response.json()
    assert initial_preview["pendingAttempts"] == 1
    assert initial_preview["problemRevision"] == {
        "conditionRevisionId": original_revision_id,
        "configVersion": 1,
    }

    (
        repaired_revision_id,
        repaired_config_version,
    ) = await _publish_repaired_test_problem(
        fixture,
        problem_public_id=problem_public_id,
        correct_answer="179",
    )
    preview_response = await fixture.client.get(
        route,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert preview_response.status == 200
    preview = await preview_response.json()
    assert preview["problemRevision"] == {
        "conditionRevisionId": repaired_revision_id,
        "configVersion": repaired_config_version,
    }
    assert preview["pendingAttempts"] == 1

    missing_origin = await fixture.client.post(
        route,
        json={
            "schemaVersion": 1,
            "problemRevision": preview["problemRevision"],
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert missing_origin.status == 403
    stale = await fixture.client.post(
        route,
        json={
            "schemaVersion": 1,
            "problemRevision": initial_preview["problemRevision"],
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "test_problem_revision_changed"

    cursors_before = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    rechecked = await fixture.client.post(
        route,
        json={
            "schemaVersion": 1,
            "problemRevision": preview["problemRevision"],
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert rechecked.status == 200, await rechecked.text()
    receipt = await rechecked.json()
    assert receipt == {
        "schemaVersion": 1,
        "problemId": problem_public_id,
        "problemRevision": preview["problemRevision"],
        "pendingBefore": 1,
        "checked": 1,
        "correct": 1,
        "wrong": 0,
        "stillPending": 0,
        "skippedConcurrent": 0,
        "threadInvalidationKey": f"problems/{problem_public_id}/test-attempts",
        "requestId": "content.http.test",
    }
    assert fixture.client.app[pwa_app.PWA_STATE]["cursors"] == {
        **cursors_before,
        "student": cursors_before["student"] + 1,
    }

    history_response = await fixture.client.get(
        student_route,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert history_response.status == 200
    history = await history_response.json()
    assert history["attempts"][0]["outcome"] == "correct"
    assert history["attempts"][0]["problemRevision"] == {
        "conditionRevisionId": original_revision_id,
        "configVersion": 1,
    }
    assert history["attempts"][0]["feedback"] is None
    stored = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            connection.execute("SELECT teacher_id FROM results").fetchone()[
                "teacher_id"
            ],
        )
    )
    assert stored == (1, ADMIN_USER_ID)

    repeated = await fixture.client.post(
        route,
        json={
            "schemaVersion": 1,
            "problemRevision": preview["problemRevision"],
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert repeated.status == 200
    repeated_payload = await repeated.json()
    assert repeated_payload["pendingBefore"] == repeated_payload["checked"] == 0


async def test_staff_lists_explicit_same_lesson_bulk_upload_targets(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    url = f"/staff/api/v1/content/group-lessons/{fixture.group_lesson_a}/upload-targets"

    forbidden = await fixture.client.get(
        url,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert forbidden.status == 403

    response = await fixture.client.get(
        url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert response.status == 200, await response.text()
    assert await response.json() == {
        "courseLessonId": "course-lesson-content-http",
        "courseId": "course-content-http",
        "courseName": "Математика",
        "lessonNumber": 41,
        "targets": [
            {
                "groupLessonId": fixture.group_lesson_a,
                "groupId": "group-content-http-a",
                "groupName": "A",
                "groupShortCode": "a",
                "colorKey": None,
                "status": "active",
            },
            {
                "groupLessonId": fixture.group_lesson_b,
                "groupId": "group-content-http-b",
                "groupName": "B",
                "groupShortCode": "b",
                "colorKey": None,
                "status": "active",
            },
        ],
        "requestId": "content.http.test",
    }

    missing = await fixture.client.get(
        "/staff/api/v1/content/group-lessons/missing-lesson/upload-targets",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert missing.status == 404


async def test_identical_source_upload_is_idempotent(content_http: ContentHttpFixture):
    fixture = content_http
    source = "\\задача Одинаковый файл. \\кзадача".encode()
    first = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="same.tex",
        source=source,
    )
    repeated = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="same.tex",
        source=source,
    )

    assert first.status == repeated.status == 201
    assert (await first.json())["revisionId"] == (await repeated.json())["revisionId"]


async def test_failed_automatic_tikz_keeps_revision_and_returns_recovery_details(
    content_http: ContentHttpFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_tikz(_converter, _source: str) -> ConvertedAsset:
        raise AssetConversionError(
            "asset.converter_failed",
            "latex-to-pdf",
            "converter exited with code 1",
        )

    monkeypatch.setattr(SyntheticAssetConverter, "tikz_to_svg", fail_tikz)
    uploaded = await _upload(
        content_http,
        group_lesson=content_http.group_lesson_a,
        kind="condition",
        filename="usl-03-x.tex",
        source=(
            r"\задача "
            r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
            r"\кзадача"
        ).encode(),
    )

    assert uploaded.status == 422, await uploaded.text()
    error = (await uploaded.json())["error"]
    assert error["code"] == "asset_conversion_failed"
    assert error["details"]["reason"] == "asset.converter_failed"
    assert error["details"]["capability"] == "latex-to-pdf"
    assert error["details"]["detail"] == "converter exited with code 1"
    assert error["details"]["groupLessonId"] == content_http.group_lesson_a
    assert error["details"]["logicalFilename"] == "usl-03-x.tex"
    assert error["details"]["logicalAsset"].startswith("tikz-")
    revision_id = error["details"]["revisionId"]

    diagnostics = await content_http.client.get(
        f"/staff/api/v1/content/uploads/{revision_id}/diagnostics",
        cookies=_cookie(content_http, "admin"),
        headers=_headers(),
    )
    assert diagnostics.status == 200, await diagnostics.text()
    assert (await diagnostics.json())["status"] == "uploaded"


async def test_condition_upload_ignores_tikz_from_hidden_answer(
    content_http: ContentHttpFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_tikz(_converter, _source: str) -> ConvertedAsset:
        raise AssertionError("hidden answer TikZ must not be converted for condition")

    monkeypatch.setattr(SyntheticAssetConverter, "tikz_to_svg", fail_tikz)
    uploaded = await _upload(
        content_http,
        group_lesson=content_http.group_lesson_a,
        kind="condition",
        filename="usl-03-x.tex",
        source=(
            r"\задача Видимое условие. "
            r"\ответ \begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
            r"\кответ \кзадача"
        ).encode(),
    )

    assert uploaded.status == 201, await uploaded.text()
    assert (await uploaded.json())["status"] == "uploaded"


async def test_missing_assets_upload_reuse_and_compile_share_typed_descriptors(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    source = r"""
\задача
\includegraphics{figures/photo.heic}
\includegraphics{figures/vector.svg}
\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}
\кзадача
"""
    uploaded = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="assets/condition.tex",
        source=source.encode(),
    )
    assert uploaded.status == 201, await uploaded.text()
    revision = await uploaded.json()
    revision_id = revision["revisionId"]
    initial_etag = uploaded.headers["ETag"]
    assets_url = f"/staff/api/v1/content/revisions/{revision_id}/assets"

    teacher = await fixture.client.get(
        assets_url,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert teacher.status == 403

    inventory = await fixture.client.get(
        assets_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert inventory.status == 200, await inventory.text()
    inventory_payload = await inventory.json()
    assert inventory_payload["status"] == "uploaded"
    assert len(inventory_payload["missingAssets"]) == 2
    assert (
        next(
            item for item in inventory_payload["assets"] if item["sourceKind"] == "tikz"
        )["status"]
        == "attached"
    )

    blocked = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{revision_id}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_etag),
    )
    assert blocked.status == 422
    assert (await blocked.json())["error"]["code"] == "content_assets_missing"
    stored_status = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT status FROM content_revisions WHERE public_id = ?", (revision_id,)
        ).fetchone()["status"]
    )
    assert stored_status == "uploaded"

    raster = await _upload_asset(
        fixture,
        revision_id=revision_id,
        logical_name="figures/photo.heic",
        kind="raster",
        if_match=initial_etag,
        payload=b"synthetic-heic",
        filename="photo.heic",
    )
    assert raster.status == 201, await raster.text()
    raster_payload = await raster.json()
    assert raster_payload["asset"]["mediaType"] == "image/webp"
    assert raster_payload["asset"]["src"].startswith("/pwa-content-assets/")
    raster_etag = raster.headers["ETag"]

    retry = await _upload_asset(
        fixture,
        revision_id=revision_id,
        logical_name="figures/photo.heic",
        kind="raster",
        if_match=initial_etag,
        payload=b"synthetic-heic",
        filename="photo.heic",
    )
    assert retry.status == 200, await retry.text()
    assert (await retry.json())["reused"] is True
    assert retry.headers["ETag"] == raster_etag

    puts_before_unsafe = len(fixture.asset_storage.puts)
    unsafe = await _upload_asset(
        fixture,
        revision_id=revision_id,
        logical_name="figures/vector.svg",
        kind="svg",
        if_match=raster_etag,
        payload=(
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        ),
        filename="vector.svg",
    )
    assert unsafe.status == 422
    assert (await unsafe.json())["error"]["code"] == "asset_conversion_failed"
    assert len(fixture.asset_storage.puts) == puts_before_unsafe

    vector = await _upload_asset(
        fixture,
        revision_id=revision_id,
        logical_name="figures/vector.svg",
        kind="svg",
        if_match=raster_etag,
        payload=SAFE_SVG,
        filename="vector.svg",
    )
    assert vector.status == 201, await vector.text()
    vector_etag = vector.headers["ETag"]
    final_etag = vector_etag

    resolved = await fixture.client.get(
        assets_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    resolved_payload = await resolved.json()
    assert resolved_payload["missingAssets"] == []
    assert {item["status"] for item in resolved_payload["assets"]} == {"attached"}

    compiled = await fixture.client.post(
        f"/staff/api/v1/content/revisions/{revision_id}/compile",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=final_etag),
    )
    assert compiled.status == 200, await compiled.text()
    web_preview = await fixture.client.get(
        f"/staff/api/v1/content/revisions/{revision_id}/previews/web",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    web_document = (await web_preview.json())["document"]
    serialized_web = json.dumps(web_document)
    assert raster_payload["asset"]["src"] in serialized_web
    telegram_preview = await fixture.client.get(
        f"/staff/api/v1/content/revisions/{revision_id}/previews/telegram",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    telegram_html = (await telegram_preview.json())["html"]
    assert raster_payload["asset"]["src"] in telegram_html

    media = await fixture.client.get(raster_payload["asset"]["src"])
    assert media.status == 200
    assert (await media.read()).startswith(b"synthetic-webp:")
    assert media.headers["Cache-Control"].endswith("immutable")
    malformed_media = await fixture.client.get("/pwa-content-assets/INVALID")
    assert malformed_media.status == 404
    assert await malformed_media.text() == "Content asset not found"

    puts_before_reuse = len(fixture.asset_storage.puts)
    reused_upload = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_b,
        kind="condition",
        filename="assets/condition.tex",
        source=source.encode(),
    )
    assert reused_upload.status == 201, await reused_upload.text()
    reused_revision = await reused_upload.json()
    reused_inventory = await fixture.client.get(
        f"/staff/api/v1/content/revisions/{reused_revision['revisionId']}/assets",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert reused_inventory.status == 200, await reused_inventory.text()
    assert (await reused_inventory.json())["missingAssets"] == []
    assert len(fixture.asset_storage.puts) == puts_before_reuse

    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS count FROM media_assets").fetchone()[
                "count"
            ],
            connection.execute(
                "SELECT count(*) AS count FROM content_revision_assets"
            ).fetchone()["count"],
        )
    )
    # Direct SVG and TikZ intentionally deduplicate because their sanitized
    # output bytes are identical; all three logical references stay attached.
    assert counts == (2, 6)


@pytest.mark.parametrize(
    (
        "case",
        "target",
        "logical_name",
        "kind",
        "payload",
        "filename",
        "expected_status",
        "expected_code",
    ),
    [
        (
            "missing-if-match",
            "figure",
            None,
            "raster",
            b"raster",
            "photo.heic",
            422,
            "if_match_required",
        ),
        (
            "stale-if-match",
            "figure",
            None,
            "raster",
            b"raster",
            "photo.heic",
            409,
            "version_conflict",
        ),
        (
            "unreferenced-name",
            "figure",
            "figures/not-in-source.webp",
            "raster",
            b"raster",
            "photo.heic",
            422,
            "asset_not_referenced",
        ),
        (
            "tikz-must-not-have-file",
            "tikz",
            None,
            "tikz",
            SAFE_SVG,
            "diagram.svg",
            422,
            "validation_error",
        ),
        (
            "raster-requires-file",
            "figure",
            None,
            "raster",
            None,
            None,
            422,
            "validation_error",
        ),
        (
            "figure-is-not-tikz",
            "figure",
            None,
            "tikz",
            None,
            None,
            422,
            "asset_kind_mismatch",
        ),
        (
            "tikz-is-not-uploaded-svg",
            "tikz",
            None,
            "svg",
            SAFE_SVG,
            "diagram.svg",
            422,
            "asset_kind_mismatch",
        ),
        (
            "unsafe-logical-path",
            "figure",
            "figures/../photo.heic",
            "raster",
            b"raster",
            "photo.heic",
            422,
            "validation_error",
        ),
        (
            "unsafe-source-filename",
            "figure",
            None,
            "raster",
            b"raster",
            " photo.heic ",
            422,
            "validation_error",
        ),
    ],
    ids=[
        "missing-if-match",
        "stale-if-match",
        "unreferenced-name",
        "tikz-must-not-have-file",
        "raster-requires-file",
        "figure-is-not-tikz",
        "tikz-is-not-uploaded-svg",
        "unsafe-logical-path",
        "unsafe-source-filename",
    ],
)
async def test_asset_upload_rejects_stale_unreferenced_or_malformed_requests(
    content_http: ContentHttpFixture,
    case: str,
    target: str,
    logical_name: str | None,
    kind: str,
    payload: bytes | None,
    filename: str | None,
    expected_status: int,
    expected_code: str,
):
    fixture = content_http
    uploaded = await _upload(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename=f"asset-negative/{case}.tex",
        source=(
            r"\задача "
            r"\includegraphics{figures/photo.heic} "
            r"\begin{tikzpicture}x\end{tikzpicture} "
            r"\кзадача"
        ).encode(),
    )
    assert uploaded.status == 201, await uploaded.text()
    revision = await uploaded.json()
    revision_id = revision["revisionId"]
    inventory = await fixture.client.get(
        f"/staff/api/v1/content/revisions/{revision_id}/assets",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert inventory.status == 200, await inventory.text()
    assets = (await inventory.json())["assets"]
    target_name = next(
        item["logicalName"]
        for item in assets
        if item["sourceKind"] == ("tikz" if target == "tikz" else "figure")
    )
    if_match = uploaded.headers["ETag"]
    if case == "missing-if-match":
        if_match = None
    elif case == "stale-if-match":
        if_match = f'"{revision_id}:v999"'

    if case == "unsafe-source-filename":
        boundary = "vmshpwa-unsafe-filename"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            'name="logicalName"\r\n\r\n'
            f"{logical_name or target_name}\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="kind"\r\n\r\n'
            f"{kind}\r\n--{boundary}\r\nContent-Disposition: form-data; "
            'name="asset"; filename=" photo.heic "\r\n'
            "Content-Type: image/heic\r\n\r\nraster\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        response = await fixture.client.post(
            f"/staff/api/v1/content/revisions/{revision_id}/assets",
            data=body,
            cookies=_cookie(fixture, "admin"),
            headers={
                **_headers(unsafe=True, if_match=if_match),
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
    else:
        response = await _upload_asset(
            fixture,
            revision_id=revision_id,
            logical_name=logical_name or target_name,
            kind=kind,
            if_match=if_match,
            payload=payload,
            filename=filename,
        )

    assert response.status == expected_status, await response.text()
    assert (await response.json())["error"]["code"] == expected_code
    stored = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT status, version FROM content_revisions WHERE public_id = ?",
            (revision_id,),
        ).fetchone()
    )
    assert (stored["status"], stored["version"]) == (
        "uploaded",
        revision["version"],
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

    revision_id, problem_id = fixture.factory.run_write(resolve_match_without_metadata)
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


async def test_staff_problem_matching_and_metadata_grid_http_workflow(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    revision, _compile_etag = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="review/condition.tex",
        source=(
            "\\задача[title=Орехи] Сколько орехов? \\кзадача\n"
            "\\задача[title=Ладьи] Расставьте ладьи. \\кзадача"
        ),
        review=False,
    )
    match_url = (
        f"/staff/api/v1/content/revisions/{revision['revisionId']}/problem-matches"
    )
    forbidden = await fixture.client.get(
        match_url,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert forbidden.status == 403

    initial_response = await fixture.client.get(
        match_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert initial_response.status == 200, await initial_response.text()
    initial = await initial_response.json()
    assert initial["version"] == 1
    assert initial["etag"] == initial_response.headers["ETag"]
    assert [item["sourceTitle"] for item in initial["items"]] == [
        "Орехи",
        "Ладьи",
    ]
    assert initial["candidates"] == []
    match_request = {
        "matches": [
            {
                "sourceOrdinal": item["sourceOrdinal"],
                "sourceItem": item["sourceItem"],
                "decision": "insert_new",
                "problemId": None,
            }
            for item in initial["items"]
        ]
    }
    missing_etag = await fixture.client.put(
        match_url,
        json=match_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert missing_etag.status == 422
    assert (await missing_etag.json())["error"]["code"] == "if_match_required"

    partial = await fixture.client.put(
        match_url,
        json={"matches": match_request["matches"][:1]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert partial.status == 422
    assert (await partial.json())["error"]["code"] == "content_validation_failed"

    matched_response = await fixture.client.put(
        match_url,
        json=match_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert matched_response.status == 200, await matched_response.text()
    matched = await matched_response.json()
    assert matched["version"] == 3
    assert all(item["match"]["problemId"] for item in matched["items"])

    stale_match = await fixture.client.put(
        match_url,
        json=match_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert stale_match.status == 409
    assert (await stale_match.json())["error"]["code"] == "version_conflict"

    # A retry made after reading the new ETag is harmless and creates no rows.
    retried_match = await fixture.client.put(
        match_url,
        json=match_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=matched_response.headers["ETag"]),
    )
    assert retried_match.status == 200
    assert (await retried_match.json())["version"] == 3

    grid_url = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/metadata-grid"
    grid_response = await fixture.client.get(
        grid_url,
        params={"revisionId": revision["revisionId"]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert grid_response.status == 200, await grid_response.text()
    grid = await grid_response.json()
    first, second = grid["rows"]
    assert not first["reviewed"] and not second["reviewed"]
    first.update(
        {
            "title": "Сколько орехов",
            "problemType": 1,
            "answerType": 2,
            "answerValidation": None,
            "validationError": "Введите число орехов, например 7",
            "correctAnswer": "7",
            "correctAnswerChecker": None,
            "wrongAnswer": "Нет, не столько орехов",
            "congratulation": "Да, всё верно!",
        }
    )
    second.update(
        {
            "title": "Расстановка ладей",
            "problemType": 2,
            "answerType": None,
            "answerValidation": None,
            "validationError": None,
            "correctAnswer": None,
            "correctAnswerChecker": None,
            "wrongAnswer": None,
            "congratulation": None,
        }
    )
    for row in (first, second):
        row.pop("reviewed")
    metadata_request = {"revisionId": revision["revisionId"], "rows": [first, second]}

    invalid_request = json.loads(json.dumps(metadata_request))
    invalid_request["rows"][1]["correctAnswer"] = "скрытое старое значение"
    invalid = await fixture.client.put(
        grid_url,
        json=invalid_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=grid_response.headers["ETag"]),
    )
    assert invalid.status == 422
    assert (await invalid.json())["error"]["code"] == "content_validation_failed"
    unchanged = await fixture.client.get(
        grid_url,
        params={"revisionId": revision["revisionId"]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert not any(row["reviewed"] for row in (await unchanged.json())["rows"])

    wrong_scope = await fixture.client.put(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_b}/metadata-grid",
        json=metadata_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=grid_response.headers["ETag"]),
    )
    assert wrong_scope.status == 422
    assert (await wrong_scope.json())["error"]["code"] == "revision_scope_mismatch"

    saved_response = await fixture.client.put(
        grid_url,
        json=metadata_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=grid_response.headers["ETag"]),
    )
    assert saved_response.status == 200, await saved_response.text()
    saved = await saved_response.json()
    assert saved["version"] == 5
    assert all(row["reviewed"] for row in saved["rows"])

    conflicting_request = json.loads(json.dumps(metadata_request))
    conflicting_request["rows"][0]["title"] = "Ошибочно изменённое название"
    conflict = await fixture.client.put(
        grid_url,
        json=conflicting_request,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=saved_response.headers["ETag"]),
    )
    assert conflict.status == 409
    assert (await conflict.json())["error"]["code"] == "version_conflict"

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

    created = await _create_lesson_window(fixture, group_lesson=fixture.group_lesson_a)
    assert created.status == 201, await created.text()
    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="solution",
        revision_id=solution["revisionId"],
    )
    assert published.status == 201, await published.text()


async def test_hint_requires_matching_but_not_duplicate_metadata_review(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    revision, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        filename="hint-only/hint.tex",
        source="\\задача Посмотрите на чётность. \\кзадача",
        review=False,
    )
    blocked = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        revision_id=revision["revisionId"],
    )
    assert blocked.status == 422
    assert (await blocked.json())["error"]["code"] == "problem_matching_incomplete"

    match_url = (
        f"/staff/api/v1/content/revisions/{revision['revisionId']}/problem-matches"
    )
    initial_response = await fixture.client.get(
        match_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    initial = await initial_response.json()
    matched = await fixture.client.put(
        match_url,
        json={
            "matches": [
                {
                    "sourceOrdinal": initial["items"][0]["sourceOrdinal"],
                    "sourceItem": initial["items"][0]["sourceItem"],
                    "decision": "insert_new",
                    "problemId": None,
                }
            ]
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert matched.status == 200, await matched.text()

    metadata = await fixture.client.get(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/metadata-grid",
        params={"revisionId": revision["revisionId"]},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert metadata.status == 422
    assert (await metadata.json())["error"]["code"] == "metadata_requires_condition"

    published = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        revision_id=revision["revisionId"],
    )
    assert published.status == 201, await published.text()


async def test_student_reveal_uses_resolved_material_match_without_duplicate_metadata(
    content_http: ContentHttpFixture,
):
    """The Staff UI does not create problem_revisions for hints/solutions."""

    fixture = content_http
    condition, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="material-match/condition.tex",
        source="\\задача[title=Чётность] Условие. \\кзадача",
    )
    published_condition = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=condition["revisionId"],
    )
    assert published_condition.status == 201, await published_condition.text()

    hint, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        filename="material-match/hint.tex",
        source=(
            "\\задача[title=Чётность] Условие. \\кзадача\n"
            "\\подсказка Посмотрите на чётность. \\кподсказка"
        ),
        review=False,
    )
    match_url = f"/staff/api/v1/content/revisions/{hint['revisionId']}/problem-matches"
    initial_response = await fixture.client.get(
        match_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert initial_response.status == 200, await initial_response.text()
    initial = await initial_response.json()
    item = initial["items"][0]
    assert item["suggestedProblemId"] is not None
    matched = await fixture.client.put(
        match_url,
        json={
            "matches": [
                {
                    "sourceOrdinal": item["sourceOrdinal"],
                    "sourceItem": item["sourceItem"],
                    "decision": "auto_position",
                    "problemId": item["suggestedProblemId"],
                }
            ]
        },
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=initial_response.headers["ETag"]),
    )
    assert matched.status == 200, await matched.text()
    matched_problem_id = (await matched.json())["items"][0]["match"]["problemId"]
    assert matched_problem_id == item["suggestedProblemId"]

    published_hint = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="hint",
        revision_id=hint["revisionId"],
    )
    assert published_hint.status == 201, await published_hint.text()

    problem_list = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/lessons/"
        f"{fixture.group_lesson_a}/problems",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert problem_list.status == 200, await problem_list.text()
    problems = (await problem_list.json())["problems"]
    problem_public_id = problems[0]["problemId"]
    assert problem_public_id.startswith("problem-")
    assert problems[0]["materials"]["hint"] == {"status": "available"}

    revealed = await _student_reveal(
        fixture,
        group_lesson=fixture.group_lesson_a,
        problem_id=problem_public_id,
        kind="hint",
    )
    assert revealed.status == 200, await revealed.text()
    payload = await revealed.json()
    assert payload["problemId"] == problem_public_id
    assert "Посмотрите на чётность" in json.dumps(payload, ensure_ascii=False)


async def test_staff_can_preview_and_stream_exact_persisted_pdf(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    revision, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="pdf/condition.tex",
        source="\\задача Условие для PDF. \\кзадача",
    )
    repository = PwaContentRepository(fixture.factory)
    context = await repository.get_revision_context(revision["revisionId"])
    payload = b"%PDF-1.7\nsynthetic staff preview\n%%EOF\n"
    digest = hashlib.sha256(payload).hexdigest()
    object_key = content_addressed_key(PDF_STORAGE_NAMESPACE, payload, "pdf")
    await fixture.asset_storage.put(object_key, payload, "application/pdf")
    asset = await repository.register_media_asset(
        public_id="pdf-asset-content-http",
        sha256=digest,
        storage_namespace=PDF_STORAGE_NAMESPACE,
        object_key=object_key,
        public_url=None,
        media_type="application/pdf",
        byte_size=len(payload),
        width=None,
        height=None,
        source_filename="condition.tex",
        conversion_version=PDF_STORAGE_CONVERSION_VERSION,
        actor_user_id=ADMIN_USER_ID,
    )
    await repository.add_derivative(
        revision_id=context.revision.id,
        kind="pdf",
        renderer_version=PDF_RENDERER_VERSION,
        asset_id=asset.id,
        sha256=digest,
        provenance={"rendererVersion": PDF_RENDERER_VERSION},
    )

    preview_url = (
        f"/staff/api/v1/content/revisions/{revision['revisionId']}/previews/pdf"
    )
    forbidden = await fixture.client.get(
        preview_url,
        cookies=_cookie(fixture, "teacher"),
        headers=_headers(),
    )
    assert forbidden.status == 403
    preview = await fixture.client.get(
        preview_url,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert preview.status == 200, await preview.text()
    preview_payload = await preview.json()
    assert preview_payload == {
        "revisionId": revision["revisionId"],
        "kind": "pdf",
        "src": f"/staff/api/v1/content/revisions/{revision['revisionId']}/pdf",
        "contentSha256": digest,
        "byteSize": len(payload),
        "rendererVersion": PDF_RENDERER_VERSION,
    }

    streamed = await fixture.client.get(
        preview_payload["src"],
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert streamed.status == 200
    assert await streamed.read() == payload
    assert streamed.headers["Content-Type"] == "application/pdf"
    assert streamed.headers["Content-Disposition"] == (
        'inline; filename="condition-revision-1.pdf"'
    )
    assert streamed.headers["ETag"] == f'"sha256-{digest}"'

    fixture.asset_storage.objects[object_key] = payload + b"tampered"
    corrupt = await fixture.client.get(
        preview_payload["src"],
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert corrupt.status == 500
    assert (await corrupt.json())["error"]["code"] == "content_storage_invalid"


async def test_lesson_window_cutoff_has_separate_confirmation_audit_and_etag(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    route = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/lesson-window"
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
    assert created_payload["submissionClosesAt"] == _timestamp(NOW + timedelta(days=4))
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
    assert (
        schedule_payload["submissionClosesAt"] == created_payload["submissionClosesAt"]
    )

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
    with pytest.raises(
        sqlite3.IntegrityError, match="lesson window audit is immutable"
    ):
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
    window = await _create_lesson_window(fixture, group_lesson=fixture.group_lesson_a)
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
    student_hint_without_confirmation = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="hint"
    )
    student_solution_before_publish = await _student_read(
        fixture, group_lesson=fixture.group_lesson_a, kind="solution"
    )
    assert student_condition.status == 200
    assert student_hint_without_confirmation.status == 409
    assert (await student_hint_without_confirmation.json())["error"]["code"] == (
        "reveal_confirmation_required"
    )
    assert student_solution_before_publish.status == 409
    condition_wire = json.dumps(await student_condition.json(), ensure_ascii=False)
    assert "УСЛОВИЕ_ТОЛЬКО" in condition_wire
    assert "РЕШЕНИЕ_ТОЛЬКО" not in condition_wire
    assert "diagnostics" not in condition_wire
    assert "canonical" not in condition_wire
    assert "telegram" not in condition_wire.casefold()

    problem_list_response = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/lessons/"
        f"{fixture.group_lesson_a}/problems",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert problem_list_response.status == 200, await problem_list_response.text()
    problem_list = await problem_list_response.json()
    problem_id = problem_list["problems"][0]["problemId"]
    assert problem_list["problems"][0]["materials"] == {
        "hint": {"status": "available"},
        "solution": {"status": "unavailable"},
    }
    unpublished_solution_reveal = await _student_reveal(
        fixture,
        group_lesson=fixture.group_lesson_a,
        problem_id=problem_id,
        kind="solution",
    )
    assert unpublished_solution_reveal.status == 404
    invalid_reveal_body = await fixture.client.post(
        f"/student/api/v1/group-lessons/{fixture.group_lesson_a}/problems/"
        f"{problem_id}/reveal/hint",
        json={"confirmed": True},
        cookies=_cookie(fixture, "student"),
        headers=_headers(unsafe=True),
    )
    assert invalid_reveal_body.status == 422

    student_hint = await _student_reveal(
        fixture,
        group_lesson=fixture.group_lesson_a,
        problem_id=problem_id,
        kind="hint",
    )
    assert student_hint.status == 200, await student_hint.text()
    hint_payload = await student_hint.json()
    hint_wire = json.dumps(hint_payload, ensure_ascii=False)
    assert hint_payload["problemId"] == problem_id
    assert hint_payload["firstReveal"] is True
    assert hint_payload["document"]["introduction"] == []
    assert len(hint_payload["document"]["problems"]) == 1
    assert "ПОДСКАЗКА_ТОЛЬКО" in hint_wire
    assert "РЕШЕНИЕ_ТОЛЬКО" not in hint_wire
    repeated_hint = await _student_reveal(
        fixture,
        group_lesson=fixture.group_lesson_a,
        problem_id=problem_id,
        kind="hint",
    )
    assert repeated_hint.status == 200
    repeated_hint_payload = await repeated_hint.json()
    assert repeated_hint_payload["firstReveal"] is False
    assert repeated_hint_payload["revealedAt"] == hint_payload["revealedAt"]
    problem_list_after_reveal = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/lessons/"
        f"{fixture.group_lesson_a}/problems",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert (await problem_list_after_reveal.json())["problems"][0]["materials"][
        "hint"
    ] == {"status": "revealed"}

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
    student_solution = await _student_reveal(
        fixture,
        group_lesson=fixture.group_lesson_a,
        problem_id=problem_id,
        kind="solution",
    )
    assert student_solution.status == 200, await student_solution.text()
    solution_payload = await student_solution.json()
    assert solution_payload["firstReveal"] is True
    solution_wire = json.dumps(solution_payload, ensure_ascii=False)
    assert all(value in solution_wire for value in ("ОТВЕТ_ТОЛЬКО", "РЕШЕНИЕ_ТОЛЬКО"))
    assert all(
        value not in solution_wire for value in ("УСЛОВИЕ_ТОЛЬКО", "ПОДСКАЗКА_ТОЛЬКО")
    )
    reveal_rows = fixture.factory.run_read(
        lambda connection: {
            "hint": connection.execute(
                "SELECT count(*) AS count FROM hint_reveals"
            ).fetchone()["count"],
            "solution": connection.execute(
                "SELECT count(*) AS count FROM solution_reveals"
            ).fetchone()["count"],
        }
    )
    assert reveal_rows == {"hint": 1, "solution": 1}

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
    assert split_lineage.status == 201
    split_lineage_payload = await split_lineage.json()
    assert split_lineage_payload["sourceId"] == first["sourceId"]
    assert split_lineage_payload["revisionNumber"] == 3
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
    assert [item["revisionNumber"] for item in condition_state["revisions"]] == [
        3,
        2,
        1,
    ]
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


async def test_student_course_list_projects_checked_session_authority(
    content_http: ContentHttpFixture,
):
    fixture = content_http

    response = await fixture.client.get(
        "/student/api/v1/courses",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )

    assert response.status == 200, await response.text()
    assert response.headers["Cache-Control"] == "no-store"
    payload = await response.json()
    assert payload == {
        "studentId": "user-content-student",
        "enrollments": [
            {
                "enrollmentId": "enrollment-content-http",
                "studentId": "user-content-student",
                "course": {
                    "courseId": "course-content-http",
                    "code": "math",
                    "name": "Математика",
                    "subjectCode": "math",
                    "status": "active",
                    "sortOrder": 1,
                    "accentKey": "math",
                    "version": 1,
                },
                "activeGroupId": "group-content-http-a",
                "allowedGroups": [
                    {
                        "groupId": "group-content-http-a",
                        "courseId": "course-content-http",
                        "code": "a",
                        "name": "A",
                        "status": "active",
                        "sortOrder": 1,
                        "colorKey": "neutral",
                        "version": 1,
                    }
                ],
                "attendanceMode": "online",
                "status": "active",
                "version": 1,
            }
        ],
    }


async def test_student_course_enrollment_is_course_scoped_and_fail_closed(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    allowed = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/enrollment",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    forbidden = await fixture.client.get(
        "/student/api/v1/courses/course-not-granted/enrollment",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )

    assert allowed.status == 200, await allowed.text()
    assert (await allowed.json())["course"]["courseId"] == "course-content-http"
    assert forbidden.status == 403
    assert (await forbidden.json())["error"]["code"] == "forbidden"


async def test_student_course_reads_reject_ambiguous_query_parameters(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    response = await fixture.client.get(
        "/student/api/v1/courses?studentId=user-content-student",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )

    assert response.status == 422
    assert (await response.json())["error"]["code"] == "validation_error"


async def test_student_lesson_list_and_detail_expose_only_published_condition(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    list_url = "/student/api/v1/courses/course-content-http/lessons"
    initially_empty = await fixture.client.get(
        list_url,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert initially_empty.status == 200, await initially_empty.text()
    assert (await initially_empty.json())["lessons"] == []
    empty_home = await fixture.client.get(
        "/student/api/v1/home",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert empty_home.status == 200, await empty_home.text()
    assert (await empty_home.json())["courses"][0]["phase"] == "no_lesson"

    revision, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="student-read/condition.tex",
        source="\\задача Видимое условие \\кзадача",
    )
    window = await _create_lesson_window(fixture, group_lesson=fixture.group_lesson_a)
    assert window.status == 201, await window.text()
    publication = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision["revisionId"],
    )
    assert publication.status == 201, await publication.text()

    listed = await fixture.client.get(
        list_url,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert listed.status == 200, await listed.text()
    payload = await listed.json()
    assert payload["courseId"] == "course-content-http"
    assert payload["groupId"] == "group-content-http-a"
    assert payload["activeGroupId"] == "group-content-http-a"
    assert payload["nextCursor"] is None
    assert len(payload["lessons"]) == 1
    lesson = payload["lessons"][0]
    assert lesson == {
        "groupLessonId": fixture.group_lesson_a,
        "courseLessonId": "course-lesson-content-http",
        "courseId": "course-content-http",
        "groupId": "group-content-http-a",
        "lessonNumber": 41,
        "title": "Занятие 41",
        "cycleAnchorDate": "2026-09-14",
        "businessTimezone": "Europe/Moscow",
        "version": 1,
        "problemCount": 1,
        "window": {
            "windowId": (await window.json())["lessonWindowId"],
            "opensAt": "2026-09-20T13:00:00.000000Z",
            "submissionClosesAt": "2026-09-24T13:00:00.000000Z",
            "hintScheduledAt": None,
            "solutionScheduledAt": "2026-09-24T13:00:00.000000Z",
            "timezone": "Europe/Moscow",
            "source": "native",
            "version": 1,
        },
        "materials": {
            "condition": {
                "status": "published",
                "revisionId": revision["revisionId"],
                "publishedAt": "2026-09-20T13:00:00.000000Z",
                "publicationVersion": 1,
            },
            "hint": {"status": "unavailable"},
            "solution": {"status": "unavailable"},
        },
    }
    detailed = await fixture.client.get(
        f"{list_url}/{fixture.group_lesson_a}",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert detailed.status == 200, await detailed.text()
    assert await detailed.json() == lesson
    home = await fixture.client.get(
        "/student/api/v1/home",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert home.status == 200, await home.text()
    home_payload = await home.json()
    assert home_payload["studentId"] == "user-content-student"
    assert home_payload["generatedAt"] == "2026-09-20T13:00:00.000000Z"
    assert home_payload["courses"] == [
        {
            "enrollment": {
                "enrollmentId": "enrollment-content-http",
                "studentId": "user-content-student",
                "course": {
                    "courseId": "course-content-http",
                    "code": "math",
                    "name": "Математика",
                    "subjectCode": "math",
                    "status": "active",
                    "sortOrder": 1,
                    "accentKey": "math",
                    "version": 1,
                },
                "activeGroupId": "group-content-http-a",
                "allowedGroups": [
                    {
                        "groupId": "group-content-http-a",
                        "courseId": "course-content-http",
                        "code": "a",
                        "name": "A",
                        "status": "active",
                        "sortOrder": 1,
                        "colorKey": "neutral",
                        "version": 1,
                    }
                ],
                "attendanceMode": "online",
                "status": "active",
                "version": 1,
            },
            "phase": "solving",
            "currentLesson": lesson,
        }
    ]

    publication_payload = await publication.json()
    hidden = await fixture.client.post(
        f"/staff/api/v1/publications/{publication_payload['publicationId']}/hide",
        json={},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True, if_match=publication.headers["ETag"]),
    )
    assert hidden.status == 200, await hidden.text()
    after_hide = await fixture.client.get(
        list_url,
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert (await after_hide.json())["lessons"] == []
    home_after_hide = await fixture.client.get(
        "/student/api/v1/home",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert (await home_after_hide.json())["courses"][0]["phase"] == "no_lesson"
    hidden_detail = await fixture.client.get(
        f"{list_url}/{fixture.group_lesson_a}",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert hidden_detail.status == 404


async def test_student_problem_list_uses_opaque_ids_and_logical_work_status(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    revision_a, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        filename="student-problems/a.tex",
        source="""
\\задача Первая задача \\кзадача
\\задача Вторая задача \\кзадача
\\задача Третья задача \\кзадача
\\задача Четвёртая задача \\кзадача
\\задача Синонимичная задача \\кзадача
""",
    )
    publication_a = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_a,
        kind="condition",
        revision_id=revision_a["revisionId"],
    )
    assert publication_a.status == 201, await publication_a.text()

    revision_b, _ = await _upload_and_compile(
        fixture,
        group_lesson=fixture.group_lesson_b,
        kind="condition",
        filename="student-problems/b.tex",
        source="\\задача Синонимичная задача \\кзадача",
    )
    publication_b = await _publish(
        fixture,
        group_lesson=fixture.group_lesson_b,
        kind="condition",
        revision_id=revision_b["revisionId"],
    )
    assert publication_b.status == 201, await publication_b.text()

    def seed_work(connection):
        problems_a = connection.execute(
            "SELECT problem.id, problem.public_id, problem_revision.source_ordinal "
            "FROM problem_revisions AS problem_revision "
            "JOIN content_revisions AS revision "
            "  ON revision.id = problem_revision.content_revision_id "
            "JOIN problems AS problem ON problem.id = problem_revision.problem_id "
            "WHERE revision.public_id = ? ORDER BY problem_revision.source_ordinal",
            (revision_a["revisionId"],),
        ).fetchall()
        problem_b = connection.execute(
            "SELECT problem.id FROM problem_revisions AS problem_revision "
            "JOIN content_revisions AS revision "
            "  ON revision.id = problem_revision.content_revision_id "
            "JOIN problems AS problem ON problem.id = problem_revision.problem_id "
            "WHERE revision.public_id = ?",
            (revision_b["revisionId"],),
        ).fetchone()
        assert len(problems_a) == 5
        connection.executemany(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, answer, res_type) "
            "VALUES (?, ?, 'content-a', 41, ?, ?, ?, '', 1)",
            (
                (
                    STUDENT_USER_ID,
                    problems_a[0]["id"],
                    TEACHER_USER_ID,
                    "2026-09-20T12:00:00Z",
                    17,
                ),
                (
                    STUDENT_USER_ID,
                    problems_a[1]["id"],
                    TEACHER_USER_ID,
                    "2026-09-20T12:01:00Z",
                    17,
                ),
                (
                    STUDENT_USER_ID,
                    problems_a[2]["id"],
                    TEACHER_USER_ID,
                    "2026-09-20T12:02:00Z",
                    -1,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO written_tasks_queue "
            "(ts, student_id, problem_id, cur_status, teacher_ts, teacher_id) "
            "VALUES ('2026-09-20T12:03:00Z', ?, ?, 1, "
            "'2026-09-20T12:03:00Z', ?)",
            (STUDENT_USER_ID, problems_a[1]["id"], TEACHER_USER_ID),
        )
        connection.execute(
            "INSERT INTO written_tasks_discussions "
            "(ts, student_id, problem_id, teacher_id, text) "
            "VALUES ('2026-09-20T12:04:00Z', ?, ?, NULL, 'Отправлено')",
            (STUDENT_USER_ID, problems_a[3]["id"]),
        )
        connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, answer, res_type) "
            "VALUES (?, ?, 'content-b', 41, ?, '2026-09-20T12:05:00Z', 16, '', 2)",
            (STUDENT_USER_ID, problem_b["id"], TEACHER_USER_ID),
        )
        course_lesson_id = connection.execute(
            "SELECT course_lesson_id FROM group_lessons WHERE public_id = ?",
            (fixture.group_lesson_a,),
        ).fetchone()["course_lesson_id"]
        group_lessons = {
            row["public_id"]: row["id"]
            for row in connection.execute(
                "SELECT id, public_id FROM group_lessons WHERE public_id IN (?, ?)",
                (fixture.group_lesson_a, fixture.group_lesson_b),
            )
        }
        return problems_a, int(problem_b["id"]), int(course_lesson_id), group_lessons

    problems_a, problem_b_id, course_lesson_id, group_lessons = (
        fixture.factory.run_write(seed_work)
    )
    repository = PwaContentRepository(fixture.factory, clock=lambda: NOW)
    synonym_group = await repository.create_synonym_group(
        public_id="synonym-student-problems",
        course_lesson_id=course_lesson_id,
        group_key="student-problems",
        display_title="Синонимичная задача",
        actor_user_id=ADMIN_USER_ID,
    )
    await repository.add_synonym_member(
        synonym_group_id=synonym_group.id,
        group_lesson_id=group_lessons[fixture.group_lesson_a],
        problem_id=int(problems_a[4]["id"]),
        actor_user_id=ADMIN_USER_ID,
    )
    await repository.add_synonym_member(
        synonym_group_id=synonym_group.id,
        group_lesson_id=group_lessons[fixture.group_lesson_b],
        problem_id=problem_b_id,
        actor_user_id=ADMIN_USER_ID,
    )

    response = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/lessons/"
        f"{fixture.group_lesson_a}/problems",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["conditionRevisionId"] == revision_a["revisionId"]
    assert payload["courseId"] == "course-content-http"
    assert payload["groupId"] == "group-content-http-a"
    assert payload["groupLessonId"] == fixture.group_lesson_a
    assert [problem["status"] for problem in payload["problems"]] == [
        "accepted",
        "checking",
        "rejected",
        "sent",
        "accepted",
    ]
    assert all(
        problem["problemId"].startswith("problem-") for problem in payload["problems"]
    )
    assert [problem["sourceOrdinal"] for problem in payload["problems"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert all(problem["configVersion"] >= 1 for problem in payload["problems"])
    assert payload["problems"][0]["verdict"] == {
        "verdictId": 17,
        "symbol": "✅+",
        "weight": 1.0,
    }
    assert payload["problems"][1]["verdict"] is None
    assert payload["problems"][4]["verdict"] == {
        "verdictId": 16,
        "symbol": "✅+.",
        "weight": 0.95,
    }

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, answer, res_type) "
            "VALUES (?, ?, 'content-a', 41, ?, '2026-09-20T12:06:00Z', 14, '', 1)",
            (STUDENT_USER_ID, problems_a[1]["id"], TEACHER_USER_ID),
        )
    )
    rechecked = await fixture.client.get(
        "/student/api/v1/courses/course-content-http/lessons/"
        f"{fixture.group_lesson_a}/problems",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    assert rechecked.status == 200, await rechecked.text()
    rechecked_payload = await rechecked.json()
    assert rechecked_payload["problems"][1]["status"] == "rejected"
    assert rechecked_payload["problems"][1]["verdict"]["verdictId"] == 14


async def test_student_lesson_reads_enforce_group_scope_and_strict_cursor(
    content_http: ContentHttpFixture,
):
    fixture = content_http
    base = "/student/api/v1/courses/course-content-http/lessons"
    forbidden_group = await fixture.client.get(
        f"{base}?group=group-content-http-b",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    malformed_cursor = await fixture.client.get(
        f"{base}?cursor=0",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    duplicate_group = await fixture.client.get(
        f"{base}?group=group-content-http-a&group=group-content-http-a",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    forbidden_detail = await fixture.client.get(
        f"{base}/{fixture.group_lesson_b}",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    malformed_detail = await fixture.client.get(
        f"{base}/INVALID-LESSON-ID",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    forbidden_problems = await fixture.client.get(
        f"{base}/{fixture.group_lesson_b}/problems",
        cookies=_cookie(fixture, "student"),
        headers=_headers(),
    )
    forbidden_reveal = await _student_reveal(
        fixture,
        group_lesson=fixture.group_lesson_b,
        problem_id="problem-forbidden-scope",
        kind="hint",
    )

    assert forbidden_group.status == 403
    assert malformed_cursor.status == 422
    assert duplicate_group.status == 422
    assert forbidden_detail.status == 403
    assert forbidden_problems.status == 403
    assert forbidden_reveal.status == 403
    assert malformed_detail.status == 404
