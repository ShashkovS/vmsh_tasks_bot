"""Explicit migration commands and runtime schema checks for the PWA contour."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import yoyo


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_ROOT = REPOSITORY_ROOT / "migrations"


class SchemaMismatchError(RuntimeError):
    """Raised when a runtime database is not at the repository migration head."""


@dataclass(frozen=True, slots=True)
class MigrationState:
    expected: tuple[tuple[str, str], ...]
    applied: tuple[tuple[str, str], ...]
    missing: tuple[str, ...]
    unexpected_current_generation: tuple[str, ...]
    hash_mismatches: tuple[str, ...]

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


def _read_applied_migrations(database_path: Path) -> tuple[tuple[str, str], ...]:
    if not database_path.is_file():
        return ()
    with closing(
        sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    ) as connection:
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


def inspect_migration_state(database_path: str | Path) -> MigrationState:
    """Compare an existing database with this checkout without mutating it."""

    expected = _expected_migrations()
    applied = _read_applied_migrations(Path(database_path))
    expected_by_id = dict(expected)
    applied_by_id = dict(applied)
    minimum_current_number = min(
        number
        for migration_id, _hash in expected
        if (number := _migration_number(migration_id)) is not None
    )

    missing = tuple(
        migration_id
        for migration_id, _hash in expected
        if migration_id not in applied_by_id
    )
    hash_mismatches = tuple(
        migration_id
        for migration_id, expected_hash in expected
        if migration_id in applied_by_id
        and applied_by_id[migration_id] != expected_hash
    )
    # Production databases legitimately retain pre-0030 history alongside the
    # merged baseline. Unknown IDs at or after the current generation instead
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
    )


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
            backend.apply_migrations(backend.to_apply(migrations))
    # WAL is a persistent database property, so the maintenance command owns
    # this mutation. Runtime startup only verifies it. See ADR 0002.
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if str(journal_mode).casefold() != "wal":
            raise RuntimeError(f"Could not enable SQLite WAL mode: {journal_mode}")
    return require_current_schema(path)
