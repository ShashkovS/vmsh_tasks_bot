"""Read-only cutover proof; vmshpwa/docs/problem-release.md.

Compare every prior product column and validate the independent release state.
Only counts and digests leave the database; authored content stays private.
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
            "AND name NOT IN ('lesson_problem_release','lesson_problem_release_events') "
            "ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info({quote(table)})")
                if not (table == "group_lessons" and row[1] == "problem_release_version")
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
        if args.baseline:
            assert not connection.execute(
                "SELECT 1 FROM group_lessons WHERE problem_release_version!=1 LIMIT 1"
            ).fetchone(), "Release version did not start at one"
            for table in ("lesson_problem_release", "lesson_problem_release_events"):
                assert not connection.execute(f"PRAGMA foreign_key_check({table})").fetchall()
                assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
            triggers = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                )
            }
            assert {
                "lesson_problem_release_events_no_update",
                "lesson_problem_release_events_no_delete",
            } <= triggers, "Release audit is missing immutable guards"
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
