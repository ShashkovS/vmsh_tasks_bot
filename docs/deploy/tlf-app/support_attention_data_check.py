"""Read-only migration proof; see vmshpwa/docs/question-attention.md.

Digest every existing product table, excluding only the new receipt table.
Reports contain counts/hashes, never messages or personal data.
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
        connection.execute("BEGIN")
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        report = {}
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%yoyo%' "
            "AND name!='support_entry_reads' ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info({quote(table)})")
            ]
            fields = ",".join(map(quote, columns))
            digest = hashlib.sha256()
            count = 0
            for row in connection.execute(
                f"SELECT {fields} FROM {quote(table)} ORDER BY {fields}"
            ):
                digest.update(repr(tuple(row)).encode())
                digest.update(b"\n")
                count += 1
            report[table] = {"count": count, "sha256": digest.hexdigest()}
        has_receipts = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='support_entry_reads'"
        ).fetchone()
        if has_receipts:
            assert not connection.execute(
                "SELECT 1 FROM support_entry_reads r "
                "LEFT JOIN support_entries e ON e.id=r.entry_id "
                "LEFT JOIN support_threads t ON t.id=e.thread_id "
                "WHERE e.id IS NULL OR t.id IS NULL "
                "OR e.author_kind NOT IN ('teacher','admin') "
                "OR r.student_user_id!=t.student_user_id "
                "OR r.read_at<e.server_received_at LIMIT 1"
            ).fetchone(), "Invalid support read receipt"
        if args.baseline:
            assert has_receipts, "Receipt table is missing"
            assert not connection.execute(
                "SELECT 1 FROM support_entries e "
                "WHERE e.author_kind IN ('teacher','admin') "
                "AND NOT EXISTS(SELECT 1 FROM support_entry_reads r "
                "WHERE r.entry_id=e.id) LIMIT 1"
            ).fetchone(), "Existing reply was not backfilled"
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
