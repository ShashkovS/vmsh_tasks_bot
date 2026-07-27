"""Controlled Phase-1 Student authentication import for a disposable DB copy.

The command has no default database and refuses the authoritative ``db/vmsh.db``,
symlinks, hard links, permissive decision files and a schema which is not at the
repository migration head.  Preview reads an exact in-memory snapshot.  Apply
revalidates the complete plan under ``BEGIN IMMEDIATE`` and is transactional.

Only aggregate reports are suitable for committing.  An optional row-level
report is accepted exclusively below ``.runtime/`` and is written with mode
``0600``.  See Phase 1 in
``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sqlite3
import stat
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from db_methods.pwa.migrations import require_current_schema
from models.pwa.auth import (
    STUDENT_USERNAME_ALGORITHM_VERSION,
    CredentialHasher,
    build_student_username,
    legacy_telegram_token_risk_shapes,
    normalize_login,
    normalize_telegram_token,
)
from vmshpwa.scripts.report_io import AtomicReportWriteError, atomic_write_text
from vmshpwa.scripts.safe_source import (
    SafeSourceError,
    fingerprint,
    read_and_fingerprint,
    secure_open,
    verify_path_matches,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITATIVE_DATABASE = REPOSITORY_ROOT / "db" / "vmsh.db"
RUNTIME_ROOT = REPOSITORY_ROOT / ".runtime"
IMPORT_DATABASE_ROOT = RUNTIME_ROOT / "auth-import"

DECISION_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
STUDENT_TYPE = 1
PROVISIONING_SOURCE = "controlled-student-import-v1"
_CANONICAL_USERNAME = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?\Z")
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?\Z")
_REQUIRED_TABLES = {
    "users",
    "auth_accounts",
    "course_enrollments",
    "course_group_access",
    "course_enrollment_events",
}


class AuthImportError(RuntimeError):
    """Raised when a controlled import cannot be proved safe."""


@dataclass(frozen=True, slots=True)
class ImportDecisions:
    excluded_user_ids: frozenset[int]
    collision_overrides: Mapping[int, str]


@dataclass(frozen=True, slots=True)
class StudentSourceRow:
    user_id: int
    name: str
    surname: str
    birthday: str | None
    token: str | None
    chat_id: int | None
    public_id: str | None


@dataclass(frozen=True, slots=True)
class StudentAssessment:
    row: StudentSourceRow
    canonical_username: str | None
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExistingAccount:
    public_id: str
    username_normalized: str
    username_algorithm_version: int | None
    provisioning_source: str
    credential_hash: str
    status: str


@dataclass(frozen=True, slots=True)
class ImportPlan:
    assessments: tuple[StudentAssessment, ...]
    excluded_user_ids: frozenset[int]
    effective_usernames: Mapping[int, str]
    pending_user_ids: tuple[int, ...]
    pending_user_public_id_ids: tuple[int, ...]
    existing_user_ids: tuple[int, ...]
    collision_groups: int
    collision_rows: int
    blocker_rows: int


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthImportError("Decision JSON contains a duplicate object key")
        result[key] = value
    return result


def _require_exact_keys(
    value: object, expected: set[str], *, label: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise AuthImportError(f"{label} must contain exactly the documented keys")
    return value


def _require_user_id(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AuthImportError(f"{label} must be a positive legacy user ID")
    return value


def _require_owner_only_file(descriptor: int, *, label: str) -> None:
    mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
    if mode & 0o077:
        raise AuthImportError(f"{label} must not be accessible by group or others")


def _reject_symlink_components(path: Path, *, label: str) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        except OSError as error:
            raise AuthImportError(f"Could not inspect {label} path") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise AuthImportError(f"{label} path must not contain symlinks")


def _require_path_names_descriptor(path: Path, descriptor: int) -> None:
    try:
        path_metadata = path.lstat()
        descriptor_metadata = os.fstat(descriptor)
    except OSError as error:
        raise AuthImportError(
            "Import database identity could not be revalidated"
        ) from error
    if (
        stat.S_ISLNK(path_metadata.st_mode)
        or not stat.S_ISREG(path_metadata.st_mode)
        or path_metadata.st_nlink != 1
        or descriptor_metadata.st_nlink != 1
        or (path_metadata.st_dev, path_metadata.st_ino)
        != (descriptor_metadata.st_dev, descriptor_metadata.st_ino)
    ):
        raise AuthImportError("Import database path changed during apply")


def load_decisions(path: Path) -> ImportDecisions:
    """Load the strict owner-only launch cohort decision contract."""

    supplied_path = Path(path)
    _reject_symlink_components(supplied_path, label="Decision file")
    if supplied_path.is_symlink():
        raise AuthImportError("Decision file must be a regular single-link file")
    absolute = Path(os.path.abspath(supplied_path))
    allowed_root = Path(os.path.abspath(IMPORT_DATABASE_ROOT))
    if not absolute.is_relative_to(allowed_root):
        raise AuthImportError(
            "Decision file must be below the dedicated .runtime/auth-import root"
        )
    try:
        with secure_open(supplied_path) as descriptor:
            _require_owner_only_file(descriptor, label="Decision file")
            before, content = read_and_fingerprint(descriptor)
            verify_path_matches(supplied_path, before)
            if len(content) > 2 * 1024 * 1024:
                raise AuthImportError("Decision file is unexpectedly large")
            try:
                payload = json.loads(
                    content.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise AuthImportError(
                    "Decision file is not valid UTF-8 JSON"
                ) from error
            after = fingerprint(descriptor)
            verify_path_matches(supplied_path, after)
            if before != after:
                raise AuthImportError("Decision file changed while it was read")
    except SafeSourceError as error:
        raise AuthImportError(str(error)) from error

    root = _require_exact_keys(
        payload,
        {
            "schemaVersion",
            "purpose",
            "studentUsernameAlgorithmVersion",
            "cohort",
            "excludedLegacyUserIds",
            "collisionOverrides",
        },
        label="Decision document",
    )
    if root["schemaVersion"] != DECISION_SCHEMA_VERSION:
        raise AuthImportError("Unsupported decision schema version")
    if root["purpose"] != "phase1-student-auth-import":
        raise AuthImportError("Decision document has the wrong purpose")
    if root["studentUsernameAlgorithmVersion"] != STUDENT_USERNAME_ALGORITHM_VERSION:
        raise AuthImportError("Decision document uses a different username algorithm")
    cohort = _require_exact_keys(
        root["cohort"], {"legacyUserType"}, label="Decision cohort"
    )
    if cohort["legacyUserType"] != STUDENT_TYPE:
        raise AuthImportError("Only the explicit users.type = 1 cohort is supported")

    raw_exclusions = root["excludedLegacyUserIds"]
    if not isinstance(raw_exclusions, list):
        raise AuthImportError("excludedLegacyUserIds must be a JSON array")
    excluded = tuple(
        _require_user_id(value, label="excludedLegacyUserIds item")
        for value in raw_exclusions
    )
    if len(excluded) != len(set(excluded)):
        raise AuthImportError("excludedLegacyUserIds contains a duplicate")

    raw_overrides = root["collisionOverrides"]
    if not isinstance(raw_overrides, list):
        raise AuthImportError("collisionOverrides must be a JSON array")
    overrides: dict[int, str] = {}
    for index, raw_override in enumerate(raw_overrides):
        override = _require_exact_keys(
            raw_override,
            {"legacyUserId", "username"},
            label=f"collisionOverrides[{index}]",
        )
        user_id = _require_user_id(
            override["legacyUserId"], label="collision override legacyUserId"
        )
        username = override["username"]
        if not isinstance(username, str):
            raise AuthImportError("Collision override username must be a string")
        normalized = normalize_login(username)
        if username != normalized or not _CANONICAL_USERNAME.fullmatch(normalized):
            raise AuthImportError(
                "Collision override username must already be canonical lowercase ASCII"
            )
        if user_id in overrides:
            raise AuthImportError("collisionOverrides contains a duplicate user")
        overrides[user_id] = normalized
    if frozenset(excluded) & overrides.keys():
        raise AuthImportError("An excluded user cannot also have a collision override")
    if len(overrides.values()) != len(set(overrides.values())):
        raise AuthImportError("Collision override usernames must be unique")
    return ImportDecisions(frozenset(excluded), overrides)


def _reject_authoritative_or_unsafe_database(path: Path, *, for_apply: bool) -> Path:
    supplied = Path(path)
    _reject_symlink_components(supplied, label="Import database")
    if supplied.is_symlink():
        raise AuthImportError("Import database must not be a symlink")
    absolute = Path(os.path.abspath(supplied))
    if absolute == AUTHORITATIVE_DATABASE.absolute():
        raise AuthImportError("The authoritative db/vmsh.db is never an import target")
    try:
        if absolute.exists() and AUTHORITATIVE_DATABASE.exists():
            if absolute.samefile(AUTHORITATIVE_DATABASE):
                raise AuthImportError(
                    "A link to the authoritative db/vmsh.db is never an import target"
                )
    except OSError as error:
        raise AuthImportError("Could not establish import database identity") from error
    allowed_root = Path(os.path.abspath(IMPORT_DATABASE_ROOT))
    if not absolute.is_relative_to(allowed_root):
        raise AuthImportError(
            "Import database must be below the dedicated .runtime/auth-import root"
        )
    _reject_symlink_components(allowed_root, label="Import database root")
    try:
        with secure_open(absolute) as descriptor:
            if for_apply:
                _require_owner_only_file(descriptor, label="Apply database")
    except SafeSourceError as error:
        raise AuthImportError(str(error)) from error
    return absolute


def _require_import_schema(path: Path) -> None:
    try:
        require_current_schema(path)
    except Exception as error:
        raise AuthImportError(
            "Import database must be an explicitly migrated disposable copy"
        ) from error
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
        if not _REQUIRED_TABLES <= tables:
            raise AuthImportError("Import database lacks required Phase-1 tables")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "public_id" not in columns:
            raise AuthImportError("Import database lacks users.public_id")


def _require_quiescent_database(path: Path) -> None:
    if any(
        path.with_name(path.name + suffix).exists()
        for suffix in ("-wal", "-shm", "-journal")
    ):
        raise AuthImportError(
            "Import database must be quiescent without WAL/journal sidecars"
        )


def _deserialize_snapshot(content: bytes) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", autocommit=True)
    try:
        deserialize = getattr(connection, "deserialize", None)
        if not callable(deserialize):
            raise AuthImportError("SQLite deserialize support is required")
        deserialize(content)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        return connection
    except Exception:
        connection.close()
        raise


def _read_snapshot(path: Path) -> tuple[sqlite3.Connection, object]:
    try:
        _require_quiescent_database(path)
        with secure_open(path) as descriptor:
            before, content = read_and_fingerprint(descriptor)
            verify_path_matches(path, before)
            connection = _deserialize_snapshot(content)
            after = fingerprint(descriptor)
            verify_path_matches(path, after)
            if before != after:
                connection.close()
                raise AuthImportError("Import database changed during preview")
            _require_quiescent_database(path)
            return connection, before
    except SafeSourceError as error:
        raise AuthImportError(str(error)) from error


def _parse_birthday(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):  # fmt: skip
        return None
    return parsed if parsed <= date.today() else None


def _assess(row: StudentSourceRow) -> StudentAssessment:
    blockers: list[str] = []
    birthday = _parse_birthday(row.birthday)
    surname = " ".join(row.surname.strip().split())
    if birthday is None:
        blockers.append("invalidBirthday")
    if not surname:
        blockers.append("emptySurname")
    token = "" if row.token is None else str(row.token).strip()
    if not token or legacy_telegram_token_risk_shapes(token, row.chat_id):
        blockers.append("unsafeTelegramToken")
    canonical_username: str | None = None
    if birthday is not None and surname:
        try:
            canonical_username = build_student_username(surname, birthday)
        except ValueError:
            blockers.append("emptyUsernameStem")
    return StudentAssessment(row, canonical_username, tuple(sorted(set(blockers))))


def _load_students(connection: sqlite3.Connection) -> tuple[StudentAssessment, ...]:
    rows = connection.execute(
        "SELECT id, name, surname, birthday, token, chat_id, public_id "
        "FROM users WHERE type = ? ORDER BY id",
        (STUDENT_TYPE,),
    ).fetchall()
    return tuple(
        _assess(
            StudentSourceRow(
                user_id=int(row["id"]),
                name=str(row["name"]),
                surname=str(row["surname"]),
                birthday=None if row["birthday"] is None else str(row["birthday"]),
                token=None if row["token"] is None else str(row["token"]),
                chat_id=None if row["chat_id"] is None else int(row["chat_id"]),
                public_id=(None if row["public_id"] is None else str(row["public_id"])),
            )
        )
        for row in rows
    )


def _load_existing_accounts(
    connection: sqlite3.Connection,
) -> dict[int, ExistingAccount]:
    rows = connection.execute(
        "SELECT linked_user_id, public_id, username_normalized, "
        "username_algorithm_version, provisioning_source, credential_hash, status "
        "FROM auth_accounts WHERE audience = 'student'"
    ).fetchall()
    result: dict[int, ExistingAccount] = {}
    for row in rows:
        linked_user_id = row["linked_user_id"]
        if linked_user_id is None or int(linked_user_id) in result:
            raise AuthImportError("Existing Student account graph is not canonical")
        result[int(linked_user_id)] = ExistingAccount(
            public_id=str(row["public_id"]),
            username_normalized=str(row["username_normalized"]),
            username_algorithm_version=row["username_algorithm_version"],
            provisioning_source=str(row["provisioning_source"]),
            credential_hash=str(row["credential_hash"]),
            status=str(row["status"]),
        )
    return result


def _collision_members(
    assessments: Sequence[StudentAssessment], excluded: frozenset[int]
) -> tuple[set[int], int]:
    by_username: dict[str, list[int]] = {}
    for assessment in assessments:
        if (
            assessment.row.user_id not in excluded
            and not assessment.blocker_codes
            and assessment.canonical_username is not None
        ):
            by_username.setdefault(assessment.canonical_username, []).append(
                assessment.row.user_id
            )
    groups = [members for members in by_username.values() if len(members) > 1]
    return {user_id for members in groups for user_id in members}, len(groups)


def build_plan(
    connection: sqlite3.Connection,
    decisions: ImportDecisions,
    *,
    credential_hasher: CredentialHasher | None = None,
    verify_existing_credentials: bool = False,
) -> ImportPlan:
    """Validate one complete cohort decision and return a secret-bearing plan."""

    assessments = _load_students(connection)
    cohort_ids = {assessment.row.user_id for assessment in assessments}
    referenced_ids = set(decisions.excluded_user_ids) | set(
        decisions.collision_overrides
    )
    if not referenced_ids <= cohort_ids:
        raise AuthImportError("Decision document references a user outside the cohort")

    collision_ids, collision_group_count = _collision_members(
        assessments, decisions.excluded_user_ids
    )
    if set(decisions.collision_overrides) != collision_ids:
        raise AuthImportError(
            "Every active canonical collision row needs exactly one explicit override"
        )

    effective_usernames: dict[int, str] = {}
    blocker_rows = 0
    for assessment in assessments:
        user_id = assessment.row.user_id
        if user_id in decisions.excluded_user_ids:
            continue
        if assessment.blocker_codes or assessment.canonical_username is None:
            blocker_rows += 1
            continue
        effective_usernames[user_id] = decisions.collision_overrides.get(
            user_id, assessment.canonical_username
        )
    if blocker_rows:
        raise AuthImportError(
            "Every blocked Student row must be listed as an explicit exclusion"
        )
    if len(effective_usernames.values()) != len(set(effective_usernames.values())):
        raise AuthImportError("Effective Student usernames are not unique")

    existing_accounts = _load_existing_accounts(connection)
    if set(existing_accounts) & set(decisions.excluded_user_ids):
        raise AuthImportError(
            "An explicitly excluded row already has a Student account"
        )

    # An existing account outside this explicit launch cohort is a conflicting
    # independent decision, not something this importer may silently absorb.
    if not set(existing_accounts) <= set(effective_usernames):
        raise AuthImportError(
            "Target contains a Student account outside this launch cohort"
        )
    username_owner = {
        account.username_normalized: user_id
        for user_id, account in existing_accounts.items()
    }
    pending: list[int] = []
    existing: list[int] = []
    hasher = credential_hasher or CredentialHasher()
    assessment_by_id = {
        assessment.row.user_id: assessment for assessment in assessments
    }
    for user_id, username in sorted(effective_usernames.items()):
        owner = username_owner.get(username)
        if owner is not None and owner != user_id:
            raise AuthImportError(
                "Effective username conflicts with an existing account"
            )
        account = existing_accounts.get(user_id)
        if account is None:
            pending.append(user_id)
            continue
        row = assessment_by_id[user_id].row
        valid_credential = True
        if verify_existing_credentials:
            token = normalize_telegram_token(row.token or "")
            valid_credential = hasher.verify(account.credential_hash, token).valid
        if not (
            account.username_normalized == username
            and account.username_algorithm_version == STUDENT_USERNAME_ALGORITHM_VERSION
            and account.provisioning_source == PROVISIONING_SOURCE
            and account.status == "active"
            and _PUBLIC_ID.fullmatch(account.public_id)
            and row.public_id is not None
            and _PUBLIC_ID.fullmatch(row.public_id)
            and valid_credential
        ):
            raise AuthImportError("Existing Student account does not match this import")
        existing.append(user_id)

    return ImportPlan(
        assessments=assessments,
        excluded_user_ids=decisions.excluded_user_ids,
        effective_usernames=effective_usernames,
        pending_user_ids=tuple(pending),
        pending_user_public_id_ids=tuple(
            user_id
            for user_id in pending
            if assessment_by_id[user_id].row.public_id is None
        ),
        existing_user_ids=tuple(existing),
        collision_groups=collision_group_count,
        collision_rows=len(collision_ids),
        blocker_rows=0,
    )


def aggregate_report(
    plan: ImportPlan,
    *,
    operation: str,
    inserted_rows: int | None = None,
    inserted_user_public_ids: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic report with no identifiers or credential material."""

    blocker_counts: Counter[str] = Counter()
    for assessment in plan.assessments:
        blocker_counts.update(assessment.blocker_codes)
    if operation == "preview":
        new_accounts = len(plan.pending_user_ids)
        new_user_public_ids = len(plan.pending_user_public_id_ids)
        already_imported = len(plan.existing_user_ids)
        status = "ready"
    else:
        new_accounts = 0 if inserted_rows is None else inserted_rows
        new_user_public_ids = (
            0 if inserted_user_public_ids is None else inserted_user_public_ids
        )
        already_imported = len(plan.existing_user_ids) - new_accounts
        status = "applied" if new_accounts else "already-applied"
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "operation": operation,
        "status": status,
        "source": "explicit-disposable-migrated-copy",
        "cohort": {
            "definition": "users.type = 1",
            "selectedRows": len(plan.assessments),
            "excludedRows": len(plan.excluded_user_ids),
            "activatedRows": len(plan.effective_usernames),
        },
        "decisions": {
            "usernameAlgorithmVersion": STUDENT_USERNAME_ALGORITHM_VERSION,
            "collisionGroups": plan.collision_groups,
            "collisionRows": plan.collision_rows,
            "explicitCollisionOverrides": plan.collision_rows,
            "blockerRowsExcluded": sum(
                bool(assessment.blocker_codes)
                and assessment.row.user_id in plan.excluded_user_ids
                for assessment in plan.assessments
            ),
            "blockerCodes": {
                key: blocker_counts[key]
                for key in (
                    "invalidBirthday",
                    "emptySurname",
                    "unsafeTelegramToken",
                    "emptyUsernameStem",
                )
            },
        },
        "databaseChanges": {
            "newUserPublicIds": new_user_public_ids,
            "newStudentAccounts": new_accounts,
            "alreadyImportedAccounts": already_imported,
            "plaintextCredentialCopies": 0,
            "existingCredentialVerification": (
                "deferred-to-apply" if operation == "preview" else "verified"
            ),
        },
        "courseBackfill": {
            "ownedByThisIncrement": False,
            "enrollmentsCreated": 0,
            "accessRowsCreated": 0,
            "eventsCreated": 0,
            "reason": (
                "Course enrollment/access/history needs a separately approved "
                "legacy group-mode mapping; this auth import does not fabricate it."
            ),
        },
    }


def detailed_report(plan: ImportPlan) -> dict[str, Any]:
    """Build a local owner-only decision aid. Never commit this structure."""

    rows = []
    for assessment in plan.assessments:
        user_id = assessment.row.user_id
        rows.append(
            {
                "legacyUserId": user_id,
                "disposition": (
                    "excluded"
                    if user_id in plan.excluded_user_ids
                    else "already-imported"
                    if user_id in plan.existing_user_ids
                    else "activate"
                ),
                "canonicalUsername": assessment.canonical_username,
                "effectiveUsername": plan.effective_usernames.get(user_id),
                "blockers": list(assessment.blocker_codes),
            }
        )
    return {
        "schemaVersion": 1,
        "classification": "owner-only-local-do-not-commit",
        "rows": rows,
    }


def inventory_report(
    assessments: Sequence[StudentAssessment],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return aggregate and owner-only inventory views before decisions exist."""

    collision_ids, collision_groups = _collision_members(assessments, frozenset())
    blocker_counts: Counter[str] = Counter()
    for assessment in assessments:
        blocker_counts.update(assessment.blocker_codes)
    aggregate = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "operation": "inventory",
        "status": "decisions-required",
        "source": "explicit-disposable-migrated-copy",
        "cohort": {
            "definition": "users.type = 1",
            "selectedRows": len(assessments),
        },
        "decisionsRequired": {
            "fieldOrTokenBlockerRows": sum(
                bool(assessment.blocker_codes) for assessment in assessments
            ),
            "canonicalCollisionGroups": collision_groups,
            "canonicalCollisionRows": len(collision_ids),
            "blockerCodes": {
                key: blocker_counts[key]
                for key in (
                    "invalidBirthday",
                    "emptySurname",
                    "unsafeTelegramToken",
                    "emptyUsernameStem",
                )
            },
        },
        "credentialWork": {
            "argon2HashesComputed": 0,
            "plaintextCredentialCopies": 0,
        },
    }
    detail = {
        "schemaVersion": 1,
        "classification": "owner-only-local-do-not-commit",
        "purpose": "prepare-explicit-auth-import-decisions",
        "rows": [
            {
                "legacyUserId": assessment.row.user_id,
                "canonicalUsername": assessment.canonical_username,
                "canonicalCollision": assessment.row.user_id in collision_ids,
                "blockers": list(assessment.blocker_codes),
            }
            for assessment in assessments
        ],
    }
    return aggregate, detail


def _write_json(path: Path, payload: Mapping[str, Any], *, mode: int) -> None:
    try:
        atomic_write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            mode=mode,
        )
    except AtomicReportWriteError as error:
        raise AuthImportError("Could not write import report") from error


def _write_owner_only_detail(path: Path, payload: Mapping[str, Any]) -> None:
    target = Path(os.path.abspath(path))
    runtime_root = Path(os.path.abspath(IMPORT_DATABASE_ROOT))
    if not target.is_relative_to(runtime_root):
        raise AuthImportError(
            "Detailed reports are allowed only below .runtime/auth-import"
        )
    _reject_symlink_components(runtime_root, label="Runtime root")
    _reject_symlink_components(target.parent, label="Detailed report")
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent, label="Detailed report")
    if not target.parent.resolve().is_relative_to(runtime_root.resolve()):
        raise AuthImportError("Detailed report parent escapes .runtime")
    if target.is_symlink():
        raise AuthImportError("Detailed report target must not be a symlink")
    if target.exists() and target.stat().st_nlink != 1:
        raise AuthImportError("Detailed report target must not be a hard link")
    _write_json(target, payload, mode=0o600)
    if stat.S_IMODE(target.stat().st_mode) != 0o600:
        raise AuthImportError("Detailed report permissions are not owner-only")


def write_detailed_report(path: Path, plan: ImportPlan) -> None:
    _write_owner_only_detail(path, detailed_report(plan))


def inspect_import(
    database_path: Path,
) -> tuple[tuple[StudentAssessment, ...], dict[str, Any], dict[str, Any]]:
    """Inventory blockers/collisions without credentials or a decision file."""

    path = _reject_authoritative_or_unsafe_database(database_path, for_apply=False)
    _require_import_schema(path)
    connection, _fingerprint = _read_snapshot(path)
    with closing(connection):
        assessments = _load_students(connection)
    aggregate, detail = inventory_report(assessments)
    return assessments, aggregate, detail


def preview_import(
    database_path: Path,
    decisions: ImportDecisions,
    *,
    credential_hasher: CredentialHasher | None = None,
) -> tuple[ImportPlan, dict[str, Any]]:
    path = _reject_authoritative_or_unsafe_database(database_path, for_apply=False)
    _require_import_schema(path)
    connection, _fingerprint = _read_snapshot(path)
    with closing(connection):
        plan = build_plan(connection, decisions, credential_hasher=credential_hasher)
    return plan, aggregate_report(plan, operation="preview")


def _random_public_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(16)}"


def _display_name(row: StudentSourceRow) -> str:
    return " ".join(part for part in (row.name.strip(), row.surname.strip()) if part)


def apply_import(
    database_path: Path,
    decisions: ImportDecisions,
    *,
    confirmed_database: Path,
    credential_hasher: CredentialHasher | None = None,
    public_id_factory: Callable[[str], str] = _random_public_id,
    now: datetime | None = None,
) -> tuple[ImportPlan, dict[str, Any]]:
    """Apply one fully validated plan, or roll back every target mutation."""

    path = _reject_authoritative_or_unsafe_database(database_path, for_apply=True)
    if Path(confirmed_database).absolute() != path:
        raise AuthImportError("Apply confirmation does not exactly match the database")
    _require_import_schema(path)
    hasher = credential_hasher or CredentialHasher()

    # Compute Argon2 hashes before acquiring SQLite's write lock. The complete
    # source plan is compared again under BEGIN IMMEDIATE before any mutation.
    preview_connection, _fingerprint = _read_snapshot(path)
    with closing(preview_connection):
        preview_plan = build_plan(
            preview_connection, decisions, credential_hasher=hasher
        )
    assessment_by_id = {
        assessment.row.user_id: assessment for assessment in preview_plan.assessments
    }
    hashes: dict[int, str] = {}
    for user_id in preview_plan.pending_user_ids:
        token = normalize_telegram_token(assessment_by_id[user_id].row.token or "")
        hashes[user_id] = hasher.hash(token)

    occurred_at = (now or datetime.now().astimezone()).isoformat()
    try:
        with secure_open(path) as target_descriptor:
            _require_owner_only_file(target_descriptor, label="Apply database")
            _require_path_names_descriptor(path, target_descriptor)
            connection = sqlite3.connect(path, autocommit=True)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("PRAGMA busy_timeout = 5000")
                connection.execute("BEGIN IMMEDIATE")
                _require_path_names_descriptor(path, target_descriptor)
                locked_plan = build_plan(
                    connection,
                    decisions,
                    credential_hasher=hasher,
                    verify_existing_credentials=True,
                )
                if locked_plan.assessments != preview_plan.assessments or (
                    locked_plan.pending_user_ids != preview_plan.pending_user_ids
                    or locked_plan.existing_user_ids != preview_plan.existing_user_ids
                    or locked_plan.pending_user_public_id_ids
                    != preview_plan.pending_user_public_id_ids
                    or dict(locked_plan.effective_usernames)
                    != dict(preview_plan.effective_usernames)
                ):
                    raise AuthImportError(
                        "Import source changed after preview validation"
                    )

                for user_id in locked_plan.pending_user_ids:
                    row = assessment_by_id[user_id].row
                    user_public_id = row.public_id or public_id_factory("usr")
                    account_public_id = public_id_factory("acct")
                    if not _PUBLIC_ID.fullmatch(
                        user_public_id
                    ) or not _PUBLIC_ID.fullmatch(account_public_id):
                        raise AuthImportError(
                            "Public ID factory produced a non-canonical ID"
                        )
                    if row.public_id is None:
                        changed = connection.execute(
                            "UPDATE users SET public_id = ? "
                            "WHERE id = ? AND public_id IS NULL AND type = ?",
                            (user_public_id, user_id, STUDENT_TYPE),
                        ).rowcount
                        if changed != 1:
                            raise AuthImportError(
                                "Student row changed during public-ID assignment"
                            )
                    username = locked_plan.effective_usernames[user_id]
                    connection.execute(
                        "INSERT INTO auth_accounts "
                        "(public_id, audience, username, username_normalized, "
                        "username_algorithm_version, provisioning_source, "
                        "display_name, credential_kind, credential_hash, "
                        "linked_user_id, status, credential_version, created_at, "
                        "updated_at) VALUES (?, 'student', ?, ?, ?, ?, ?, "
                        "'telegram_token', ?, ?, 'active', 1, ?, ?)",
                        (
                            account_public_id,
                            username,
                            username,
                            STUDENT_USERNAME_ALGORITHM_VERSION,
                            PROVISIONING_SOURCE,
                            _display_name(row),
                            hashes[user_id],
                            user_id,
                            occurred_at,
                            occurred_at,
                        ),
                    )
                _require_path_names_descriptor(path, target_descriptor)
                connection.execute("COMMIT")
            except (AuthImportError, sqlite3.Error) as error:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                if isinstance(error, AuthImportError):
                    raise
                raise AuthImportError(
                    "Transactional Student auth import failed"
                ) from error
            finally:
                connection.close()
            _require_path_names_descriptor(path, target_descriptor)
    except SafeSourceError as error:
        raise AuthImportError(str(error)) from error

    # Re-open and prove the result, including credential verification. This is
    # also the idempotent-rerun contract: the next run reports zero new rows.
    final_connection, _fingerprint = _read_snapshot(path)
    with closing(final_connection):
        final_plan = build_plan(
            final_connection,
            decisions,
            credential_hasher=hasher,
            verify_existing_credentials=True,
        )
    if final_plan.pending_user_ids:
        raise AuthImportError("Committed import could not be verified")
    return final_plan, aggregate_report(
        final_plan,
        operation="apply",
        inserted_rows=len(preview_plan.pending_user_ids),
        inserted_user_public_ids=len(preview_plan.pending_user_public_id_ids),
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--database", type=Path, required=True)
    inventory_parser.add_argument("--report", type=Path, required=True)
    inventory_parser.add_argument("--detail-report", type=Path, required=True)
    for command in ("preview", "apply"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--database", type=Path, required=True)
        command_parser.add_argument("--decisions", type=Path, required=True)
        command_parser.add_argument("--report", type=Path, required=True)
        command_parser.add_argument("--detail-report", type=Path)
        if command == "apply":
            command_parser.add_argument("--confirm-database", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "inventory":
            assessments, report, detail = inspect_import(args.database)
            _write_json(args.report, report, mode=0o644)
            _write_owner_only_detail(args.detail_report, detail)
            print(
                "Student auth import decisions required: "
                f"selected={len(assessments)} "
                f"blockers={report['decisionsRequired']['fieldOrTokenBlockerRows']} "
                f"collisions={report['decisionsRequired']['canonicalCollisionRows']}"
            )
            return 0

        decisions = load_decisions(args.decisions)
        if args.command == "preview":
            plan, report = preview_import(args.database, decisions)
        else:
            plan, report = apply_import(
                args.database,
                decisions,
                confirmed_database=args.confirm_database,
            )
        _write_json(args.report, report, mode=0o644)
        if args.detail_report is not None:
            write_detailed_report(args.detail_report, plan)
        print(
            "Student auth import "
            f"{report['status']}: selected={report['cohort']['selectedRows']} "
            f"activated={report['cohort']['activatedRows']} "
            f"excluded={report['cohort']['excludedRows']}"
        )
    except AuthImportError as error:
        # Error messages are deliberately categorical and never include source
        # rows, usernames, tokens, hashes or opaque IDs.
        print(f"student auth import error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
