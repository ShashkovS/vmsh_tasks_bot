"""Current schema cache keeps real migrations and isolated test data."""

import sqlite3
import subprocess
import sys

import pytest

from db_methods.pwa import require_current_schema
from pwa_tests import sqlite_template as templates


def test_copies_preserve_schema_wal_history_and_isolate_rows(tmp_path):
    cache = tmp_path / "cache"
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    state = templates.create_test_database(first, cache_root=cache)
    templates.create_test_database(second, cache_root=cache)
    assert state.is_current
    assert require_current_schema(second) == state
    with sqlite3.connect(first) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        db.execute("INSERT INTO kv(key,value) VALUES('isolation-probe','first')")
    with sqlite3.connect(second) as db:
        assert (
            db.execute("SELECT value FROM kv WHERE key='isolation-probe'").fetchone()
            is None
        )
    assert first.stat().st_mode & 0o777 == 0o600


def test_cache_changes_when_migration_changes_or_is_added(tmp_path):
    migration = tmp_path / "0001.example.sql"
    migration.write_text("CREATE TABLE probe(id);")
    original = templates.schema_cache_key(tmp_path)
    migration.write_text("CREATE TABLE probe(id INTEGER);")
    changed = templates.schema_cache_key(tmp_path)
    assert original != changed
    (tmp_path / "0002.example.sql").write_text("ALTER TABLE probe ADD COLUMN value;")
    assert templates.schema_cache_key(tmp_path) != changed


def test_repeated_copies_migrate_once_and_corrupt_cache_is_rebuilt(
    tmp_path, monkeypatch
):
    calls = []
    migrate = templates.apply_schema_migrations
    monkeypatch.setattr(
        templates,
        "apply_schema_migrations",
        lambda path: calls.append(path) or migrate(path),
    )
    cache = tmp_path / "cache"
    templates.create_test_database(tmp_path / "one.db", cache_root=cache)
    templates.create_test_database(tmp_path / "two.db", cache_root=cache)
    assert len(calls) == 1
    template = next(cache.glob("*.sqlite3"))
    template.chmod(0o600)
    template.write_bytes(b"corrupt")
    templates._current_template.cache_clear()
    templates.create_test_database(tmp_path / "three.db", cache_root=cache)
    assert len(calls) == 2
    assert require_current_schema(tmp_path / "three.db").is_current


def test_existing_database_and_symlink_are_never_overwritten(tmp_path):
    existing = tmp_path / "existing.db"
    existing.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        templates.create_test_database(existing)
    link = tmp_path / "link.db"
    link.symlink_to(existing)
    with pytest.raises(FileExistsError):
        templates.create_test_database(link)
    assert existing.read_bytes() == b"keep"


def test_workers_share_only_template_and_copy_into_separate_files(tmp_path):
    script = (
        "from pathlib import Path; from pwa_tests.sqlite_template import create_test_database; "
        "import sys; create_test_database(Path(sys.argv[1]), cache_root=Path(sys.argv[2]))"
    )
    workers = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                script,
                str(tmp_path / f"worker-{i}.db"),
                str(tmp_path / "cache"),
            ],
            stdout=subprocess.DEVNULL,
        )
        for i in range(3)
    ]
    assert [worker.wait(timeout=30) for worker in workers] == [0, 0, 0]
    assert len(list((tmp_path / "cache").glob("*.sqlite3"))) == 1
    for i in range(3):
        assert require_current_schema(tmp_path / f"worker-{i}.db").is_current
