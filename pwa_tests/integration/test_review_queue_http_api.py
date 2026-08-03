"""Real aiohttp/SQLite authorization tests for the Phase-6 review queue."""

from __future__ import annotations

import itertools
import json
import apps.pwa_api.review_routes as review_routes_module
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest
from aiohttp import web
from argon2 import PasswordHasher

from apps import pwa_app
from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from db_methods.pwa.reviews import PwaWrittenReviewQueueRepository
from db_methods.pwa.written_submissions import PwaWrittenSubmissionRepository
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.object_storage import LocalObjectStorage
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from models.pwa.auth import AuthAudience, CredentialHasher


ORIGIN = "http://127.0.0.1:5380"
HOST = "127.0.0.1:5380"
NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)
TEST_HASHER = PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)
STUDENT_ID = 953_001
FULL_TEACHER_ID = 953_002
PARTIAL_TEACHER_ID = 953_003
ADMIN_ID = 953_004


@dataclass(frozen=True, slots=True)
class ReviewHttpFixture:
    client: object
    factory: PwaConnectionFactory
    queue_public_ids: tuple[str, str]
    cookies: MappingProxyType
    student_cookie: str
    family_cookie: str
    telegram_calls: list[tuple[int, str, tuple[bytes, ...]]]
    render_calls: list[dict[str, object]]
    telegram_should_fail: list[bool]
    render_should_fail: list[bool]


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


def _seed_review_http(factory: PwaConnectionFactory) -> tuple[str, str]:
    now = _timestamp()

    def seed(connection):
        connection.execute("DELETE FROM kv_logins")
        connection.executemany(
            "INSERT INTO users (id, public_id, chat_id, type, name, surname) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                (
                    STUDENT_ID,
                    "review-http-student",
                    9_530_001,
                    int(USER_TYPE.STUDENT),
                    "Анна",
                    "Белова",
                ),
                (
                    FULL_TEACHER_ID,
                    "review-http-teacher-full",
                    None,
                    int(USER_TYPE.TEACHER),
                    "Мария",
                    "Полная",
                ),
                (
                    PARTIAL_TEACHER_ID,
                    "review-http-teacher-partial",
                    None,
                    int(USER_TYPE.TEACHER),
                    "Иван",
                    "Частичный",
                ),
                (
                    ADMIN_ID,
                    "review-http-admin",
                    None,
                    int(USER_TYPE.ADMIN),
                    "Ада",
                    "Администратор",
                ),
            ),
        )
        student_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, credential_kind, "
                "credential_hash, linked_user_id, status, created_at, updated_at) "
                "VALUES ('review-http-account-student', 'student', "
                "'review-http-student', 'review-http-student', 1, 'synthetic-test', "
                "'telegram_token', ?, ?, 'active', ?, ?) RETURNING id",
                (TEST_HASHER.hash("student-token"), STUDENT_ID, now, now),
            ).fetchone()["id"]
        )
        assert student_account_id > 0
        family_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "provisioning_source, display_name, credential_kind, credential_hash, "
                "status, created_at, updated_at) VALUES "
                "('review-http-account-family', 'family', 'review-http-family', "
                "'review-http-family', 'synthetic-test', 'Семья Беловых', 'password', "
                "?, 'active', ?, ?) RETURNING id",
                (TEST_HASHER.hash("family-password"), now, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, is_primary, created_at, updated_at) "
            "VALUES (?, ?, 1, ?, ?)",
            (family_account_id, STUDENT_ID, now, now),
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(public_id, code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) VALUES "
                "('review-http-season', 'review-http', 'Review HTTP', "
                "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) "
                "RETURNING id",
                (now, now),
            ).fetchone()["id"]
        )
        course_id = int(
            connection.execute(
                "INSERT INTO courses "
                "(public_id, season_id, code, name, subject_code, status, "
                "sort_order, accent_key, created_at, updated_at) VALUES "
                "('review-http-course', ?, 'math', 'Математика', 'math', "
                "'active', 1, 'math', ?, ?) RETURNING id",
                (season_id, now, now),
            ).fetchone()["id"]
        )
        for group_id, public_id, short_code, sort_order in (
            ("review-http-a", "review-http-group-a", "a", 1),
            ("review-http-b", "review-http-group-b", "b", 2),
        ):
            connection.execute(
                "INSERT INTO groups "
                "(group_id, short_code, public_name, sort_order, is_active, "
                "is_default, allow_self_switch, is_system, score_weight, public_id, "
                "course_id, status, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, ?, 'active', ?, ?)",
                (
                    group_id,
                    short_code,
                    f"Группа {short_code}",
                    sort_order,
                    public_id,
                    course_id,
                    now,
                    now,
                ),
            )
        connection.executemany(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, display_name, "
            "credential_kind, credential_hash, linked_user_id, status, "
            "created_at, updated_at) VALUES (?, 'staff', ?, ?, NULL, "
            "'synthetic-test', NULL, 'password', ?, ?, 'active', ?, ?)",
            (
                (
                    "review-http-account-full",
                    "review-http-full",
                    "review-http-full",
                    TEST_HASHER.hash("full-password"),
                    FULL_TEACHER_ID,
                    now,
                    now,
                ),
                (
                    "review-http-account-partial",
                    "review-http-partial",
                    "review-http-partial",
                    TEST_HASHER.hash("partial-password"),
                    PARTIAL_TEACHER_ID,
                    now,
                    now,
                ),
                (
                    "review-http-account-admin",
                    "review-http-admin",
                    "review-http-admin",
                    TEST_HASHER.hash("admin-password"),
                    ADMIN_ID,
                    now,
                    now,
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, created_at, "
            "updated_at) VALUES (?, ?, ?, 'teacher', ?, ?, ?)",
            (
                (FULL_TEACHER_ID, course_id, None, now, now, now),
                (
                    PARTIAL_TEACHER_ID,
                    course_id,
                    "review-http-a",
                    now,
                    now,
                    now,
                ),
            ),
        )
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(public_id, course_id, lesson_number, created_at, updated_at) "
                "VALUES ('review-http-course-lesson', ?, 41, ?, ?) RETURNING id",
                (course_id, now, now),
            ).fetchone()["id"]
        )
        synonym_id = int(
            connection.execute(
                "INSERT INTO problem_synonym_groups "
                "(public_id, course_lesson_id, group_key, display_title, status, "
                "created_at, updated_at) VALUES "
                "('review-http-synonym', ?, 'shared', 'Общая задача', 'active', ?, ?) "
                "RETURNING id",
                (course_lesson_id, now, now),
            ).fetchone()["id"]
        )
        queue_public_ids: list[str] = []
        for index, group_id in enumerate(("review-http-a", "review-http-b"), start=1):
            group_lesson_id = int(
                connection.execute(
                    "INSERT INTO group_lessons "
                    "(public_id, course_lesson_id, course_id, group_id, "
                    "cycle_anchor_date, business_timezone, status, created_at, "
                    "updated_at) VALUES (?, ?, ?, ?, '2026-09-28', "
                    "'Europe/Moscow', 'active', ?, ?) RETURNING id",
                    (
                        f"review-http-group-lesson-{index}",
                        course_lesson_id,
                        course_id,
                        group_id,
                        now,
                        now,
                    ),
                ).fetchone()["id"]
            )
            problem_id = int(
                connection.execute(
                    "INSERT INTO problems "
                    "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                    "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                    "congrat, synonyms) VALUES "
                    "(?, 41, ?, '', ?, '', 2, 0, '', '', '', '', '', '') "
                    "RETURNING id",
                    (group_id, index, f"Общая задача, ветка {index}"),
                ).fetchone()["id"]
            )
            source_id = int(
                connection.execute(
                    "INSERT INTO content_sources "
                    "(public_id, group_lesson_id, kind, logical_filename, "
                    "source_encoding, created_at) VALUES (?, ?, 'condition', ?, "
                    "'utf-8', ?) RETURNING id",
                    (
                        f"review-http-source-{index}",
                        group_lesson_id,
                        f"review-http-{index}.tex",
                        now,
                    ),
                ).fetchone()["id"]
            )
            revision_id = int(
                connection.execute(
                    "INSERT INTO content_revisions "
                    "(public_id, source_id, revision_number, source_sha256, "
                    "latex_text, parser_version, status, canonical_json, "
                    "diagnostics_json, provenance_json, created_at) VALUES "
                    "(?, ?, 1, ?, 'problem', 'review-http-test', 'ready', '{}', "
                    "'[]', '{}', ?) RETURNING id",
                    (
                        f"review-http-revision-{index}",
                        source_id,
                        str(index) * 64,
                        now,
                    ),
                ).fetchone()["id"]
            )
            connection.execute(
                "INSERT INTO content_problem_matches "
                "(content_revision_id, source_ordinal, source_item, problem_id, "
                "decision, resolved_by_user_id, resolved_at, diagnostics_json, "
                "created_at) VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
                (revision_id, problem_id, ADMIN_ID, now, now),
            )
            problem_revision_id = int(
                connection.execute(
                    "INSERT INTO problem_revisions "
                    "(problem_id, content_revision_id, source_ordinal, source_item, "
                    "display_number, title, normalized_title, problem_type, answer_type, "
                    "answer_config_json, attempt_policy_json, config_version, created_at) "
                    "VALUES (?, ?, 1, '1', ?, ?, ?, 2, 0, '{}', '{}', 1, ?)",
                    (
                        problem_id,
                        revision_id,
                        f"41{index}",
                        f"Общая задача, ветка {index}",
                        f"общая задача ветка {index}",
                        now,
                    ),
                ).lastrowid
            )
            connection.execute(
                "INSERT INTO problem_synonym_members "
                "(synonym_group_id, group_lesson_id, problem_id, added_by_user_id, "
                "added_at, membership_version) VALUES (?, ?, ?, ?, ?, 1)",
                (synonym_id, group_lesson_id, problem_id, ADMIN_ID, now),
            )
            submitted_at = _timestamp(NOW - timedelta(minutes=3 - index))
            thread_id = int(
                connection.execute(
                    "INSERT INTO submission_threads "
                    "(public_id, student_user_id, problem_id, condition_revision_id, "
                    "status, latest_entry_at, created_at, updated_at, version) "
                    "VALUES (?, ?, ?, ?, 'awaiting_review', ?, ?, ?, 2) RETURNING id",
                    (
                        f"review-http-thread-{index}",
                        STUDENT_ID,
                        problem_id,
                        revision_id,
                        submitted_at,
                        submitted_at,
                        submitted_at,
                    ),
                ).fetchone()["id"]
            )
            entry_id = int(
                connection.execute(
                    "INSERT INTO submission_entries "
                    "(public_id, thread_id, problem_revision_id, author_kind, "
                    "author_user_id, channel, entry_kind, state, text, client_created_at, "
                    "server_received_at, version) VALUES (?, ?, ?, 'student', ?, 'pwa', "
                    "'submission', 'submitted', ?, ?, ?, 2) RETURNING id",
                    (
                        f"review-http-entry-{index}",
                        thread_id,
                        problem_revision_id,
                        STUDENT_ID,
                        f"Решение HTTP {index}",
                        submitted_at,
                        submitted_at,
                    ),
                ).fetchone()["id"]
            )
            if index == 1:
                asset_id = int(
                    connection.execute(
                        "INSERT INTO media_assets "
                        "(public_id, sha256, storage_namespace, object_key, public_url, "
                        "media_type, byte_size, width, height, source_filename, "
                        "conversion_version, created_by_user_id, created_at) "
                        "VALUES ('review-http-asset-1', ?, 'submission', "
                        "'submission/review-http-asset-1.webp', "
                        "'https://assets.test/review-http-asset-1.webp', "
                        "'image/webp', 1024, 1200, 900, 'page.webp', "
                        "'submission-webp-v1', ?, ?) RETURNING id",
                        ("f" * 64, STUDENT_ID, submitted_at),
                    ).fetchone()["id"]
                )
                connection.execute(
                    "INSERT INTO submission_attachments "
                    "(public_id, entry_id, asset_id, ordinal, client_filename, "
                    "upload_status, created_at) VALUES "
                    "('review-http-attachment-1', ?, ?, 0, 'page.webp', 'stored', ?)",
                    (entry_id, asset_id, submitted_at),
                )
            queue_public_id = f"review-http-queue-{index}"
            connection.execute(
                "INSERT INTO written_tasks_queue "
                "(public_id, ts, student_id, problem_id, cur_status, updated_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (
                    queue_public_id,
                    submitted_at,
                    STUDENT_ID,
                    problem_id,
                    now,
                ),
            )
            queue_public_ids.append(queue_public_id)
        return tuple(queue_public_ids)

    return factory.run_write(seed)


@pytest.fixture()
async def review_http(tmp_path, aiohttp_client, monkeypatch) -> ReviewHttpFixture:
    database_path = tmp_path / "review-http.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    queue_public_ids = _seed_review_http(factory)
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
    claim_tokens = (f"review-http-claim-{index}" for index in itertools.count(1))
    review_repository = PwaWrittenReviewQueueRepository(
        factory,
        clock=lambda: NOW,
        claim_token_factory=lambda: next(claim_tokens),
        review_public_id_factory=lambda: "review-http-completed",
        annotation_public_id_factory=lambda: "review-http-annotation",
        comment_public_id_factory=lambda: "review-http-comment",
        event_public_id_factory=lambda: "review-http-event",
    )
    telegram_calls: list[tuple[int, str, tuple[bytes, ...]]] = []
    render_calls: list[dict[str, object]] = []
    telegram_should_fail = [False]
    render_should_fail = [False]

    async def render_composite(**kwargs) -> bytes:
        render_calls.append(kwargs)
        if render_should_fail[0]:
            raise RuntimeError("synthetic renderer failure")
        return b"\x89PNG\r\n\x1a\nfake-review-annotation"

    async def send_review_telegram(
        chat_id: int,
        text: str,
        images: tuple[bytes, ...],
    ) -> None:
        telegram_calls.append((chat_id, text, images))
        if telegram_should_fail[0]:
            raise RuntimeError("synthetic Telegram failure")

    monkeypatch.setattr(
        review_routes_module,
        "render_review_annotation_composite_png",
        render_composite,
    )
    storage = LocalObjectStorage(tmp_path / "media")
    await storage.put(
        "submission/review-http-asset-1.webp",
        b"review-http-source-webp",
        "image/webp",
    )
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="review-http-test",
        config_name="review_http_test",
        pwa_prototype=True,
        nats_server=None,
    )
    pwa_app.configure(
        app,
        broker=InProcessBroker("review_http_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
        review_queue_repository=review_repository,
        review_telegram_sender=send_review_telegram,
        written_submission_repository=PwaWrittenSubmissionRepository(
            factory, clock=lambda: NOW
        ),
    )
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    app[PWA_CONTENT_OBJECT_STORAGE] = storage
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
            "full": await login(
                AuthAudience.STAFF, "review-http-full", "full-password"
            ),
            "partial": await login(
                AuthAudience.STAFF, "review-http-partial", "partial-password"
            ),
            "admin": await login(
                AuthAudience.STAFF, "review-http-admin", "admin-password"
            ),
        }
    )
    return ReviewHttpFixture(
        client=client,
        factory=factory,
        queue_public_ids=queue_public_ids,
        cookies=cookies,
        student_cookie=await login(
            AuthAudience.STUDENT, "review-http-student", "student-token"
        ),
        family_cookie=await login(
            AuthAudience.FAMILY, "review-http-family", "family-password"
        ),
        telegram_calls=telegram_calls,
        render_calls=render_calls,
        telegram_should_fail=telegram_should_fail,
        render_should_fail=render_should_fail,
    )


def _headers(*, unsafe: bool = False) -> dict[str, str]:
    headers = {"Host": HOST, "X-Request-ID": "review.http.test"}
    if unsafe:
        headers.update({"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"})
    return headers


def _cookie(fixture: ReviewHttpFixture, identity: str) -> dict[str, str]:
    return {COOKIE_POLICY[AuthAudience.STAFF].access_name: fixture.cookies[identity]}


def _student_cookie(fixture: ReviewHttpFixture) -> dict[str, str]:
    return {COOKIE_POLICY[AuthAudience.STUDENT].access_name: fixture.student_cookie}


def _family_cookie(fixture: ReviewHttpFixture) -> dict[str, str]:
    return {COOKIE_POLICY[AuthAudience.FAMILY].access_name: fixture.family_cookie}


def _complete_payload(lease: dict[str, object]) -> dict[str, object]:
    evidence_by_queue = {
        branch["queueId"]: branch for branch in lease["evidenceBranches"]
    }
    return {
        "schemaVersion": 1,
        "claimToken": lease["claimToken"],
        "idempotencyKey": "review-http-complete-1",
        "verdict": 16,
        "comment": "Проверено через Staff PWA.",
        "confirmWithoutComment": False,
        "branches": [
            {
                "queueId": branch["queueId"],
                "leaseVersion": branch["leaseVersion"],
                "threadId": evidence_by_queue[branch["queueId"]]["thread"]["threadId"],
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
        "annotations": [],
        "internalReactionId": None,
    }


def _annotation_payload() -> dict[str, object]:
    return {
        "attachmentId": "review-http-attachment-1",
        "schemaVersion": 1,
        "rotation": 90,
        "marks": [
            {
                "markId": "review-http-mark-1",
                "kind": "arrow",
                "data": {
                    "start": {"x": 0.1, "y": 0.2},
                    "end": {"x": 0.5, "y": 0.6},
                    "width": 0.01,
                    "color": "red",
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_review_list_is_private_and_logical_case_scope_is_fail_closed(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    anonymous = await fixture.client.get(
        "/staff/api/v1/review/items", headers=_headers()
    )
    assert anonymous.status == 401

    full = await fixture.client.get(
        "/staff/api/v1/review/items",
        cookies=_cookie(fixture, "full"),
        headers=_headers(),
    )
    assert full.status == 200, await full.text()
    payload = await full.json()
    assert payload["schemaVersion"] == 1
    assert payload["requestId"] == "review.http.test"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["queueId"] == fixture.queue_public_ids[0]
    assert payload["items"][0]["logicalCaseId"] == "review-http-synonym"
    assert len(payload["items"][0]["branches"]) == 2
    assert "student_user_id" not in str(payload)

    partial = await fixture.client.get(
        "/staff/api/v1/review/items",
        cookies=_cookie(fixture, "partial"),
        headers=_headers(),
    )
    assert partial.status == 200
    assert (await partial.json())["items"] == []

    forbidden_claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{fixture.queue_public_ids[0]}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "partial"),
        headers=_headers(unsafe=True),
    )
    assert forbidden_claim.status == 403
    assert (await forbidden_claim.json())["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_claim_heartbeat_owner_and_release_are_enforced(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    queue_id = fixture.queue_public_ids[0]
    cursors_before_claim = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert claim.status == 200, await claim.text()
    claim_payload = await claim.json()
    claim_token = claim_payload["lease"]["claimToken"]
    assert claim_token == "review-http-claim-1"
    assert len(claim_payload["lease"]["branches"]) == 2
    cursors_after_claim = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    assert cursors_after_claim == {
        **cursors_before_claim,
        "staff": cursors_before_claim["staff"] + 1,
    }

    conflict = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert conflict.status == 409
    assert (await conflict.json())["error"]["code"] == "review_already_claimed"
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_claim
    )

    foreign_release = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/release",
        json={"schemaVersion": 1, "claimToken": claim_token},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert foreign_release.status == 409
    assert (await foreign_release.json())["error"]["code"] == "review_lease_lost"
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_claim
    )

    heartbeat = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/heartbeat",
        json={"schemaVersion": 1, "claimToken": claim_token},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert heartbeat.status == 200, await heartbeat.text()
    assert {
        branch["leaseVersion"]
        for branch in (await heartbeat.json())["lease"]["branches"]
    } == {2}
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == (
        cursors_after_claim
    )

    released = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/release",
        json={"schemaVersion": 1, "claimToken": claim_token},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert released.status == 200, await released.text()
    assert (await released.json())["releasedItems"] == 2
    cursors_after_release = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    assert cursors_after_release == {
        **cursors_after_claim,
        "staff": cursors_after_claim["staff"] + 1,
    }

    reclaimed = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert reclaimed.status == 200, await reclaimed.text()
    assert (await reclaimed.json())["lease"]["claimToken"] == "review-http-claim-2"
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_after_release,
        "staff": cursors_after_release["staff"] + 1,
    }


@pytest.mark.asyncio
async def test_review_mutations_reject_non_strict_body(review_http: ReviewHttpFixture):
    fixture = review_http
    response = await fixture.client.post(
        f"/staff/api/v1/review/items/{fixture.queue_public_ids[0]}/claim",
        json={"schemaVersion": 1, "teacherUserId": FULL_TEACHER_ID},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert response.status == 422
    assert (await response.json())["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_complete_review_is_atomic_and_idempotent_over_http(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert claim.status == 200, await claim.text()
    lease = (await claim.json())["lease"]
    assert [branch["problemNumber"] for branch in lease["branches"]] == [
        "41a.1",
        "41b.2",
    ]
    assert {branch["courseName"] for branch in lease["branches"]} == {"Математика"}
    assert [branch["thread"]["threadId"] for branch in lease["evidenceBranches"]] == [
        "review-http-thread-1",
        "review-http-thread-2",
    ]
    assert [
        entry["authorKind"]
        for branch in lease["evidenceBranches"]
        for entry in branch["thread"]["timelineEntries"]
    ] == ["student", "student"]
    payload = _complete_payload(lease)
    payload["internalReactionId"] = 100
    payload["annotations"] = [_annotation_payload()]

    completed = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert completed.status == 200, await completed.text()
    result = (await completed.json())["review"]
    assert result == {
        "reviewId": "review-http-completed",
        "targetThreadId": "review-http-thread-2",
        "targetProblemId": lease["branches"][1]["problemId"],
        "targetThreadStatus": "accepted",
        "verdict": 16,
        "commentEntryId": "review-http-comment",
        "evidenceEntryIds": ["review-http-entry-1", "review-http-entry-2"],
        "annotations": [
            {
                "annotationId": "review-http-annotation",
                "attachmentId": "review-http-attachment-1",
                "schemaVersion": 1,
                "rotation": 90,
                "markCount": 1,
            }
        ],
        "internalReaction": {
            "reviewId": "review-http-completed",
            "reactionId": 100,
            "version": 1,
            "editableUntil": _timestamp(NOW + timedelta(hours=1)),
            "updatedAt": _timestamp(),
            "deleted": False,
        },
        "completedAt": _timestamp(),
        "replayed": False,
    }

    replay = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 200, await replay.text()
    assert (await replay.json())["review"]["replayed"] is True
    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM results) AS results, "
            "(SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM written_tasks_queue) AS queue"
        ).fetchone()
    )
    assert counts == {"results": 1, "reviews": 1, "queue": 0}
    assert len(fixture.telegram_calls) == 1
    telegram_chat_id, telegram_text, telegram_images = fixture.telegram_calls[0]
    assert telegram_chat_id == 9_530_001
    assert "41a.1 — Общая задача, ветка 1" in telegram_text
    assert "41b.2 — Общая задача, ветка 2" in telegram_text
    assert "Результат: ✅+." in telegram_text
    assert "Проверено через Staff PWA." in telegram_text
    assert telegram_images == (b"\x89PNG\r\n\x1a\nfake-review-annotation",)
    assert fixture.render_calls == [
        {
            "source_webp": b"review-http-source-webp",
            "rotation": 90,
            "marks": payload["annotations"][0]["marks"],
        }
    ]
    notifications = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.public_id AS account_public_id, event.category, "
            "event.route, event.payload_json, event.deliver_after "
            "FROM notification_events AS event "
            "JOIN auth_accounts AS account ON account.id = event.account_id"
        ).fetchall()
    )
    assert len(notifications) == 1
    assert notifications[0]["account_public_id"] == "review-http-account-student"
    assert notifications[0]["category"] == "review_completed"
    assert notifications[0]["route"] == "/student/notifications"
    assert notifications[0]["deliver_after"] == _timestamp(NOW + timedelta(minutes=30))
    assert json.loads(notifications[0]["payload_json"]) == {
        "count": 1,
        "reviewIds": ["review-http-completed"],
        "problemIds": [branch["problemId"] for branch in lease["branches"]],
    }


@pytest.mark.asyncio
async def test_review_telegram_failures_do_not_rollback_completed_review(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    fixture.render_should_fail[0] = True
    fixture.telegram_should_fail[0] = True
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert claim.status == 200, await claim.text()
    payload = _complete_payload((await claim.json())["lease"])
    payload["annotations"] = [_annotation_payload()]

    response = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )

    assert response.status == 200, await response.text()
    assert (await response.json())["review"]["replayed"] is False
    assert len(fixture.render_calls) == 1
    assert len(fixture.telegram_calls) == 1
    assert fixture.telegram_calls[0][2] == ()
    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM results) AS results"
        ).fetchone()
    )
    assert counts == {"reviews": 1, "results": 1}


@pytest.mark.asyncio
async def test_review_telegram_projection_read_failure_is_post_commit_only(
    review_http: ReviewHttpFixture,
    monkeypatch,
):
    fixture = review_http

    def fail_read(*_args, **_kwargs):
        raise RuntimeError("synthetic post-commit read failure")

    monkeypatch.setattr(
        review_routes_module,
        "read_review_telegram_delivery",
        fail_read,
    )
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    payload = _complete_payload((await claim.json())["lease"])

    response = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )

    assert response.status == 200, await response.text()
    assert fixture.telegram_calls == []
    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM results) AS results"
        ).fetchone()
    )
    assert counts == {"reviews": 1, "results": 1}


@pytest.mark.asyncio
async def test_admin_correction_is_append_only_and_marks_old_reaction_stale(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    lease = (await claim.json())["lease"]
    completion_payload = _complete_payload(lease)
    completion_payload["internalReactionId"] = 100
    completed = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=completion_payload,
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert completed.status == 200, await completed.text()
    source_review_id = (await completed.json())["review"]["reviewId"]
    correction_payload = {
        "schemaVersion": 1,
        "idempotencyKey": "review-http-correction-1",
        "verdict": 13,
        "comment": "Перепроверено администратором: переход не доказан.",
        "confirmWithoutComment": False,
    }

    corrected = await fixture.client.post(
        f"/staff/api/v1/reviews/{source_review_id}/correction",
        json=correction_payload,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert corrected.status == 200, await corrected.text()
    correction = (await corrected.json())["correction"]
    assert correction["correctsReviewId"] == source_review_id
    assert correction["verdict"] == 13
    assert correction["threadStatus"] == "needs_work"
    assert correction["replayed"] is False

    replay = await fixture.client.post(
        f"/staff/api/v1/reviews/{source_review_id}/correction",
        json=correction_payload,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert replay.status == 200, await replay.text()
    assert (await replay.json())["correction"]["replayed"] is True

    stale = await fixture.client.post(
        f"/staff/api/v1/reviews/{source_review_id}/correction",
        json={**correction_payload, "idempotencyKey": "review-http-correction-2"},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "review_correction_stale"

    forbidden = await fixture.client.post(
        f"/staff/api/v1/reviews/{correction['reviewId']}/correction",
        json={**correction_payload, "idempotencyKey": "review-http-correction-3"},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert forbidden.status == 403

    inbox = await fixture.client.get(
        "/staff/api/v1/review/reactions",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert inbox.status == 200, await inbox.text()
    teacher_reaction = (await inbox.json())["items"][0]
    assert teacher_reaction["reviewId"] == source_review_id
    assert teacher_reaction["isLatestReview"] is False
    assert [entry["entryId"] for entry in teacher_reaction["evidenceEntries"]] == [
        "review-http-entry-1",
        "review-http-entry-2",
    ]
    assert teacher_reaction["evidenceEntries"][0]["attachments"] == [
        {"attachmentId": "review-http-attachment-1", "ordinal": 0}
    ]
    stored = fixture.factory.run_read(
        lambda connection: {
            "review_verdicts": [
                row["verdict"]
                for row in connection.execute(
                    "SELECT verdict FROM submission_reviews ORDER BY id"
                ).fetchall()
            ],
            "result_verdicts": [
                row["verdict"]
                for row in connection.execute(
                    "SELECT verdict FROM results ORDER BY id"
                ).fetchall()
            ],
        }
    )
    assert stored == {"review_verdicts": [16, 13], "result_verdicts": [-2, 13]}


@pytest.mark.asyncio
async def test_internal_reaction_http_is_strict_optimistic_and_reviewer_owned(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    lease = (await claim.json())["lease"]
    completed = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=_complete_payload(lease),
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert completed.status == 200, await completed.text()
    review_id = (await completed.json())["review"]["reviewId"]

    selected = await fixture.client.put(
        f"/staff/api/v1/reviews/{review_id}/internal-reaction",
        json={"schemaVersion": 1, "reactionId": 103, "expectedVersion": 0},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert selected.status == 200, await selected.text()
    selected_payload = (await selected.json())["internalReaction"]
    assert selected_payload["reactionId"] == 103
    assert selected_payload["version"] == 1
    assert selected_payload["deleted"] is False

    stale = await fixture.client.put(
        f"/staff/api/v1/reviews/{review_id}/internal-reaction",
        json={"schemaVersion": 1, "reactionId": 101, "expectedVersion": 0},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == ("review_internal_reaction_changed")

    foreign = await fixture.client.put(
        f"/staff/api/v1/reviews/{review_id}/internal-reaction",
        json={"schemaVersion": 1, "reactionId": 101, "expectedVersion": 1},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert foreign.status == 403
    assert (await foreign.json())["error"]["code"] == "forbidden"

    invalid = await fixture.client.put(
        f"/staff/api/v1/reviews/{review_id}/internal-reaction",
        json={"schemaVersion": 1, "reactionId": 1, "expectedVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert invalid.status == 422
    assert (await invalid.json())["error"]["code"] == (
        "review_internal_reaction_invalid"
    )

    deleted = await fixture.client.delete(
        f"/staff/api/v1/reviews/{review_id}/internal-reaction",
        json={"schemaVersion": 1, "expectedVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert deleted.status == 200, await deleted.text()
    deleted_payload = (await deleted.json())["internalReaction"]
    assert deleted_payload["reactionId"] is None
    assert deleted_payload["version"] == 2
    assert deleted_payload["deleted"] is True


@pytest.mark.asyncio
async def test_student_reaction_http_updates_owner_and_family_projection(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    lease = (await claim.json())["lease"]
    complete_payload = _complete_payload(lease)
    complete_payload["internalReactionId"] = 103
    completed = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=complete_payload,
        cookies=_cookie(fixture, "full"),
        headers=_headers(unsafe=True),
    )
    assert completed.status == 200, await completed.text()
    review = (await completed.json())["review"]
    review_id = review["reviewId"]
    problem_id = review["targetProblemId"]

    cursors_before = dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"])
    invalid = await fixture.client.put(
        f"/student/api/v1/reviews/{review_id}/reaction",
        json={"schemaVersion": 1, "reactionId": 100, "expectedVersion": 0},
        cookies=_student_cookie(fixture),
        headers=_headers(unsafe=True),
    )
    assert invalid.status == 422
    assert (await invalid.json())["error"]["code"] == (
        "review_student_reaction_invalid"
    )
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == cursors_before

    selected = await fixture.client.put(
        f"/student/api/v1/reviews/{review_id}/reaction",
        json={"schemaVersion": 1, "reactionId": 0, "expectedVersion": 0},
        cookies=_student_cookie(fixture),
        headers=_headers(unsafe=True),
    )
    assert selected.status == 200, await selected.text()
    selected_payload = await selected.json()
    assert selected_payload["reviewId"] == review_id
    assert selected_payload["studentReaction"] == {
        "reactionId": 0,
        "version": 1,
        "editableUntil": _timestamp(NOW + timedelta(hours=1)),
        "updatedAt": _timestamp(NOW),
        "deleted": False,
    }
    assert dict(fixture.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_before,
        "student": cursors_before["student"] + 1,
        "family": cursors_before["family"] + 1,
        "staff": cursors_before["staff"] + 1,
    }

    stale = await fixture.client.put(
        f"/student/api/v1/reviews/{review_id}/reaction",
        json={"schemaVersion": 1, "reactionId": 2, "expectedVersion": 0},
        cookies=_student_cookie(fixture),
        headers=_headers(unsafe=True),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == ("review_student_reaction_changed")

    student_thread = await fixture.client.get(
        f"/student/api/v1/problems/{problem_id}/thread",
        cookies=_student_cookie(fixture),
        headers=_headers(),
    )
    assert student_thread.status == 200, await student_thread.text()
    student_review = (await student_thread.json())["thread"]["reviews"][0]
    assert student_review["studentReaction"] == selected_payload["studentReaction"]
    assert "internalReaction" not in student_review

    family_thread = await fixture.client.get(
        f"/family/api/v1/children/review-http-student/problems/{problem_id}/thread",
        cookies=_family_cookie(fixture),
        headers=_headers(),
    )
    assert family_thread.status == 200, await family_thread.text()
    family_review = (await family_thread.json())["thread"]["reviews"][0]
    assert family_review["studentReaction"] == selected_payload["studentReaction"]
    assert "internalReaction" not in family_review

    teacher_inbox = await fixture.client.get(
        "/staff/api/v1/review/reactions",
        cookies=_cookie(fixture, "full"),
        headers=_headers(),
    )
    assert teacher_inbox.status == 403

    admin_inbox = await fixture.client.get(
        "/staff/api/v1/review/reactions",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert admin_inbox.status == 200, await admin_inbox.text()
    inbox_payload = await admin_inbox.json()
    assert inbox_payload["schemaVersion"] == 1
    assert inbox_payload["nextCursor"] is None
    assert len(inbox_payload["items"]) == 2
    inbox_by_kind = {item["kind"]: item for item in inbox_payload["items"]}
    assert set(inbox_by_kind) == {"student", "teacher"}
    assert inbox_by_kind["student"]["reactionId"] == 0
    assert inbox_by_kind["student"]["student"] == {
        "studentId": "review-http-student",
        "displayName": "Белова Анна",
    }
    assert inbox_by_kind["teacher"]["reactionId"] == 103
    assert inbox_by_kind["teacher"]["reviewer"] == {
        "staffId": "review-http-teacher-full",
        "displayName": "Полная Мария",
    }
    assert inbox_by_kind["teacher"]["comment"] == "Проверено через Staff PWA."

    inbox_repository = PwaWrittenReviewQueueRepository(
        fixture.factory,
        clock=lambda: NOW,
    )
    first_page = await inbox_repository.list_reaction_inbox(page_size=1)
    assert len(first_page.items) == 1
    assert first_page.next_cursor == first_page.items[0].item_public_id
    second_page = await inbox_repository.list_reaction_inbox(
        cursor=first_page.next_cursor,
        page_size=1,
    )
    assert len(second_page.items) == 1
    assert second_page.items[0].item_public_id != first_page.items[0].item_public_id
    assert second_page.next_cursor is None

    disagreement_filter = await fixture.client.get(
        "/staff/api/v1/review/reactions?kind=student&reactionId=2",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert disagreement_filter.status == 200
    assert (await disagreement_filter.json())["items"] == []

    cross_kind_filter = await fixture.client.get(
        "/staff/api/v1/review/reactions?kind=student&reactionId=103",
        cookies=_cookie(fixture, "admin"),
        headers=_headers(),
    )
    assert cross_kind_filter.status == 422

    deleted = await fixture.client.delete(
        f"/student/api/v1/reviews/{review_id}/reaction",
        json={"schemaVersion": 1, "expectedVersion": 1},
        cookies=_student_cookie(fixture),
        headers=_headers(unsafe=True),
    )
    assert deleted.status == 200, await deleted.text()
    deleted_payload = (await deleted.json())["studentReaction"]
    assert deleted_payload["reactionId"] is None
    assert deleted_payload["version"] == 2
    assert deleted_payload["deleted"] is True


@pytest.mark.asyncio
async def test_complete_review_reports_thread_change_and_confirmation_errors(
    review_http: ReviewHttpFixture,
):
    fixture = review_http
    queue_id = fixture.queue_public_ids[0]
    claim = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    lease = (await claim.json())["lease"]
    payload = _complete_payload(lease)
    payload["annotations"] = [
        {
            "attachmentId": "review-http-attachment-1",
            "schemaVersion": 1,
            "rotation": 0,
            "marks": [
                {
                    "markId": "review-http-invalid-box",
                    "kind": "rectangle",
                    "data": {
                        "x": 0.9,
                        "y": 0.9,
                        "width": 0.2,
                        "height": 0.2,
                        "strokeWidth": 0.01,
                        "color": "red",
                    },
                }
            ],
        }
    ]
    invalid_annotation = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert invalid_annotation.status == 422
    assert (await invalid_annotation.json())["error"]["code"] == (
        "review_annotation_invalid"
    )
    payload["annotations"] = []
    payload.update({"verdict": 11, "comment": None})
    confirmation = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert confirmation.status == 422
    assert (await confirmation.json())["error"]["code"] == (
        "review_confirmation_required"
    )

    payload["confirmWithoutComment"] = True
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE submission_threads SET updated_at = ?, version = version + 1 "
            "WHERE public_id = 'review-http-thread-1'",
            (_timestamp(),),
        )
    )
    conflict = await fixture.client.post(
        f"/staff/api/v1/review/items/{queue_id}/complete",
        json=payload,
        cookies=_cookie(fixture, "admin"),
        headers=_headers(unsafe=True),
    )
    assert conflict.status == 409
    assert (await conflict.json())["error"]["code"] == "review_thread_changed"
