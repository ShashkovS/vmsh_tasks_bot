"""Exact Phase-6 queue rebuild, guards and legacy-write compatibility."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0051.pwa_review_queue_leases"
PUBLIC_ID = re.compile(r"wq-[1-9][0-9]*")
NOW = "2026-10-04T12:00:00.000000Z"


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


def _seed_legacy_queue(connection: sqlite3.Connection) -> tuple[int, int, int]:
    student_id = -951_001
    teacher_id = -951_002
    connection.executemany(
        "INSERT INTO users (id, type, name, surname) VALUES (?, ?, ?, 'Queue')",
        (
            (student_id, 1, "Student"),
            (teacher_id, 2, "Teacher"),
        ),
    )
    problem_id = int(
        connection.execute(
            "INSERT INTO problems "
            "(group_id, lesson, prob, item, title, prob_text, prob_type, synonyms) "
            "VALUES ('queue-a', 41, 1, '', 'Queue problem', '', 2, '') "
            "RETURNING id"
        ).fetchone()[0]
    )
    queue_id = int(
        connection.execute(
            "INSERT INTO written_tasks_queue "
            "(ts, student_id, problem_id, cur_status, teacher_ts, teacher_id) "
            "VALUES (?, ?, ?, 1, ?, ?) RETURNING id",
            (NOW, student_id, problem_id, NOW, teacher_id),
        ).fetchone()[0]
    )
    return queue_id, problem_id, student_id


def _columns(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row[1]): str(row[2]).casefold()
        for row in connection.execute("PRAGMA table_info(written_tasks_queue)")
    }


def test_review_queue_rebuild_up_down_up_preserves_rows_and_legacy_writes(tmp_path):
    database_path = tmp_path / "phase6-review-queue.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0050.pwa_submission_entry_replacements"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)

    with sqlite3.connect(database_path) as connection:
        queue_id, problem_id, student_id = _seed_legacy_queue(connection)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        columns = _columns(connection)
        assert columns["teacher_id"] == "integer"
        assert {
            "claim_token",
            "claimed_at",
            "lease_expires_at",
            "lease_version",
            "updated_at",
        } <= columns.keys()
        row = connection.execute(
            "SELECT * FROM written_tasks_queue WHERE id = ?", (queue_id,)
        ).fetchone()
        assert row is not None
        assert PUBLIC_ID.fullmatch(str(row[1]))
        assert row[7] == -951_002
        assert row[8:11] == (None, None, None)
        assert row[11] == 0

        legacy_problem_id = int(
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, synonyms) "
                "VALUES ('queue-a', 41, 2, '', 'Legacy insert', '', 2, '') "
                "RETURNING id"
            ).fetchone()[0]
        )
        legacy_queue_id = int(
            connection.execute(
                "INSERT INTO written_tasks_queue "
                "(ts, student_id, problem_id, cur_status) VALUES (?, ?, ?, 0) "
                "RETURNING id",
                ("2026-10-04T12:01:00.000000Z", student_id, legacy_problem_id),
            ).fetchone()[0]
        )
        legacy_public_id = connection.execute(
            "SELECT public_id FROM written_tasks_queue WHERE id = ?", (legacy_queue_id,)
        ).fetchone()[0]
        assert PUBLIC_ID.fullmatch(str(legacy_public_id))
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert set(_columns(connection)) == {
            "id",
            "ts",
            "student_id",
            "problem_id",
            "cur_status",
            "teacher_ts",
            "teacher_id",
        }
        assert connection.execute(
            "SELECT count(*) FROM written_tasks_queue"
        ).fetchone() == (2,)
        connection.execute(
            "UPDATE written_tasks_queue SET cur_status = 0 WHERE id = ?", (queue_id,)
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert PUBLIC_ID.fullmatch(
            str(
                connection.execute(
                    "SELECT public_id FROM written_tasks_queue WHERE id = ?",
                    (queue_id,),
                ).fetchone()[0]
            )
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_review_queue_rebuild_rejects_non_integer_teacher_identity(tmp_path):
    database_path = tmp_path / "phase6-review-queue-invalid-teacher.sqlite3"
    migration_ids = {item.id for item in _migrations() if item.id != MIGRATION_ID}
    _apply(database_path, migration_ids)

    with sqlite3.connect(database_path) as connection:
        _queue_id, problem_id, student_id = _seed_legacy_queue(connection)
        connection.execute(
            "UPDATE written_tasks_queue SET teacher_id = '2026-10-04 12:00:00' "
            "WHERE student_id = ? AND problem_id = ?",
            (student_id, problem_id),
        )

    with pytest.raises(sqlite3.IntegrityError):
        _apply(database_path, {MIGRATION_ID})

    with sqlite3.connect(database_path) as connection:
        assert "claim_token" not in _columns(connection)
        assert connection.execute(
            "SELECT teacher_id FROM written_tasks_queue WHERE student_id = ?",
            (student_id,),
        ).fetchone() == ("2026-10-04 12:00:00",)
