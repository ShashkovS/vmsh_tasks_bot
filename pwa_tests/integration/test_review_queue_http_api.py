"""Real aiohttp/SQLite authorization tests for the Phase-6 review queue."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest
from aiohttp import web
from argon2 import PasswordHasher

from apps import pwa_app
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from db_methods.pwa.reviews import PwaWrittenReviewQueueRepository
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import RUNTIME_CONFIG
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
            "INSERT INTO users (id, public_id, type, name, surname) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (
                    STUDENT_ID,
                    "review-http-student",
                    int(USER_TYPE.STUDENT),
                    "Анна",
                    "Белова",
                ),
                (
                    FULL_TEACHER_ID,
                    "review-http-teacher-full",
                    int(USER_TYPE.TEACHER),
                    "Мария",
                    "Полная",
                ),
                (
                    PARTIAL_TEACHER_ID,
                    "review-http-teacher-partial",
                    int(USER_TYPE.TEACHER),
                    "Иван",
                    "Частичный",
                ),
                (
                    ADMIN_ID,
                    "review-http-admin",
                    int(USER_TYPE.ADMIN),
                    "Ада",
                    "Администратор",
                ),
            ),
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
async def review_http(tmp_path, aiohttp_client) -> ReviewHttpFixture:
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
    )
    client = await aiohttp_client(app)

    async def login(username: str, password: str) -> str:
        response = await client.post(
            "/staff/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=_headers(unsafe=True),
        )
        assert response.status == 200, await response.text()
        cookie = response.cookies[COOKIE_POLICY[AuthAudience.STAFF].access_name].value
        client.session.cookie_jar.clear()
        return cookie

    cookies = MappingProxyType(
        {
            "full": await login("review-http-full", "full-password"),
            "partial": await login("review-http-partial", "partial-password"),
            "admin": await login("review-http-admin", "admin-password"),
        }
    )
    return ReviewHttpFixture(
        client=client,
        factory=factory,
        queue_public_ids=queue_public_ids,
        cookies=cookies,
    )


def _headers(*, unsafe: bool = False) -> dict[str, str]:
    headers = {"Host": HOST, "X-Request-ID": "review.http.test"}
    if unsafe:
        headers.update({"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"})
    return headers


def _cookie(fixture: ReviewHttpFixture, identity: str) -> dict[str, str]:
    return {COOKIE_POLICY[AuthAudience.STAFF].access_name: fixture.cookies[identity]}


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
    payload["annotations"] = [
        {
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
    ]

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
    assert (await stale.json())["error"]["code"] == (
        "review_internal_reaction_changed"
    )

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
