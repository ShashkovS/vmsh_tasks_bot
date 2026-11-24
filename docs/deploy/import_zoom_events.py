"""Append a reviewed legacy TSV to zoom_events; see zoom-events-import-20261008/STATUS.md.

Uses only stdlib and never starts the application. Preview is read-only; apply
requires a new verified online backup, then replans within one write transaction.
"""

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import time


COLUMNS = (
    "id", "event_ts", "event", "zoom_user_name", "zoom_user_id",
    "breakout_room_uuid", "user_id",
)
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM zoom_events ORDER BY id"
INSERT = "INSERT INTO zoom_events (" + ",".join(COLUMNS) + ") VALUES (?,?,?,?,?,?,?)"
NULLS = {"", "\\N", "NULL"}


def read_source(path, expected_sha256):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Source SHA256 differs from the reviewed dump")
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter="\t")
    if tuple(next(reader, ())) != COLUMNS:
        raise ValueError("Unexpected TSV header")
    rows = []
    ids = set()
    for number, row in enumerate(reader, 2):
        if len(row) != len(COLUMNS):
            raise ValueError(f"Unexpected column count at TSV record {number}")
        source_id = int(row[0])
        if source_id <= 0 or source_id in ids:
            raise ValueError(f"Invalid or repeated source ID at TSV record {number}")
        ids.add(source_id)
        timestamp = datetime.fromisoformat(row[1])
        if timestamp.tzinfo is not None or not row[2]:
            raise ValueError(f"Invalid legacy timestamp/event at TSV record {number}")
        rows.append((source_id, row[1], row[2], *(
            None if value in NULLS else value for value in row[3:]
        )))
    if not rows:
        raise ValueError("The dump is empty")
    # SQLite affinity matches the existing adapter, including textual Zoom IDs
    # stored in the INTEGER-affinity column. No float/manual coercion is used.
    with closing(sqlite3.connect(":memory:")) as stage:
        stage.execute("CREATE TABLE zoom_events (id INTEGER PRIMARY KEY, "
                      "event_ts TIMESTAMP NOT NULL, event TEXT NOT NULL, "
                      "zoom_user_name TEXT, zoom_user_id INTEGER, "
                      "breakout_room_uuid TEXT, user_id INTEGER)")
        stage.executemany(INSERT, rows)
        rows = stage.execute(SELECT).fetchall()
    return rows, digest


def check_schema(db):
    if tuple(row[1] for row in db.execute("PRAGMA table_info(zoom_events)")) != COLUMNS:
        raise ValueError("Unexpected target zoom_events schema")
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' "
                  "AND tbl_name='zoom_events'").fetchone():
        raise ValueError("Target has Zoom triggers; review their effects before importing")


def plan(db, source):
    check_schema(db)
    existing = db.execute(SELECT).fetchall()
    available = Counter(row[1:] for row in existing)
    used_ids = {row[0] for row in existing}
    next_id = max(used_ids | {row[0] for row in source}) + 1
    additions = []
    reassigned = 0
    for row in source:
        content = row[1:]
        if available[content]:
            available[content] -= 1
            continue
        source_id = row[0]
        if source_id in used_ids:
            source_id = next_id
            next_id += 1
            reassigned += 1
        used_ids.add(source_id)
        additions.append((source_id, *content))
    user_ids = {row[-1] for row in source if row[-1] is not None}
    for user_id in user_ids:
        if not isinstance(user_id, int) or not db.execute(
            "SELECT 1 FROM users WHERE id=?", (user_id,)
        ).fetchone():
            raise ValueError("Dump contains an unresolved internal user ID")
    return existing, additions, reassigned


def online_backup(database, destination):
    destination = destination.resolve()
    if destination == database.resolve():
        raise ValueError("Backup must not be the live database")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst, pages=256, sleep=0.01)
            if dst.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("Backup integrity check failed; import was not started")
    return str(destination)


def run(database, source_path, source_sha256, *, apply=False, backup=None):
    source, digest = read_source(source_path, source_sha256)
    target = database.resolve()
    if not target.is_file():
        raise ValueError("Existing target database is required")
    mode = "rw" if apply else "ro"
    backup_path = None
    if apply:
        if backup is None:
            raise ValueError("Apply requires a fresh backup path")
        if not os.access(target, os.W_OK):
            raise PermissionError("Run as the database owner; target is not writable")
        backup_path = online_backup(target, backup)
    with closing(sqlite3.connect(target.as_uri() + "?mode=" + mode, uri=True,
                                isolation_level=None, timeout=1)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if apply:
            db.execute("PRAGMA synchronous=FULL")
        else:
            db.execute("PRAGMA query_only=ON")
        started = time.monotonic()
        db.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            existing, additions, reassigned = plan(db, source)
            queue = db.execute("SELECT * FROM zoom_queue ORDER BY zoom_user_name").fetchall()
            if apply:
                db.executemany(INSERT, additions)
                after = db.execute(SELECT).fetchall()
                if not set(existing).issubset(set(after)):
                    raise RuntimeError("Pre-existing Zoom events changed")
                if Counter(row[1:] for row in source) - Counter(row[1:] for row in after):
                    raise RuntimeError("Imported content/multiplicity verification failed")
                if len(after) != len(existing) + len(additions):
                    raise RuntimeError("Unexpected row count after import")
                if queue != db.execute("SELECT * FROM zoom_queue ORDER BY zoom_user_name").fetchall():
                    raise RuntimeError("Zoom queue changed during import")
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return {
        "mode": "apply" if apply else "preview",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(target), "source_sha256": digest,
        "source_rows": len(source), "source_id_min": min(row[0] for row in source),
        "source_id_max": max(row[0] for row in source),
        "source_event_ts_min": min(row[1] for row in source),
        "source_event_ts_max": max(row[1] for row in source),
        "existing_rows": len(existing), "rows_to_insert": len(additions),
        "already_present": len(source) - len(additions),
        "source_ids_reassigned": reassigned,
        "rows_after": len(existing) + (len(additions) if apply else 0),
        "source_event_types": dict(Counter(row[2] for row in source)),
        "existing_events_preserved": True, "zoom_queue_preserved": True,
        "transaction_seconds": round(time.monotonic() - started, 4),
        "backup": backup_path, "backup_integrity": "ok" if backup_path else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preview", "apply"))
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        # Reserve the evidence file before touching the database. A reused or
        # unwritable report path must not fail only after a successful commit.
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            try:
                result = run(args.database, args.source, args.source_sha256,
                             apply=args.mode == "apply", backup=args.backup)
            except Exception as error:
                json.dump({"ok": False, "error_type": type(error).__name__,
                           "error": str(error)}, handle)
                handle.write("\n")
                raise
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        # Errors contain only operator context, never TSV participant values.
        print(json.dumps({"ok": False, "error_type": type(error).__name__,
                          "error": str(error)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
