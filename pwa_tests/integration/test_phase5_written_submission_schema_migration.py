"""Exact additive migration and SQLite guards for Phase-5 written evidence."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0047.pwa_submission_threads_entries_assets"
NOW = "2026-09-27T13:00:00.000000Z"
LATER = "2026-09-27T13:01:00.000000Z"
EXPECTED_OBJECTS = {
    "media_assets_locked_submission_immutable",
    "submission_attachments",
    "submission_attachments_asset_contract_insert",
    "submission_attachments_asset_idx",
    "submission_attachments_delete_guard",
    "submission_attachments_entry_mutable_insert",
    "submission_attachments_entry_mutable_update",
    "submission_attachments_entry_order_idx",
    "submission_attachments_id_entry_uq",
    "submission_attachments_identity_immutable",
    "submission_attachments_lock_result_scope_update",
    "submission_attachments_locked_immutable",
    "submission_attachments_max_ten_insert",
    "submission_attachments_state_transition_guard",
    "submission_entries",
    "submission_entries_author_idempotency_uq",
    "submission_entries_author_scope_insert",
    "submission_entries_author_scope_update",
    "submission_entries_delete_forbidden",
    "submission_entries_id_thread_uq",
    "submission_entries_identity_immutable",
    "submission_entries_legacy_group_idx",
    "submission_entries_lock_requires_attachments_locked",
    "submission_entries_nonempty_insert",
    "submission_entries_nonempty_update",
    "submission_entries_state_transition_guard",
    "submission_entries_terminal_immutable",
    "submission_entries_thread_history_idx",
    "submission_entries_version_guard",
    "submission_material_reassignment_items",
    "submission_material_reassignment_items_delete_forbidden",
    "submission_material_reassignment_items_immutable_update",
    "submission_material_reassignment_items_projection_idx",
    "submission_material_reassignment_items_scope_insert",
    "submission_material_reassignments",
    "submission_material_reassignments_delete_forbidden",
    "submission_material_reassignments_immutable_update",
    "submission_material_reassignments_student_history_idx",
    "submission_threads",
    "submission_threads_delete_forbidden",
    "submission_threads_id_owner_problem_uq",
    "submission_threads_identity_immutable",
    "submission_threads_one_active_uq",
    "submission_threads_problem_revision_scope_insert",
    "submission_threads_result_kind_insert",
    "submission_threads_result_kind_update",
    "submission_threads_review_queue_idx",
    "submission_threads_state_transition_guard",
    "submission_threads_student_updated_idx",
    "submission_threads_version_guard",
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


def _insert_context(connection: sqlite3.Connection) -> dict[str, int]:
    student_id = -947_001
    other_student_id = -947_002
    teacher_id = -947_003
    for user_id, user_type, name, public_id in (
        (student_id, 1, "Written Student", "student-written-schema"),
        (other_student_id, 1, "Other Student", "student-written-schema-other"),
        (teacher_id, 2, "Written Teacher", "teacher-written-schema"),
    ):
        connection.execute(
            "INSERT INTO users (id, type, name, surname, public_id) "
            "VALUES (?, ?, ?, 'Schema', ?)",
            (user_id, user_type, name, public_id),
        )

    season_id = int(
        connection.execute(
            "INSERT INTO seasons "
            "(public_id, code, title, starts_on, ends_on, session_expires_on, "
            "status, created_at, updated_at) VALUES "
            "('season-written-schema', 'written-schema', 'Written schema', "
            "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) "
            "RETURNING id",
            (NOW, NOW),
        ).fetchone()[0]
    )
    course_id = int(
        connection.execute(
            "INSERT INTO courses "
            "(public_id, season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "('course-written-schema', ?, 'math', 'Math', 'math', 'active', 1, "
            "'math', ?, ?) RETURNING id",
            (season_id, NOW, NOW),
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, public_id, course_id, "
        "status, created_at, updated_at) VALUES "
        "('written-a', 'a', 'A', 1, 1, 0, 1, 0, 1.0, "
        "'group-written-a', ?, 'active', ?, ?)",
        (course_id, NOW, NOW),
    )
    course_lesson_id = int(
        connection.execute(
            "INSERT INTO course_lessons "
            "(public_id, course_id, lesson_number, created_at, updated_at) "
            "VALUES ('lesson-written-41', ?, 41, ?, ?) RETURNING id",
            (course_id, NOW, NOW),
        ).fetchone()[0]
    )
    group_lesson_id = int(
        connection.execute(
            "INSERT INTO group_lessons "
            "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "('group-lesson-written-a', ?, ?, 'written-a', '2026-09-21', "
            "'Europe/Moscow', 'active', ?, ?) RETURNING id",
            (course_lesson_id, course_id, NOW, NOW),
        ).fetchone()[0]
    )
    source_id = int(
        connection.execute(
            "INSERT INTO content_sources "
            "(public_id, group_lesson_id, kind, logical_filename, source_encoding, "
            "created_at) VALUES ('source-written-condition', ?, 'condition', "
            "'condition.tex', 'utf-8', ?) RETURNING id",
            (group_lesson_id, NOW),
        ).fetchone()[0]
    )
    revision_id = int(
        connection.execute(
            "INSERT INTO content_revisions "
            "(public_id, source_id, revision_number, source_sha256, latex_text, "
            "parser_version, status, canonical_json, diagnostics_json, "
            "provenance_json, created_at) VALUES "
            "('revision-written-condition', ?, 1, ?, 'two problems', 'test-v1', "
            "'ready', '{}', '[]', '{}', ?) RETURNING id",
            (source_id, "7" * 64, NOW),
        ).fetchone()[0]
    )
    unrelated_revision_id = int(
        connection.execute(
            "INSERT INTO content_revisions "
            "(public_id, source_id, revision_number, source_sha256, latex_text, "
            "parser_version, status, canonical_json, diagnostics_json, "
            "provenance_json, created_at) VALUES "
            "('revision-written-unmatched', ?, 2, ?, 'unmatched', 'test-v1', "
            "'ready', '{}', '[]', '{}', ?) RETURNING id",
            (source_id, "8" * 64, NOW),
        ).fetchone()[0]
    )

    problem_ids: list[int] = []
    for ordinal, title in ((1, "Written one"), (2, "Written two")):
        problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                "congrat, synonyms) VALUES "
                "('written-a', 41, ?, '', ?, '', 2, 0, '', '', '', '', '', '') "
                "RETURNING id",
                (ordinal, title),
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO content_problem_matches "
            "(content_revision_id, source_ordinal, source_item, problem_id, decision, "
            "resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
            "VALUES (?, ?, ?, ?, 'manual_match', ?, ?, '[]', ?)",
            (revision_id, ordinal, str(ordinal), problem_id, teacher_id, NOW, NOW),
        )
        connection.execute(
            "INSERT INTO problem_revisions "
            "(problem_id, content_revision_id, source_ordinal, source_item, "
            "display_number, title, normalized_title, problem_type, answer_type, "
            "answer_config_json, attempt_policy_json, config_version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 2, 0, '{}', '{}', 1, ?)",
            (
                problem_id,
                revision_id,
                ordinal,
                str(ordinal),
                str(ordinal),
                title,
                title.casefold(),
                NOW,
            ),
        )
        problem_ids.append(problem_id)

    return {
        "student": student_id,
        "other_student": other_student_id,
        "teacher": teacher_id,
        "problem_one": problem_ids[0],
        "problem_two": problem_ids[1],
        "revision": revision_id,
        "unrelated_revision": unrelated_revision_id,
    }


def _insert_thread(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    student_id: int,
    problem_id: int,
    revision_id: int,
    status: str = "open",
    result_id: int | None = None,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO submission_threads "
            "(public_id, student_user_id, problem_id, condition_revision_id, status, "
            "latest_result_id, latest_entry_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                public_id,
                student_id,
                problem_id,
                revision_id,
                status,
                result_id,
                NOW,
                NOW,
                NOW,
            ),
        ).fetchone()[0]
    )


def _insert_entry(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    thread_id: int,
    student_id: int,
    state: str = "draft",
    text: str | None = None,
    idempotency_key: str | None = None,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO submission_entries "
            "(public_id, thread_id, author_kind, author_user_id, channel, entry_kind, "
            "state, text, client_created_at, server_received_at, idempotency_key, "
            "payload_sha256) VALUES (?, ?, 'student', ?, 'pwa', 'submission', ?, ?, "
            "?, ?, ?, ?) RETURNING id",
            (
                public_id,
                thread_id,
                student_id,
                state,
                text,
                NOW,
                NOW,
                idempotency_key,
                "a" * 64 if idempotency_key else None,
            ),
        ).fetchone()[0]
    )


def _insert_asset(
    connection: sqlite3.Connection,
    *,
    ordinal: int,
    namespace: str = "submission",
    media_type: str = "image/webp",
    width: int = 1200,
    height: int = 1600,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO media_assets "
            "(public_id, sha256, storage_namespace, object_key, public_url, "
            "media_type, byte_size, width, height, source_filename, "
            "conversion_version, created_at) VALUES (?, ?, ?, ?, ?, ?, 1024, ?, ?, "
            "'page.jpg', 'written-webp-v1', ?) RETURNING id",
            (
                f"asset-written-{ordinal}",
                f"{ordinal:064x}",
                namespace,
                f"sol_imgs/integration/page-{ordinal}.webp",
                f"https://assets.invalid/page-{ordinal}.webp",
                media_type,
                width,
                height,
                NOW,
            ),
        ).fetchone()[0]
    )


def _insert_attachment(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    entry_id: int,
    asset_id: int,
    ordinal: int,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO submission_attachments "
            "(public_id, entry_id, asset_id, ordinal, client_filename, "
            "upload_status, created_at) VALUES (?, ?, ?, ?, 'page.jpg', 'stored', ?) "
            "RETURNING id",
            (public_id, entry_id, asset_id, ordinal, NOW),
        ).fetchone()[0]
    )


def _insert_result(
    connection: sqlite3.Connection,
    *,
    student_id: int,
    problem_id: int,
    result_type: int,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, "
            "answer, res_type) VALUES (?, ?, 'written-a', 41, NULL, ?, 18, NULL, ?) "
            "RETURNING id",
            (student_id, problem_id, NOW, result_type),
        ).fetchone()[0]
    )


def test_phase5_written_schema_exact_up_down_up_and_additive(tmp_path):
    database_path = tmp_path / "phase5-written-schema.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0046.pwa_test_attempts_idempotency"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
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
        for table in (
            "submission_threads",
            "submission_entries",
            "submission_attachments",
            "submission_material_reassignments",
            "submission_material_reassignment_items",
        ):
            assert connection.execute(f'PRAGMA foreign_key_check("{table}")').fetchall() == []
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


def test_phase5_thread_scope_result_state_version_and_one_active(tmp_path):
    database_path = tmp_path / "phase5-thread-guards.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        context = _insert_context(connection)
        thread_id = _insert_thread(
            connection,
            public_id="thread-written-one",
            student_id=context["student"],
            problem_id=context["problem_one"],
            revision_id=context["revision"],
        )

        with pytest.raises(sqlite3.IntegrityError, match="outside problem scope"):
            _insert_thread(
                connection,
                public_id="thread-wrong-revision",
                student_id=context["student"],
                problem_id=context["problem_two"],
                revision_id=context["unrelated_revision"],
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_thread(
                connection,
                public_id="thread-active-duplicate",
                student_id=context["student"],
                problem_id=context["problem_one"],
                revision_id=context["revision"],
            )

        _insert_thread(
            connection,
            public_id="thread-closed-history",
            student_id=context["student"],
            problem_id=context["problem_one"],
            revision_id=context["revision"],
            status="closed",
        )
        test_result_id = _insert_result(
            connection,
            student_id=context["student"],
            problem_id=context["problem_one"],
            result_type=1,
        )
        with pytest.raises(sqlite3.IntegrityError, match="not written evidence"):
            connection.execute(
                "UPDATE submission_threads SET latest_result_id = ?, "
                "updated_at = ?, version = 2 WHERE id = ?",
                (test_result_id, LATER, thread_id),
            )

        written_result_id = _insert_result(
            connection,
            student_id=context["student"],
            problem_id=context["problem_one"],
            result_type=2,
        )
        with pytest.raises(sqlite3.IntegrityError, match="state transition"):
            connection.execute(
                "UPDATE submission_threads SET status = 'accepted', "
                "latest_result_id = ?, updated_at = ?, version = 2 WHERE id = ?",
                (written_result_id, LATER, thread_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="next version"):
            connection.execute(
                "UPDATE submission_threads SET status = 'awaiting_review', "
                "updated_at = ? WHERE id = ?",
                (LATER, thread_id),
            )
        connection.execute(
            "UPDATE submission_threads SET status = 'awaiting_review', "
            "updated_at = ?, version = 2 WHERE id = ?",
            (LATER, thread_id),
        )
        connection.execute(
            "UPDATE submission_threads SET status = 'accepted', "
            "latest_result_id = ?, updated_at = ?, version = 3 WHERE id = ?",
            (written_result_id, LATER, thread_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
            connection.execute(
                "UPDATE submission_threads SET problem_id = ?, version = 4 WHERE id = ?",
                (context["problem_two"], thread_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            connection.execute("DELETE FROM submission_threads WHERE id = ?", (thread_id,))


def test_phase5_entry_author_idempotency_nonempty_and_lifecycle(tmp_path):
    database_path = tmp_path / "phase5-entry-guards.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        context = _insert_context(connection)
        thread_id = _insert_thread(
            connection,
            public_id="thread-entry-guards",
            student_id=context["student"],
            problem_id=context["problem_one"],
            revision_id=context["revision"],
        )
        entry_id = _insert_entry(
            connection,
            public_id="entry-draft",
            thread_id=thread_id,
            student_id=context["student"],
            idempotency_key="entry-key-one",
        )

        with pytest.raises(sqlite3.IntegrityError, match="outside thread scope"):
            _insert_entry(
                connection,
                public_id="entry-wrong-owner",
                thread_id=thread_id,
                student_id=context["other_student"],
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_entry(
                connection,
                public_id="entry-duplicate-key",
                thread_id=thread_id,
                student_id=context["student"],
                idempotency_key="entry-key-one",
            )
        with pytest.raises(sqlite3.IntegrityError, match="requires text"):
            connection.execute(
                "UPDATE submission_entries SET state = 'submitted', version = 2 "
                "WHERE id = ?",
                (entry_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="next version"):
            connection.execute(
                "UPDATE submission_entries SET text = 'Решение' WHERE id = ?",
                (entry_id,),
            )
        connection.execute(
            "UPDATE submission_entries SET text = 'Решение', "
            "payload_sha256 = ?, version = 2 WHERE id = ?",
            ("b" * 64, entry_id),
        )
        connection.execute(
            "UPDATE submission_entries SET state = 'submitted', version = 3 "
            "WHERE id = ?",
            (entry_id,),
        )
        with pytest.raises(sqlite3.IntegrityError, match="state transition"):
            connection.execute(
                "UPDATE submission_entries SET state = 'uploading', version = 4 "
                "WHERE id = ?",
                (entry_id,),
            )
        connection.execute(
            "UPDATE submission_entries SET state = 'deleted', deleted_at = ?, "
            "version = 4 WHERE id = ?",
            (LATER, entry_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE submission_entries SET text = 'changed', version = 5 WHERE id = ?",
                (entry_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            connection.execute("DELETE FROM submission_entries WHERE id = ?", (entry_id,))


def test_phase5_attachment_contract_limit_reorder_and_lock(tmp_path):
    database_path = tmp_path / "phase5-attachment-guards.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        context = _insert_context(connection)
        thread_id = _insert_thread(
            connection,
            public_id="thread-attachment-guards",
            student_id=context["student"],
            problem_id=context["problem_one"],
            revision_id=context["revision"],
        )
        entry_id = _insert_entry(
            connection,
            public_id="entry-ten-pages",
            thread_id=thread_id,
            student_id=context["student"],
            state="uploading",
        )

        invalid_asset_id = _insert_asset(
            connection,
            ordinal=90,
            namespace="content",
        )
        with pytest.raises(sqlite3.IntegrityError, match="final webp"):
            _insert_attachment(
                connection,
                public_id="attachment-wrong-namespace",
                entry_id=entry_id,
                asset_id=invalid_asset_id,
                ordinal=0,
            )
        oversized_asset_id = _insert_asset(connection, ordinal=91, width=1921)
        with pytest.raises(sqlite3.IntegrityError, match="final webp"):
            _insert_attachment(
                connection,
                public_id="attachment-oversized",
                entry_id=entry_id,
                asset_id=oversized_asset_id,
                ordinal=0,
            )

        attachment_ids: list[int] = []
        for ordinal in range(10):
            asset_id = _insert_asset(connection, ordinal=ordinal + 1)
            attachment_ids.append(
                _insert_attachment(
                    connection,
                    public_id=f"attachment-page-{ordinal + 1}",
                    entry_id=entry_id,
                    asset_id=asset_id,
                    ordinal=ordinal,
                )
            )
        extra_asset_id = _insert_asset(connection, ordinal=92)
        with pytest.raises(sqlite3.IntegrityError, match="at most ten"):
            _insert_attachment(
                connection,
                public_id="attachment-page-eleven",
                entry_id=entry_id,
                asset_id=extra_asset_id,
                ordinal=10,
            )

        # Sparse ordinals make a swap possible without deleting an uploaded
        # object, despite SQLite checking UNIQUE constraints immediately.
        connection.execute(
            "UPDATE submission_attachments SET ordinal = 1000 WHERE id = ?",
            (attachment_ids[0],),
        )
        connection.execute(
            "UPDATE submission_attachments SET ordinal = 0 WHERE id = ?",
            (attachment_ids[1],),
        )
        connection.execute(
            "UPDATE submission_attachments SET ordinal = 1 WHERE id = ?",
            (attachment_ids[0],),
        )
        assert connection.execute(
            "SELECT ordinal FROM submission_attachments WHERE id IN (?, ?) "
            "ORDER BY ordinal",
            (attachment_ids[0], attachment_ids[1]),
        ).fetchall() == [(0,), (1,)]

        lock_thread_id = _insert_thread(
            connection,
            public_id="thread-lock-evidence",
            student_id=context["student"],
            problem_id=context["problem_two"],
            revision_id=context["revision"],
        )
        lock_entry_id = _insert_entry(
            connection,
            public_id="entry-lock-evidence",
            thread_id=lock_thread_id,
            student_id=context["student"],
            state="uploading",
        )
        lock_asset_id = _insert_asset(connection, ordinal=93)
        lock_attachment_id = _insert_attachment(
            connection,
            public_id="attachment-lock-evidence",
            entry_id=lock_entry_id,
            asset_id=lock_asset_id,
            ordinal=0,
        )
        connection.execute(
            "UPDATE submission_entries SET state = 'submitted', version = 2 "
            "WHERE id = ?",
            (lock_entry_id,),
        )
        written_result_id = _insert_result(
            connection,
            student_id=context["student"],
            problem_id=context["problem_two"],
            result_type=2,
        )
        with pytest.raises(sqlite3.IntegrityError, match="outside review evidence"):
            connection.execute(
                "UPDATE submission_attachments SET upload_status = 'locked', "
                "locked_at = ?, locked_by_result_id = ? WHERE id = ?",
                (LATER, written_result_id, lock_attachment_id),
            )
        connection.execute(
            "UPDATE media_assets SET immutable_at = ? WHERE id = ?",
            (LATER, lock_asset_id),
        )
        connection.execute(
            "UPDATE submission_attachments SET upload_status = 'locked', "
            "locked_at = ?, locked_by_result_id = ? WHERE id = ?",
            (LATER, written_result_id, lock_attachment_id),
        )
        connection.execute(
            "UPDATE submission_entries SET state = 'locked', locked_at = ?, "
            "version = 3 WHERE id = ?",
            (LATER, lock_entry_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="media asset is immutable"):
            connection.execute(
                "UPDATE media_assets SET source_filename = 'changed.jpg' WHERE id = ?",
                (lock_asset_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            connection.execute(
                "DELETE FROM submission_attachments WHERE id = ?",
                (lock_attachment_id,),
            )


def test_phase5_material_reassignment_scope_and_append_only(tmp_path):
    database_path = tmp_path / "phase5-reassignment-guards.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        context = _insert_context(connection)
        source_thread_id = _insert_thread(
            connection,
            public_id="thread-reassign-source",
            student_id=context["student"],
            problem_id=context["problem_one"],
            revision_id=context["revision"],
        )
        target_thread_id = _insert_thread(
            connection,
            public_id="thread-reassign-target",
            student_id=context["student"],
            problem_id=context["problem_two"],
            revision_id=context["revision"],
        )
        source_entry_id = _insert_entry(
            connection,
            public_id="entry-reassign-source",
            thread_id=source_thread_id,
            student_id=context["student"],
            state="uploading",
            text="Это решение второй задачи",
        )
        target_entry_id = _insert_entry(
            connection,
            public_id="entry-reassign-target",
            thread_id=target_thread_id,
            student_id=context["student"],
            text="Target text",
        )
        asset_id = _insert_asset(connection, ordinal=94)
        attachment_id = _insert_attachment(
            connection,
            public_id="attachment-reassign-source",
            entry_id=source_entry_id,
            asset_id=asset_id,
            ordinal=0,
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO submission_material_reassignments "
                "(public_id, student_user_id, source_thread_id, target_thread_id, "
                "source_problem_id, target_problem_id, performed_by_user_id, "
                "request_id, created_at) VALUES "
                "('reassignment-wrong-owner', ?, ?, ?, ?, ?, ?, 'wrong-owner', ?)",
                (
                    context["other_student"],
                    source_thread_id,
                    target_thread_id,
                    context["problem_one"],
                    context["problem_two"],
                    context["teacher"],
                    NOW,
                ),
            )

        reassignment_id = int(
            connection.execute(
                "INSERT INTO submission_material_reassignments "
                "(public_id, student_user_id, source_thread_id, target_thread_id, "
                "source_problem_id, target_problem_id, performed_by_user_id, reason, "
                "request_id, created_at) VALUES "
                "('reassignment-valid', ?, ?, ?, ?, ?, ?, 'Неверная задача', "
                "'reassignment-request-one', ?) RETURNING id",
                (
                    context["student"],
                    source_thread_id,
                    target_thread_id,
                    context["problem_one"],
                    context["problem_two"],
                    context["teacher"],
                    NOW,
                ),
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO submission_material_reassignment_items "
            "(reassignment_id, source_entry_id, item_kind, attachment_id, ordinal) "
            "VALUES (?, ?, 'entry_text', NULL, 0)",
            (reassignment_id, source_entry_id),
        )
        connection.execute(
            "INSERT INTO submission_material_reassignment_items "
            "(reassignment_id, source_entry_id, item_kind, attachment_id, ordinal) "
            "VALUES (?, ?, 'attachment', ?, 1)",
            (reassignment_id, source_entry_id, attachment_id),
        )

        with pytest.raises(sqlite3.IntegrityError, match="outside source scope"):
            connection.execute(
                "INSERT INTO submission_material_reassignment_items "
                "(reassignment_id, source_entry_id, item_kind, attachment_id, ordinal) "
                "VALUES (?, ?, 'entry_text', NULL, 2)",
                (reassignment_id, target_entry_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="outside source scope"):
            connection.execute(
                "INSERT INTO submission_material_reassignment_items "
                "(reassignment_id, source_entry_id, item_kind, attachment_id, ordinal) "
                "VALUES (?, ?, 'attachment', ?, 3)",
                (reassignment_id, target_entry_id, attachment_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE submission_material_reassignments SET reason = 'changed' "
                "WHERE id = ?",
                (reassignment_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            connection.execute(
                "DELETE FROM submission_material_reassignment_items "
                "WHERE reassignment_id = ? AND ordinal = 0",
                (reassignment_id,),
            )

        assert connection.execute(
            "SELECT item_kind, attachment_id FROM "
            "submission_material_reassignment_items WHERE reassignment_id = ? "
            "ORDER BY ordinal",
            (reassignment_id,),
        ).fetchall() == [("entry_text", None), ("attachment", attachment_id)]
        for table in (
            "submission_threads",
            "submission_entries",
            "submission_attachments",
            "submission_material_reassignments",
            "submission_material_reassignment_items",
        ):
            assert connection.execute(
                f'PRAGMA foreign_key_check("{table}")'
            ).fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
