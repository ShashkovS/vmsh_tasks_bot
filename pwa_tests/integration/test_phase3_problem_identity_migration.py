"""Exact migration and legacy-write compatibility for problem public IDs."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT


MIGRATION_ID = "0044.pwa_problem_identity"
PUBLIC_ID = re.compile(r"problem-[0-9a-f]{32}")
EXPECTED_OBJECTS = {
    "problems_public_id_uq",
    "problems_public_id_fill_after_insert",
    "problems_public_id_immutable",
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


def _columns(connection: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in connection.execute("PRAGMA table_info(problems)")}


def _objects(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
        )
    }


def _insert_legacy_problem(
    connection: sqlite3.Connection, *, number: int, title: str
) -> int:
    return int(
        connection.execute(
            "INSERT INTO problems "
            "(group_id, lesson, prob, item, title, prob_text, prob_type, synonyms) "
            "VALUES ('н', 41, ?, '', ?, '', 2, '') RETURNING id",
            (number, title),
        ).fetchone()[0]
    )


def test_phase3_problem_identity_exact_up_down_up_and_legacy_writes(tmp_path):
    database_path = tmp_path / "phase3-problem-identity.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0043.pwa_lesson_window_audit"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)

    with sqlite3.connect(database_path) as connection:
        before_columns = _columns(connection)
        before_objects = _objects(connection)
        original_id = _insert_legacy_problem(
            connection, number=1, title="Задача до миграции"
        )

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert "public_id" in _columns(connection)
        assert EXPECTED_OBJECTS <= _objects(connection)
        original_public_id = connection.execute(
            "SELECT public_id FROM problems WHERE id = ?", (original_id,)
        ).fetchone()[0]
        assert PUBLIC_ID.fullmatch(original_public_id)

        legacy_id = _insert_legacy_problem(
            connection, number=2, title="Новая задача из legacy-бота"
        )
        legacy_public_id = connection.execute(
            "SELECT public_id FROM problems WHERE id = ?", (legacy_id,)
        ).fetchone()[0]
        assert PUBLIC_ID.fullmatch(legacy_public_id)
        assert legacy_public_id != original_public_id

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE problems SET public_id = 'problem-replacement' WHERE id = ?",
                (legacy_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, synonyms, public_id) "
                "VALUES ('н', 41, 3, '', 'Duplicate', '', 2, '', ?)",
                (original_public_id,),
            )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _columns(connection) == before_columns
        assert _objects(connection) == before_objects
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        public_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT public_id FROM problems ORDER BY id"
            ).fetchall()
        ]
        assert len(public_ids) == len(set(public_ids))
        assert all(PUBLIC_ID.fullmatch(value) for value in public_ids)
        assert EXPECTED_OBJECTS <= _objects(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
