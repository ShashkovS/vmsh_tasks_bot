"""Atomically build the deterministic ``baseline-v1`` PWA runtime database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from db_methods.pwa import (
    PwaConnectionFactory,
    apply_schema_migrations,
    maintenance_database_lock,
)
from pwa_tests.fixtures.seed import load_baseline_v1
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_ROOT = REPOSITORY_ROOT / "db"
DEFAULT_MEDIA_ROOT = REPOSITORY_ROOT / ".runtime" / "vmshpwa"
AUTHORITATIVE_DATABASE = REPOSITORY_ROOT / "db" / "vmsh.db"

PROFILE_LAYOUT = {
    "pwa-human": ("human", "vmshpwa_dev.sqlite3"),
    "pwa-agent": ("agent", "vmshpwa_agent.sqlite3"),
    "pwa-e2e": ("e2e", "vmshpwa_e2e.sqlite3"),
}

# Phase-1 ownership rows precede the legacy graph; actor references in the
# course row intentionally stay NULL so the course can be inserted before the
# groups/users cycle.  This is synthetic fixture wiring, not the production
# backfill. See development-plan/05-phase-1-auth.md.
INSERT_ORDER = (
    "seasons",
    "courses",
    "groups",
    "users",
    "auth_accounts",
    "family_student_links",
    "auth_sessions",
    "auth_refresh_consumed_secrets",
    "auth_events",
    "auth_throttle_buckets",
    "course_enrollments",
    "course_group_access",
    "course_enrollment_events",
    "staff_scopes",
    "student_strength",
    "lessons",
    "problems",
    "states",
    "user_changes_log",
    "written_tasks_discussions",
    "written_tasks_queue",
    "results",
)

CANONICAL_ORDER_BY = {
    "seasons": "id",
    "courses": "id",
    "groups": "group_id",
    "users": "id",
    "auth_accounts": "id",
    "family_student_links": "family_account_id, student_user_id",
    "auth_sessions": "id",
    "auth_refresh_consumed_secrets": "session_id, refresh_secret_hash",
    "auth_events": "id",
    "auth_throttle_buckets": ("audience, bucket_kind, bucket_key_hmac, key_version"),
    "course_enrollments": "id",
    "course_group_access": "enrollment_id, group_id, valid_from",
    "course_enrollment_events": "id",
    "staff_scopes": "id",
    "student_strength": "student_id",
    "lessons": "id",
    "problems": "id",
    "states": "user_id",
    "user_changes_log": "ts, user_id, change_type",
    "written_tasks_discussions": "id",
    "written_tasks_queue": "id",
    "results": "id",
    "kv": "key",
    "kv_logins": "id",
}

EXPECTED_LEGACY_REACTION_FOREIGN_KEYS = {
    ("result_id", "results", "id"),
    (
        "zoom_conversation_id",
        "zoom_conversation",
        "zoom_conversation_id",
    ),
    ("reaction_id", "reaction_enum", "reaction_id"),
    ("reaction_type_id", "reaction_type_enum", "reaction_type_id"),
}


@dataclass(frozen=True, slots=True)
class SeedReport:
    database_path: Path
    fixture: str
    canonical_digest: str
    row_counts: Mapping[str, int]
    foreign_key_exclusions: tuple[str, ...]
    durability_confirmed: bool
    durability_warning: str | None


def _configured_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise RuntimeError(f"PWA seed refuses a symlink {label}: {path}")


def _require_seed_paths(
    runtime_config: PwaMaintenanceConfig,
    *,
    database_root: Path,
    media_root: Path,
) -> tuple[Path, Path]:
    require_pwa_maintenance_profile(runtime_config)
    profile = runtime_config.runtime_profile
    if profile not in PROFILE_LAYOUT:
        raise RuntimeError(
            "PWA seed supports only pwa-human, pwa-agent and pwa-e2e profiles"
        )
    if getattr(runtime_config, "production_mode", False):
        raise RuntimeError("PWA seed is forbidden in production mode")

    expected_instance, expected_filename = PROFILE_LAYOUT[profile]
    if runtime_config.pwa_instance != expected_instance:
        raise RuntimeError(
            f"PWA seed profile {profile} requires instance {expected_instance!r}"
        )

    database_root = database_root.absolute()
    media_root = media_root.absolute()
    database_path = _configured_path(runtime_config.db_filename).absolute()
    configured_media_path = _configured_path(runtime_config.pwa_media_root).absolute()
    expected_database = database_root / expected_filename
    expected_media = media_root / expected_instance

    _reject_symlink(database_root, label="database root")
    _reject_symlink(media_root, label="media root")
    _reject_symlink(database_path.parent, label="database parent")
    _reject_symlink(database_path, label="database target")
    _reject_symlink(configured_media_path.parent, label="media parent")
    _reject_symlink(configured_media_path, label="media target")

    if database_path == AUTHORITATIVE_DATABASE.absolute():
        raise RuntimeError("PWA seed must never target the authoritative db/vmsh.db")
    if database_path.exists() and AUTHORITATIVE_DATABASE.exists():
        try:
            same_database = database_path.samefile(AUTHORITATIVE_DATABASE)
        except OSError:
            same_database = False
        if same_database:
            raise RuntimeError(
                "PWA seed must never target a hard link to authoritative db/vmsh.db"
            )
    if database_path != expected_database:
        raise RuntimeError(
            f"Unknown PWA seed database target for {profile}: {database_path}"
        )
    if configured_media_path != expected_media:
        raise RuntimeError(
            f"Unknown PWA seed media target for {profile}: {configured_media_path}"
        )
    return database_path, configured_media_path


def _insert_rows(
    connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    columns = tuple(rows[0])
    if any(tuple(row) != columns for row in rows):
        raise ValueError(f"All {table} fixture rows must use the same column order")
    column_sql = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _column in columns)
    connection.executemany(
        f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders})',
        [tuple(row[column] for column in columns) for row in rows],
    )


def _validate_fixture(payload: dict[str, Any]) -> None:
    tables = payload.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(INSERT_ORDER):
        raise ValueError("baseline-v1 must contain exactly the Phase-1 seed tables")
    if payload.get("schemaVersion") != 3:
        raise ValueError("baseline-v1 must use Phase-3 schemaVersion 3")

    users = tables["users"]
    if any(user["token"] is not None or user["chat_id"] is not None for user in users):
        raise ValueError("baseline-v1 users must not contain tokens or Telegram IDs")
    if any(
        url and not url.startswith("https://example.invalid/")
        for group in tables["groups"]
        if (url := group["conditions_url"])
    ):
        raise ValueError("baseline-v1 may use only example.invalid URLs")

    user_ids = {user["id"] for user in users}
    user_public_ids = [user.get("public_id") for user in users]
    if any(
        not isinstance(public_id, str) or not public_id for public_id in user_public_ids
    ):
        raise ValueError("Every fixture user must have an opaque public ID")
    if len(user_public_ids) != len(set(user_public_ids)):
        raise ValueError("Fixture user public IDs must be unique")
    problem_public_ids = [problem.get("public_id") for problem in tables["problems"]]
    if any(
        not isinstance(public_id, str) or not public_id
        for public_id in problem_public_ids
    ):
        raise ValueError("Every fixture problem must have an opaque public ID")
    if len(problem_public_ids) != len(set(problem_public_ids)):
        raise ValueError("Fixture problem public IDs must be unique")
    seasons = {season["id"] for season in tables["seasons"]}
    courses = {course["id"]: course for course in tables["courses"]}
    if any(course["season_id"] not in seasons for course in courses.values()):
        raise ValueError("Every fixture course must belong to a fixture season")

    groups = {(group["course_id"], group["group_id"]) for group in tables["groups"]}
    if any(course_id not in courses for course_id, _group_id in groups):
        raise ValueError("Every fixture group must belong to a fixture course")

    accounts = {account["id"]: account for account in tables["auth_accounts"]}
    account_public_ids = {
        account["public_id"]: account for account in accounts.values()
    }
    if len(account_public_ids) != len(accounts):
        raise ValueError("Fixture auth account public IDs must be unique")
    if any(
        not account["credential_hash"].startswith("$argon2id$v=19$")
        for account in accounts.values()
    ):
        raise ValueError("Fixture credentials must be encoded Argon2id hashes")
    if any(
        account["linked_user_id"] is not None
        and account["linked_user_id"] not in user_ids
        for account in accounts.values()
    ):
        raise ValueError("Fixture auth account refers to an unknown legacy user")

    enrollments = {
        enrollment["id"]: enrollment for enrollment in tables["course_enrollments"]
    }
    if any(
        enrollment["student_user_id"] not in user_ids
        or enrollment["course_id"] not in courses
        or (enrollment["course_id"], enrollment["active_group_id"]) not in groups
        for enrollment in enrollments.values()
    ):
        raise ValueError("Fixture enrollment has an unknown student/course/group")
    access_rows = tables["course_group_access"]
    if any(
        row["enrollment_id"] not in enrollments
        or row["course_id"] != enrollments[row["enrollment_id"]]["course_id"]
        or (row["course_id"], row["group_id"]) not in groups
        for row in access_rows
    ):
        raise ValueError("Fixture group access is outside its enrollment course")
    active_access = {
        (row["enrollment_id"], row["group_id"])
        for row in access_rows
        if row["valid_to"] is None
    }
    if any(
        (enrollment["id"], enrollment["active_group_id"]) not in active_access
        for enrollment in enrollments.values()
    ):
        raise ValueError("Every active fixture group must have active access")

    if any(
        scope["staff_user_id"] not in user_ids
        or scope["course_id"] not in courses
        or (
            scope["group_id"] is not None
            and (scope["course_id"], scope["group_id"]) not in groups
        )
        for scope in tables["staff_scopes"]
    ):
        raise ValueError("Fixture staff scope has an unknown user/course/group")

    # A baseline starts before any browser has logged in. Populating sessions,
    # auth audit, throttle state, or change history would make tests depend on
    # an unexplained prior request and would require embedding refresh secrets.
    for empty_table in (
        "auth_sessions",
        "auth_refresh_consumed_secrets",
        "auth_events",
        "auth_throttle_buckets",
        "course_enrollment_events",
    ):
        if tables[empty_table]:
            raise ValueError(f"baseline-v1 requires an empty {empty_table} table")

    family = payload["seedMetadata"]["familyPersona"]
    student_ids = {user["id"] for user in users if user["type"] == 1}
    if set(family["studentUserIds"]) - student_ids:
        raise ValueError("The Family fixture refers to an unknown Student")
    if family.get("materializeInPhase") != 1:
        raise ValueError("The Family persona must identify its Phase-1 materialization")
    family_account = account_public_ids.get(family.get("accountPublicId"))
    if family_account is None or family_account["audience"] != "family":
        raise ValueError("The Family persona must name its materialized Family account")
    linked_students = {
        link["student_user_id"]
        for link in tables["family_student_links"]
        if link["family_account_id"] == family_account["id"]
        and link["revoked_at"] is None
    }
    if linked_students != set(family["studentUserIds"]):
        raise ValueError("The Family persona links do not match its Student list")


def _populate_database(database: PwaConnectionFactory, payload: dict[str, Any]) -> None:
    tables: dict[str, list[dict[str, Any]]] = payload["tables"]

    def populate(connection: sqlite3.Connection) -> None:
        # Migration 0038 carries historical credential rows. They never belong
        # in a synthetic runtime and reference users that are absent from a
        # fresh DB. Phase 10 owns production cleanup. This disposable copy is
        # purged before population, then VACUUMed before installation. Until
        # that purge finishes, the mode-0600 sibling temp can still contain the
        # migration literals; see pwa_tests/reports/baseline-v1.md.
        connection.execute("DELETE FROM kv_logins")
        connection.execute("DELETE FROM groups")
        connection.execute("DELETE FROM kv")
        for table in INSERT_ORDER:
            _insert_rows(connection, table, tables[table])
        connection.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?)",
            (
                "vmshpwa.seed",
                json.dumps(
                    payload["seedMetadata"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )

    database.run_write(populate)


def _reaction_foreign_keys(connection: sqlite3.Connection) -> set[tuple[str, str, str]]:
    return {
        (row["from"], row["table"], row["to"])
        for row in connection.execute("PRAGMA foreign_key_list(reactions)")
    }


def _has_known_reactions_foreign_key_defect(
    connection: sqlite3.Connection,
) -> bool:
    actual = _reaction_foreign_keys(connection)
    if actual != EXPECTED_LEGACY_REACTION_FOREIGN_KEYS:
        return False
    zoom_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(zoom_conversation)")
    }
    return "id" in zoom_columns and "zoom_conversation_id" not in zoom_columns


def _validate_known_defective_reactions_foreign_keys(
    connection: sqlite3.Connection,
) -> None:
    """Validate every usable FK while excluding one malformed legacy target.

    SQLite cannot run ``foreign_key_check(reactions)`` when even one FK points
    at a missing parent column. The production-derived legacy schema has that
    exact defect only for ``zoom_conversation_id``. Skipping the whole table
    would also hide broken result/reaction references, so those three simple
    keys are checked explicitly. See development-plan/04-phase-0-baseline.md.
    """

    excluded = (
        "zoom_conversation_id",
        "zoom_conversation",
        "zoom_conversation_id",
    )
    for child_column, parent_table, parent_column in sorted(
        _reaction_foreign_keys(connection)
    ):
        if (child_column, parent_table, parent_column) == excluded:
            continue
        child_sql = _quote_identifier(child_column)
        parent_table_sql = _quote_identifier(parent_table)
        parent_sql = _quote_identifier(parent_column)
        violating_rows = list(
            connection.execute(
                "SELECT child.rowid, child."
                f"{child_sql} FROM reactions AS child "
                f"WHERE child.{child_sql} IS NOT NULL "
                "AND NOT EXISTS ("
                f"SELECT 1 FROM {parent_table_sql} AS parent "
                f"WHERE parent.{parent_sql} = child.{child_sql}"
                ") ORDER BY child.rowid LIMIT 20"
            )
        )
        if violating_rows:
            rendered = [tuple(row) for row in violating_rows]
            raise RuntimeError(
                "Seeded SQLite has foreign-key violations in "
                f"reactions.{child_column} -> {parent_table}.{parent_column}: "
                f"{rendered}"
            )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _validate_database(database_path: Path) -> tuple[str, ...]:
    exclusions: list[str] = []
    with closing(sqlite3.connect(database_path, autocommit=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise RuntimeError(f"Seeded SQLite failed integrity_check: {integrity}")

        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            if table == "reactions" and _has_known_reactions_foreign_key_defect(
                connection
            ):
                exclusions.append(
                    "reactions.zoom_conversation_id -> "
                    "zoom_conversation.zoom_conversation_id (legacy schema defect)"
                )
                _validate_known_defective_reactions_foreign_keys(connection)
                continue
            try:
                violations = list(
                    connection.execute(
                        f"PRAGMA foreign_key_check({_quote_identifier(table)})"
                    )
                )
            except sqlite3.DatabaseError as exc:
                raise RuntimeError(
                    f"Could not validate foreign keys for table {table}"
                ) from exc
            if violations:
                rendered = [tuple(row) for row in violations]
                raise RuntimeError(
                    f"Seeded SQLite has foreign-key violations in {table}: {rendered}"
                )

        missing_seed_tables = set(CANONICAL_ORDER_BY).difference(tables)
        if missing_seed_tables:
            raise RuntimeError(
                "Seeded SQLite is missing canonical Phase-1 tables: "
                + ", ".join(sorted(missing_seed_tables))
            )

        credential_count = connection.execute(
            "SELECT count(*) FROM kv_logins"
        ).fetchone()[0]
        if credential_count:
            raise RuntimeError("Synthetic seed retained migration-carried credentials")
    return tuple(exclusions)


def _compact_database(database_path: Path) -> None:
    # DELETE alone leaves the migration-carried credential strings in free
    # SQLite pages. Checkpoint + VACUUM makes the disposable baseline artifact
    # contain only its synthetic rows.
    with closing(sqlite3.connect(database_path, autocommit=True)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("VACUUM")
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _canonical_database(database_path: Path) -> tuple[str, dict[str, int]]:
    canonical: dict[str, list[dict[str, Any]]] = {}
    row_counts: dict[str, int] = {}
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        for table, order_by in CANONICAL_ORDER_BY.items():
            rows = [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM {_quote_identifier(table)} ORDER BY {order_by}"
                )
            ]
            canonical[table] = rows
            row_counts[table] = len(rows)
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest(), row_counts


def _database_sidecars(database_path: Path) -> tuple[Path, ...]:
    return (
        database_path.with_name(database_path.name + "-wal"),
        database_path.with_name(database_path.name + "-shm"),
        database_path.with_name(database_path.name + "-journal"),
    )


def _existing_sidecars(database_path: Path) -> list[Path]:
    return [path for path in _database_sidecars(database_path) if path.exists()]


def _require_no_target_sidecars(database_path: Path) -> None:
    existing = _existing_sidecars(database_path)
    if existing:
        raise RuntimeError(
            "PWA seed target has SQLite sidecars and may be open; stop the runtime first: "
            + ", ".join(str(path) for path in existing)
        )


def _prepare_target_for_replace(database_path: Path) -> None:
    """Let SQLite recover stale sidecars, but never separate a live WAL.

    SQLite documents the WAL as part of the persistent database state and says
    the safe way to remove an orphaned WAL is to open and immediately close the
    database. ``TRUNCATE`` additionally reports a busy reader/writer instead of
    letting the seed guess. If another process still owns the database, its
    sidecars remain and replacement is refused.

    See https://www.sqlite.org/wal.html#the_wal_file and
    https://www.sqlite.org/pragma.html#pragma_wal_checkpoint.
    """

    existing = _existing_sidecars(database_path)
    if not existing:
        return
    if not database_path.is_file():
        _require_no_target_sidecars(database_path)
    for sidecar in existing:
        _reject_symlink(sidecar, label="SQLite sidecar")

    try:
        with closing(
            sqlite3.connect(database_path, timeout=0, autocommit=True)
        ) as connection:
            connection.execute("PRAGMA busy_timeout = 0")
            checkpoint = connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            if checkpoint is not None and int(checkpoint[0]) != 0:
                raise RuntimeError(
                    "PWA seed target is busy; stop the runtime before seeding"
                )
    except sqlite3.Error as error:
        raise RuntimeError(
            "PWA seed could not safely recover SQLite sidecars; "
            "stop the runtime before seeding"
        ) from error

    _require_no_target_sidecars(database_path)


def _fsync_path(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _seed_runtime_under_lock(
    database_path: Path,
    configured_media_root: Path,
    payload: dict[str, Any],
) -> SeedReport:
    """Build and replace a seed while the caller holds exclusive lifecycle lock."""

    _prepare_target_for_replace(database_path)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=database_path.parent,
        prefix=f".{database_path.name}.baseline-v1-",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        apply_schema_migrations(temporary_path)
        database = PwaConnectionFactory(temporary_path)
        _populate_database(database, payload)
        exclusions = _validate_database(temporary_path)
        _compact_database(temporary_path)
        final_exclusions = _validate_database(temporary_path)
        if final_exclusions != exclusions:
            raise RuntimeError("Foreign-key validation changed after SQLite compaction")

        digest, row_counts = _canonical_database(temporary_path)
        expected_digest = payload.get("expectedCanonicalDigest")
        if expected_digest not in {None, "PENDING", digest}:
            raise RuntimeError(
                "baseline-v1 canonical digest changed: "
                f"expected {expected_digest}, got {digest}"
            )

        # The lifecycle lock excludes cooperating runtimes throughout the
        # build. This final SQLite check still detects non-cooperating legacy
        # clients before the pathname is replaced. See ADR 0002.
        _prepare_target_for_replace(database_path)
        configured_media_root.mkdir(parents=True, exist_ok=True)
        _fsync_path(temporary_path)
        _fsync_path(database_path.parent)
        os.replace(temporary_path, database_path)
        # Replacement is already complete at this point. A platform-specific
        # directory fsync failure must not turn a successful atomic swap into a
        # reported build failure (which would falsely promise the old DB is
        # still installed), but crash durability must be reported honestly.
        durability_confirmed = True
        durability_warning = None
        try:
            _fsync_path(database_path.parent)
        except OSError as error:
            durability_confirmed = False
            durability_warning = (
                "atomic replacement completed, but the final directory fsync "
                f"failed ({type(error).__name__}); crash durability is unconfirmed"
            )
            print(f"WARNING: {durability_warning}", file=sys.stderr)
        report = SeedReport(
            database_path=database_path,
            fixture=payload["fixture"],
            canonical_digest=digest,
            row_counts=row_counts,
            foreign_key_exclusions=exclusions,
            durability_confirmed=durability_confirmed,
            durability_warning=durability_warning,
        )
    finally:
        for disposable in (temporary_path, *_database_sidecars(temporary_path)):
            disposable.unlink(missing_ok=True)

    return report


def seed_runtime(
    runtime_config: PwaMaintenanceConfig,
    *,
    database_root: Path | None = None,
    media_root: Path | None = None,
) -> SeedReport:
    """Build, validate and atomically install the selected isolated seed DB."""

    payload = load_baseline_v1()
    _validate_fixture(payload)
    database_path, configured_media_root = _require_seed_paths(
        runtime_config,
        database_root=database_root or DEFAULT_DATABASE_ROOT,
        media_root=media_root or DEFAULT_MEDIA_ROOT,
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # SQLite explicitly warns that renaming an open database can corrupt its
    # pathname-derived WAL/journal pairing. Runtime workers therefore hold the
    # shared form of this lock for their whole lifecycle; seed owns exclusive
    # access from the first sidecar inspection through replace+directory fsync.
    # Decision and primary sources: ADR 0002.
    with maintenance_database_lock(database_path):
        report = _seed_runtime_under_lock(
            database_path,
            configured_media_root,
            payload,
        )
    print(
        f"Seeded {runtime_config.pwa_instance}: {database_path} "
        f"fixture={report.fixture} digest={report.canonical_digest} "
        "durability="
        f"{'confirmed' if report.durability_confirmed else 'unconfirmed'}"
    )
    return report


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Seed the explicitly selected isolated PWA profile"
    )
    parser.parse_args(argv)
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("PWA seed is forbidden when PROD=true")
    require_pwa_profile_environment()
    # See migrate_runtime.py: never import the legacy config loader before the
    # explicit profile guard has succeeded.
    from helpers.config import config

    seed_runtime(config)


if __name__ == "__main__":
    main()
