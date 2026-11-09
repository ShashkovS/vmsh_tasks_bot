"""Restore one SQLite backup into an isolated Phase 11 rehearsal database."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from db_methods.pwa.migrations import apply_schema_migrations
from vmshpwa.scripts.report_io import atomic_write_text


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REHEARSAL_ROOT = REPOSITORY_ROOT / ".runtime" / "phase11-rehearsal" / "restores"
LEGACY_TABLES = (
    "users",
    "lessons",
    "problems",
    "results",
    "written_tasks_discussions",
)


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _legacy_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in LEGACY_TABLES
    }


def rehearse_restore(source: Path, target: Path, recorded_at: str) -> dict[str, object]:
    """Copy, migrate and verify a database without changing the source."""

    if not source.is_file():
        raise ValueError("Source database does not exist")
    if not _inside(target, REHEARSAL_ROOT):
        raise ValueError("Restore target must be below the Phase 11 restore directory")
    if target.exists():
        raise ValueError("Restore target already exists")
    if source.resolve() == target.resolve():
        raise ValueError("Source and restore target must be different files")

    target.parent.mkdir(parents=True, exist_ok=True)
    total_started = time.monotonic()
    copy_started = total_started
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_connection:
        source_connection.execute("BEGIN")
        source_counts = _legacy_counts(source_connection)
        with sqlite3.connect(target) as target_connection:
            source_connection.backup(target_connection)
    copy_seconds = time.monotonic() - copy_started
    target.chmod(0o600)

    with sqlite3.connect(target) as restored_connection:
        restored_before_migration = _legacy_counts(restored_connection)
    if restored_before_migration != source_counts:
        raise RuntimeError("Restored legacy row counts differ from the backup snapshot")

    migration_started = time.monotonic()
    migration_state = apply_schema_migrations(target)
    migration_seconds = time.monotonic() - migration_started

    verification_started = time.monotonic()
    with sqlite3.connect(target) as restored_connection:
        restored_after_migration = _legacy_counts(restored_connection)
        integrity_check = str(
            restored_connection.execute("PRAGMA integrity_check").fetchone()[0]
        )
        journal_mode = str(
            restored_connection.execute("PRAGMA journal_mode").fetchone()[0]
        )
    verification_seconds = time.monotonic() - verification_started

    if restored_after_migration != source_counts:
        raise RuntimeError("Migrations changed legacy row counts during restore")
    if integrity_check != "ok":
        raise RuntimeError(f"Restored SQLite integrity check failed: {integrity_check}")
    if not migration_state.is_current:
        raise RuntimeError("Restored SQLite schema is not current")

    return {
        "schemaVersion": 1,
        "operation": "phase11-sqlite-restore-rehearsal",
        "recordedAt": recorded_at,
        "legacyRowCounts": source_counts,
        "legacyRowCountParity": True,
        "appliedMigrationCount": len(migration_state.applied),
        "schemaCurrent": True,
        "integrityCheck": integrity_check,
        "journalMode": journal_mode,
        "databaseBytes": target.stat().st_size,
        "copySeconds": round(copy_seconds, 3),
        "migrationSeconds": round(migration_seconds, 3),
        "verificationSeconds": round(verification_seconds, 3),
        "totalSeconds": round(time.monotonic() - total_started, 3),
        "sourceDatabaseRowsUpdated": 0,
        "reportContainsPersonalData": False,
        "rpoMeasured": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--recorded-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    arguments = parser.parse_args()
    report = rehearse_restore(
        arguments.source, arguments.target, arguments.recorded_at
    )
    atomic_write_text(
        arguments.report,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
