"""Atomic repository tests for Phase-4 test submissions and retries."""

from __future__ import annotations

import asyncio
import itertools
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.submissions import (
    IdempotencyPayloadMismatch,
    PwaTestSubmissionRepository,
    SubmitTestAnswerCommand,
    TestSubmissionRejected as SubmissionRejected,
)
from db_methods.pwa.written_submissions import (
    CreateWrittenAttachmentCommand,
    CreateWrittenAttachmentReceipt,
    CreateWrittenEntryCommand,
    PersistWrittenAttachment,
    PreparedWrittenAttachmentUpload,
    ProblemRevisionRef,
    PwaWrittenSubmissionRepository,
    SubmitWrittenEntryCommand,
    WrittenIdempotencyPayloadMismatch,
    WrittenSubmissionRejected,
)
from helpers.consts import ANS_TYPE, RES_TYPE, VERDICT


NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)
STUDENT_USER_ID = -947_001
OTHER_STUDENT_USER_ID = -947_002
ADMIN_USER_ID = 947_003
PROBLEM_PUBLIC_ID = "problem-submission-integer"
PENDING_PROBLEM_PUBLIC_ID = "problem-submission-pending"
UNLIMITED_PROBLEM_PUBLIC_ID = "problem-submission-unlimited"
DAILY_LIMIT_PROBLEM_PUBLIC_ID = "problem-submission-daily-limit"
WRITTEN_PROBLEM_PUBLIC_ID = "problem-submission-written"


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(slots=True)
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@dataclass(frozen=True, slots=True)
class SubmissionFixture:
    factory: PwaConnectionFactory
    repository: PwaTestSubmissionRepository
    written_repository: PwaWrittenSubmissionRepository
    clock: MutableClock
    student_account_id: int
    other_account_id: int
    problem_id: int
    problem_revision_id: int
    written_problem_id: int
    written_problem_revision_id: int
    window_id: int


@pytest.fixture()
def submission_fixture(tmp_path) -> SubmissionFixture:
    database_path = tmp_path / "test-submissions.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    clock = MutableClock(NOW)
    public_ids = (f"attempt-repository-{index}" for index in itertools.count(1))
    repository = PwaTestSubmissionRepository(
        factory,
        clock=clock,
        public_id_factory=lambda: next(public_ids),
    )
    thread_public_ids = (
        f"written-thread-repository-{index}" for index in itertools.count(1)
    )
    entry_public_ids = (
        f"written-entry-repository-{index}" for index in itertools.count(1)
    )
    written_repository = PwaWrittenSubmissionRepository(
        factory,
        clock=clock,
        thread_public_id_factory=lambda: next(thread_public_ids),
        entry_public_id_factory=lambda: next(entry_public_ids),
    )
    now = timestamp(NOW)

    def seed(connection):
        connection.execute("DELETE FROM kv_logins")
        connection.executemany(
            "INSERT INTO users (id, public_id, type, name, surname) "
            "VALUES (?, ?, 1, ?, ?)",
            (
                (
                    STUDENT_USER_ID,
                    "user-submission-student",
                    "Ирина",
                    "Тестова",
                ),
                (
                    OTHER_STUDENT_USER_ID,
                    "user-submission-other",
                    "Олег",
                    "Другой",
                ),
            ),
        )
        connection.execute(
            "INSERT INTO users (id, public_id, type, name, surname) "
            "VALUES (?, 'user-submission-admin', 128, 'Анна', 'Админова')",
            (ADMIN_USER_ID,),
        )
        student_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, "
                "credential_kind, credential_hash, linked_user_id, status, "
                "created_at, updated_at) VALUES "
                "('account-submission-student', 'student', 'submission-student', "
                "'submission-student', 1, 'synthetic-test', 'telegram_token', "
                "'hash', ?, 'active', ?, ?) RETURNING id",
                (STUDENT_USER_ID, now, now),
            ).fetchone()["id"]
        )
        other_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, "
                "credential_kind, credential_hash, linked_user_id, status, "
                "created_at, updated_at) VALUES "
                "('account-submission-other', 'student', 'submission-other', "
                "'submission-other', 1, 'synthetic-test', 'telegram_token', "
                "'hash', ?, 'active', ?, ?) RETURNING id",
                (OTHER_STUDENT_USER_ID, now, now),
            ).fetchone()["id"]
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(public_id, code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) VALUES "
                "('season-submission', 'submission', 'Submission tests', "
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
                "('course-submission', ?, 'math', 'Математика', 'math', "
                "'active', 1, 'math', ?, ?) RETURNING id",
                (season_id, now, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, "
            "is_default, allow_self_switch, is_system, score_weight, public_id, "
            "course_id, status, created_at, updated_at) VALUES "
            "('submission-a', 'a', 'Начинающие', 1, 1, 1, 1, 0, 1.0, "
            "'group-submission-a', ?, 'active', ?, ?)",
            (course_id, now, now),
        )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(public_id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) VALUES "
                "('enrollment-submission', ?, ?, 'submission-a', 'online', "
                "'active', ?, ?) RETURNING id",
                (STUDENT_USER_ID, course_id, now, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, "
            "updated_at) VALUES (?, ?, 'submission-a', ?, ?, ?)",
            (enrollment_id, course_id, now, now, now),
        )
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(public_id, course_id, lesson_number, created_at, updated_at) "
                "VALUES ('course-lesson-submission-41', ?, 41, ?, ?) RETURNING id",
                (course_id, now, now),
            ).fetchone()["id"]
        )
        group_lesson_id = int(
            connection.execute(
                "INSERT INTO group_lessons "
                "(public_id, course_lesson_id, course_id, group_id, "
                "cycle_anchor_date, business_timezone, status, created_at, "
                "updated_at) VALUES ('group-lesson-submission-41', ?, ?, "
                "'submission-a', '2026-09-14', 'Europe/Moscow', 'active', ?, ?) "
                "RETURNING id",
                (course_lesson_id, course_id, now, now),
            ).fetchone()["id"]
        )
        window_id = int(
            connection.execute(
                "INSERT INTO lesson_windows "
                "(public_id, group_lesson_id, submission_closes_at, timezone, "
                "source, created_at, updated_at) VALUES "
                "('window-submission-41', ?, ?, 'Europe/Moscow', 'native', ?, ?) "
                "RETURNING id",
                (group_lesson_id, timestamp(NOW + timedelta(days=2)), now, now),
            ).fetchone()["id"]
        )
        source_id = int(
            connection.execute(
                "INSERT INTO content_sources "
                "(public_id, group_lesson_id, kind, logical_filename, "
                "source_encoding, created_at) VALUES "
                "('source-submission-condition', ?, 'condition', "
                "'condition.tex', 'utf-8', ?) RETURNING id",
                (group_lesson_id, now),
            ).fetchone()["id"]
        )
        revision_id = int(
            connection.execute(
                "INSERT INTO content_revisions "
                "(public_id, source_id, revision_number, source_sha256, latex_text, "
                "parser_version, status, canonical_json, diagnostics_json, "
                "provenance_json, created_at) VALUES "
                "('revision-submission-condition', ?, 1, ?, '\\задача 7 \\кзадача', "
                "'test-v1', 'ready', '{}', '[]', '{}', ?) RETURNING id",
                (source_id, "a" * 64, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_derivatives "
            "(revision_id, kind, renderer_version, content_text, sha256, "
            "diagnostics_json, provenance_json, created_at) VALUES "
            "(?, 'web_ast', 'test-v1', '{}', ?, '[]', '{}', ?)",
            (revision_id, "b" * 64, now),
        )
        problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                "congrat, synonyms, public_id) VALUES "
                "('submission-a', 41, 1, '', 'Целое число', '', 1, ?, '', "
                "'Введите целое число', '7', 'Нет', 'Да', '', ?) RETURNING id",
                (int(ANS_TYPE.INTEGER), PROBLEM_PUBLIC_ID),
            ).fetchone()["id"]
        )
        answer_config = json.dumps(
            {
                "schemaVersion": 1,
                "answerType": int(ANS_TYPE.INTEGER),
                "answerValidation": None,
                "validationError": "Введите целое число.",
                "correctAnswer": "7",
                "correctAnswerChecker": None,
                "wrongAnswer": "Нет, это другое число.",
                "congratulation": "Да, всё верно!",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, "
            "decision, resolved_at, diagnostics_json, created_at) VALUES "
            "(?, 1, '1', ?, 'manual_match', ?, '[]', ?)",
            (revision_id, problem_id, now, now),
        )
        problem_revision_id = int(
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, "
                "answer_type, answer_config_json, attempt_policy_json, "
                "config_version, created_at) VALUES "
                "(?, ?, 1, '1', '1', 'Целое число', 'целое число', 1, ?, ?, ?, "
                "1, ?) RETURNING id",
                (
                    problem_id,
                    revision_id,
                    int(ANS_TYPE.INTEGER),
                    answer_config,
                    '{"schemaVersion":1}',
                    now,
                ),
            ).fetchone()["id"]
        )
        pending_problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                "congrat, synonyms, public_id) VALUES "
                "('submission-a', 41, 2, '', 'Без ответа', '', 1, ?, '', "
                "'Введите целое число', '', 'Нет', 'Да', '', ?) RETURNING id",
                (int(ANS_TYPE.INTEGER), PENDING_PROBLEM_PUBLIC_ID),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, "
            "decision, resolved_at, diagnostics_json, created_at) VALUES "
            "(?, 2, '2', ?, 'manual_match', ?, '[]', ?)",
            (revision_id, pending_problem_id, now, now),
        )
        pending_answer_config = json.dumps(
            {
                "schemaVersion": 1,
                "answerType": int(ANS_TYPE.INTEGER),
                "answerValidation": None,
                "validationError": "Введите целое число.",
                "correctAnswer": None,
                "correctAnswerChecker": None,
                "wrongAnswer": "Нет.",
                "congratulation": "Да.",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, "
            "display_number, title, normalized_title, problem_type, answer_type, "
            "answer_config_json, attempt_policy_json, config_version, created_at) "
            "VALUES (?, ?, 2, '2', '2', 'Без ответа', 'без ответа', 1, ?, ?, "
            "'{\"schemaVersion\":1}', 1, ?)",
            (
                pending_problem_id,
                revision_id,
                int(ANS_TYPE.INTEGER),
                pending_answer_config,
                now,
            ),
        )

        def insert_additional_problem(
            *,
            ordinal: int,
            public_id: str,
            title: str,
            attempt_policy_json: str,
        ) -> None:
            additional_problem_id = int(
                connection.execute(
                    "INSERT INTO problems "
                    "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                    "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                    "congrat, synonyms, public_id) VALUES "
                    "('submission-a', 41, ?, '', ?, '', 1, ?, '', "
                    "'Введите целое число', '7', 'Нет', 'Да', '', ?) RETURNING id",
                    (ordinal, title, int(ANS_TYPE.INTEGER), public_id),
                ).fetchone()["id"]
            )
            connection.execute(
                "INSERT INTO content_problem_matches "
                "(content_revision_id, source_ordinal, source_item, problem_id, "
                "decision, resolved_at, diagnostics_json, created_at) VALUES "
                "(?, ?, ?, ?, 'manual_match', ?, '[]', ?)",
                (
                    revision_id,
                    ordinal,
                    str(ordinal),
                    additional_problem_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, "
                "answer_type, answer_config_json, attempt_policy_json, "
                "config_version, created_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 1, ?)",
                (
                    additional_problem_id,
                    revision_id,
                    ordinal,
                    str(ordinal),
                    str(ordinal),
                    title,
                    title.casefold(),
                    int(ANS_TYPE.INTEGER),
                    answer_config,
                    attempt_policy_json,
                    now,
                ),
            )

        insert_additional_problem(
            ordinal=3,
            public_id=UNLIMITED_PROBLEM_PUBLIC_ID,
            title="Без ограничений",
            attempt_policy_json='{ "schemaVersion": 1, "unlimited": true }',
        )
        insert_additional_problem(
            ordinal=4,
            public_id=DAILY_LIMIT_PROBLEM_PUBLIC_ID,
            title="Дневной лимит",
            attempt_policy_json=(
                '{ "schemaVersion": 1, "maxPerHour": null, "maxPerDay": 2 }'
            ),
        )
        written_problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                "congrat, synonyms, public_id) VALUES "
                "('submission-a', 41, 5, '', 'Письменная задача', '', 2, NULL, "
                "'', '', '', '', '', '', ?) RETURNING id",
                (WRITTEN_PROBLEM_PUBLIC_ID,),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, "
            "decision, resolved_at, diagnostics_json, created_at) VALUES "
            "(?, 5, '5', ?, 'manual_match', ?, '[]', ?)",
            (revision_id, written_problem_id, now, now),
        )
        written_problem_revision_id = int(
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, "
                "answer_type, answer_config_json, attempt_policy_json, "
                "config_version, created_at) VALUES "
                "(?, ?, 5, '5', '5', 'Письменная задача', 'письменная задача', "
                "2, NULL, '{}', '{}', 1, ?) RETURNING id",
                (written_problem_id, revision_id, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO lesson_publications "
            "(public_id, group_lesson_id, kind, revision_id, state, published_at, "
            "created_at, updated_at, provenance_kind) VALUES "
            "('publication-submission-condition', ?, 'condition', ?, 'published', "
            "?, ?, ?, 'legacy_backfill')",
            (group_lesson_id, revision_id, now, now, now),
        )
        return (
            student_account_id,
            other_account_id,
            problem_id,
            problem_revision_id,
            written_problem_id,
            written_problem_revision_id,
            window_id,
        )

    (
        account_id,
        other_account_id,
        problem_id,
        problem_revision_id,
        written_problem_id,
        written_problem_revision_id,
        window_id,
    ) = factory.run_write(seed)
    return SubmissionFixture(
        factory=factory,
        repository=repository,
        written_repository=written_repository,
        clock=clock,
        student_account_id=account_id,
        other_account_id=other_account_id,
        problem_id=problem_id,
        problem_revision_id=problem_revision_id,
        written_problem_id=written_problem_id,
        written_problem_revision_id=written_problem_revision_id,
        window_id=window_id,
    )


def command(
    fixture: SubmissionFixture,
    *,
    answer: str = "7",
    key: str = "attempt-key-1",
    client_created_at: datetime = NOW,
    problem_public_id: str = PROBLEM_PUBLIC_ID,
) -> SubmitTestAnswerCommand:
    return SubmitTestAnswerCommand(
        account_id=fixture.student_account_id,
        problem_public_id=problem_public_id,
        display_answer=answer,
        client_created_at=client_created_at,
        idempotency_key=key,
    )


def publish_pending_problem_configuration(
    fixture: SubmissionFixture,
    *,
    answer_config_json: str,
    config_version: int = 2,
) -> None:
    """Publish one immutable replacement condition revision for recheck tests."""

    now = timestamp(fixture.clock.value)

    def publish(connection):
        old_publication = connection.execute(
            "SELECT publication.*, revision.source_id, revision.revision_number, "
            "source.group_lesson_id "
            "FROM lesson_publications AS publication "
            "JOIN content_revisions AS revision ON revision.id = publication.revision_id "
            "JOIN content_sources AS source ON source.id = revision.source_id "
            "WHERE publication.kind = 'condition' AND publication.state = 'published'"
        ).fetchone()
        problem = connection.execute(
            "SELECT id FROM problems WHERE public_id = ?",
            (PENDING_PROBLEM_PUBLIC_ID,),
        ).fetchone()
        connection.execute(
            "UPDATE lesson_publications SET state = 'superseded', version = version + 1, "
            "terminal_by_user_id = ?, terminal_at = ?, updated_at = ? WHERE id = ?",
            (ADMIN_USER_ID, now, now, old_publication["id"]),
        )
        revision_id = int(
            connection.execute(
                "INSERT INTO content_revisions "
                "(public_id, source_id, revision_number, source_sha256, latex_text, "
                "parser_version, status, canonical_json, diagnostics_json, "
                "provenance_json, created_at) VALUES "
                "('revision-submission-recheck', ?, ?, ?, '\\задача 179 \\кзадача', "
                "'test-v1', 'ready', '{}', '[]', '{}', ?) RETURNING id",
                (
                    old_publication["source_id"],
                    int(old_publication["revision_number"]) + 1,
                    "c" * 64,
                    now,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO content_derivatives "
            "(revision_id, kind, renderer_version, content_text, sha256, "
            "diagnostics_json, provenance_json, created_at) VALUES "
            "(?, 'web_ast', 'test-v1', '{}', ?, '[]', '{}', ?)",
            (revision_id, "d" * 64, now),
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, "
            "decision, resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
            "VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
            (revision_id, problem["id"], ADMIN_USER_ID, now, now),
        )
        connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, "
            "display_number, title, normalized_title, problem_type, answer_type, "
            "answer_config_json, attempt_policy_json, config_version, created_at, "
            "created_by_user_id) VALUES "
            "(?, ?, 1, '1', '2', 'Без ответа', 'без ответа', 1, ?, ?, "
            "'{\"schemaVersion\":1}', ?, ?, ?)",
            (
                problem["id"],
                revision_id,
                int(ANS_TYPE.INTEGER),
                answer_config_json,
                config_version,
                now,
                ADMIN_USER_ID,
            ),
        )
        connection.execute(
            "INSERT INTO lesson_publications "
            "(public_id, group_lesson_id, kind, revision_id, state, published_at, "
            "created_by_user_id, published_by_user_id, supersedes_publication_id, "
            "created_at, updated_at, provenance_kind) VALUES "
            "('publication-submission-recheck', ?, 'condition', ?, 'published', ?, "
            "?, ?, ?, ?, ?, 'interactive')",
            (
                old_publication["group_lesson_id"],
                revision_id,
                now,
                ADMIN_USER_ID,
                ADMIN_USER_ID,
                old_publication["id"],
                now,
                now,
            ),
        )

    fixture.factory.run_write(publish)


async def test_checked_attempt_dual_writes_exactly_one_legacy_result(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture

    receipt = await fixture.repository.submit_test_answer(command(fixture))
    stored = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM test_attempts").fetchone(),
            connection.execute("SELECT * FROM results").fetchone(),
            connection.execute("SELECT * FROM idempotency_records").fetchone(),
        )
    )
    attempt, result, idempotency = stored

    assert receipt.outcome == "correct"
    assert receipt.display_answer == "7"
    assert receipt.verdict == int(VERDICT.SOLVED)
    assert receipt.attempts.used_this_hour == 1
    assert receipt.attempts.remaining_this_hour == 2
    assert attempt["problem_revision_id"] == fixture.problem_revision_id
    assert attempt["result_id"] == result["id"]
    assert attempt["verdict"] == int(VERDICT.SOLVED)
    assert result["student_id"] == STUDENT_USER_ID
    assert result["problem_id"] == fixture.problem_id
    assert result["answer"] == "7"
    assert result["res_type"] == int(RES_TYPE.TEST)
    assert idempotency["state"] == "completed"
    assert idempotency["http_status"] == 201
    assert json.loads(idempotency["response_json"]) == receipt.response_payload()


async def test_wrong_answer_after_success_is_allowed_and_keeps_both_results(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture

    correct = await fixture.repository.submit_test_answer(
        command(fixture, key="attempt-correct")
    )
    wrong = await fixture.repository.submit_test_answer(
        command(fixture, answer="8", key="attempt-after-success")
    )

    rows = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT verdict, answer FROM results ORDER BY id"
        ).fetchall()
    )
    assert correct.outcome == "correct"
    assert wrong.outcome == "wrong"
    assert [(row["verdict"], row["answer"]) for row in rows] == [
        (int(VERDICT.SOLVED), "7"),
        (int(VERDICT.WRONG_ANSWER), "8"),
    ]


async def test_invalid_format_is_saved_but_does_not_count_or_create_result(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture

    receipt = await fixture.repository.submit_test_answer(
        command(fixture, answer="7.5", key="attempt-invalid")
    )
    attempt, result_count = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM test_attempts").fetchone(),
            connection.execute("SELECT count(*) AS count FROM results").fetchone()[
                "count"
            ],
        )
    )

    assert receipt.outcome == "invalid_format"
    assert receipt.attempts.used_this_hour == 0
    assert attempt["parse_status"] == "invalid_format"
    assert attempt["counts_as_attempt"] == 0
    assert attempt["normalized_answer_json"] is None
    assert attempt["result_id"] is None
    assert result_count == 0


async def test_same_idempotency_key_and_payload_replays_the_exact_receipt(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    request = command(fixture, key="attempt-replay")

    first = await fixture.repository.submit_test_answer(request)
    second = await fixture.repository.submit_test_answer(request)
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

    assert second == first
    assert second.response_payload() == first.response_payload()
    assert counts == (1, 1, 1)


async def test_same_idempotency_key_with_different_payload_is_a_conflict(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.repository.submit_test_answer(
        command(fixture, answer="7", key="attempt-mismatch")
    )

    with pytest.raises(IdempotencyPayloadMismatch) as caught:
        await fixture.repository.submit_test_answer(
            command(fixture, answer="8", key="attempt-mismatch")
        )

    assert caught.value.http_status == 409
    assert caught.value.code == "idempotency_payload_mismatch"


async def test_missing_checker_configuration_is_persisted_without_result(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    receipt = await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-configuration",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
        )
    )
    attempt, result_count = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM test_attempts").fetchone(),
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
        )
    )

    assert receipt.outcome == "pending_configuration"
    assert attempt["check_status"] == "pending_configuration"
    assert attempt["checker_version"] is None
    assert attempt["checked_at"] is None
    assert result_count == 0


async def test_pending_attempt_recheck_uses_previewed_current_configuration(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    pending = await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-for-recheck",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="179",
        )
    )
    await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-for-recheck-wrong",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="180",
        )
    )
    original_problem_revision_id = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT problem_revision_id FROM test_attempts WHERE public_id = ?",
            (pending.attempt_public_id,),
        ).fetchone()["problem_revision_id"]
    )
    preview_before = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID
    )
    repaired_config = json.dumps(
        {
            "schemaVersion": 1,
            "answerType": int(ANS_TYPE.INTEGER),
            "answerValidation": None,
            "validationError": "Введите целое число.",
            "correctAnswer": "179",
            "correctAnswerChecker": None,
            "wrongAnswer": "Нет.",
            "congratulation": "Да.",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    publish_pending_problem_configuration(
        fixture,
        answer_config_json=repaired_config,
    )
    preview = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID
    )

    assert preview_before.pending_attempts == 2
    assert preview_before.config_version == 1
    assert preview.pending_attempts == 2
    assert preview.config_version == 2

    receipt = await fixture.repository.recheck_pending_test_attempts(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
        expected_condition_revision_public_id=(preview.condition_revision_public_id),
        expected_config_version=preview.config_version,
        actor_user_id=ADMIN_USER_ID,
    )
    attempt, results = fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT * FROM test_attempts WHERE public_id = ?",
                (pending.attempt_public_id,),
            ).fetchone(),
            connection.execute("SELECT * FROM results ORDER BY id").fetchall(),
        )
    )
    history = await fixture.repository.list_test_attempts(
        account_id=fixture.student_account_id,
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
    )

    assert receipt.pending_before == receipt.checked == 2
    assert receipt.correct == receipt.wrong == 1
    assert receipt.still_pending == 0
    assert receipt.owner_account_public_ids == ("account-submission-student",)
    assert attempt["problem_revision_id"] == original_problem_revision_id
    assert attempt["check_status"] == "checked"
    assert attempt["checker_version"].startswith("pwa-test-checker-v1:")
    assert attempt["verdict"] == int(VERDICT.SOLVED)
    matching_result = next(row for row in results if row["answer"] == "179")
    assert attempt["result_id"] == matching_result["id"]
    assert {row["teacher_id"] for row in results} == {ADMIN_USER_ID}
    assert {row["answer"] for row in results} == {"179", "180"}
    assert {record.outcome for record in history.attempts} == {"correct", "wrong"}
    assert all(record.feedback is None for record in history.attempts)

    repeated = await fixture.repository.recheck_pending_test_attempts(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
        expected_condition_revision_public_id=(preview.condition_revision_public_id),
        expected_config_version=preview.config_version,
        actor_user_id=ADMIN_USER_ID,
    )
    assert repeated.pending_before == repeated.checked == 0
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS n FROM results"
            ).fetchone()["n"]
        )
        == 2
    )


async def test_recheck_keeps_attempt_pending_when_checker_is_still_broken(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-broken-recheck",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="179",
        )
    )
    broken_config = json.dumps(
        {
            "schemaVersion": 1,
            "answerType": int(ANS_TYPE.INTEGER),
            "answerValidation": None,
            "validationError": "Введите целое число.",
            "correctAnswer": None,
            "correctAnswerChecker": (
                "def check(answer):\n    return missing_name(answer)"
            ),
            "wrongAnswer": "Нет.",
            "congratulation": "Да.",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    publish_pending_problem_configuration(
        fixture,
        answer_config_json=broken_config,
    )
    preview = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID
    )

    receipt = await fixture.repository.recheck_pending_test_attempts(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
        expected_condition_revision_public_id=(preview.condition_revision_public_id),
        expected_config_version=preview.config_version,
        actor_user_id=ADMIN_USER_ID,
    )

    assert receipt.pending_before == receipt.still_pending == 1
    assert receipt.checked == receipt.correct == receipt.wrong == 0
    assert fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT check_status FROM test_attempts").fetchone()[
                "check_status"
            ],
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
        )
    ) == ("pending_configuration", 0)


async def test_recheck_rejects_stale_preview_without_changing_attempts(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-stale-recheck",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="179",
        )
    )
    preview = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID
    )
    current_config = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT answer_config_json FROM problem_revisions "
            "WHERE problem_id = (SELECT id FROM problems WHERE public_id = ?)",
            (PENDING_PROBLEM_PUBLIC_ID,),
        ).fetchone()["answer_config_json"]
    )
    publish_pending_problem_configuration(
        fixture,
        answer_config_json=str(current_config),
    )

    with pytest.raises(SubmissionRejected) as caught:
        await fixture.repository.recheck_pending_test_attempts(
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            expected_condition_revision_public_id=(
                preview.condition_revision_public_id
            ),
            expected_config_version=preview.config_version,
            actor_user_id=ADMIN_USER_ID,
        )

    assert caught.value.code == "test_problem_revision_changed"
    assert fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT check_status FROM test_attempts").fetchone()[
                "check_status"
            ],
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
        )
    ) == ("pending_configuration", 0)


async def test_concurrent_rechecks_create_one_result(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-concurrent-recheck",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="179",
        )
    )
    config = json.dumps(
        {
            "schemaVersion": 1,
            "answerType": int(ANS_TYPE.INTEGER),
            "answerValidation": None,
            "validationError": "Введите целое число.",
            "correctAnswer": "179",
            "correctAnswerChecker": None,
            "wrongAnswer": "Нет.",
            "congratulation": "Да.",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    publish_pending_problem_configuration(fixture, answer_config_json=config)
    preview = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID
    )

    receipts = await asyncio.gather(
        *(
            fixture.repository.recheck_pending_test_attempts(
                problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
                expected_condition_revision_public_id=(
                    preview.condition_revision_public_id
                ),
                expected_config_version=preview.config_version,
                actor_user_id=ADMIN_USER_ID,
            )
            for _ in range(2)
        )
    )

    assert sum(receipt.checked for receipt in receipts) == 1
    assert fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            connection.execute("SELECT check_status FROM test_attempts").fetchone()[
                "check_status"
            ],
        )
    ) == (1, "checked")


async def test_recheck_rolls_back_result_when_attempt_transition_fails(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-pending-recheck-rollback",
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="179",
        )
    )
    config = json.dumps(
        {
            "schemaVersion": 1,
            "answerType": int(ANS_TYPE.INTEGER),
            "answerValidation": None,
            "validationError": "Введите целое число.",
            "correctAnswer": "179",
            "correctAnswerChecker": None,
            "wrongAnswer": "Нет.",
            "congratulation": "Да.",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    publish_pending_problem_configuration(fixture, answer_config_json=config)
    preview = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID
    )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "CREATE TRIGGER synthetic_recheck_crash BEFORE UPDATE ON test_attempts "
            "BEGIN SELECT raise(abort, 'synthetic recheck crash'); END"
        )
    )

    with pytest.raises(sqlite3.IntegrityError, match="synthetic recheck crash"):
        await fixture.repository.recheck_pending_test_attempts(
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            expected_condition_revision_public_id=(
                preview.condition_revision_public_id
            ),
            expected_config_version=preview.config_version,
            actor_user_id=ADMIN_USER_ID,
        )

    assert fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            connection.execute("SELECT check_status FROM test_attempts").fetchone()[
                "check_status"
            ],
        )
    ) == (0, "pending_configuration")

    fixture.factory.run_write(
        lambda connection: connection.execute("DROP TRIGGER synthetic_recheck_crash")
    )
    retried = await fixture.repository.recheck_pending_test_attempts(
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
        expected_condition_revision_public_id=(preview.condition_revision_public_id),
        expected_config_version=preview.config_version,
        actor_user_id=ADMIN_USER_ID,
    )
    assert retried.checked == 1


async def test_offline_answer_created_at_cutoff_is_timely_after_late_delivery(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    cutoff = NOW - timedelta(days=1)
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE lesson_windows SET submission_closes_at = ? WHERE id = ?",
            (timestamp(cutoff), fixture.window_id),
        )
    )

    receipt = await fixture.repository.submit_test_answer(
        command(
            fixture,
            key="attempt-offline-at-cutoff",
            client_created_at=cutoff,
        )
    )
    attempt = fixture.factory.run_read(
        lambda connection: connection.execute("SELECT * FROM test_attempts").fetchone()
    )

    assert receipt.outcome == "correct"
    assert receipt.clock_suspicious is True
    assert attempt["clock_suspicious"] == 1
    assert attempt["clock_skew_seconds"] == 24 * 60 * 60


async def test_late_answer_failure_is_idempotent_and_writes_no_attempt(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    cutoff = NOW - timedelta(minutes=1)
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE lesson_windows SET submission_closes_at = ? WHERE id = ?",
            (timestamp(cutoff), fixture.window_id),
        )
    )
    request = command(fixture, key="attempt-late", client_created_at=NOW)

    for _ in range(2):
        with pytest.raises(SubmissionRejected) as caught:
            await fixture.repository.submit_test_answer(request)
        assert caught.value.code == "submission_deadline_passed"
        assert caught.value.http_status == 409

    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM test_attempts").fetchone()[
                "n"
            ],
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            connection.execute(
                "SELECT state, http_status FROM idempotency_records"
            ).fetchone(),
        )
    )
    assert counts[:2] == (0, 0)
    assert counts[2]["state"] == "failed"
    assert counts[2]["http_status"] == 409


async def test_hour_limit_blocks_fourth_counted_attempt_but_not_invalid_format(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    for index in range(3):
        await fixture.repository.submit_test_answer(
            command(
                fixture,
                answer="8",
                key=f"attempt-limit-{index}",
            )
        )

    with pytest.raises(SubmissionRejected) as caught:
        await fixture.repository.submit_test_answer(
            command(fixture, answer="8", key="attempt-limit-blocked")
        )
    invalid = await fixture.repository.submit_test_answer(
        command(fixture, answer="not-an-integer", key="attempt-limit-invalid")
    )

    assert caught.value.code == "test_attempt_hour_limit"
    assert caught.value.http_status == 429
    assert invalid.outcome == "invalid_format"
    assert invalid.attempts.used_this_hour == 3
    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM test_attempts").fetchone()[
                "n"
            ],
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
        )
    )
    assert counts == (4, 3)


async def test_explicit_unlimited_policy_accepts_repeated_attempts(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture

    receipts = [
        await fixture.repository.submit_test_answer(
            command(
                fixture,
                answer="8",
                key=f"attempt-unlimited-{index}",
                problem_public_id=UNLIMITED_PROBLEM_PUBLIC_ID,
            )
        )
        for index in range(8)
    ]

    assert receipts[-1].attempts.used_this_hour == 8
    assert receipts[-1].attempts.used_today == 8
    assert receipts[-1].attempts.unlimited is True
    assert receipts[-1].attempts.remaining_this_hour is None
    assert receipts[-1].attempts.remaining_today is None


async def test_daily_limit_is_independent_from_the_hour_limit(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    for index in range(2):
        await fixture.repository.submit_test_answer(
            command(
                fixture,
                answer="8",
                key=f"attempt-daily-{index}",
                problem_public_id=DAILY_LIMIT_PROBLEM_PUBLIC_ID,
            )
        )

    with pytest.raises(SubmissionRejected) as caught:
        await fixture.repository.submit_test_answer(
            command(
                fixture,
                answer="8",
                key="attempt-daily-blocked",
                problem_public_id=DAILY_LIMIT_PROBLEM_PUBLIC_ID,
            )
        )

    assert caught.value.code == "test_attempt_day_limit"
    assert caught.value.details == {
        "usedThisHour": 2,
        "remainingThisHour": None,
        "usedToday": 2,
        "remainingToday": 0,
        "unlimited": False,
    }


async def test_two_concurrent_retries_create_one_attempt_and_one_result(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    request = command(fixture, key="attempt-race")

    first, second = await asyncio.gather(
        fixture.repository.submit_test_answer(request),
        fixture.repository.submit_test_answer(request),
    )

    assert first == second
    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM test_attempts").fetchone()[
                "n"
            ],
            connection.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
        )
    )
    assert counts == (1, 1)


async def test_failure_after_result_insert_rolls_back_and_retry_is_clean(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "CREATE TRIGGER synthetic_attempt_crash BEFORE INSERT ON test_attempts "
            "BEGIN SELECT raise(abort, 'synthetic crash after result'); END"
        )
    )
    request = command(fixture, key="attempt-crash")

    with pytest.raises(sqlite3.IntegrityError, match="synthetic crash"):
        await fixture.repository.submit_test_answer(request)
    counts_after_crash = fixture.factory.run_read(
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
    assert counts_after_crash == (0, 0, 0)

    fixture.factory.run_write(
        lambda connection: connection.execute("DROP TRIGGER synthetic_attempt_crash")
    )
    receipt = await fixture.repository.submit_test_answer(request)
    assert receipt.outcome == "correct"


async def test_other_student_cannot_discover_or_submit_the_problem(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    request = SubmitTestAnswerCommand(
        account_id=fixture.other_account_id,
        problem_public_id=PROBLEM_PUBLIC_ID,
        display_answer="7",
        client_created_at=NOW,
        idempotency_key="attempt-other-student",
    )

    with pytest.raises(SubmissionRejected) as caught:
        await fixture.repository.submit_test_answer(request)

    assert caught.value.http_status == 404
    assert caught.value.code == "test_problem_not_found"


async def test_history_is_reverse_ordered_paginated_and_keeps_safe_feedback(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    first = await fixture.repository.submit_test_answer(
        command(
            fixture,
            answer="8",
            key="00000000-0000-4000-8000-000000000031",
        )
    )
    fixture.clock.value += timedelta(minutes=1)
    second = await fixture.repository.submit_test_answer(
        command(
            fixture,
            answer="7",
            key="00000000-0000-4000-8000-000000000032",
            client_created_at=fixture.clock.value,
        )
    )

    first_page = await fixture.repository.list_test_attempts(
        account_id=fixture.student_account_id,
        problem_public_id=PROBLEM_PUBLIC_ID,
        limit=1,
    )
    assert first_page.problem_public_id == PROBLEM_PUBLIC_ID
    assert [attempt.attempt_public_id for attempt in first_page.attempts] == [
        second.attempt_public_id
    ]
    assert first_page.attempts[0].outcome == "correct"
    assert first_page.attempts[0].check_status == "checked"
    assert first_page.attempts[0].feedback == "Да, всё верно!"
    assert first_page.attempts[0].result_version == 1
    assert first_page.next_cursor == second.attempt_public_id

    second_page = await fixture.repository.list_test_attempts(
        account_id=fixture.student_account_id,
        problem_public_id=PROBLEM_PUBLIC_ID,
        cursor=first_page.next_cursor,
        limit=1,
    )
    assert [attempt.attempt_public_id for attempt in second_page.attempts] == [
        first.attempt_public_id
    ]
    assert second_page.attempts[0].outcome == "wrong"
    assert second_page.attempts[0].display_answer == "8"
    assert second_page.attempts[0].feedback == "Нет, это другое число."
    assert second_page.next_cursor is None


async def test_history_allows_empty_current_problem_and_old_owned_work_after_access_revoked(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    empty = await fixture.repository.list_test_attempts(
        account_id=fixture.student_account_id,
        problem_public_id=PROBLEM_PUBLIC_ID,
    )
    assert empty.attempts == ()

    receipt = await fixture.repository.submit_test_answer(
        command(
            fixture,
            answer="7",
            key="00000000-0000-4000-8000-000000000033",
        )
    )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_group_access SET valid_to = ?, updated_at = ? "
            "WHERE group_id = 'submission-a'",
            (
                timestamp(NOW + timedelta(seconds=1)),
                timestamp(NOW + timedelta(seconds=1)),
            ),
        )
    )
    fixture.clock.value = NOW + timedelta(seconds=2)

    history = await fixture.repository.list_test_attempts(
        account_id=fixture.student_account_id,
        problem_public_id=PROBLEM_PUBLIC_ID,
    )
    assert [attempt.attempt_public_id for attempt in history.attempts] == [
        receipt.attempt_public_id
    ]


async def test_history_does_not_expose_stale_receipt_copy_after_recheck(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    pending = await fixture.repository.submit_test_answer(
        command(
            fixture,
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            answer="179",
            key="00000000-0000-4000-8000-000000000034",
        )
    )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE test_attempts SET check_status = 'failed', "
            "checker_version = 'synthetic-recheck-v1', checked_at = ? "
            "WHERE public_id = ?",
            (timestamp(NOW), pending.attempt_public_id),
        )
    )

    history = await fixture.repository.list_test_attempts(
        account_id=fixture.student_account_id,
        problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
    )
    attempt = history.attempts[0]
    assert attempt.outcome == "checker_failed"
    assert attempt.check_status == "failed"
    assert attempt.feedback is None
    assert attempt.checker_message is None


async def test_history_rejects_foreign_owner_and_foreign_cursor_without_disclosure(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    receipt = await fixture.repository.submit_test_answer(
        command(
            fixture,
            answer="7",
            key="00000000-0000-4000-8000-000000000035",
        )
    )

    with pytest.raises(SubmissionRejected) as foreign_problem:
        await fixture.repository.list_test_attempts(
            account_id=fixture.other_account_id,
            problem_public_id=PROBLEM_PUBLIC_ID,
        )
    assert foreign_problem.value.http_status == 404

    with pytest.raises(SubmissionRejected) as foreign_cursor:
        await fixture.repository.list_test_attempts(
            account_id=fixture.student_account_id,
            problem_public_id=PENDING_PROBLEM_PUBLIC_ID,
            cursor=receipt.attempt_public_id,
        )
    assert foreign_cursor.value.http_status in {404, 422}


def written_entry_command(
    fixture: SubmissionFixture,
    *,
    text: str | None = "Решение по шагам.",
    key: str = "written-create-key-1",
    client_created_at: datetime = NOW,
) -> CreateWrittenEntryCommand:
    return CreateWrittenEntryCommand(
        account_id=fixture.student_account_id,
        problem_public_id=WRITTEN_PROBLEM_PUBLIC_ID,
        problem_revision=ProblemRevisionRef(
            condition_revision_public_id="revision-submission-condition",
            config_version=1,
        ),
        text=text,
        client_created_at=client_created_at,
        idempotency_key=key,
    )


def submit_written_entry_command(
    fixture: SubmissionFixture,
    *,
    entry_public_id: str,
    thread_version: int,
    entry_version: int = 1,
    key: str = "written-submit-key-1",
) -> SubmitWrittenEntryCommand:
    return SubmitWrittenEntryCommand(
        account_id=fixture.student_account_id,
        entry_public_id=entry_public_id,
        expected_entry_version=entry_version,
        expected_thread_version=thread_version,
        attachment_public_ids=(),
        idempotency_key=key,
    )


def written_attachment_command(
    fixture: SubmissionFixture,
    *,
    entry_public_id: str,
    thread_version: int,
    entry_version: int = 1,
    ordinal: int = 0,
    key: str = "written-attachment-key-1",
    source_sha256: str = "b" * 64,
) -> CreateWrittenAttachmentCommand:
    return CreateWrittenAttachmentCommand(
        account_id=fixture.student_account_id,
        entry_public_id=entry_public_id,
        expected_entry_version=entry_version,
        expected_thread_version=thread_version,
        ordinal=ordinal,
        client_filename="страница-1.heic",
        source_sha256=source_sha256,
        idempotency_key=key,
    )


def persisted_written_attachment(*, suffix: str = "1") -> PersistWrittenAttachment:
    return PersistWrittenAttachment(
        object_key=f"sol_imgs/user_{STUDENT_USER_ID}/2026/lesson_41/final-{suffix}.webp",
        public_url=f"https://assets.invalid/final-{suffix}.webp",
        output_sha256=suffix[-1] * 64,
        byte_size=1_024,
        width=1_440,
        height=1_920,
    )


async def test_written_draft_keeps_exact_revision_and_replays_without_duplicates(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    command = written_entry_command(fixture)

    first = await fixture.written_repository.create_entry(command)
    replay = await fixture.written_repository.create_entry(command)
    stored = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM submission_threads").fetchall(),
            connection.execute("SELECT * FROM submission_entries").fetchall(),
            connection.execute(
                "SELECT * FROM idempotency_records "
                "WHERE operation = 'written-entry:create'"
            ).fetchall(),
        )
    )

    assert first.entry.problem_revision == command.problem_revision
    assert first.entry.text == "Решение по шагам."
    assert first.entry.state == "draft"
    assert first.thread_status == "open"
    assert first.thread_version == 1
    assert replay == first
    assert replay.replayed is True
    assert [len(rows) for rows in stored] == [1, 1, 1]
    assert stored[1][0]["problem_revision_id"] == fixture.written_problem_revision_id


async def test_written_create_key_rejects_a_different_payload(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.written_repository.create_entry(written_entry_command(fixture))

    with pytest.raises(WrittenIdempotencyPayloadMismatch):
        await fixture.written_repository.create_entry(
            written_entry_command(fixture, text="Другое решение.")
        )


async def test_written_attachment_keeps_server_scope_and_replays_once(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture)
    )
    command = written_attachment_command(
        fixture,
        entry_public_id=draft.entry.public_id,
        thread_version=draft.thread_version,
    )

    prepared = await fixture.written_repository.prepare_attachment_upload(command)
    assert isinstance(prepared, PreparedWrittenAttachmentUpload)
    assert prepared.scope.student_user_id == STUDENT_USER_ID
    assert prepared.scope.season_year == 2026
    assert prepared.scope.lesson_number == 41
    assert prepared.scope.problem_public_id == WRITTEN_PROBLEM_PUBLIC_ID

    receipt = await fixture.written_repository.complete_attachment_upload(
        prepared, persisted_written_attachment()
    )
    replay = await fixture.written_repository.prepare_attachment_upload(command)
    assert isinstance(replay, CreateWrittenAttachmentReceipt)
    stored = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM media_assets").fetchall(),
            connection.execute("SELECT * FROM submission_attachments").fetchall(),
            connection.execute("SELECT * FROM submission_entries").fetchone(),
            connection.execute("SELECT * FROM submission_threads").fetchone(),
            connection.execute(
                "SELECT * FROM idempotency_records "
                "WHERE operation = 'written-attachment:create'"
            ).fetchall(),
        )
    )

    assert receipt.entry.version == 2
    assert receipt.thread_version == 2
    assert len(receipt.entry.attachments) == 1
    assert receipt.entry.attachments[0].ordinal == 0
    assert receipt.entry.attachments[0].media_type == "image/webp"
    assert receipt.entry.attachments[0].media_path.endswith(
        f"/{receipt.entry.attachments[0].public_id}/media"
    )
    media = await fixture.written_repository.get_attachment_media(
        account_id=fixture.student_account_id,
        entry_public_id=draft.entry.public_id,
        attachment_public_id=receipt.entry.attachments[0].public_id,
    )
    assert media.object_key == persisted_written_attachment().object_key
    with pytest.raises(WrittenSubmissionRejected) as foreign:
        await fixture.written_repository.get_attachment_media(
            account_id=fixture.other_account_id,
            entry_public_id=draft.entry.public_id,
            attachment_public_id=receipt.entry.attachments[0].public_id,
        )
    assert foreign.value.code == "written_attachment_not_found"
    assert replay == receipt
    assert replay.replayed is True
    assert [len(rows) for rows in (stored[0], stored[1], stored[4])] == [1, 1, 1]
    assert stored[0][0]["storage_namespace"] == "submission"
    assert stored[0][0]["source_filename"] == "страница-1.heic"
    assert stored[2]["version"] == 2
    assert stored[3]["version"] == 2


async def test_written_attachment_version_failure_is_idempotent_and_empty(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture)
    )
    stale = written_attachment_command(
        fixture,
        entry_public_id=draft.entry.public_id,
        thread_version=draft.thread_version + 1,
    )

    for _ in range(2):
        with pytest.raises(WrittenSubmissionRejected) as rejected:
            await fixture.written_repository.prepare_attachment_upload(stale)
        assert rejected.value.code == "written_submission_version_conflict"

    assert fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT count(*) AS n FROM media_assets").fetchone()[
                "n"
            ],
            connection.execute(
                "SELECT count(*) AS n FROM submission_attachments"
            ).fetchone()["n"],
        )
    ) == (0, 0)


async def test_written_photo_only_entry_submits_with_exact_attachment_order(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture, text=None)
    )
    prepared = await fixture.written_repository.prepare_attachment_upload(
        written_attachment_command(
            fixture,
            entry_public_id=draft.entry.public_id,
            thread_version=draft.thread_version,
        )
    )
    assert isinstance(prepared, PreparedWrittenAttachmentUpload)
    uploaded = await fixture.written_repository.complete_attachment_upload(
        prepared, persisted_written_attachment()
    )
    attachment_id = uploaded.entry.attachments[0].public_id

    submitted = await fixture.written_repository.submit_entry(
        SubmitWrittenEntryCommand(
            account_id=fixture.student_account_id,
            entry_public_id=draft.entry.public_id,
            expected_entry_version=uploaded.entry.version,
            expected_thread_version=uploaded.thread_version,
            attachment_public_ids=(attachment_id,),
            idempotency_key="written-photo-submit-key-1",
        )
    )

    assert submitted.entry.state == "submitted"
    assert [item.public_id for item in submitted.entry.attachments] == [attachment_id]
    assert submitted.thread_status == "awaiting_review"


async def test_written_text_entry_submits_atomically_and_replays(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture)
    )
    command = submit_written_entry_command(
        fixture,
        entry_public_id=draft.entry.public_id,
        thread_version=draft.thread_version,
    )

    receipt = await fixture.written_repository.submit_entry(command)
    replay = await fixture.written_repository.submit_entry(command)
    stored = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM submission_threads").fetchone(),
            connection.execute("SELECT * FROM submission_entries").fetchone(),
            connection.execute(
                "SELECT * FROM idempotency_records "
                "WHERE operation = 'written-entry:submit'"
            ).fetchall(),
        )
    )
    thread, entry, idempotency = stored

    assert receipt.thread_status == "awaiting_review"
    assert receipt.thread_version == 2
    assert receipt.entry.state == "submitted"
    assert receipt.entry.version == 2
    assert replay == receipt
    assert replay.replayed is True
    assert thread["status"] == "awaiting_review"
    assert thread["version"] == 2
    assert entry["state"] == "submitted"
    assert entry["version"] == 2
    assert len(idempotency) == 1


async def test_written_blank_submit_failure_is_idempotent_and_non_mutating(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture, text="   ")
    )
    command = submit_written_entry_command(
        fixture,
        entry_public_id=draft.entry.public_id,
        thread_version=draft.thread_version,
    )

    for _ in range(2):
        with pytest.raises(WrittenSubmissionRejected) as rejected:
            await fixture.written_repository.submit_entry(command)
        assert rejected.value.code == "written_entry_empty"
        assert rejected.value.http_status == 422

    entry, thread, idempotency = fixture.factory.run_read(
        lambda connection: (
            connection.execute("SELECT * FROM submission_entries").fetchone(),
            connection.execute("SELECT * FROM submission_threads").fetchone(),
            connection.execute(
                "SELECT * FROM idempotency_records "
                "WHERE operation = 'written-entry:submit'"
            ).fetchall(),
        )
    )
    assert entry["state"] == "draft"
    assert entry["version"] == 1
    assert thread["status"] == "open"
    assert thread["version"] == 1
    assert len(idempotency) == 1
    assert idempotency[0]["state"] == "failed"


async def test_written_submit_rejects_stale_versions_without_partial_update(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture)
    )

    with pytest.raises(WrittenSubmissionRejected) as rejected:
        await fixture.written_repository.submit_entry(
            submit_written_entry_command(
                fixture,
                entry_public_id=draft.entry.public_id,
                thread_version=draft.thread_version + 1,
            )
        )

    assert rejected.value.code == "written_submission_version_conflict"
    entry = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT state, version FROM submission_entries"
        ).fetchone()
    )
    assert entry == {"state": "draft", "version": 1}


async def test_written_offline_entry_created_before_cutoff_submits_later(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    cutoff = NOW + timedelta(days=2)
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture, client_created_at=cutoff - timedelta(minutes=1))
    )
    fixture.clock.value = cutoff + timedelta(days=1)

    receipt = await fixture.written_repository.submit_entry(
        submit_written_entry_command(
            fixture,
            entry_public_id=draft.entry.public_id,
            thread_version=draft.thread_version,
        )
    )

    assert receipt.entry.state == "submitted"
    assert receipt.clock_suspicious is True


async def test_written_thread_history_survives_access_revocation(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    draft = await fixture.written_repository.create_entry(
        written_entry_command(fixture)
    )
    fixture.factory.run_write(
        lambda connection: (
            connection.execute(
                "UPDATE submission_threads SET status = 'closed', "
                "version = version + 1, updated_at = ?",
                (timestamp(NOW + timedelta(seconds=1)),),
            ),
            connection.execute(
                "UPDATE course_group_access SET valid_to = ?, version = version + 1, "
                "updated_at = ?",
                (
                    timestamp(NOW + timedelta(seconds=1)),
                    timestamp(NOW + timedelta(seconds=1)),
                ),
            ),
        )
    )
    fixture.clock.value = NOW + timedelta(seconds=2)

    thread = await fixture.written_repository.get_thread(
        account_id=fixture.student_account_id,
        problem_public_id=WRITTEN_PROBLEM_PUBLIC_ID,
    )

    assert thread is not None
    assert thread.public_id == draft.thread_public_id
    assert [entry.public_id for entry in thread.entries] == [draft.entry.public_id]


async def test_written_thread_does_not_disclose_another_students_work(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    await fixture.written_repository.create_entry(written_entry_command(fixture))

    with pytest.raises(WrittenSubmissionRejected) as rejected:
        await fixture.written_repository.get_thread(
            account_id=fixture.other_account_id,
            problem_public_id=WRITTEN_PROBLEM_PUBLIC_ID,
        )

    assert rejected.value.code == "written_problem_not_found"
    assert rejected.value.http_status == 404


async def test_concurrent_written_create_retries_make_one_draft(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    command = written_entry_command(fixture)

    first, second = await asyncio.gather(
        fixture.written_repository.create_entry(command),
        fixture.written_repository.create_entry(command),
    )

    assert first == second
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
                "WHERE operation = 'written-entry:create'"
            ).fetchone()["n"],
        )
    )
    assert counts == (1, 1, 1)


async def test_written_create_fault_rolls_back_and_retry_is_clean(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "CREATE TRIGGER fail_written_entry_insert BEFORE INSERT "
            "ON submission_entries BEGIN SELECT raise(abort, 'synthetic fault'); END"
        )
    )

    with pytest.raises(sqlite3.IntegrityError, match="synthetic fault"):
        await fixture.written_repository.create_entry(written_entry_command(fixture))

    assert fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT count(*) AS n FROM submission_threads"
            ).fetchone()["n"],
            connection.execute(
                "SELECT count(*) AS n FROM submission_entries"
            ).fetchone()["n"],
            connection.execute(
                "SELECT count(*) AS n FROM idempotency_records "
                "WHERE operation = 'written-entry:create'"
            ).fetchone()["n"],
        )
    ) == (0, 0, 0)

    fixture.factory.run_write(
        lambda connection: connection.execute("DROP TRIGGER fail_written_entry_insert")
    )
    receipt = await fixture.written_repository.create_entry(
        written_entry_command(fixture)
    )
    assert receipt.entry.state == "draft"


async def test_written_entry_created_after_cutoff_cannot_be_submitted(
    submission_fixture: SubmissionFixture,
):
    fixture = submission_fixture
    cutoff = NOW + timedelta(days=2)
    fixture.clock.value = cutoff + timedelta(minutes=5)
    draft = await fixture.written_repository.create_entry(
        written_entry_command(
            fixture,
            client_created_at=cutoff + timedelta(minutes=1),
        )
    )

    with pytest.raises(WrittenSubmissionRejected) as rejected:
        await fixture.written_repository.submit_entry(
            submit_written_entry_command(
                fixture,
                entry_public_id=draft.entry.public_id,
                thread_version=draft.thread_version,
            )
        )

    assert rejected.value.code == "submission_deadline_passed"
    assert rejected.value.details == {"submissionClosesAt": timestamp(cutoff)}
