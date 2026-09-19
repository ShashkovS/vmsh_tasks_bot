"""Controlled Student auth import security and transaction tests."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import time
from pathlib import Path

import pytest
from argon2 import PasswordHasher

from db_methods.pwa.migrations import apply_schema_migrations
from models.pwa.auth import CredentialHasher, normalize_telegram_token
from vmshpwa.scripts import auth_import
from vmshpwa.scripts.auth_import import (
    AuthImportError,
    apply_import,
    inspect_import,
    load_decisions,
    preview_import,
    write_detailed_report,
)


@pytest.fixture(autouse=True)
def _allow_only_this_test_import_root(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_import, "IMPORT_DATABASE_ROOT", tmp_path)


def _cheap_hasher() -> CredentialHasher:
    return CredentialHasher(
        PasswordHasher(
            time_cost=1,
            memory_cost=1024,
            parallelism=1,
            hash_len=16,
            salt_len=8,
        )
    )


def _database(path: Path) -> Path:
    apply_schema_migrations(path)
    with sqlite3.connect(path, autocommit=True) as connection:
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.executemany(
            "INSERT INTO users "
            "(id, type, name, surname, birthday, token, chat_id, online) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, 1)",
            (
                (101, "Анна", "Иванова", "2012-01-02", "SafeTokenA8", 900101),
                (102, "Алина", "Иванова", "2011-04-02", "SafeTokenB8", 900102),
                (103, "Борис", "Петров", None, "SafeTokenC8", 900103),
                (104, "Вера", "Сидорова", "2013-05-04", "SafeTokenD8", 900104),
            ),
        )
    path.chmod(0o600)
    return path


def _production_size_database(path: Path, *, student_count: int = 1617) -> Path:
    apply_schema_migrations(path)
    with sqlite3.connect(path, autocommit=True) as connection:
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.executemany(
            "INSERT INTO users "
            "(id, type, name, surname, birthday, token, chat_id, online) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, 1)",
            (
                (
                    10_000 + index,
                    "Synthetic",
                    f"Student{index:04d}",
                    f"2012-01-{index % 28 + 1:02d}",
                    f"safe-token-{index:04d}-x",
                    8_000_000 + index,
                )
                for index in range(student_count)
            ),
        )
    path.chmod(0o600)
    return path


def _decision_payload(
    *,
    exclusions: list[int] | None = None,
    overrides: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "purpose": "phase1-student-auth-import",
        "studentUsernameAlgorithmVersion": 1,
        "cohort": {"legacyUserType": 1},
        "excludedLegacyUserIds": [103] if exclusions is None else exclusions,
        "collisionOverrides": (
            [
                {"legacyUserId": 101, "username": "ivanova-a-02"},
                {"legacyUserId": 102, "username": "ivanova-b-02"},
            ]
            if overrides is None
            else overrides
        ),
    }


def _decisions(
    path: Path,
    *,
    exclusions: list[int] | None = None,
    overrides: list[dict[str, object]] | None = None,
) -> Path:
    path.write_text(
        json.dumps(
            _decision_payload(exclusions=exclusions, overrides=overrides),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _logical_auth_state(path: Path) -> tuple[list[tuple], list[tuple]]:
    with sqlite3.connect(path) as connection:
        users = connection.execute(
            "SELECT id, public_id FROM users WHERE type = 1 ORDER BY id"
        ).fetchall()
        accounts = connection.execute(
            "SELECT audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "linked_user_id, status, credential_version "
            "FROM auth_accounts ORDER BY linked_user_id"
        ).fetchall()
    return users, accounts


def test_preview_is_deterministic_aggregate_and_does_not_mutate_source(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    before = database.read_bytes()

    first_plan, first = preview_import(
        database, decisions, credential_hasher=_cheap_hasher()
    )
    _second_plan, second = preview_import(
        database, decisions, credential_hasher=_cheap_hasher()
    )

    assert first == second
    assert database.read_bytes() == before
    assert first == {
        "schemaVersion": 1,
        "operation": "preview",
        "status": "ready",
        "source": "explicit-disposable-migrated-copy",
        "cohort": {
            "definition": "users.type = 1",
            "selectedRows": 4,
            "excludedRows": 1,
            "activatedRows": 3,
        },
        "decisions": {
            "usernameAlgorithmVersion": 1,
            "collisionGroups": 1,
            "collisionRows": 2,
            "explicitCollisionOverrides": 2,
            "blockerRowsExcluded": 1,
            "blockerCodes": {
                "invalidBirthday": 1,
                "emptySurname": 0,
                "unsafeTelegramToken": 0,
                "emptyUsernameStem": 0,
            },
        },
        "databaseChanges": {
            "newUserPublicIds": 0,
            "newStudentAccounts": 3,
            "alreadyImportedAccounts": 0,
            "plaintextCredentialCopies": 0,
            "existingCredentialVerification": "deferred-to-apply",
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
    serialized = json.dumps(first, ensure_ascii=False)
    for private_value in (
        "101",
        "Иванова",
        "ivanova-a-02",
        "SafeTokenA8",
        "$argon2",
        first_plan.assessments[0].row.token,
    ):
        assert private_value not in serialized


def test_inventory_and_preview_do_no_argon2_work_and_inventory_detail_is_local(
    tmp_path, monkeypatch
):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))

    class NoCredentialWork:
        def hash(self, _credential):
            raise AssertionError("preview must not hash credentials")

        def verify(self, _encoded_hash, _credential):
            raise AssertionError("preview must not verify credentials")

    assessments, aggregate, detail = inspect_import(database)
    _plan, preview = preview_import(
        database, decisions, credential_hasher=NoCredentialWork()
    )

    assert len(assessments) == 4
    assert aggregate["credentialWork"] == {
        "argon2HashesComputed": 0,
        "plaintextCredentialCopies": 0,
    }
    assert aggregate["decisionsRequired"]["canonicalCollisionRows"] == 2
    assert aggregate["decisionsRequired"]["fieldOrTokenBlockerRows"] == 1
    assert len(detail["rows"]) == 4
    assert preview["databaseChanges"]["existingCredentialVerification"] == (
        "deferred-to-apply"
    )

    runtime_root = tmp_path / ".runtime"
    monkeypatch.setattr(auth_import, "IMPORT_DATABASE_ROOT", runtime_root)
    target = runtime_root / "inventory.json"
    auth_import._write_owner_only_detail(target, detail)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    serialized = target.read_text(encoding="utf-8")
    assert "SafeToken" not in serialized
    assert "$argon2" not in serialized


def test_production_size_preview_is_bounded_and_never_hashes_credentials(tmp_path):
    database = _production_size_database(tmp_path / "production-size.sqlite3")
    decisions = load_decisions(
        _decisions(tmp_path / "decisions.json", exclusions=[], overrides=[])
    )

    class NoCredentialWork:
        def hash(self, _credential):
            raise AssertionError("preview must not hash credentials")

        def verify(self, _encoded_hash, _credential):
            raise AssertionError("preview must not verify credentials")

    started = time.perf_counter()
    _plan, report = preview_import(
        database, decisions, credential_hasher=NoCredentialWork()
    )
    elapsed = time.perf_counter() - started

    assert report["cohort"]["selectedRows"] == 1617
    assert report["cohort"]["activatedRows"] == 1617
    assert elapsed < 5.0


def test_preview_requires_explicit_exclusion_for_every_blocker(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json", exclusions=[]))

    with pytest.raises(AuthImportError, match="explicit exclusion"):
        preview_import(database, decisions, credential_hasher=_cheap_hasher())


def test_missing_birthday_and_missing_token_are_separate_explicit_blockers(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    with sqlite3.connect(database, autocommit=True) as connection:
        connection.execute("UPDATE users SET token = NULL WHERE id = 104")
    decisions = load_decisions(
        _decisions(tmp_path / "decisions.json", exclusions=[103, 104])
    )

    _plan, report = preview_import(
        database, decisions, credential_hasher=_cheap_hasher()
    )

    assert report["decisions"]["blockerRowsExcluded"] == 2
    assert report["decisions"]["blockerCodes"]["invalidBirthday"] == 1
    assert report["decisions"]["blockerCodes"]["unsafeTelegramToken"] == 1


def test_preview_requires_exact_overrides_for_every_active_collision_row(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    no_overrides = load_decisions(_decisions(tmp_path / "none.json", overrides=[]))
    partial_override = load_decisions(
        _decisions(
            tmp_path / "partial.json",
            overrides=[{"legacyUserId": 101, "username": "ivanova-a-02"}],
        )
    )

    for decisions in (no_overrides, partial_override):
        with pytest.raises(AuthImportError, match="Every active canonical collision"):
            preview_import(database, decisions, credential_hasher=_cheap_hasher())


def test_decision_contract_rejects_unknown_ids_duplicate_and_noncanonical_login(
    tmp_path,
):
    unknown = load_decisions(
        _decisions(
            tmp_path / "unknown.json",
            exclusions=[103, 999],
        )
    )
    database = _database(tmp_path / "copy.sqlite3")
    with pytest.raises(AuthImportError, match="outside the cohort"):
        preview_import(database, unknown, credential_hasher=_cheap_hasher())

    duplicate_payload = _decision_payload()
    duplicate_payload["excludedLegacyUserIds"] = [103, 103]
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(duplicate_payload), encoding="utf-8")
    duplicate_path.chmod(0o600)
    with pytest.raises(AuthImportError, match="contains a duplicate"):
        load_decisions(duplicate_path)

    invalid_payload = _decision_payload()
    invalid_payload["collisionOverrides"] = [
        {"legacyUserId": 101, "username": " Иванова 02 "},
        {"legacyUserId": 102, "username": "ivanova-b-02"},
    ]
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid_payload), encoding="utf-8")
    invalid_path.chmod(0o600)
    with pytest.raises(AuthImportError, match="canonical lowercase ASCII"):
        load_decisions(invalid_path)


def test_apply_hashes_normalized_legacy_token_without_second_plaintext_copy(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    hasher = _cheap_hasher()

    _plan, report = apply_import(
        database,
        decisions,
        confirmed_database=database,
        credential_hasher=hasher,
        now=auth_import.datetime.fromisoformat("2026-07-27T12:00:00+00:00"),
    )

    assert report["status"] == "applied"
    assert report["databaseChanges"] == {
        "newUserPublicIds": 0,
        "newStudentAccounts": 3,
        "alreadyImportedAccounts": 0,
        "plaintextCredentialCopies": 0,
        "existingCredentialVerification": "verified",
    }
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        imported = connection.execute(
            "SELECT a.*, u.public_id AS user_public_id, u.token AS legacy_token "
            "FROM auth_accounts a JOIN users u ON u.id = a.linked_user_id "
            "ORDER BY a.linked_user_id"
        ).fetchall()
        assert len(imported) == 3
        assert (
            connection.execute("SELECT count(*) FROM course_enrollments").fetchone()[0]
            == 0
        )
        for row in imported:
            assert row["public_id"].startswith("a-")
            assert row["user_public_id"].startswith("u-")
            assert row["public_id"] != row["user_public_id"]
            assert row["credential_kind"] == "telegram_token"
            assert row["credential_hash"].startswith("$argon2id$")
            assert hasher.verify(
                row["credential_hash"],
                normalize_telegram_token(row["legacy_token"]),
            ).valid
            assert row["legacy_token"] not in row["credential_hash"]
        auth_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(auth_accounts)")
        }
        assert "token" not in auth_columns
        assert "credential" not in auth_columns


def test_apply_rerun_is_idempotent_and_reports_no_new_rows(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    hasher = _cheap_hasher()
    apply_import(
        database,
        decisions,
        confirmed_database=database,
        credential_hasher=hasher,
    )
    before = _logical_auth_state(database)

    _plan, report = apply_import(
        database,
        decisions,
        confirmed_database=database,
        credential_hasher=hasher,
    )

    assert _logical_auth_state(database) == before
    assert report["status"] == "already-applied"
    assert report["databaseChanges"] == {
        "newUserPublicIds": 0,
        "newStudentAccounts": 0,
        "alreadyImportedAccounts": 3,
        "plaintextCredentialCopies": 0,
        "existingCredentialVerification": "verified",
    }


def test_apply_rolls_back_every_change_on_account_write_failure(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    before = _logical_auth_state(database)

    with sqlite3.connect(database, autocommit=True) as connection:
        connection.execute(
            "CREATE TRIGGER auth_import_test_failure BEFORE INSERT ON auth_accounts "
            "BEGIN SELECT raise(ABORT, 'synthetic import failure'); END"
        )
    with pytest.raises(
        AuthImportError, match="Transactional Student auth import failed"
    ):
        apply_import(
            database,
            decisions,
            confirmed_database=database,
            credential_hasher=_cheap_hasher(),
        )

    assert _logical_auth_state(database) == before


def test_apply_rejects_source_change_between_prehash_preview_and_transaction(
    tmp_path,
):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    delegate = _cheap_hasher()

    class MutatingHasher:
        changed = False

        def hash(self, credential):
            encoded = delegate.hash(credential)
            if not self.changed:
                self.changed = True
                with sqlite3.connect(database, autocommit=True) as connection:
                    connection.execute(
                        "UPDATE users SET token = 'ChangedTokenD8' WHERE id = 104"
                    )
            return encoded

        def verify(self, encoded_hash, credential):
            return delegate.verify(encoded_hash, credential)

    before = _logical_auth_state(database)

    with pytest.raises(AuthImportError, match="changed after preview"):
        apply_import(
            database,
            decisions,
            confirmed_database=database,
            credential_hasher=MutatingHasher(),
        )

    # The synthetic concurrent writer changed one legacy token, but the
    # importer itself assigned no public IDs and inserted no account.
    assert _logical_auth_state(database) == before
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT token FROM users WHERE id = 104").fetchone()[0]
            == "ChangedTokenD8"
        )


def test_apply_requires_exact_confirmation_owner_only_database_and_safe_paths(
    tmp_path, monkeypatch
):
    database = _database(tmp_path / "copy.sqlite3")
    decision_path = _decisions(tmp_path / "decisions.json")
    decisions = load_decisions(decision_path)

    with pytest.raises(AuthImportError, match="confirmation"):
        apply_import(
            database,
            decisions,
            confirmed_database=tmp_path / "other.sqlite3",
            credential_hasher=_cheap_hasher(),
        )

    database.chmod(0o644)
    with pytest.raises(AuthImportError, match="group or others"):
        apply_import(
            database,
            decisions,
            confirmed_database=database,
            credential_hasher=_cheap_hasher(),
        )
    database.chmod(0o600)

    authoritative = tmp_path / "authoritative.sqlite3"
    authoritative.write_bytes(database.read_bytes())
    authoritative.chmod(0o600)
    monkeypatch.setattr(auth_import, "AUTHORITATIVE_DATABASE", authoritative)
    before = authoritative.read_bytes()
    with pytest.raises(AuthImportError, match="authoritative"):
        preview_import(authoritative, decisions, credential_hasher=_cheap_hasher())
    assert authoritative.read_bytes() == before

    outside_root = tmp_path.parent / "not-authorized-import-target.sqlite3"
    with pytest.raises(AuthImportError, match="dedicated .runtime/auth-import"):
        preview_import(outside_root, decisions, credential_hasher=_cheap_hasher())


def test_database_and_decision_symlinks_hardlinks_and_permissions_are_refused(
    tmp_path, monkeypatch
):
    database = _database(tmp_path / "copy.sqlite3")
    decision_path = _decisions(tmp_path / "decisions.json")

    decision_path.chmod(0o644)
    with pytest.raises(AuthImportError, match="group or others"):
        load_decisions(decision_path)
    decision_path.chmod(0o600)

    decision_symlink = tmp_path / "decision-link.json"
    decision_symlink.symlink_to(decision_path)
    with pytest.raises(AuthImportError, match="symlink"):
        load_decisions(decision_symlink)
    decision_hardlink = tmp_path / "decision-hard.json"
    os.link(decision_path, decision_hardlink)
    with pytest.raises(AuthImportError, match="hard-linked"):
        load_decisions(decision_path)
    decision_hardlink.unlink()

    decisions = load_decisions(decision_path)
    database_symlink = tmp_path / "database-link.sqlite3"
    database_symlink.symlink_to(database)
    with pytest.raises(AuthImportError, match="symlink"):
        preview_import(database_symlink, decisions, credential_hasher=_cheap_hasher())
    database_hardlink = tmp_path / "database-hard.sqlite3"
    os.link(database, database_hardlink)
    with pytest.raises(AuthImportError, match="hard-linked"):
        preview_import(database, decisions, credential_hasher=_cheap_hasher())

    database_hardlink.unlink()
    alias_directory = tmp_path / "alias-directory"
    alias_directory.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AuthImportError, match="contain symlinks"):
        preview_import(
            alias_directory / database.name,
            decisions,
            credential_hasher=_cheap_hasher(),
        )

    narrow_root = tmp_path / "dedicated-root"
    narrow_root.mkdir()
    monkeypatch.setattr(auth_import, "IMPORT_DATABASE_ROOT", narrow_root)
    with pytest.raises(AuthImportError, match="dedicated .runtime/auth-import"):
        load_decisions(decision_path)


def test_preview_refuses_non_quiescent_database_sidecars(tmp_path):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    wal_path = Path(str(database) + "-wal")
    wal_path.touch()

    with pytest.raises(AuthImportError, match="quiescent"):
        preview_import(database, decisions, credential_hasher=_cheap_hasher())

    assert wal_path.exists()


def test_owner_detail_report_stays_below_runtime_and_is_mode_0600(
    tmp_path, monkeypatch
):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = load_decisions(_decisions(tmp_path / "decisions.json"))
    plan, _report = preview_import(
        database, decisions, credential_hasher=_cheap_hasher()
    )
    runtime_root = tmp_path / ".runtime"
    monkeypatch.setattr(auth_import, "IMPORT_DATABASE_ROOT", runtime_root)
    target = runtime_root / "auth-import" / "details.json"

    write_detailed_report(target, plan)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    details = json.loads(target.read_text(encoding="utf-8"))
    assert details["classification"] == "owner-only-local-do-not-commit"
    assert {row["legacyUserId"] for row in details["rows"]} == {
        101,
        102,
        103,
        104,
    }
    serialized = target.read_text(encoding="utf-8")
    assert "SafeToken" not in serialized
    assert "$argon2" not in serialized

    with pytest.raises(AuthImportError, match="only below .runtime"):
        write_detailed_report(tmp_path / "details.json", plan)


def test_cli_failure_is_categorical_and_never_leaks_source_values(tmp_path, capsys):
    database = _database(tmp_path / "copy.sqlite3")
    decisions = _decisions(tmp_path / "decisions.json", overrides=[])
    report = tmp_path / "aggregate.json"
    capsys.readouterr()

    assert (
        auth_import.main(
            [
                "preview",
                "--database",
                str(database),
                "--decisions",
                str(decisions),
                "--report",
                str(report),
            ]
        )
        == 1
    )

    output = capsys.readouterr()
    assert output.out == ""
    assert "canonical collision" in output.err
    assert not report.exists()
    for private_value in (
        "101",
        "Иванова",
        "ivanova-02",
        "SafeTokenA8",
        "$argon2",
    ):
        assert private_value not in output.err
