"""Read-only release proof; pwa_tests/reports/release-20261003/README.md.

Fresh sets add an empty slot table and display views. Compare prior tables, including
support receipts and raw Zoom events; output only counts and digests.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    path = Path(sys.argv[1]).resolve()
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as connection:
        connection.execute("BEGIN")
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        report = {}
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='content_problem_slots'"
        ).fetchone():
            assert (
                connection.execute(
                    "SELECT count(*) FROM content_problem_slots"
                ).fetchone()[0]
                == 0
            )
            assert (
                connection.execute("SELECT count(*) FROM active_problems").fetchone()[0]
                == connection.execute("SELECT count(*) FROM problems").fetchone()[0]
            )
            assert not connection.execute(
                "SELECT 1 FROM problems p JOIN problem_catalog c ON c.id=p.id WHERE p.public_id != c.public_id OR p.item != c.item LIMIT 1"
            ).fetchone()
            assert not connection.execute(
                "PRAGMA foreign_key_check(content_problem_slots)"
            ).fetchall()
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%yoyo%' AND name != 'content_problem_slots' ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            fields = ",".join(
                quote(row[1])
                for row in connection.execute(f"PRAGMA table_info({quote(table)})")
            )
            digest = hashlib.sha256()
            count = 0
            for row in connection.execute(
                f"SELECT {fields} FROM {quote(table)} ORDER BY {fields}"
            ):
                digest.update(repr(tuple(row)).encode())
                digest.update(b"\n")
                count += 1
            report[table] = {"count": count, "sha256": digest.hexdigest()}
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
