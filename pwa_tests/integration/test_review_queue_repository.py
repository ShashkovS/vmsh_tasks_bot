"""Shared-SQLite lease and synonym-case tests for the Staff review queue."""

from __future__ import annotations

import asyncio
import itertools
import multiprocessing
import os
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.reviews import (
    CompleteReviewCommand,
    CompleteReviewReceipt,
    PwaWrittenReviewQueueRepository,
    ReviewAnnotationManifest,
    ReviewAnnotationMark,
    ReviewAnnotationReceipt,
    ReviewCompletionInvalid,
    ReviewEvidenceBranchExpectation,
    ReviewEvidenceEntryExpectation,
    ReviewIdempotencyConflict,
    ReviewInternalReactionConflict,
    ReviewInternalReactionInvalid,
    ReviewInternalReactionWindowClosed,
    ReviewStudentReactionConflict,
    ReviewStudentReactionInvalid,
    ReviewStudentReactionNotFound,
    ReviewStudentReactionWindowClosed,
    ReviewLease,
    ReviewLeaseConflict,
    ReviewLeaseLost,
    ReviewQueueForbidden,
    ReviewQueueNotFound,
    ReviewStaffScope,
    ReviewThreadChanged,
)
from db_methods.pwa.written_submissions import PwaWrittenSubmissionRepository
from helpers.consts import USER_TYPE, VERDICT
from models.pwa.review_corrections import (
    ReviewCorrectionCommand,
    ReviewCorrectionForbidden,
    ReviewCorrectionStale,
    correct_written_review,
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


class _SyntheticCompletionFailure(RuntimeError):
    pass


def _claim_review_in_subprocess(
    database_path: str,
    queue_public_id: str,
    teacher_user_id: int,
) -> str:
    """Exercise a real independent interpreter against the shared WAL file."""

    repository = PwaWrittenReviewQueueRepository(
        PwaConnectionFactory(database_path),
        clock=lambda: NOW,
        claim_token_factory=lambda: f"process-claim-{os.getpid()}",
    )
    try:
        asyncio.run(
            repository.claim(
                queue_public_id=queue_public_id,
                teacher_user_id=teacher_user_id,
                scope=ALL_GROUPS_SCOPE,
            )
        )
    except ReviewLeaseConflict:
        return "conflict"
    return "claimed"


@pytest.fixture()
def review_queue_fixture(tmp_path) -> ReviewQueueFixture:
    database_path = tmp_path / "review-queue.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    clock = MutableClock(NOW)
    tokens = (f"review-claim-test-{index}" for index in itertools.count(1))
    reaction_events = (
        f"review-reaction-event-test-{index}" for index in itertools.count(1)
    )
    student_reaction_events = (
        f"review-student-reaction-event-test-{index}" for index in itertools.count(1)
    )
    repository = PwaWrittenReviewQueueRepository(
        factory,
        clock=clock,
        claim_token_factory=lambda: next(tokens),
        review_public_id_factory=lambda: "review-completed-test",
        annotation_public_id_factory=lambda: "review-annotation-test",
        comment_public_id_factory=lambda: "review-comment-test",
        event_public_id_factory=lambda: "review-event-test",
        internal_reaction_event_public_id_factory=lambda: next(reaction_events),
        student_reaction_event_public_id_factory=lambda: next(student_reaction_events),
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
            problem_revision_id = int(
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
                ).lastrowid
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
            submitted_at = _timestamp(NOW - timedelta(minutes=3 - index))
            thread_id = int(
                connection.execute(
                    "INSERT INTO submission_threads "
                    "(public_id, student_user_id, problem_id, condition_revision_id, "
                    "status, latest_entry_at, created_at, updated_at, version) "
                    "VALUES (?, ?, ?, ?, 'awaiting_review', ?, ?, ?, 2) RETURNING id",
                    (
                        f"review-thread-test-{index}",
                        STUDENT_ID,
                        problem_id,
                        revision_id,
                        submitted_at,
                        submitted_at,
                        submitted_at,
                    ),
                ).fetchone()["id"]
            )
            if index == 1:
                connection.execute(
                    "INSERT INTO submission_entries "
                    "(public_id, thread_id, problem_revision_id, author_kind, "
                    "author_user_id, channel, entry_kind, state, text, client_created_at, "
                    "server_received_at, locked_at, version) VALUES "
                    "('review-old-teacher-comment', ?, ?, 'teacher', ?, 'pwa', "
                    "'teacher_comment', 'locked', 'Поясните первый переход.', ?, ?, ?, 1)",
                    (
                        thread_id,
                        problem_revision_id,
                        TEACHER_ONE_ID,
                        submitted_at,
                        submitted_at,
                        submitted_at,
                    ),
                )
            entry_id = int(
                connection.execute(
                    "INSERT INTO submission_entries "
                    "(public_id, thread_id, problem_revision_id, author_kind, "
                    "author_user_id, channel, entry_kind, state, text, client_created_at, "
                    "server_received_at, version) VALUES (?, ?, ?, 'student', ?, 'pwa', "
                    "'submission', 'submitted', ?, ?, ?, 2) RETURNING id",
                    (
                        f"review-entry-test-{index}",
                        thread_id,
                        problem_revision_id,
                        STUDENT_ID,
                        f"Решение {index}",
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
                        "VALUES ('review-asset-test-1', ?, 'submission', "
                        "'submission/review-asset-test-1.webp', "
                        "'https://assets.test/review-asset-test-1.webp', "
                        "'image/webp', 1024, 1200, 900, 'page.webp', "
                        "'submission-webp-v1', ?, ?) RETURNING id",
                        ("a" * 64, STUDENT_ID, submitted_at),
                    ).fetchone()["id"]
                )
                connection.execute(
                    "INSERT INTO submission_attachments "
                    "(public_id, entry_id, asset_id, ordinal, client_filename, "
                    "upload_status, created_at) VALUES "
                    "('review-attachment-test-1', ?, ?, 0, 'page.webp', 'stored', ?)",
                    (entry_id, asset_id, submitted_at),
                )
            queue_public_id = f"review-queue-test-{index}"
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
    assert [item.problem_number for item in lease.items] == ["41а.1", "41б.2"]
    assert [item.group_name for item in lease.items] == ["Группа а", "Группа б"]
    assert {item.course_name for item in lease.items} == {"Математика"}
    assert {item.lease_version for item in lease.items} == {1}
    assert [branch.thread_public_id for branch in lease.evidence_branches] == [
        "review-thread-test-1",
        "review-thread-test-2",
    ]
    assert [
        entry.entry_public_id
        for branch in lease.evidence_branches
        for entry in branch.entries
    ] == ["review-entry-test-1", "review-entry-test-2"]
    assert [
        entry.entry_public_id
        for branch in lease.evidence_branches
        for entry in branch.timeline_entries
    ] == [
        "review-old-teacher-comment",
        "review-entry-test-1",
        "review-entry-test-2",
    ]
    assert [
        entry.author_kind
        for branch in lease.evidence_branches
        for entry in branch.timeline_entries
    ] == ["teacher", "student", "student"]

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


def _complete_command(
    lease: ReviewLease,
    *,
    idempotency_key: str = "review-completion-idempotency-1",
    verdict: VERDICT = VERDICT.VERDICT_PLUS_DOT,
    annotations: tuple[ReviewAnnotationManifest, ...] = (),
    internal_reaction_id: int | None = None,
    comment: str | None = "Точная формулировка проверки.",
    confirm_without_comment: bool = False,
) -> CompleteReviewCommand:
    evidence_by_queue = {
        branch.queue_public_id: branch for branch in lease.evidence_branches
    }
    return CompleteReviewCommand(
        queue_public_id=lease.items[0].queue_public_id,
        claim_token=lease.claim_token,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
        idempotency_key=idempotency_key,
        verdict=int(verdict),
        comment=comment,
        confirm_without_comment=confirm_without_comment,
        branches=tuple(
            ReviewEvidenceBranchExpectation(
                queue_public_id=item.queue_public_id,
                lease_version=item.lease_version,
                thread_public_id=str(
                    evidence_by_queue[item.queue_public_id].thread_public_id
                ),
                thread_version=int(
                    evidence_by_queue[item.queue_public_id].thread_version or 0
                ),
                entries=tuple(
                    ReviewEvidenceEntryExpectation(
                        entry_public_id=entry.entry_public_id,
                        entry_version=entry.entry_version,
                    )
                    for entry in evidence_by_queue[item.queue_public_id].entries
                ),
            )
            for item in lease.items
        ),
        annotations=annotations,
        internal_reaction_id=internal_reaction_id,
    )


def _annotation_manifest(
    *, attachment_public_id: str = "review-attachment-test-1"
) -> ReviewAnnotationManifest:
    return ReviewAnnotationManifest(
        attachment_public_id=attachment_public_id,
        schema_version=1,
        rotation=90,
        marks=(
            ReviewAnnotationMark.from_payload(
                mark_public_id="mark-pencil-1",
                kind="pencil",
                data={
                    "points": [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}],
                    "width": 0.01,
                    "color": "red",
                },
            ),
            ReviewAnnotationMark.from_payload(
                mark_public_id="mark-text-1",
                kind="text",
                data={
                    "x": 0.35,
                    "y": 0.45,
                    "text": "Проверьте этот переход",
                    "size": 0.04,
                    "color": "blue",
                },
            ),
            ReviewAnnotationMark.from_payload(
                mark_public_id="mark-arrow-1",
                kind="arrow",
                data={
                    "start": {"x": 0.5, "y": 0.5},
                    "end": {"x": 0.7, "y": 0.6},
                    "width": 0.008,
                    "color": "graphite",
                },
            ),
            ReviewAnnotationMark.from_payload(
                mark_public_id="mark-rectangle-1",
                kind="rectangle",
                data={
                    "x": 0.1,
                    "y": 0.7,
                    "width": 0.25,
                    "height": 0.15,
                    "strokeWidth": 0.006,
                    "color": "red",
                },
            ),
            ReviewAnnotationMark.from_payload(
                mark_public_id="mark-highlight-1",
                kind="highlight",
                data={"x": 0.4, "y": 0.75, "width": 0.3, "height": 0.08},
            ),
            ReviewAnnotationMark.from_payload(
                mark_public_id="mark-eraser-1",
                kind="eraser",
                data={
                    "points": [{"x": 0.2, "y": 0.2}, {"x": 0.21, "y": 0.22}],
                    "width": 0.02,
                },
            ),
        ),
    )


@pytest.mark.parametrize(
    ("kind", "data"),
    (
        (
            "pencil",
            {
                "points": [{"x": -0.1, "y": 0}, {"x": 0, "y": 0}],
                "width": 0.01,
                "color": "red",
            },
        ),
        (
            "arrow",
            {
                "start": {"x": 0.5, "y": 0.5},
                "end": {"x": 0.5, "y": 0.5},
                "width": 0.01,
                "color": "red",
            },
        ),
        (
            "rectangle",
            {
                "x": 0.9,
                "y": 0.9,
                "width": 0.2,
                "height": 0.2,
                "strokeWidth": 0.01,
                "color": "red",
            },
        ),
        ("text", {"x": 0.1, "y": 0.1, "text": " ", "size": 0.04, "color": "blue"}),
    ),
)
def test_annotation_domain_rejects_invalid_normalized_geometry(kind, data):
    with pytest.raises(ReviewCompletionInvalid, match="annotation"):
        ReviewAnnotationMark.from_payload(
            mark_public_id="invalid-mark", kind=kind, data=data
        )


@pytest.mark.asyncio
async def test_complete_persists_annotation_manifest_atomically_and_immutably(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    command = _complete_command(lease, annotations=(_annotation_manifest(),))

    receipt = await fixture.repository.complete(command)

    assert receipt.annotations == (
        ReviewAnnotationReceipt(
            annotation_public_id="review-annotation-test",
            attachment_public_id="review-attachment-test-1",
            schema_version=1,
            rotation=90,
            mark_count=6,
        ),
    )
    stored = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT marks_json, payload_sha256 FROM submission_review_annotations"
        ).fetchone()
    )
    assert len(stored["payload_sha256"]) == 64
    assert '"kind":"pencil"' in stored["marks_json"]
    assert '"kind":"text"' in stored["marks_json"]

    for statement in (
        "UPDATE submission_review_annotations SET rotation = 0",
        "DELETE FROM submission_review_annotations",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="review annotation"):
            fixture.factory.run_write(
                lambda connection, sql=statement: connection.execute(sql)
            )

    replay = await fixture.repository.complete(command)
    assert replay.replayed is True
    assert replay.annotations == receipt.annotations


@pytest.mark.asyncio
async def test_complete_accepts_evidence_captured_before_own_lease_heartbeat(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    command = _complete_command(lease)

    fixture.clock.value += timedelta(minutes=10)
    heartbeat = await fixture.repository.heartbeat(
        queue_public_id=fixture.queue_public_ids[0],
        claim_token=lease.claim_token,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert {item.lease_version for item in heartbeat.items} == {2}

    receipt = await fixture.repository.complete(command)

    assert receipt.review_public_id == "review-completed-test"


@pytest.mark.asyncio
async def test_review_correction_appends_history_and_replaces_legacy_result(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    completed = await fixture.repository.complete(
        _complete_command(lease, verdict=VERDICT.VERDICT_PLUS_DOT)
    )
    command = ReviewCorrectionCommand(
        source_review_public_id=completed.review_public_id,
        reviewer_user_id=TEACHER_ONE_ID,
        reviewer_type=int(USER_TYPE.TEACHER),
        scope=ALL_GROUPS_SCOPE,
        idempotency_key="review-correction-test-1",
        verdict=int(VERDICT.VERDICT_MINUS_PLUS),
        comment="После перепроверки одного перехода не хватает.",
        confirm_without_comment=False,
    )

    corrected = await correct_written_review(
        fixture.factory, command, now=NOW + timedelta(minutes=1)
    )
    replay = await correct_written_review(
        fixture.factory, command, now=NOW + timedelta(minutes=2)
    )

    assert corrected.source_review_public_id == completed.review_public_id
    assert corrected.verdict == int(VERDICT.VERDICT_MINUS_PLUS)
    assert corrected.status == "needs_work"
    assert replay.review_public_id == corrected.review_public_id
    assert replay.replayed is True
    stored = fixture.factory.run_read(
        lambda connection: {
            "reviews": connection.execute(
                "SELECT public_id, verdict FROM submission_reviews ORDER BY id"
            ).fetchall(),
            "results": connection.execute(
                "SELECT verdict FROM results ORDER BY id"
            ).fetchall(),
            "evidence": connection.execute(
                "SELECT review_id, count(*) AS count "
                "FROM submission_review_evidence_entries GROUP BY review_id ORDER BY review_id"
            ).fetchall(),
            "thread": connection.execute(
                "SELECT status, latest_result_id, version FROM submission_threads "
                "WHERE public_id = ?",
                (completed.target_thread_public_id,),
            ).fetchone(),
        }
    )
    assert [row["verdict"] for row in stored["reviews"]] == [16, 13]
    assert [row["verdict"] for row in stored["results"]] == [-2, 13]
    assert [row["count"] for row in stored["evidence"]] == [2, 2]
    assert stored["thread"]["status"] == "needs_work"
    assert stored["thread"]["version"] == 5

    with pytest.raises(ReviewCorrectionStale):
        await correct_written_review(
            fixture.factory,
            replace(command, idempotency_key="review-correction-test-2"),
            now=NOW + timedelta(minutes=3),
        )
    with pytest.raises(ReviewCorrectionForbidden):
        await correct_written_review(
            fixture.factory,
            ReviewCorrectionCommand(
                source_review_public_id=corrected.review_public_id,
                reviewer_user_id=TEACHER_TWO_ID,
                reviewer_type=int(USER_TYPE.TEACHER),
                scope=ALL_GROUPS_SCOPE,
                idempotency_key="review-correction-test-3",
                verdict=17,
                comment=None,
                confirm_without_comment=False,
            ),
            now=NOW + timedelta(minutes=4),
        )


@pytest.mark.asyncio
async def test_student_thread_projects_review_annotation_and_student_reaction(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    completed = await fixture.repository.complete(
        _complete_command(
            lease,
            annotations=(_annotation_manifest(),),
            internal_reaction_id=100,
        )
    )
    reaction = await fixture.repository.set_student_reaction(
        review_public_id=completed.review_public_id,
        reaction_id=2,
        expected_version=0,
        student_user_id=STUDENT_ID,
    )

    now = _timestamp(fixture.clock.value)
    account_id = fixture.factory.run_write(
        lambda connection: int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, "
                "credential_kind, credential_hash, "
                "linked_user_id, status, created_at, updated_at) VALUES "
                "('review-student-account', 'student', 'review-student', "
                "'review-student', 1, 'synthetic-test', 'telegram_token', "
                "'test-only-hash', ?, 'active', ?, ?) RETURNING id",
                (STUDENT_ID, now, now),
            ).fetchone()["id"]
        )
    )
    written = PwaWrittenSubmissionRepository(fixture.factory, clock=fixture.clock)

    first = await written.get_thread(
        account_id=account_id, problem_public_id=lease.items[0].problem_public_id
    )
    second = await written.get_thread(
        account_id=account_id, problem_public_id=lease.items[1].problem_public_id
    )

    assert first is not None and second is not None
    first_review = first.payload()["reviews"][0]
    second_review = second.payload()["reviews"][0]
    assert first_review["reviewId"] == "review-completed-test"
    assert first_review["targetProblemId"] == lease.items[1].problem_public_id
    assert first_review["reviewerName"] == "Первая Мария"
    assert first_review["comment"] == "Точная формулировка проверки."
    assert first_review["evidenceEntryIds"] == ["review-entry-test-1"]
    assert first_review["annotations"] == [_annotation_manifest().payload()]
    assert first_review["studentReaction"] == {
        "reactionId": 2,
        "version": 1,
        "editableUntil": _timestamp(reaction.state.editable_until),
        "updatedAt": _timestamp(reaction.state.updated_at),
        "deleted": False,
    }
    assert "internalReaction" not in first_review
    assert second_review["evidenceEntryIds"] == ["review-entry-test-2"]
    assert second_review["annotations"] == []
    assert second_review["studentReaction"] == first_review["studentReaction"]


@pytest.mark.asyncio
async def test_complete_rejects_annotation_outside_current_evidence_without_writes(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )

    with pytest.raises(ReviewCompletionInvalid, match="outside current evidence"):
        await fixture.repository.complete(
            _complete_command(
                lease,
                annotations=(
                    _annotation_manifest(attachment_public_id="foreign-attachment"),
                ),
            )
        )
    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM submission_review_annotations) AS annotations, "
            "(SELECT count(*) FROM results) AS results"
        ).fetchone()
    )
    assert counts == {"reviews": 0, "annotations": 0, "results": 0}


@pytest.mark.asyncio
async def test_complete_freezes_synonym_evidence_and_targets_latest_branch(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    command = _complete_command(lease)

    receipt = await fixture.repository.complete(command)

    assert receipt.target_problem_public_id == lease.items[1].problem_public_id
    assert receipt.target_thread_public_id == "review-thread-test-2"
    assert receipt.target_thread_status == "accepted"
    assert receipt.evidence_entry_public_ids == (
        "review-entry-test-1",
        "review-entry-test-2",
    )
    assert receipt.comment_entry_public_id == "review-comment-test"
    rows = fixture.factory.run_read(
        lambda connection: {
            "queue": connection.execute(
                "SELECT count(*) AS count FROM written_tasks_queue"
            ).fetchone()["count"],
            "results": connection.execute(
                "SELECT problem_id, verdict, res_type FROM results"
            ).fetchall(),
            "reviews": connection.execute(
                "SELECT count(*) AS count FROM submission_reviews"
            ).fetchone()["count"],
            "evidence": connection.execute(
                "SELECT count(*) AS count FROM submission_review_evidence_entries"
            ).fetchone()["count"],
            "threads": connection.execute(
                "SELECT public_id, status, version FROM submission_threads "
                "ORDER BY public_id"
            ).fetchall(),
        }
    )
    assert rows["queue"] == 0
    assert rows["reviews"] == 1
    assert rows["evidence"] == 2
    assert rows["results"] == [
        {
            "problem_id": lease.items[1].problem_id,
            "verdict": int(VERDICT.VERDICT_PLUS_DOT),
            "res_type": 2,
        }
    ]
    assert rows["threads"] == [
        {"public_id": "review-thread-test-1", "status": "closed", "version": 3},
        {
            "public_id": "review-thread-test-2",
            "status": "accepted",
            "version": 3,
        },
    ]

    with pytest.raises(sqlite3.IntegrityError, match="reviewed submission entry"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE submission_entries SET text = 'changed', version = 3 "
                "WHERE public_id = 'review-entry-test-1'"
            )
        )

    replay = await fixture.repository.complete(command)
    assert replay.replayed is True
    assert replay.review_public_id == receipt.review_public_id
    with pytest.raises(ReviewIdempotencyConflict):
        await fixture.repository.complete(
            _complete_command(
                lease,
                idempotency_key=command.idempotency_key,
                verdict=VERDICT.VERDICT_PLUS,
            )
        )


@pytest.mark.asyncio
async def test_complete_resolves_only_current_student_and_family_recipients(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    now = _timestamp(NOW)
    revoked_at = _timestamp(NOW + timedelta(minutes=1))

    def seed_recipients(connection):
        connection.execute(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) VALUES "
            "('review-student-account', 'student', 'review-student', "
            "'review-student', 1, 'synthetic-test', 'telegram_token', "
            "'test-only-student-hash', ?, 'active', ?, ?)",
            (STUDENT_ID, now, now),
        )
        family_ids: dict[str, int] = {}
        for public_id, status in (
            ("review-family-active", "active"),
            ("review-family-blocked", "blocked"),
            ("review-family-revoked-link", "active"),
        ):
            family_ids[public_id] = int(
                connection.execute(
                    "INSERT INTO auth_accounts "
                    "(public_id, audience, username, username_normalized, "
                    "provisioning_source, display_name, credential_kind, "
                    "credential_hash, status, created_at, updated_at) VALUES "
                    "(?, 'family', ?, ?, 'synthetic-test', 'Семья', 'password', "
                    "'test-only-family-hash', ?, ?, ?) RETURNING id",
                    (public_id, public_id, public_id, status, now, now),
                ).fetchone()["id"]
            )
        connection.executemany(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, is_primary, created_at, "
            "updated_at, revoked_at) VALUES (?, ?, 1, ?, ?, ?)",
            (
                (family_ids["review-family-active"], STUDENT_ID, now, now, None),
                (family_ids["review-family-blocked"], STUDENT_ID, now, now, None),
                (
                    family_ids["review-family-revoked-link"],
                    STUDENT_ID,
                    now,
                    revoked_at,
                    revoked_at,
                ),
            ),
        )

    fixture.factory.run_write(seed_recipients)
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    receipt = await fixture.repository.complete(_complete_command(lease))

    assert receipt.owner_account_public_ids == ("review-student-account",)
    assert receipt.family_account_public_ids == ("review-family-active",)


@pytest.mark.asyncio
async def test_complete_rejects_a_thread_change_without_partial_writes(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    command = _complete_command(lease)
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE submission_threads SET updated_at = ?, version = version + 1 "
            "WHERE public_id = 'review-thread-test-1'",
            (_timestamp(NOW + timedelta(minutes=5)),),
        )
    )

    with pytest.raises(ReviewThreadChanged):
        await fixture.repository.complete(command)

    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM results) AS results, "
            "(SELECT count(*) FROM written_tasks_queue) AS queue"
        ).fetchone()
    )
    assert counts == {"reviews": 0, "results": 0, "queue": 2}


@pytest.mark.asyncio
async def test_complete_persists_internal_reaction_atomically_and_replays_it(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    command = _complete_command(lease, internal_reaction_id=100)

    receipt = await fixture.repository.complete(command)

    assert receipt.internal_reaction is not None
    assert receipt.internal_reaction.reaction_id == 100
    assert receipt.internal_reaction.version == 1
    assert receipt.internal_reaction.editable_until == NOW + timedelta(hours=1)
    stored = fixture.factory.run_read(
        lambda connection: {
            "state": connection.execute(
                "SELECT reaction_id, version, deleted_at "
                "FROM submission_review_internal_reactions"
            ).fetchone(),
            "events": connection.execute(
                "SELECT event_kind, reaction_id, state_version "
                "FROM submission_review_internal_reaction_events ORDER BY id"
            ).fetchall(),
        }
    )
    assert stored == {
        "state": {"reaction_id": 100, "version": 1, "deleted_at": None},
        "events": [{"event_kind": "selected", "reaction_id": 100, "state_version": 1}],
    }
    replay = await fixture.repository.complete(command)
    assert replay.replayed is True
    assert replay.internal_reaction == receipt.internal_reaction


@pytest.mark.asyncio
async def test_internal_reaction_supports_optimistic_change_delete_and_reselect(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    receipt = await fixture.repository.complete(
        _complete_command(lease, internal_reaction_id=100)
    )

    changed = await fixture.repository.set_internal_reaction(
        review_public_id=receipt.review_public_id,
        reaction_id=103,
        expected_version=1,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert (changed.reaction_id, changed.version, changed.deleted) == (103, 2, False)
    unchanged = await fixture.repository.set_internal_reaction(
        review_public_id=receipt.review_public_id,
        reaction_id=103,
        expected_version=2,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert unchanged == changed

    deleted = await fixture.repository.delete_internal_reaction(
        review_public_id=receipt.review_public_id,
        expected_version=2,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert (deleted.reaction_id, deleted.version, deleted.deleted) == (None, 3, True)
    fixture.clock.value += timedelta(minutes=10)
    selected = await fixture.repository.set_internal_reaction(
        review_public_id=receipt.review_public_id,
        reaction_id=101,
        expected_version=3,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert (selected.reaction_id, selected.version, selected.deleted) == (101, 4, False)
    events = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT event_kind, reaction_id, state_version "
            "FROM submission_review_internal_reaction_events ORDER BY state_version"
        ).fetchall()
    )
    assert events == [
        {"event_kind": "selected", "reaction_id": 100, "state_version": 1},
        {"event_kind": "changed", "reaction_id": 103, "state_version": 2},
        {"event_kind": "deleted", "reaction_id": None, "state_version": 3},
        {"event_kind": "selected", "reaction_id": 101, "state_version": 4},
    ]
    for statement in (
        "UPDATE submission_review_internal_reaction_events SET event_kind = 'changed'",
        "DELETE FROM submission_review_internal_reaction_events",
        "DELETE FROM submission_review_internal_reactions",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="reaction"):
            fixture.factory.run_write(
                lambda connection, sql=statement: connection.execute(sql)
            )


@pytest.mark.asyncio
async def test_internal_reaction_fails_closed_on_type_owner_version_and_window(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    with pytest.raises(ReviewInternalReactionInvalid):
        await fixture.repository.complete(
            _complete_command(lease, internal_reaction_id=0)
        )
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS count FROM submission_reviews"
            ).fetchone()["count"]
        )
        == 0
    )

    receipt = await fixture.repository.complete(_complete_command(lease))
    with pytest.raises(ReviewInternalReactionInvalid, match="written Teacher"):
        await fixture.repository.set_internal_reaction(
            review_public_id=receipt.review_public_id,
            reaction_id=1,
            expected_version=0,
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        )
    with pytest.raises(ReviewQueueForbidden, match="original reviewer"):
        await fixture.repository.set_internal_reaction(
            review_public_id=receipt.review_public_id,
            reaction_id=100,
            expected_version=0,
            teacher_user_id=TEACHER_TWO_ID,
            scope=ALL_GROUPS_SCOPE,
        )
    selected = await fixture.repository.set_internal_reaction(
        review_public_id=receipt.review_public_id,
        reaction_id=100,
        expected_version=0,
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert selected.version == 1
    with pytest.raises(ReviewInternalReactionConflict):
        await fixture.repository.set_internal_reaction(
            review_public_id=receipt.review_public_id,
            reaction_id=101,
            expected_version=0,
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        )
    fixture.clock.value += timedelta(hours=1, microseconds=1)
    with pytest.raises(ReviewInternalReactionWindowClosed):
        await fixture.repository.delete_internal_reaction(
            review_public_id=receipt.review_public_id,
            expected_version=1,
            teacher_user_id=TEACHER_ONE_ID,
            scope=ALL_GROUPS_SCOPE,
        )


@pytest.mark.asyncio
async def test_student_reaction_is_owner_scoped_optimistic_and_append_only(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    review = await fixture.repository.complete(_complete_command(lease))

    with pytest.raises(ReviewStudentReactionNotFound):
        await fixture.repository.set_student_reaction(
            review_public_id=review.review_public_id,
            reaction_id=0,
            expected_version=0,
            student_user_id=TEACHER_TWO_ID,
        )
    with pytest.raises(ReviewStudentReactionInvalid, match="written Student"):
        await fixture.repository.set_student_reaction(
            review_public_id=review.review_public_id,
            reaction_id=100,
            expected_version=0,
            student_user_id=STUDENT_ID,
        )

    selected = await fixture.repository.set_student_reaction(
        review_public_id=review.review_public_id,
        reaction_id=0,
        expected_version=0,
        student_user_id=STUDENT_ID,
    )
    assert (
        selected.state.reaction_id,
        selected.state.version,
        selected.state.deleted,
        selected.state.editable_until,
    ) == (0, 1, False, NOW + timedelta(hours=1))
    assert selected.evidence_problem_public_ids == tuple(
        item.problem_public_id for item in lease.items
    )
    assert selected.owner_account_public_ids == ()
    assert selected.family_account_public_ids == ()
    assert selected.admin_account_public_ids == ()

    unchanged = await fixture.repository.set_student_reaction(
        review_public_id=review.review_public_id,
        reaction_id=0,
        expected_version=1,
        student_user_id=STUDENT_ID,
    )
    assert unchanged.state == selected.state
    changed = await fixture.repository.set_student_reaction(
        review_public_id=review.review_public_id,
        reaction_id=2,
        expected_version=1,
        student_user_id=STUDENT_ID,
    )
    assert (changed.state.reaction_id, changed.state.version) == (2, 2)
    with pytest.raises(ReviewStudentReactionConflict):
        await fixture.repository.set_student_reaction(
            review_public_id=review.review_public_id,
            reaction_id=1,
            expected_version=1,
            student_user_id=STUDENT_ID,
        )

    deleted = await fixture.repository.delete_student_reaction(
        review_public_id=review.review_public_id,
        expected_version=2,
        student_user_id=STUDENT_ID,
    )
    assert (
        deleted.state.reaction_id,
        deleted.state.version,
        deleted.state.deleted,
    ) == (
        None,
        3,
        True,
    )
    fixture.clock.value += timedelta(minutes=10)
    reselected = await fixture.repository.set_student_reaction(
        review_public_id=review.review_public_id,
        reaction_id=1,
        expected_version=3,
        student_user_id=STUDENT_ID,
    )
    assert (reselected.state.reaction_id, reselected.state.version) == (1, 4)

    events = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT event_kind, reaction_id, state_version "
            "FROM submission_review_student_reaction_events ORDER BY state_version"
        ).fetchall()
    )
    assert events == [
        {"event_kind": "selected", "reaction_id": 0, "state_version": 1},
        {"event_kind": "changed", "reaction_id": 2, "state_version": 2},
        {"event_kind": "deleted", "reaction_id": None, "state_version": 3},
        {"event_kind": "selected", "reaction_id": 1, "state_version": 4},
    ]
    for statement in (
        "UPDATE submission_review_student_reaction_events SET event_kind = 'changed'",
        "DELETE FROM submission_review_student_reaction_events",
        "DELETE FROM submission_review_student_reactions",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="reaction"):
            fixture.factory.run_write(
                lambda connection, sql=statement: connection.execute(sql)
            )

    fixture.clock.value = NOW + timedelta(hours=1, microseconds=1)
    with pytest.raises(ReviewStudentReactionWindowClosed):
        await fixture.repository.delete_student_reaction(
            review_public_id=review.review_public_id,
            expected_version=4,
            student_user_id=STUDENT_ID,
        )


@pytest.mark.asyncio
async def test_plus_dot_is_an_accepted_verdict_without_comment(review_queue_fixture):
    fixture = review_queue_fixture
    # The domain constructor itself is the policy boundary; no database call is needed.
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    command = _complete_command(
        lease,
        verdict=VERDICT.VERDICT_PLUS_DOT,
        comment=None,
        confirm_without_comment=False,
    )
    assert command.verdict == int(VERDICT.VERDICT_PLUS_DOT)


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


def test_separate_processes_have_exactly_one_claim_winner(review_queue_fixture):
    fixture = review_queue_fixture
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as executor:
        futures = [
            executor.submit(
                _claim_review_in_subprocess,
                str(fixture.factory.database_path),
                fixture.queue_public_ids[0],
                teacher_user_id,
            )
            for teacher_user_id in (TEACHER_ONE_ID, TEACHER_TWO_ID)
        ]
        outcomes = [future.result(timeout=20) for future in futures]

    assert sorted(outcomes) == ["claimed", "conflict"]
    stored = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(distinct claim_token) AS tokens, "
            "count(distinct teacher_id) AS teachers, min(cur_status) AS status "
            "FROM written_tasks_queue"
        ).fetchone()
    )
    assert stored == {"tokens": 1, "teachers": 1, "status": 1}


@pytest.mark.asyncio
async def test_expired_lease_cannot_complete_and_another_teacher_recovers(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    fixture.clock.value += timedelta(minutes=31)

    with pytest.raises(ReviewLeaseLost):
        await fixture.repository.complete(_complete_command(lease))

    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM results) AS results, "
            "(SELECT count(*) FROM written_tasks_queue) AS queued"
        ).fetchone()
    )
    assert counts == {"reviews": 0, "results": 0, "queued": 2}

    recovered = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_TWO_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    assert recovered.teacher_user_id == TEACHER_TWO_ID
    assert recovered.claim_token != lease.claim_token


@pytest.mark.asyncio
async def test_concurrent_completion_has_one_commit_and_no_duplicate_result(
    review_queue_fixture,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    outcomes = await asyncio.gather(
        fixture.repository.complete(
            _complete_command(lease, idempotency_key="review-race-a")
        ),
        fixture.repository.complete(
            _complete_command(lease, idempotency_key="review-race-b")
        ),
        return_exceptions=True,
    )

    assert (
        len(
            [result for result in outcomes if isinstance(result, CompleteReviewReceipt)]
        )
        == 1
    )
    assert (
        len([result for result in outcomes if isinstance(result, ReviewQueueNotFound)])
        == 1
    )
    counts = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM submission_reviews) AS reviews, "
            "(SELECT count(*) FROM results) AS results, "
            "(SELECT count(*) FROM submission_review_evidence_entries) AS evidence, "
            "(SELECT count(*) FROM submission_review_events) AS events, "
            "(SELECT count(*) FROM written_tasks_queue) AS queued"
        ).fetchone()
    )
    assert counts == {
        "reviews": 1,
        "results": 1,
        "evidence": 2,
        "events": 1,
        "queued": 0,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_checkpoint",
    (
        "result",
        "comment",
        "review",
        "internal-reaction",
        "evidence",
        "annotations",
        "threads",
        "queue",
        "event",
    ),
)
async def test_completion_fault_at_every_write_boundary_rolls_back_atomically(
    review_queue_fixture,
    failed_checkpoint,
):
    fixture = review_queue_fixture
    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )

    def checkpoint(name: str) -> None:
        if name == failed_checkpoint:
            raise _SyntheticCompletionFailure(name)

    repository = PwaWrittenReviewQueueRepository(
        fixture.factory,
        clock=fixture.clock,
        review_public_id_factory=lambda: "review-fault-completed",
        annotation_public_id_factory=lambda: "review-fault-annotation",
        comment_public_id_factory=lambda: "review-fault-comment",
        event_public_id_factory=lambda: "review-fault-event",
        internal_reaction_event_public_id_factory=lambda: (
            "review-fault-internal-reaction-event"
        ),
        completion_checkpoint=checkpoint,
    )

    with pytest.raises(_SyntheticCompletionFailure, match=failed_checkpoint):
        await repository.complete(
            _complete_command(
                lease,
                annotations=(_annotation_manifest(),),
                internal_reaction_id=100,
            )
        )

    state = fixture.factory.run_read(
        lambda connection: {
            "counts": connection.execute(
                "SELECT (SELECT count(*) FROM results) AS results, "
                "(SELECT count(*) FROM submission_reviews) AS reviews, "
                "(SELECT count(*) FROM submission_review_evidence_entries) AS evidence, "
                "(SELECT count(*) FROM submission_review_evidence_attachments) AS attachments, "
                "(SELECT count(*) FROM submission_review_annotations) AS annotations, "
                "(SELECT count(*) FROM submission_review_internal_reactions) AS reactions, "
                "(SELECT count(*) FROM submission_review_internal_reaction_events) "
                "AS reaction_events, "
                "(SELECT count(*) FROM submission_review_events) AS events, "
                "(SELECT count(*) FROM submission_entries "
                "WHERE public_id = 'review-fault-comment') AS comments"
            ).fetchone(),
            "queue": connection.execute(
                "SELECT cur_status, claim_token, lease_version "
                "FROM written_tasks_queue ORDER BY public_id"
            ).fetchall(),
            "threads": connection.execute(
                "SELECT status, version FROM submission_threads ORDER BY public_id"
            ).fetchall(),
        }
    )
    assert state["counts"] == {
        "results": 0,
        "reviews": 0,
        "evidence": 0,
        "attachments": 0,
        "annotations": 0,
        "reactions": 0,
        "reaction_events": 0,
        "events": 0,
        "comments": 0,
    }
    assert state["queue"] == [
        {"cur_status": 1, "claim_token": lease.claim_token, "lease_version": 1},
        {"cur_status": 1, "claim_token": lease.claim_token, "lease_version": 1},
    ]
    assert state["threads"] == [
        {"status": "awaiting_review", "version": 2},
        {"status": "awaiting_review", "version": 2},
    ]
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE media_assets SET source_filename = 'after-rollback.webp' "
            "WHERE public_id = 'review-asset-test-1'"
        )
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


@pytest.mark.asyncio
async def test_teacher_can_resume_own_active_legacy_claim(review_queue_fixture):
    fixture = review_queue_fixture
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE written_tasks_queue SET cur_status = 1, teacher_id = ?, "
            "teacher_ts = ?, updated_at = ? WHERE public_id = ?",
            (
                TEACHER_ONE_ID,
                _timestamp(fixture.clock.value),
                _timestamp(fixture.clock.value),
                fixture.queue_public_ids[0],
            ),
        )
    )

    lease = await fixture.repository.claim(
        queue_public_id=fixture.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )

    assert len(lease.items) == 2
    assert lease.teacher_user_id == TEACHER_ONE_ID
    assert lease.claim_token
