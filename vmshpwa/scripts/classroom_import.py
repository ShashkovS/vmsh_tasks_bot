"""Preview or apply the one-time classroom Excel export."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from db_methods.pwa.migrations import require_current_schema
from helpers.pwa.classroom_import import read_classroom_export
from models.pwa.classroom_import import (
    analyze_classroom_import,
    apply_classroom_import,
)


def _connection(path: Path, *, read_only: bool) -> sqlite3.Connection:
    target = f"{path.resolve().as_uri()}?mode=ro" if read_only else str(path)
    connection = sqlite3.connect(target, uri=read_only, autocommit=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _write_report(report: dict[str, object], path: Path | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(text, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Classroom import report: {path}")


def preview(args: argparse.Namespace) -> dict[str, object]:
    database = Path(args.database).resolve()
    require_current_schema(database)
    source_hash, header_row, rows = read_classroom_export(
        args.xlsx, sheet_name=args.sheet
    )
    with _connection(database, read_only=True) as connection:
        report, _plan = analyze_classroom_import(
            connection,
            event_public_id=args.event,
            source_sha256=source_hash,
            source_sheet=args.sheet,
            header_row=header_row,
            rows=rows,
        )
    _write_report(report, None if args.report is None else Path(args.report))
    return report


def apply(args: argparse.Namespace) -> dict[str, object]:
    database = Path(args.database).resolve()
    if database != Path(args.confirm_database).resolve():
        raise RuntimeError("--confirm-database must name the exact apply target")
    require_current_schema(database)
    source_hash, header_row, rows = read_classroom_export(
        args.xlsx, sheet_name=args.sheet
    )
    with _connection(database, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            receipt = apply_classroom_import(
                connection,
                event_public_id=args.event,
                source_sha256=source_hash,
                source_sheet=args.sheet,
                header_row=header_row,
                rows=rows,
                confirmed_source_sha256=args.confirm_source_sha256,
                confirmed_preview_sha256=args.confirm_preview_sha256,
                actor_user_id=args.actor_user_id,
                now=datetime.now(UTC).isoformat(),
            )
        except Exception:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")
    _write_report(receipt, None if args.report is None else Path(args.report))
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "apply"):
        item = subparsers.add_parser(command)
        item.add_argument("--database", required=True)
        item.add_argument("--xlsx", required=True)
        item.add_argument("--sheet", default="Итог")
        item.add_argument("--event", required=True)
        item.add_argument("--report")
        if command == "apply":
            item.add_argument("--confirm-database", required=True)
            item.add_argument("--confirm-source-sha256", required=True)
            item.add_argument("--confirm-preview-sha256", required=True)
            item.add_argument("--actor-user-id", required=True, type=int)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "preview":
        preview(args)
    else:
        apply(args)


if __name__ == "__main__":
    main()
