"""Private server proofs; vmshpwa/docs/paste-evidence.md and migration 0119."""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))


def facts(path):
    with sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True) as c:
        c.execute("BEGIN")
        assert c.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        foreign_keys = sorted(c.execute("PRAGMA foreign_key_check").fetchall(), key=repr)
        tables = {}
        for (table,) in c.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE '%yoyo%' ORDER BY name"
        ).fetchall():
            quote = lambda name: '"' + name.replace('"', '""') + '"'
            fields = [row[1] for row in c.execute(f"PRAGMA table_info({quote(table)})")]
            if table == "submission_entries" and "text_origin_json" in fields:
                fields.remove("text_origin_json")
            selected = ','.join(map(quote, fields))
            digest, count = hashlib.sha256(), 0
            for row in c.execute(f"SELECT {selected} FROM {quote(table)} ORDER BY {selected}"):
                digest.update(repr(tuple(row)).encode() + b"\n")
                count += 1
            tables[table] = {"count": count, "sha256": digest.hexdigest()}
        columns = [row[1] for row in c.execute("PRAGMA table_info(submission_entries)")]
        origin = "text_origin_json" in columns
        populated = c.execute("SELECT count(*) FROM submission_entries WHERE text_origin_json IS NOT NULL").fetchone()[0] if origin else 0
        return {"tables": tables, "integrity": "ok", "foreign_key_count": len(foreign_keys),
                "foreign_key_sha256": hashlib.sha256(repr(foreign_keys).encode()).hexdigest(),
                "has_origin_column": origin, "populated_origins": populated}


def compare(before, after):
    assert before["tables"] == after["tables"], "Existing product rows changed"
    assert before["foreign_key_count"] == after["foreign_key_count"]
    assert before["foreign_key_sha256"] == after["foreign_key_sha256"]
    assert not before["has_origin_column"] and after["has_origin_column"]
    assert after["populated_origins"] == 0
    return {"existing_tables_preserved": len(before["tables"]), "existing_rows_preserved": sum(t["count"] for t in before["tables"].values()),
            "nullable_origin_column": "pass", "foreign_key_violations_preserved": True, "integrity": "ok"}


def rehearse(path):
    import yoyo
    from db_methods.pwa.migrations import apply_schema_migrations, require_current_schema
    before = facts(path)
    apply_schema_migrations(path)
    checked = compare(before, facts(path))
    selected = [item for item in yoyo.read_migrations("migrations") if item.id == "0119.text_origin"]
    assert len(selected) == 1
    with yoyo.get_backend(f"sqlite:///{Path(path).resolve()}") as backend, backend.lock():
        backend.rollback_migrations(selected)
    assert facts(path) == before
    apply_schema_migrations(path)
    compare(before, facts(path))
    require_current_schema(path)
    checked["up_down_up"] = "pass"
    return checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["facts", "rehearse", "compare"])
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    result = facts(args.paths[0]) if args.mode == "facts" else rehearse(args.paths[0]) if args.mode == "rehearse" else compare(*(json.loads(Path(p).read_text()) for p in args.paths))
    print(json.dumps(result, sort_keys=True))
