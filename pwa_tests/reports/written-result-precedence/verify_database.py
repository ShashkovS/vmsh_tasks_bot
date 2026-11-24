"""Verify a stopped-writer 0110 cutover against its consistent backup.

See written-result-precedence/README.md. Emit counts only; compare the whole
product ledger, manual pointers and existing foreign-key violations in memory.
"""

import argparse
import json
import sqlite3
from pathlib import Path

from .rehearse import current, fingerprints
from db_methods.pwa.migrations import require_current_schema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    require_current_schema(args.after)
    with (
        sqlite3.connect(
            args.before.resolve().as_uri() + "?mode=ro", uri=True
        ) as before,
        sqlite3.connect(args.after.resolve().as_uri() + "?mode=ro", uri=True) as after,
    ):
        assert after.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        keys = before.execute("PRAGMA foreign_key_check").fetchall()
        assert after.execute("PRAGMA foreign_key_check").fetchall() == keys
        tables = fingerprints(before)
        assert fingerprints(after) == tables
        query = (
            "SELECT student_id,problem_id,result_id FROM live_mark_cells "
            "WHERE result_id IS NOT NULL ORDER BY 1,2"
        )
        pointers = before.execute(query).fetchall()
        assert after.execute(query).fetchall() == pointers
        old, new = current(before), current(after)
        changed = [k for k in old.keys() | new.keys() if old.get(k) != new.get(k)]
        repaired = [
            k
            for k in changed
            if old.get(k, (0, 0, 0))[2] < 0.8 and new.get(k, (0, 0, 0))[2] >= 0.8
        ]
        schema_objects = after.execute(
            "SELECT count(*) FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' "
            "AND name NOT IN ('_yoyo_log','_yoyo_migration','_yoyo_version','yoyo_lock')"
        ).fetchone()[0]
        print(
            json.dumps(
                dict(
                    integrity="ok",
                    unchangedProductTables=len(tables),
                    resultsCount=tables["results"]["count"],
                    retainedManualPointers=len(pointers),
                    existingForeignKeyViolations=len(keys),
                    newForeignKeyViolations=0,
                    changedCurrentResults=len(changed),
                    repairedAcceptedResults=len(repaired),
                    schemaObjects=schema_objects,
                ),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
