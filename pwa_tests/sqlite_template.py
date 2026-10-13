"""Independent current-schema copies for tests, built from the single baseline.

See reports/check-optimization-20261003/README.md and testing-strategy.md.
Only repository migration data enters this cache; live DBs are never read.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from db_methods.pwa.migrations import (
    MIGRATIONS_ROOT,
    MigrationState,
    apply_schema_migrations,
    require_current_schema,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / ".runtime/vmshpwa/test-cache/schema"


def schema_cache_key(migrations_root: Path = MIGRATIONS_ROOT) -> str:
    """Invalidate on migration contents, the migrator, dependencies or SQLite."""

    digest = hashlib.sha256()
    digest.update(f"schema-template-v1:{sys.version}:{sqlite3.sqlite_version}".encode())
    for path in (ROOT / "db_methods/pwa/migrations.py", ROOT / "uv.lock"):
        digest.update(path.read_bytes())
    for path in sorted(migrations_root.iterdir()):
        if path.is_file() and path.suffix in {".sql", ".py"}:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _process_schema_key() -> str:
    # A pytest process collects one checkout. A new run computes a new key;
    # ordinary tests never repeatedly build the schema.
    return schema_cache_key()


def _valid_template(database: Path, manifest: Path, key: str) -> bool:
    if database.is_symlink() or manifest.is_symlink():
        raise ValueError("A test DB template must not be a symlink")
    try:
        record = json.loads(manifest.read_text())
        with database.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return digest == record["sha256"] and record["key"] == key
    except OSError, ValueError, KeyError:
        return False


@lru_cache(maxsize=16)
def _current_template(cache_root: Path, key: str) -> tuple[Path, MigrationState, str]:
    if any(path.is_symlink() for path in (cache_root, *cache_root.parents)):
        raise ValueError("A test DB cache must not contain symlinks")
    cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    database = cache_root / f"{key}.sqlite3"
    manifest = cache_root / f"{key}.json"
    # Unlike the E2E suite lock, workers wait for this short, shared build.
    # Their test data lives in separate writable copies, never this file.
    with (cache_root / "template.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not _valid_template(database, manifest, key):
            descriptor, name = tempfile.mkstemp(dir=cache_root, suffix=".sqlite3")
            os.close(descriptor)
            temporary = Path(name)
            try:
                apply_schema_migrations(temporary)
                with closing(sqlite3.connect(temporary)) as connection:
                    if (
                        connection.execute("PRAGMA integrity_check").fetchone()[0]
                        != "ok"
                    ):
                        raise RuntimeError("Invalid migrated test DB template")
                    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                os.replace(temporary, database)
                database.chmod(0o400)
                with database.open("rb") as stream:
                    sha = hashlib.file_digest(stream, "sha256").hexdigest()
                manifest.write_text(json.dumps({"sha256": sha, "key": key}) + "\n")
            finally:
                for path in (
                    temporary,
                    Path(f"{temporary}-wal"),
                    Path(f"{temporary}-shm"),
                ):
                    path.unlink(missing_ok=True)
        state = require_current_schema(database)
        record = json.loads(manifest.read_text())
    return database, state, record["sha256"]


def create_test_database(
    database_path: str | Path, *, cache_root: Path | None = None
) -> MigrationState:
    """Create an independent writable DB with WAL, seed rows and yoyo history."""

    path = Path(database_path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"Test DB already exists: {path}")
    if os.environ.get("VMSH_TEST_DB_TEMPLATE") == "0":
        return apply_schema_migrations(path)
    template, state, expected_hash = _current_template(
        cache_root or CACHE_ROOT, _process_schema_key()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with template.open("rb") as source, path.open("xb") as target:
        path.chmod(0o600)
        while block := source.read(1024 * 1024):
            target.write(block)
            digest.update(block)
    if digest.hexdigest() != expected_hash:
        path.unlink()
        _current_template.cache_clear()
        raise RuntimeError("Test schema cache changed; rerun to rebuild it")
    return state
