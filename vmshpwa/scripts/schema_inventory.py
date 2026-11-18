"""Generate and verify the deterministic Phase-0 SQLite schema inventory."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from db_methods.pwa.migrations import apply_schema_migrations
from db_methods.pwa.schema_inventory import (
    SCHEMA_DRIFT_FORMAT,
    SchemaInventoryError,
    capture_schema_inventory,
    compare_schema_inventories,
    inventory_json,
    load_inventory,
    render_drift_markdown,
    render_schema_snapshot,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = REPOSITORY_ROOT / "pwa_tests/fixtures/schema_inventory.v1.json"
DEFAULT_SNAPSHOT = REPOSITORY_ROOT / "pwa_tests/fixtures/schema_snapshot.sql"
DEFAULT_DOCS_SNAPSHOT = REPOSITORY_ROOT / "docs/db_structure.sql"
DEFAULT_LIVE_REPORT_JSON = REPOSITORY_ROOT / "pwa_tests/reports/live-schema-drift.json"
DEFAULT_LIVE_REPORT_MD = REPOSITORY_ROOT / "pwa_tests/reports/live-schema-drift.md"


class ArtifactMismatchError(SchemaInventoryError):
    """Raised when a committed generated artifact is stale."""


def _require_canonical_write_path(path: Path, expected: Path, label: str) -> None:
    # These commands replace files atomically. Keeping their write set fixed is
    # safer than letting a mistyped --snapshot overwrite an unrelated database.
    if path.is_symlink() or path.absolute() != expected.absolute():
        raise SchemaInventoryError(
            f"{label} write target must be the canonical repository artifact"
        )


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _fresh_inventory() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vmsh-schema-inventory-") as directory:
        database_path = Path(directory) / "migration-head.sqlite3"
        apply_schema_migrations(database_path)
        return capture_schema_inventory(
            database_path,
            source_kind="repository-migration-head",
        )


def _assert_text(path: Path, expected: str) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ArtifactMismatchError(
            f"cannot read generated artifact {path}: {error}"
        ) from error
    if actual != expected:
        try:
            display_path = path.relative_to(REPOSITORY_ROOT)
        except ValueError:
            display_path = path
        raise ArtifactMismatchError(f"generated artifact is stale: {display_path}")


def generate_fresh_artifacts(
    *,
    inventory_path: Path = DEFAULT_INVENTORY,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    docs_snapshot_path: Path = DEFAULT_DOCS_SNAPSHOT,
    write: bool,
) -> dict[str, Any]:
    inventory = _fresh_inventory()
    inventory_content = inventory_json(inventory)
    snapshot_content = render_schema_snapshot(inventory)
    if write:
        _require_canonical_write_path(inventory_path, DEFAULT_INVENTORY, "inventory")
        _require_canonical_write_path(snapshot_path, DEFAULT_SNAPSHOT, "snapshot")
        _require_canonical_write_path(
            docs_snapshot_path, DEFAULT_DOCS_SNAPSHOT, "docs snapshot"
        )
        _write_atomic(inventory_path, inventory_content)
        _write_atomic(snapshot_path, snapshot_content)
        _write_atomic(docs_snapshot_path, snapshot_content)
    return inventory


def check_fresh_artifacts(
    *,
    inventory_path: Path = DEFAULT_INVENTORY,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    docs_snapshot_path: Path = DEFAULT_DOCS_SNAPSHOT,
) -> dict[str, Any]:
    inventory = _fresh_inventory()
    _assert_text(inventory_path, inventory_json(inventory))
    snapshot = render_schema_snapshot(inventory)
    _assert_text(snapshot_path, snapshot)
    _assert_text(docs_snapshot_path, snapshot)
    return inventory


def build_live_report(
    database_path: Path,
    *,
    inventory_path: Path = DEFAULT_INVENTORY,
) -> dict[str, Any]:
    expected = load_inventory(inventory_path)
    actual = capture_schema_inventory(
        database_path,
        source_kind="agreed-live-baseline",
        # This command fingerprints an acknowledged read-only snapshot. It must
        # report a deployment lag rather than mutate the database or pretend it
        # is runtime-ready; PwaConnectionFactory remains fail-closed at head.
        require_migration_head=False,
    )
    return compare_schema_inventories(expected, actual)


def write_live_report(
    database_path: Path,
    *,
    inventory_path: Path = DEFAULT_INVENTORY,
    json_path: Path = DEFAULT_LIVE_REPORT_JSON,
    markdown_path: Path = DEFAULT_LIVE_REPORT_MD,
) -> dict[str, Any]:
    report = build_live_report(database_path, inventory_path=inventory_path)
    _require_canonical_write_path(inventory_path, DEFAULT_INVENTORY, "inventory")
    _require_canonical_write_path(json_path, DEFAULT_LIVE_REPORT_JSON, "JSON report")
    _require_canonical_write_path(
        markdown_path, DEFAULT_LIVE_REPORT_MD, "Markdown report"
    )
    _write_atomic(
        json_path,
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    _write_atomic(markdown_path, render_drift_markdown(report))
    return report


def check_live_report(
    database_path: Path,
    *,
    inventory_path: Path = DEFAULT_INVENTORY,
    json_path: Path = DEFAULT_LIVE_REPORT_JSON,
    markdown_path: Path = DEFAULT_LIVE_REPORT_MD,
) -> dict[str, Any]:
    report = build_live_report(database_path, inventory_path=inventory_path)
    _assert_text(
        json_path,
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    _assert_text(markdown_path, render_drift_markdown(report))
    return report


def _path(value: str) -> Path:
    # Preserve the lexical path so the write guard can reject a symlink alias;
    # resolving here would make it indistinguishable from the approved target.
    return Path(value).absolute()


def _add_fresh_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--inventory", type=_path, default=DEFAULT_INVENTORY)
    parser.add_argument("--snapshot", type=_path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--docs-snapshot", type=_path, default=DEFAULT_DOCS_SNAPSHOT)


def _add_live_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", type=_path, required=True)
    parser.add_argument("--inventory", type=_path, default=DEFAULT_INVENTORY)
    parser.add_argument("--json-report", type=_path, default=DEFAULT_LIVE_REPORT_JSON)
    parser.add_argument("--markdown-report", type=_path, default=DEFAULT_LIVE_REPORT_MD)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="render fresh migration-head artifacts"
    )
    _add_fresh_paths(generate)
    generate.add_argument(
        "--write",
        action="store_true",
        help="atomically replace committed artifacts; without this flag nothing is written",
    )

    check = subparsers.add_parser("check", help="verify committed fresh artifacts")
    _add_fresh_paths(check)

    report_live = subparsers.add_parser(
        "report-live", help="produce a sanitized read-only live drift report"
    )
    _add_live_paths(report_live)
    report_live.add_argument(
        "--write",
        action="store_true",
        help="atomically replace report files; without this flag nothing is written",
    )

    check_live = subparsers.add_parser(
        "check-live", help="verify a live schema against the committed sanitized report"
    )
    _add_live_paths(check_live)
    return parser


def _summary(payload: Mapping[str, Any]) -> str:
    if payload.get("format") == SCHEMA_DRIFT_FORMAT:
        return json.dumps(
            {
                "format": payload["format"],
                "actual_product_sha256": payload["actual_product_sha256"],
                "known_schema_defects": [
                    defect["code"] for defect in payload["known_schema_defects"]
                ],
                "legacy_derived_count": len(payload["legacy_derived_objects"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    return json.dumps(
        {
            "format": payload["format"],
            "product_sha256": payload["product"]["sha256"],
            "product_object_count": payload["product"]["object_count"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "generate":
            result = generate_fresh_artifacts(
                inventory_path=arguments.inventory,
                snapshot_path=arguments.snapshot,
                docs_snapshot_path=arguments.docs_snapshot,
                write=arguments.write,
            )
        elif arguments.command == "check":
            result = check_fresh_artifacts(
                inventory_path=arguments.inventory,
                snapshot_path=arguments.snapshot,
                docs_snapshot_path=arguments.docs_snapshot,
            )
        elif arguments.command == "report-live":
            if arguments.write:
                result = write_live_report(
                    arguments.database,
                    inventory_path=arguments.inventory,
                    json_path=arguments.json_report,
                    markdown_path=arguments.markdown_report,
                )
            else:
                result = build_live_report(
                    arguments.database,
                    inventory_path=arguments.inventory,
                )
        elif arguments.command == "check-live":
            result = check_live_report(
                arguments.database,
                inventory_path=arguments.inventory,
                json_path=arguments.json_report,
                markdown_path=arguments.markdown_report,
            )
        else:  # pragma: no cover - argparse guarantees a known command.
            raise AssertionError(arguments.command)
    except SchemaInventoryError as error:
        print(f"schema inventory failed: {error}")
        return 1
    print(_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
