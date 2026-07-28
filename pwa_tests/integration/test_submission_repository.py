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
from helpers.consts import ANS_TYPE, RES_TYPE, VERDICT


NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)
STUDENT_USER_ID = -947_001
OTHER_STUDENT_USER_ID = -947_002
PROBLEM_PUBLIC_ID = "problem-submission-integer"
PENDING_PROBLEM_PUBLIC_ID = "problem-submission-pending"
UNLIMITED_PROBLEM_PUBLIC_ID = "problem-submission-unlimited"
DAILY_LIMIT_PROBLEM_PUBLIC_ID = "problem-submission-daily-limit"


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
    clock: MutableClock
    student_account_id: int
    other_account_id: int
    problem_id: int
    problem_revision_id: int
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
            window_id,
        )

    account_id, other_account_id, problem_id, problem_revision_id, window_id = (
        factory.run_write(seed)
    )
    return SubmissionFixture(
        factory=factory,
        repository=repository,
        clock=clock,
        student_account_id=account_id,
        other_account_id=other_account_id,
        problem_id=problem_id,
        problem_revision_id=problem_revision_id,
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
