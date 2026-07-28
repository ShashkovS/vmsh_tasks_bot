"""Shared-SQLite lease and synonym-case tests for the Staff review queue."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.reviews import (
    PwaWrittenReviewQueueRepository,
    ReviewLease,
    ReviewLeaseConflict,
    ReviewLeaseLost,
    ReviewQueueForbidden,
    ReviewStaffScope,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)
STUDENT_ID = -952_001
TEACHER_ONE_ID = -952_002
TEACHER_TWO_ID = -952_003


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


@dataclass(slots=True)
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@dataclass(frozen=True, slots=True)
class ReviewQueueFixture:
    factory: PwaConnectionFactory
    repository: PwaWrittenReviewQueueRepository
    clock: MutableClock
    queue_public_ids: tuple[str, str]


ALL_GROUPS_SCOPE = ReviewStaffScope(
    group_public_ids=frozenset({"review-group-a", "review-group-b"})
)


@pytest.fixture()
def review_queue_fixture(tmp_path) -> ReviewQueueFixture:
    database_path = tmp_path / "review-queue.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    clock = MutableClock(NOW)
    tokens = (f"review-claim-test-{index}" for index in itertools.count(1))
    repository = PwaWrittenReviewQueueRepository(
        factory, clock=clock, claim_token_factory=lambda: next(tokens)
    )
    now = _timestamp(NOW)

    def seed(connection):
        connection.executemany(
            "INSERT INTO users (id, public_id, type, name, surname) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (STUDENT_ID, "review-student", 1, "Анна", "Белова"),
                (TEACHER_ONE_ID, "review-teacher-one", 2, "Мария", "Первая"),
                (TEACHER_TWO_ID, "review-teacher-two", 2, "Иван", "Второй"),
            ),
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(public_id, code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) VALUES "
                "('review-season', 'review', 'Review', '2026-09-01', "
                "'2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()["id"]
        )
        course_id = int(
            connection.execute(
                "INSERT INTO courses "
                "(public_id, season_id, code, name, subject_code, status, "
                "sort_order, accent_key, created_at, updated_at) VALUES "
                "('review-course', ?, 'math', 'Математика', 'math', 'active', "
                "1, 'math', ?, ?) RETURNING id",
                (season_id, now, now),
            ).fetchone()["id"]
        )
        for group_id, public_id, short_code, sort_order in (
            ("review-a", "review-group-a", "а", 1),
            ("review-b", "review-group-b", "б", 2),
        ):
            connection.execute(
                "INSERT INTO groups "
                "(group_id, short_code, public_name, sort_order, is_active, "
                "is_default, allow_self_switch, is_system, score_weight, "
                "public_id, course_id, status, created_at, updated_at) VALUES "
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
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(public_id, course_id, lesson_number, created_at, updated_at) "
                "VALUES ('review-course-lesson', ?, 41, ?, ?) RETURNING id",
                (course_id, now, now),
            ).fetchone()["id"]
        )
        synonym_group_id = int(
            connection.execute(
                "INSERT INTO problem_synonym_groups "
                "(public_id, course_lesson_id, group_key, display_title, status, "
                "created_at, updated_at) VALUES "
                "('review-synonym-case', ?, 'shared', 'Общая задача', 'active', ?, ?) "
                "RETURNING id",
                (course_lesson_id, now, now),
            ).fetchone()["id"]
        )

        queue_public_ids: list[str] = []
        for index, group_id in enumerate(("review-a", "review-b"), start=1):
            group_lesson_id = int(
                connection.execute(
                    "INSERT INTO group_lessons "
                    "(public_id, course_lesson_id, course_id, group_id, "
                    "cycle_anchor_date, business_timezone, status, created_at, "
                    "updated_at) VALUES (?, ?, ?, ?, '2026-09-28', "
                    "'Europe/Moscow', 'active', ?, ?) RETURNING id",
                    (
                        f"review-group-lesson-{index}",
                        course_lesson_id,
                        course_id,
                        group_id,
                        now,
                        now,
                    ),
                ).fetchone()["id"]
            )
            source_id = int(
                connection.execute(
                    "INSERT INTO content_sources "
                    "(public_id, group_lesson_id, kind, logical_filename, "
                    "source_encoding, created_at) VALUES (?, ?, 'condition', ?, "
                    "'utf-8', ?) RETURNING id",
                    (
                        f"review-source-{index}",
                        group_lesson_id,
                        f"review-{index}.tex",
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
                    "(?, ?, 1, ?, 'problem', 'review-test', 'ready', '{}', '[]', "
                    "'{}', ?) RETURNING id",
                    (f"review-revision-{index}", source_id, str(index) * 64, now),
                ).fetchone()["id"]
            )
            problem_id = int(
                connection.execute(
                    "INSERT INTO problems "
                    "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                    "ans_type, ans_validation, validation_error, cor_ans, "
                    "wrong_ans, congrat, synonyms) VALUES "
                    "(?, 41, ?, '', ?, '', 2, 0, '', '', '', '', '', '') "
                    "RETURNING id",
                    (group_id, index, f"Задача {index}"),
                ).fetchone()["id"]
            )
            connection.execute(
                "INSERT INTO content_problem_matches "
                "(content_revision_id, source_ordinal, source_item, problem_id, "
                "decision, resolved_by_user_id, resolved_at, diagnostics_json, "
                "created_at) VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
                (revision_id, problem_id, TEACHER_ONE_ID, now, now),
            )
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, "
                "answer_type, answer_config_json, attempt_policy_json, "
                "config_version, created_at) VALUES "
                "(?, ?, 1, '1', ?, ?, ?, 2, 0, '{}', '{}', 1, ?)",
                (
                    problem_id,
                    revision_id,
                    f"41{index}",
                    f"Задача {index}",
                    f"задача {index}",
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO problem_synonym_members "
                "(synonym_group_id, group_lesson_id, problem_id, "
                "added_by_user_id, added_at, membership_version) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (
                    synonym_group_id,
                    group_lesson_id,
                    problem_id,
                    TEACHER_ONE_ID,
                    now,
                ),
            )
            queue_public_id = f"review-queue-test-{index}"
            connection.execute(
                "INSERT INTO written_tasks_queue "
                "(public_id, ts, student_id, problem_id, cur_status, updated_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (
                    queue_public_id,
                    _timestamp(NOW + timedelta(minutes=index)),
                    STUDENT_ID,
                    problem_id,
                    now,
                ),
            )
            queue_public_ids.append(queue_public_id)
        return tuple(queue_public_ids)

    queue_public_ids = factory.run_write(seed)
    return ReviewQueueFixture(
        factory=factory,
        repository=repository,
        clock=clock,
        queue_public_ids=queue_public_ids,
    )


@pytest.mark.asyncio
async def test_claim_heartbeat_and_release_cover_one_synonym_case(review_queue_fixture):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )

    assert lease.logical_case_public_id == "review-synonym-case"
    assert lease.claim_token == "review-claim-test-1"
    assert lease.teacher_user_id == TEACHER_ONE_ID
    assert [item.group_id for item in lease.items] == ["review-a", "review-b"]
    assert {item.lease_version for item in lease.items} == {1}

    fixture.clock.value += timedelta(minutes=10)
    heartbeat = await fixture.repository.heartbeat(
        queue_public_id=fixture.queue_public_ids[0],
        claim_token=lease.claim_token,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert heartbeat.expires_at == fixture.clock.value + timedelta(minutes=30)
    assert {item.lease_version for item in heartbeat.items} == {2}

    assert (
        await fixture.repository.release(
            queue_public_id=fixture.queue_public_ids[0],
            claim_token=lease.claim_token,
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        )
        == 2
    )
    with pytest.raises(ReviewLeaseLost):
        await fixture.repository.heartbeat(
            queue_public_id=fixture.queue_public_ids[0],
            claim_token=lease.claim_token,
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        )


@pytest.mark.asyncio
async def test_list_groups_synonyms_and_hides_partial_scope(review_queue_fixture):
    fixture = review_queue_fixture
    page = await fixture.repository.list_cases(scope=ALL_GROUPS_SCOPE)

    assert page.next_cursor is None
    assert len(page.items) == 1
    case = page.items[0]
    assert case.queue_public_id == fixture.queue_public_ids[0]
    assert case.logical_case_public_id == "review-synonym-case"
    assert [item.group_id for item in case.items] == ["review-a", "review-b"]
    assert all(item.problem_public_id.startswith("problem-") for item in case.items)
    assert case.lock is None

    partial = await fixture.repository.list_cases(
        scope=ReviewStaffScope(group_public_ids=frozenset({"review-group-a"}))
    )
    assert partial.items == ()


@pytest.mark.asyncio
async def test_concurrent_staff_claims_have_exactly_one_winner(review_queue_fixture):
    fixture = review_queue_fixture

    outcomes = await asyncio.gather(
        fixture.repository.claim(
            queue_public_id=fixture.queue_public_ids[0],
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        ),
        fixture.repository.claim(
            queue_public_id=fixture.queue_public_ids[0],
            teacher_user_id=TEACHER_TWO_ID,
            scope=ALL_GROUPS_SCOPE,
        ),
        return_exceptions=True,
    )

    assert len([result for result in outcomes if isinstance(result, ReviewLease)]) == 1
    assert (
        len([result for result in outcomes if isinstance(result, ReviewLeaseConflict)])
        == 1
    )


@pytest.mark.asyncio
async def test_claim_fails_closed_when_one_synonym_branch_is_outside_scope(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    with pytest.raises(ReviewQueueForbidden):
        await fixture.repository.claim(
            queue_public_id=fixture.queue_public_ids[0],
            teacher_user_id=TEACHER_ONE_ID,
            scope=ReviewStaffScope(group_public_ids=frozenset({"review-group-a"})),
        )

    rows = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT claim_token, cur_status FROM written_tasks_queue ORDER BY id"
        ).fetchall()
    )
    assert rows == [
        {"claim_token": None, "cur_status": 0},
        {"claim_token": None, "cur_status": 0},
    ]


@pytest.mark.asyncio
async def test_active_legacy_claim_blocks_pwa_until_thirty_minute_expiry(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE written_tasks_queue SET cur_status = 1, teacher_id = ?, "
            "teacher_ts = ?, updated_at = ? WHERE public_id = ?",
            (
                TEACHER_TWO_ID,
                _timestamp(fixture.clock.value),
                _timestamp(fixture.clock.value),
                fixture.queue_public_ids[0],
            ),
        )
    )

    with pytest.raises(ReviewLeaseConflict, match="legacy Telegram"):
        await fixture.repository.claim(
            queue_public_id=fixture.queue_public_ids[0],
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        )

    fixture.clock.value += timedelta(minutes=31)
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert len(lease.items) == 2
