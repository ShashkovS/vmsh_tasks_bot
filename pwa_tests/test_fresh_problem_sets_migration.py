"""MATCH-04: reversible before use, preserve historical labels after use."""

import sqlite3

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT, apply_schema_migrations


def _rollback(path):
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT)).filter(
        lambda migration: migration.id == "0109.pwa_fresh_problem_sets"
    )
    with yoyo.get_backend(f"sqlite:///{path}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(migrations))


def test_fresh_sets_migration_is_reversible_before_use(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    apply_schema_migrations(path)
    _rollback(path)
    with sqlite3.connect(path) as connection:
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='problem_catalog'"
        ).fetchone()
    apply_schema_migrations(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM active_problems"
        ).fetchone() == (0,)


def test_fresh_sets_rollback_preserves_used_slots(tmp_path):
    path = tmp_path / "used.sqlite3"
    apply_schema_migrations(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO problems(id,lesson,prob,item,title,prob_text,prob_type) "
            "VALUES (1,1,1,'__fresh__slot','Task','Text',2)"
        )
        connection.execute(
            "INSERT INTO content_problem_slots(problem_id,display_item,created_at) "
            "VALUES (1,'а','2026-10-03T00:00:00Z')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        _rollback(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT item FROM problem_catalog WHERE id=1"
        ).fetchone() == ("а",)
        assert connection.execute(
            "SELECT item FROM problems WHERE id=1"
        ).fetchone() == ("__fresh__slot",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
