"""Read-only cutover proof for figure layout; vmshpwa/dev/figure-layout-report.md.

Compare all existing product columns across migration 0106, and validate the
new frozen legacy scales. Reports contain counts/digests, never content rows.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> None:
    database = Path(sys.argv[1]).resolve()
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
        connection.execute("BEGIN")
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        report = {}
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%yoyo%' ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info({quote(table)})")
                if not (
                    table == "publication_figure_layouts"
                    and row[1] == "legacy_scales_json"
                )
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
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(publication_figure_layouts)"
            )
        }
        if "legacy_scales_json" in columns:
            for publication_id, revision_id, frozen in connection.execute(
                "SELECT layout.publication_id, publication.revision_id, layout.legacy_scales_json "
                "FROM publication_figure_layouts layout JOIN lesson_publications publication "
                "ON publication.id=layout.publication_id WHERE layout.layout_version=-1"
            ):
                expected = dict(
                    connection.execute(
                        "SELECT asset_id, scale FROM content_figure_scales WHERE revision_id=?",
                        (revision_id,),
                    )
                )
                assert json.loads(frozen) == expected, publication_id
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
