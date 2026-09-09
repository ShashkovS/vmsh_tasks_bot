from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT, apply_schema_migrations
from db_methods.pwa.schema_inventory import (
    SchemaInventoryError,
    UnknownDerivedObjectError,
    capture_schema_inventory,
    compare_schema_inventories,
    inventory_json,
    load_inventory,
    render_drift_markdown,
    render_schema_snapshot,
    validate_inventory,
)
from vmshpwa.scripts.schema_inventory import (
    DEFAULT_DOCS_SNAPSHOT,
    DEFAULT_INVENTORY,
    DEFAULT_LIVE_REPORT_JSON,
    DEFAULT_LIVE_REPORT_MD,
    DEFAULT_SNAPSHOT,
    main as schema_inventory_main,
)


def _migrated_database(path: Path) -> Path:
    apply_schema_migrations(path)
    return path


def _inventory(path: Path, source_kind: str = "test-migration-head") -> dict:
    return capture_schema_inventory(path, source_kind=source_kind)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def test_privacy_key_walker_descends_into_report_arrays():
    assert list(_walk_keys({"outer": [{"value": "private"}]})) == [
        "outer",
        "value",
    ]


def test_inventory_is_deterministic_and_does_not_read_rows(tmp_path):
    first_path = _migrated_database(tmp_path / "first.sqlite3")
    second_path = _migrated_database(tmp_path / "second.sqlite3")
    sentinel = "SENTINEL-MUST-NEVER-ENTER-SCHEMA-INVENTORY"
    with sqlite3.connect(second_path) as connection:
        connection.execute(
            "INSERT INTO kv(key, value) VALUES (?, ?)", ("probe", sentinel)
        )

    first = _inventory(first_path)
    second = _inventory(second_path)

    assert first == second
    rendered_json = inventory_json(second)
    rendered_sql = render_schema_snapshot(second)
    assert sentinel not in rendered_json
    assert sentinel not in rendered_sql
    assert "insert into" not in rendered_sql.casefold()
    assert second["product"]["object_count"] == 429
    assert second["legacy_derived"]["object_count"] == 0
    assert all(
        not record["name"].startswith("sqlite_") and "yoyo" not in record["name"]
        for record in second["product"]["objects"]
    )


def test_inventory_read_is_non_mutating(tmp_path):
    database_path = _migrated_database(tmp_path / "read-only.sqlite3")
    before = database_path.stat()

    _inventory(database_path)

    after = database_path.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)


def test_inventory_detects_schema_drift(tmp_path):
    database_path = _migrated_database(tmp_path / "drift.sqlite3")
    before = _inventory(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "ALTER TABLE kv ADD COLUMN revision INTEGER NOT NULL DEFAULT 0"
        )

    after = _inventory(database_path)
    report = compare_schema_inventories(before, after)

    assert before["product"]["sha256"] != after["product"]["sha256"]
    assert {record["name"] for record in report["ddl_text_differences"]} == {"kv"}
    assert {record["name"] for record in report["pragma_structure_differences"]} == {
        "kv"
    }


def test_live_report_redacts_default_literals_and_view_sql(tmp_path):
    expected_path = _migrated_database(tmp_path / "expected.sqlite3")
    actual_path = _migrated_database(tmp_path / "actual.sqlite3")
    sentinel = "SENTINEL-LIVE-SCHEMA-SECRET"
    with sqlite3.connect(actual_path) as connection:
        connection.execute(f"ALTER TABLE kv ADD COLUMN probe TEXT DEFAULT '{sentinel}'")
        connection.execute("DROP VIEW reaction_view")
        connection.execute(
            f"CREATE VIEW reaction_view AS SELECT '{sentinel}' AS private_literal"
        )

    report = compare_schema_inventories(
        _inventory(expected_path),
        _inventory(actual_path),
    )
    rendered = json.dumps(report, ensure_ascii=False)

    assert sentinel not in rendered
    assert "default_sql" not in rendered
    assert {item["name"] for item in report["pragma_structure_differences"]} >= {
        "kv",
        "reaction_view",
    }


def test_allowlisted_derived_object_definition_changes_live_report(tmp_path):
    expected_path = _migrated_database(tmp_path / "expected.sqlite3")
    actual_path = _migrated_database(tmp_path / "actual.sqlite3")
    sentinel = "SENTINEL-DERIVED-SECRET"
    with sqlite3.connect(actual_path) as connection:
        connection.execute("CREATE TABLE temp_user_decoder (id INTEGER PRIMARY KEY)")
    first = compare_schema_inventories(
        _inventory(expected_path),
        _inventory(actual_path),
    )
    with sqlite3.connect(actual_path) as connection:
        connection.execute("DROP TABLE temp_user_decoder")
        connection.execute(
            "CREATE TABLE temp_user_decoder "
            f"(id INTEGER PRIMARY KEY, probe TEXT DEFAULT '{sentinel}')"
        )
    second = compare_schema_inventories(
        _inventory(expected_path),
        _inventory(actual_path),
    )

    assert first["legacy_derived_objects"] != second["legacy_derived_objects"]
    assert sentinel not in json.dumps(second, ensure_ascii=False)


def test_yoyo_infrastructure_schema_drift_is_detected_without_literals(tmp_path):
    expected_path = _migrated_database(tmp_path / "expected.sqlite3")
    actual_path = _migrated_database(tmp_path / "actual.sqlite3")
    sentinel = "SENTINEL-YOYO-SECRET"
    expected = _inventory(expected_path)
    with sqlite3.connect(actual_path) as connection:
        connection.execute(
            f"ALTER TABLE _yoyo_log ADD COLUMN probe TEXT DEFAULT '{sentinel}'"
        )
    actual = _inventory(actual_path)
    report = compare_schema_inventories(expected, actual)

    assert (
        expected["migration"]["infrastructure"]["sha256"]
        != actual["migration"]["infrastructure"]["sha256"]
    )
    assert sentinel not in json.dumps(report, ensure_ascii=False)


def test_unreviewed_persistent_temp_object_fails_closed(tmp_path):
    database_path = _migrated_database(tmp_path / "unknown-temp.sqlite3")
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE temp_unreviewed (id INTEGER PRIMARY KEY)")

    with pytest.raises(UnknownDerivedObjectError, match="temp_unreviewed"):
        _inventory(database_path)


def test_legacy_yoyo_history_does_not_change_product_hash(tmp_path):
    database_path = _migrated_database(tmp_path / "legacy-history.sqlite3")
    before = _inventory(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO _yoyo_migration "
            "(migration_hash, migration_id, applied_at_utc) VALUES (?, ?, ?)",
            ("legacy-hash", "0001.synthetic", "2020-01-01T00:00:00Z"),
        )

    after = _inventory(database_path)

    assert after["product"] == before["product"]
    assert after["migration"]["legacy_history"]["count"] == 1
    assert (
        after["migration"]["legacy_history"]["sha256"]
        != before["migration"]["legacy_history"]["sha256"]
    )


@pytest.mark.parametrize("migration_id", ["9999.future", "future-without-number"])
def test_future_or_unparseable_yoyo_history_fails_closed(tmp_path, migration_id):
    database_path = _migrated_database(tmp_path / f"{migration_id}.sqlite3")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO _yoyo_migration "
            "(migration_hash, migration_id, applied_at_utc) VALUES (?, ?, ?)",
            ("future-hash", migration_id, "2026-07-27T00:00:00Z"),
        )

    with pytest.raises(SchemaInventoryError, match=f"unexpected={migration_id}"):
        _inventory(database_path)


def test_schema_snapshot_round_trips_without_yoyo_or_data(tmp_path):
    source_path = _migrated_database(tmp_path / "source.sqlite3")
    source = _inventory(source_path)
    snapshot = render_schema_snapshot(source)
    target_path = tmp_path / "snapshot.sqlite3"
    with sqlite3.connect(target_path) as connection:
        connection.executescript(snapshot)

    target = capture_schema_inventory(
        target_path,
        source_kind="schema-snapshot-roundtrip",
        require_migration_head=False,
    )

    assert target["product"] == source["product"]
    with sqlite3.connect(target_path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT count(*) FROM kv_logins").fetchone()[0] == 0


def test_inventory_validation_rejects_tampered_hash():
    inventory = load_inventory(DEFAULT_INVENTORY)
    tampered = copy.deepcopy(inventory)
    tampered["product"]["objects"][0]["sql"] += " -- changed"

    with pytest.raises(SchemaInventoryError, match="not normalized|hash mismatch"):
        validate_inventory(tampered)


def test_inventory_validation_rejects_false_migration_readiness():
    inventory = load_inventory(DEFAULT_INVENTORY)
    tampered = copy.deepcopy(inventory)
    tampered["migration"]["repository_head_status"] = {
        "is_current": True,
        "missing": ["0039.pwa_auth_accounts_sessions"],
        "changed": [],
        "unexpected": [],
    }

    with pytest.raises(SchemaInventoryError, match="migration-head status"):
        validate_inventory(tampered)


def test_committed_fresh_artifacts_match_repository_migrations(tmp_path):
    database_path = _migrated_database(tmp_path / "committed.sqlite3")
    generated = capture_schema_inventory(
        database_path,
        source_kind="repository-migration-head",
    )
    expected = load_inventory(DEFAULT_INVENTORY)
    snapshot = render_schema_snapshot(generated)

    assert generated == expected
    assert DEFAULT_SNAPSHOT.read_text(encoding="utf-8") == snapshot
    assert DEFAULT_DOCS_SNAPSHOT.read_text(encoding="utf-8") == snapshot


def test_committed_live_report_is_sanitized_and_documents_known_defects():
    report = json.loads(DEFAULT_LIVE_REPORT_JSON.read_text(encoding="utf-8"))
    markdown = DEFAULT_LIVE_REPORT_MD.read_text(encoding="utf-8")

    assert {defect["code"] for defect in report["known_schema_defects"]} == {
        "LIVE_REACTION_ENUM_TYPE_FK_MISSING",
        "LIVE_REACTIONS_ZOOM_FK_TARGET_INVALID",
    }
    assert len(report["legacy_derived_objects"]) == 12
    assert report["migration"]["repository_head_status"] == {
        "is_current": False,
        "missing": [
            "0039.pwa_auth_accounts_sessions",
            "0040.pwa_courses_access",
        ],
        "changed": [],
        "unexpected": [],
    }
    assert all(
        key not in {"row", "rows", "value", "values"} for key in _walk_keys(report)
    )
    report_strings = tuple(_walk_strings(report))
    assert all(str(Path.home()) not in value for value in report_strings)
    assert all("default_sql" not in value for value in report_strings)
    assert "Product row values were not selected" in markdown
    assert "Repository migration head current: false" in markdown
    assert render_drift_markdown(report) == markdown


def test_live_report_records_migration_lag_without_mutating_database(tmp_path):
    database_path = tmp_path / "behind.sqlite3"
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT)).filter(
        lambda migration: (
            migration.id
            not in {
                "0039.pwa_auth_accounts_sessions",
                "0040.pwa_courses_access",
                # Rebuilding a legacy table makes SQLite reparse every trigger;
                # this intentionally inconsistent lag fixture omits auth tables,
                # so it must also stay behind the Phase-6 rebuild.
                "0051.pwa_review_queue_leases",
                # This migration adds the owner-only provisioning column
                # and therefore cannot be applied to the no-auth lag fixture.
                "0076.pwa_account_provisioning_batches",
            }
        )
    )
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))
    before = database_path.read_bytes()

    expected = _inventory(_migrated_database(tmp_path / "head.sqlite3"))
    actual = capture_schema_inventory(
        database_path,
        source_kind="agreed-live-baseline",
        require_migration_head=False,
    )
    report = compare_schema_inventories(expected, actual)

    assert report["migration"]["repository_head_status"]["missing"] == [
        "0039.pwa_auth_accounts_sessions",
        "0040.pwa_courses_access",
        "0051.pwa_review_queue_leases",
        "0076.pwa_account_provisioning_batches",
    ]
    assert {item["name"] for item in report["missing_product_objects"]} >= {
        "auth_accounts",
        "courses",
    }
    assert database_path.read_bytes() == before


def test_generate_cli_requires_explicit_write_flag(tmp_path):
    inventory_path = tmp_path / "inventory.json"
    snapshot_path = tmp_path / "snapshot.sql"
    docs_path = tmp_path / "docs.sql"

    exit_code = schema_inventory_main(
        [
            "generate",
            "--inventory",
            str(inventory_path),
            "--snapshot",
            str(snapshot_path),
            "--docs-snapshot",
            str(docs_path),
        ]
    )

    assert exit_code == 0
    assert not inventory_path.exists()
    assert not snapshot_path.exists()
    assert not docs_path.exists()


def test_generate_cli_refuses_noncanonical_write_targets(tmp_path):
    target = tmp_path / "must-not-be-written.json"

    exit_code = schema_inventory_main(
        [
            "generate",
            "--inventory",
            str(target),
            "--write",
        ]
    )

    assert exit_code == 1
    assert not target.exists()


def test_generate_cli_refuses_symlink_alias_to_canonical_target(tmp_path):
    alias = tmp_path / "inventory-alias.json"
    alias.symlink_to(DEFAULT_INVENTORY)
    before = DEFAULT_INVENTORY.read_bytes()

    exit_code = schema_inventory_main(
        [
            "generate",
            "--inventory",
            str(alias),
            "--write",
        ]
    )

    assert exit_code == 1
    assert alias.is_symlink()
    assert DEFAULT_INVENTORY.read_bytes() == before


def test_live_report_cli_refuses_noncanonical_write_targets(tmp_path):
    database_path = _migrated_database(tmp_path / "source.sqlite3")
    target = tmp_path / "must-not-be-written.json"

    exit_code = schema_inventory_main(
        [
            "report-live",
            "--database",
            str(database_path),
            "--json-report",
            str(target),
            "--write",
        ]
    )

    assert exit_code == 1
    assert not target.exists()
