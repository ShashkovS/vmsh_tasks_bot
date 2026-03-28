from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


TABLES = ("groups", "users", "problems", "states")
GROUP_IDS = {"i27m", "i27p", "i27c"}
USER_IDS = {1, 2, 3, 10}


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _sanitize_users(rows: list[dict]) -> list[dict]:
    sanitized = []
    for row in rows:
        item = dict(row)
        item["chat_id"] = None
        if item.get("type") == 2:
            item["name"] = "Teacher"
            item["surname"] = "Seed"
            item["middlename"] = ""
            item["token"] = "teacher_seed"
            item["allowed_groups"] = ";i27m;i27p;i27c;"
            item["group_id"] = "i27c"
        sanitized.append(item)
    return sanitized


def export_seed(source: Path, output: Path) -> None:
    conn = sqlite3.connect(str(source))
    conn.row_factory = _dict_factory
    try:
        tables = {}
        for table_name in TABLES:
            rows = conn.execute(f"select * from {table_name} order by 1").fetchall()
            if table_name == "groups":
                rows = [row for row in rows if row["group_id"] in GROUP_IDS]
            elif table_name == "users":
                rows = [row for row in rows if row["id"] in USER_IDS]
            elif table_name == "problems":
                rows = [row for row in rows if row["group_id"] == "i27c"]
            elif table_name == "states":
                rows = [row for row in rows if row["user_id"] in USER_IDS]
            if table_name == "users":
                rows = _sanitize_users(rows)
            tables[table_name] = rows
    finally:
        conn.close()

    payload = {
        "meta": {
            "source_db": str(source),
            "notes": [
                "Derived from cleaned local DB snapshot",
                "Users are sanitized for deterministic in-repo tests",
                "Weekly richness is provided by per-test overlays",
            ],
        },
        "tables": tables,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="db/tlfedu.db")
    parser.add_argument("--output", default="tests/fixtures/live_seed.json")
    args = parser.parse_args()
    export_seed(Path(args.source), Path(args.output))


if __name__ == "__main__":
    main()
