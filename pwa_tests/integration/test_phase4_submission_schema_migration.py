"""Exact additive migration and SQLite guards for Phase-4 test attempts."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0046.pwa_test_attempts_idempotency"
NOW = "2026-09-20T13:00:00.000000Z"
EXPECTED_OBJECTS = {
    "idempotency_records",
    "idempotency_records_expiry_idx",
    "idempotency_records_account_scope_insert",
    "idempotency_records_identity_immutable",
    "idempotency_records_state_transition_guard",
    "problem_revisions_id_problem_uq",
    "results_id_student_problem_uq",
    "test_attempts",
    "test_attempts_student_problem_history_idx",
    "test_attempts_student_problem_counted_idx",
    "test_attempts_pending_configuration_idx",
    "test_attempts_payload_immutable",
    "test_attempts_check_transition_guard",
    "test_attempts_result_contract_insert",
    "test_attempts_result_contract_update",
    "test_attempts_delete_forbidden",
}


def _migrations():
    return yoyo.read_migrations(str(MIGRATIONS_ROOT))


def _apply(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(selected))


def _rollback(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(selected))


def _schema(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    return connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE '_yoyo_%' "
        "ORDER BY type, name"
    ).fetchall()


def _objects(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE '_yoyo_%'"
        )
    }


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        str(row[0]): int(
            connection.execute(f'SELECT count(*) FROM "{row[0]}"').fetchone()[0]
        )
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_yoyo_%'"
        )
    }


def _insert_student_account(connection: sqlite3.Connection) -> tuple[int, int]:
    student_id = -946_001
    connection.execute(
        "INSERT INTO users (id, type, name, surname) "
        "VALUES (?, 1, 'Attempt', 'Student')",
        (student_id,),
    )
    account_id = int(
        connection.execute(
            "INSERT INTO auth_accounts "
            "(audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES ('student', 'Attempt Student', "
            "'attempt student', 1, 'test', 'telegram_token', 'hash', ?, "
            "'active', ?, ?) RETURNING id",
            (student_id, NOW, NOW),
        ).fetchone()[0]
    )
    return student_id, account_id


def _insert_test_problem_context(
    connection: sqlite3.Connection, *, student_id: int
) -> tuple[int, int]:
    season_id = int(
        connection.execute(
            "INSERT INTO seasons "
            "(code, title, starts_on, ends_on, session_expires_on, "
            "status, created_at, updated_at) VALUES "
            "('attempt-schema', 'Attempt schema', "
            "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) "
            "RETURNING id",
            (NOW, NOW),
        ).fetchone()[0]
    )
    course_id = int(
        connection.execute(
            "INSERT INTO courses "
            "(season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "(?, 'math', 'Math', 'math', 'active', 1, "
            "'math', ?, ?) RETURNING id",
            (season_id, NOW, NOW),
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, course_id, "
        "status, created_at, updated_at) VALUES "
        "('attempt-a', 'a', 'A', 1, 1, 0, 1, 0, 1.0, ?, 'active', ?, ?)",
        (course_id, NOW, NOW),
    )
    course_lesson_id = int(
        connection.execute(
            "INSERT INTO course_lessons "
            "(course_id, lesson_number, created_at, updated_at) "
            "VALUES (?, 41, ?, ?) RETURNING id",
            (course_id, NOW, NOW),
        ).fetchone()[0]
    )
    group_lesson_id = int(
        connection.execute(
            "INSERT INTO group_lessons "
            "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "(?, ?, 'attempt-a', '2026-09-14', "
            "'Europe/Moscow', 'active', ?, ?) RETURNING id",
            (course_lesson_id, course_id, NOW, NOW),
        ).fetchone()[0]
    )
    source_id = int(
        connection.execute(
            "INSERT INTO content_sources "
            "(group_lesson_id, kind, logical_filename, source_encoding, "
            "created_at) VALUES (?, 'condition', "
            "'condition.tex', 'utf-8', ?) RETURNING id",
            (group_lesson_id, NOW),
        ).fetchone()[0]
    )
    content_revision_id = int(
        connection.execute(
            "INSERT INTO content_revisions "
            "(source_id, revision_number, source_sha256, latex_text, "
            "parser_version, status, canonical_json, diagnostics_json, "
            "provenance_json, created_at) VALUES "
            "(?, 1, ?, '\\задача 7 \\кзадача', "
            "'test-v1', 'ready', '{}', '[]', '{}', ?) RETURNING id",
            (source_id, "c" * 64, NOW),
        ).fetchone()[0]
    )
    problem_id = int(
        connection.execute(
            "INSERT INTO problems "
            "(group_id, lesson, prob, item, title, prob_text, prob_type, ans_type, "
            "ans_validation, validation_error, cor_ans, wrong_ans, congrat, synonyms) "
            "VALUES ('attempt-a', 41, 1, '', 'Цифра', '', 1, 1, '', "
            "'Введите цифру', '7', 'Нет', 'Да', '') RETURNING id"
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO content_problem_matches "
        "(content_revision_id, source_ordinal, source_item, problem_id, decision, "
        "resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
        "VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
        (content_revision_id, problem_id, student_id, NOW, NOW),
    )
    problem_revision_id = int(
        connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, "
            "display_number, title, normalized_title, problem_type, answer_type, "
            "answer_config_json, attempt_policy_json, config_version, created_at) "
            "VALUES (?, ?, 1, '1', '1', 'Цифра', 'цифра', 1, 1, '{}', '{}', 1, ?) "
            "RETURNING id",
            (problem_id, content_revision_id, NOW),
        ).fetchone()[0]
    )
    return problem_id, problem_revision_id


def test_phase4_submission_schema_exact_up_down_up_and_additive(tmp_path):
    database_path = tmp_path / "phase4-submission-schema.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0045.pwa_material_reveal_matches"
    }
    preceding = {
        item.id for item in migrations.values() if item.id.split(".", 1)[0] < "0046"
    }
    _apply(database_path, preceding)

    with sqlite3.connect(database_path) as connection:
        before_schema = _schema(connection)
        before_counts = _counts(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert EXPECTED_OBJECTS <= _objects(connection)
        assert {
            name: count
            for name, count in _counts(connection).items()
            if name in before_counts
        } == before_counts
        assert (
            connection.execute(
                'PRAGMA foreign_key_check("idempotency_records")'
            ).fetchall()
            == []
        )
        assert (
            connection.execute('PRAGMA foreign_key_check("test_attempts")').fetchall()
            == []
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _schema(connection) == before_schema
        assert _counts(connection) == before_counts
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert EXPECTED_OBJECTS <= _objects(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_phase4_idempotency_scope_hash_state_and_identity_are_guarded(tmp_path):
    database_path = tmp_path / "phase4-idempotency-guards.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        _student_id, account_id = _insert_student_account(connection)

        with pytest.raises(sqlite3.IntegrityError, match="audience mismatch"):
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('staff', ?, 'test-attempt', 'key-wrong', "
                "?, 'processing', ?)",
                (account_id, "a" * 64, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, 'test-attempt', 'key-hash', "
                "'NOT-A-SHA', 'processing', ?)",
                (account_id, NOW),
            )

        record_id = int(
            connection.execute(
                "INSERT INTO idempotency_records "
                "(audience, account_id, operation, idempotency_key, payload_sha256, "
                "state, created_at) VALUES ('student', ?, 'test-attempt', 'key-ok', "
                "?, 'processing', ?) RETURNING id",
                (account_id, "b" * 64, NOW),
            ).fetchone()[0]
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE idempotency_records SET state = 'completed' WHERE id = ?",
                (record_id,),
            )
        connection.execute(
            "UPDATE idempotency_records SET state = 'completed', http_status = 201, "
            "response_json = '{}', completed_at = ? WHERE id = ?",
            (NOW, record_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="state transition"):
            connection.execute(
                "UPDATE idempotency_records SET http_status = 200 WHERE id = ?",
                (record_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE idempotency_records SET idempotency_key = 'replaced' WHERE id = ?",
                (record_id,),
            )

        assert (
            connection.execute(
                'PRAGMA foreign_key_check("idempotency_records")'
            ).fetchall()
            == []
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_phase4_attempt_revision_result_and_state_invariants(tmp_path):
    database_path = tmp_path / "phase4-attempt-guards.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        student_id, _account_id = _insert_student_account(connection)
        problem_id, problem_revision_id = _insert_test_problem_context(
            connection, student_id=student_id
        )
        result_id = int(
            connection.execute(
                "INSERT INTO results "
                "(student_id, problem_id, group_id, lesson, ts, verdict, answer, "
                "res_type) VALUES (?, ?, 'attempt-a', 41, ?, 18, '7', 1) RETURNING id",
                (student_id, problem_id, NOW),
            ).fetchone()[0]
        )
        attempt_id = int(
            connection.execute(
                "INSERT INTO test_attempts "
                "(student_user_id, problem_id, problem_revision_id, "
                "answer_payload_json, normalized_answer_json, parse_status, "
                "counts_as_attempt, check_status, client_created_at, "
                "server_received_at, clock_skew_seconds, clock_suspicious, "
                "idempotency_key, payload_sha256, checker_version, verdict, "
                "result_id, created_at, checked_at) VALUES "
                "(?, ?, ?, ?, ?, 'valid', 1, 'checked', ?, ?, "
                "0, 0, 'attempt-key-1', ?, 'legacy-standard-v1', 18, ?, ?, ?) "
                "RETURNING id",
                (
                    student_id,
                    problem_id,
                    problem_revision_id,
                    '{"displayAnswer":"7"}',
                    '{"kind":"integer","value":"7"}',
                    NOW,
                    NOW,
                    "d" * 64,
                    result_id,
                    NOW,
                    NOW,
                ),
            ).fetchone()[0]
        )

        invalid_id = int(
            connection.execute(
                "INSERT INTO test_attempts "
                "(student_user_id, problem_id, problem_revision_id, "
                "answer_payload_json, parse_status, counts_as_attempt, check_status, "
                "client_created_at, server_received_at, clock_skew_seconds, "
                "clock_suspicious, idempotency_key, payload_sha256, created_at, "
                "checked_at) VALUES (?, ?, ?, ?, "
                "'invalid_format', 0, 'checked', ?, ?, 0, 0, 'attempt-key-2', ?, ?, ?) "
                "RETURNING id",
                (
                    student_id,
                    problem_id,
                    problem_revision_id,
                    '{"displayAnswer":"17"}',
                    NOW,
                    NOW,
                    "e" * 64,
                    NOW,
                    NOW,
                ),
            ).fetchone()[0]
        )
        assert invalid_id != attempt_id

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO test_attempts "
                "(student_user_id, problem_id, problem_revision_id, "
                "answer_payload_json, parse_status, counts_as_attempt, check_status, "
                "client_created_at, server_received_at, clock_skew_seconds, "
                "clock_suspicious, idempotency_key, payload_sha256, created_at, "
                "checked_at) VALUES (?, ?, ?, ?, "
                "'invalid_format', 1, 'checked', ?, ?, 0, 0, 'attempt-key-3', ?, ?, ?)",
                (
                    student_id,
                    problem_id,
                    problem_revision_id,
                    '{"displayAnswer":"17"}',
                    NOW,
                    NOW,
                    "f" * 64,
                    NOW,
                    NOW,
                ),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO test_attempts "
                "(student_user_id, problem_id, problem_revision_id, "
                "answer_payload_json, normalized_answer_json, parse_status, "
                "counts_as_attempt, check_status, client_created_at, "
                "server_received_at, clock_skew_seconds, clock_suspicious, "
                "idempotency_key, payload_sha256, checker_version, verdict, "
                "result_id, created_at, checked_at) VALUES "
                "(?, ?, ?, ?, ?, 'valid', 1, 'checked', "
                "?, ?, 0, 0, 'attempt-key-4', ?, 'legacy-standard-v1', 18, ?, ?, ?)",
                (
                    student_id,
                    problem_id,
                    problem_revision_id,
                    '{"displayAnswer":"8"}',
                    '{"kind":"integer","value":"8"}',
                    NOW,
                    NOW,
                    "1" * 64,
                    result_id,
                    NOW,
                    NOW,
                ),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE test_attempts SET answer_payload_json = ? WHERE id = ?",
                ('{"displayAnswer":"8"}', attempt_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            connection.execute("DELETE FROM test_attempts WHERE id = ?", (attempt_id,))

        assert (
            connection.execute('PRAGMA foreign_key_check("test_attempts")').fetchall()
            == []
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
