"""Read-only preview for linking existing Family accounts to Students."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from db_methods.pwa.family_link_import import (
    find_family_account_id,
    find_family_link,
    find_student_user_id,
)
from models.pwa.family_link_import import (
    FamilyLinkImportDiagnostic,
    FamilyLinkImportRow,
    parse_family_link_csv,
)


def _diagnostic(diagnostic: FamilyLinkImportDiagnostic) -> dict[str, object]:
    result: dict[str, object] = {"code": diagnostic.code}
    if diagnostic.row_number is not None:
        result["rowNumber"] = diagnostic.row_number
    return result


def _read_only_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _preview_row(
    connection: sqlite3.Connection,
    row: FamilyLinkImportRow,
) -> tuple[str | None, FamilyLinkImportDiagnostic | None]:
    family_account_id = find_family_account_id(
        connection,
        username_normalized=row.family_username_normalized,
    )
    if family_account_id is None:
        return None, FamilyLinkImportDiagnostic(
            row.row_number, "family_account_not_found"
        )

    student_user_id = find_student_user_id(
        connection,
        public_id=row.student_public_id,
    )
    if student_user_id is None:
        return None, FamilyLinkImportDiagnostic(row.row_number, "student_not_found")

    current = find_family_link(
        connection,
        family_account_id=family_account_id,
        student_user_id=student_user_id,
    )
    if current is None:
        return "create", None
    if current["revoked_at"] is not None:
        return "restore", None
    if (
        current["relationship_label"] == row.relationship_label
        and bool(current["is_primary"]) == row.is_primary
    ):
        return "unchanged", None
    return "update", None


def preview_family_link_import(
    *,
    database_path: Path,
    csv_path: Path,
) -> dict[str, object]:
    """Return a redacted preview and never open the database for writes."""

    source_bytes = csv_path.read_bytes()
    try:
        source = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {
            "schemaVersion": 1,
            "ready": False,
            "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
            "rowCount": 0,
            "validRowCount": 0,
            "actions": {"create": 0, "restore": 0, "update": 0, "unchanged": 0},
            "diagnostics": [{"code": "invalid_utf8"}],
        }

    parsed = parse_family_link_csv(source)
    diagnostics = list(parsed.diagnostics)
    actions = {"create": 0, "restore": 0, "update": 0, "unchanged": 0}
    if parsed.rows:
        with closing(_read_only_connection(database_path)) as connection:
            for row in parsed.rows:
                action, diagnostic = _preview_row(connection, row)
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                elif action is not None:
                    actions[action] += 1

    return {
        "schemaVersion": 1,
        "ready": not diagnostics,
        "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
        "rowCount": parsed.source_row_count,
        "validRowCount": len(parsed.rows),
        "actions": actions,
        # Row number plus a stable code is enough to repair the local source;
        # production usernames and Student IDs never enter the report.
        "diagnostics": [_diagnostic(item) for item in diagnostics],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview links between existing Family accounts and Students"
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    report = preview_family_link_import(
        database_path=arguments.database,
        csv_path=arguments.csv,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
