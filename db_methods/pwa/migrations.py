"""Explicit migration commands and runtime schema checks for the PWA contour."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import yoyo


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_ROOT = REPOSITORY_ROOT / "migrations"
BASELINE_ID = "0111.current_schema"
MERGED_MIGRATION_BOUNDARY = 111


class SchemaMismatchError(RuntimeError):
    """Raised when a runtime database is not at the repository migration head."""


@dataclass(frozen=True, slots=True)
class MigrationState:
    expected: tuple[tuple[str, str], ...]
    applied: tuple[tuple[str, str], ...]
    missing: tuple[str, ...]
    unexpected_current_generation: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    baseline_adoptable: bool = False

    @property
    def is_current(self) -> bool:
        return not (
            self.missing or self.unexpected_current_generation or self.hash_mismatches
        )


def _expected_migrations() -> tuple[tuple[str, str], ...]:
    return tuple(
        (migration.id, migration.hash)
        for migration in yoyo.read_migrations(str(MIGRATIONS_ROOT))
    )


def _migration_number(migration_id: str) -> int | None:
    prefix = migration_id.partition(".")[0]
    return int(prefix) if prefix.isdigit() else None


def _read_applied_migrations(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, str], ...]:
    table = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = '_yoyo_migration'"
    ).fetchone()
    if table is None:
        return ()
    return tuple(
        connection.execute(
            "SELECT migration_id, migration_hash FROM _yoyo_migration "
            "ORDER BY migration_id"
        ).fetchall()
    )


def _can_adopt_baseline(
    connection: sqlite3.Connection | None, applied: dict[str, str]
) -> bool:
    if connection is None or BASELINE_ID in applied:
        return False
    metadata = {}
    for line in (MIGRATIONS_ROOT / f"{BASELINE_ID}.sql").read_text().splitlines()[:5]:
        key, separator, value = line.removeprefix("-- ").partition(": ")
        if separator:
            metadata[key] = value
    previous_id, previous_hash = metadata["Previous head"].split(":")
    if applied.get(previous_id) != previous_hash:
        return False
    # Only an exact current schema may be adopted; no legacy SQL is replayed.
    # Decision and rollout contract: vmshpwa/docs/schema-baseline-20261004.md.
    from .schema_inventory import product_ddl_sha256

    return product_ddl_sha256(connection) == metadata["Product DDL SHA256"]


def inspect_connection_schema(connection: sqlite3.Connection | None) -> MigrationState:
    """Inspect schema bookkeeping in the caller's read transaction."""

    expected = _expected_migrations()
    applied = _read_applied_migrations(connection) if connection is not None else ()
    expected_by_id = dict(expected)
    applied_by_id = dict(applied)
    minimum_current_number = min(
        number
        for migration_id, _hash in expected
        if (number := _migration_number(migration_id)) is not None
    )

    adoptable = _can_adopt_baseline(connection, applied_by_id)
    missing = tuple(
        migration_id
        for migration_id, _hash in expected
        if migration_id not in applied_by_id
        and not (migration_id == BASELINE_ID and adoptable)
    )
    hash_mismatches = tuple(
        migration_id
        for migration_id, expected_hash in expected
        if migration_id in applied_by_id
        and applied_by_id[migration_id] != expected_hash
    )
    # Production databases retain pre-baseline history. Unknown IDs at or after
    # the current generation instead
    # mean that this checkout is older than the database and must fail closed.
    # Decision: vmshpwa/dev/development-plan/00-engineering-contract.md,
    # "SQLite, transactions and shared domain logic".
    unexpected = tuple(
        migration_id
        for migration_id, _hash in applied
        if migration_id not in expected_by_id
        and (
            (number := _migration_number(migration_id)) is None
            or number >= minimum_current_number
        )
    )
    return MigrationState(
        expected=expected,
        applied=applied,
        missing=missing,
        unexpected_current_generation=unexpected,
        hash_mismatches=hash_mismatches,
        baseline_adoptable=adoptable,
    )


def inspect_migration_state(database_path: str | Path) -> MigrationState:
    """Compare an existing database with this checkout without mutating it."""

    path = Path(database_path)
    if not path.is_file():
        return inspect_connection_schema(None)
    with closing(
        sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    ) as connection:
        connection.execute("BEGIN")
        return inspect_connection_schema(connection)


def require_current_schema(database_path: str | Path) -> MigrationState:
    """Fail fast when startup sees missing, changed, or future migrations."""

    state = inspect_migration_state(database_path)
    if state.is_current:
        return state
    details = []
    if state.missing:
        details.append(f"missing={','.join(state.missing)}")
    if state.unexpected_current_generation:
        details.append("unexpected=" + ",".join(state.unexpected_current_generation))
    if state.hash_mismatches:
        details.append(f"changed={','.join(state.hash_mismatches)}")
    raise SchemaMismatchError(
        "SQLite schema is not at the repository migration head; "
        "run the explicit migration command (" + "; ".join(details) + ")"
    )


def apply_schema_migrations(database_path: str | Path) -> MigrationState:
    """Apply repository migrations under yoyo's inter-process migration lock."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT))
    with yoyo.get_backend(f"sqlite:///{path.resolve()}") as backend:
        with backend.lock():
            state = inspect_migration_state(path)
            if state.hash_mismatches or state.unexpected_current_generation:
                require_current_schema(path)
            if BASELINE_ID not in dict(state.applied):
                if state.baseline_adoptable:
                    backend.mark_migrations(
                        [item for item in migrations if item.id == BASELINE_ID]
                    )
                else:
                    with closing(sqlite3.connect(path)) as connection:
                        has_product_schema = connection.execute(
                            "SELECT 1 FROM sqlite_schema WHERE sql IS NOT NULL "
                            "AND name NOT LIKE 'sqlite_%' "
                            "AND name NOT IN ('_yoyo_log', '_yoyo_migration', "
                            "'_yoyo_version', 'yoyo_lock') LIMIT 1"
                        ).fetchone()
                    if has_product_schema:
                        raise SchemaMismatchError(
                            "Existing SQLite schema cannot adopt the current baseline"
                        )
            backend.apply_migrations(backend.to_apply(migrations))
    # WAL is a persistent database property, so the maintenance command owns
    # this mutation. Runtime startup only verifies it. See ADR 0002.
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if str(journal_mode).casefold() != "wal":
            raise RuntimeError(f"Could not enable SQLite WAL mode: {journal_mode}")
    return require_current_schema(path)
