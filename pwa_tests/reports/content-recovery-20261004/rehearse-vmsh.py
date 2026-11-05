"""Rehearse 0112 on a server-only consistent copy; export counts/digests only.

Run with the production interpreter via SSH, supplying base64 migration bytes.
No application config, credentials, live DML or educational publication.
"""

import base64
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import yoyo


ROOT = Path("/web/vmsh_tasks_bot/vmsh_tasks_bot")
MIGRATION_ID = "0112.scheduled_publication_lifecycle"


def product_snapshot(connection):
    result = {}
    for (name,) in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_yoyo%' "
        "AND name <> 'yoyo_lock' ORDER BY name"
    ):
        quoted = '"' + name.replace('"', '""') + '"'
        digest = hashlib.sha256()
        count = 0
        try:
            rows = connection.execute(f"SELECT * FROM {quoted} ORDER BY rowid")
        except sqlite3.OperationalError:
            columns = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
            order = ", ".join('"' + row[1].replace('"', '""') + '"' for row in columns)
            rows = connection.execute(f"SELECT * FROM {quoted} ORDER BY {order}")
        for row in rows:
            digest.update(repr(row).encode())
            digest.update(b"\n")
            count += 1
        result[name] = {"count": count, "sha256": digest.hexdigest()}
    return result


directory = Path(tempfile.mkdtemp(prefix="vmsh-content-recovery-"))
try:
    database = directory / "rehearsal.sqlite3"
    with sqlite3.connect(
        f"file:{ROOT / 'db/production_v2.db'}?mode=ro", uri=True
    ) as live:
        with sqlite3.connect(database) as copy:
            live.backup(copy, pages=256, sleep=0.05)
    with sqlite3.connect(database) as copy:
        fk_errors_before = sorted(copy.execute("PRAGMA foreign_key_check").fetchall())
        before = product_snapshot(copy)
        objects_before = copy.execute(
            "SELECT type, name, sql FROM sqlite_schema WHERE sql IS NOT NULL "
            "AND name NOT LIKE '_yoyo%' AND name <> 'yoyo_lock' ORDER BY type, name"
        ).fetchall()
    migrations = directory / "migrations"
    migrations.mkdir()
    shutil.copyfile(
        ROOT / "migrations/0111.current_schema.sql",
        migrations / "0111.current_schema.sql",
    )
    migration_bytes = base64.b64decode(sys.argv[1], validate=True)
    migration_path = migrations / f"{MIGRATION_ID}.py"
    migration_path.write_bytes(migration_bytes)
    started = time.monotonic()
    migration_list = yoyo.read_migrations(str(migrations))
    with yoyo.get_backend(f"sqlite:///{database}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migration_list))
    migration_seconds = time.monotonic() - started
    migration_file = next(item for item in migration_list if item.id == MIGRATION_ID)
    migration_file.load()
    migration = vars(migration_file.module)
    with sqlite3.connect(database) as copy:
        after = product_snapshot(copy)
        objects_after = copy.execute(
            "SELECT type, name, sql FROM sqlite_schema WHERE sql IS NOT NULL "
            "AND name NOT LIKE '_yoyo%' AND name <> 'yoyo_lock' ORDER BY type, name"
        ).fetchall()
        changed_objects = [
            name
            for kind, name, sql in objects_after
            if (kind, name, sql) not in objects_before
        ]
        assert changed_objects == ["lesson_publications"], changed_objects
        assert before == after
        assert copy.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (
            sorted(copy.execute("PRAGMA foreign_key_check").fetchall())
            == fk_errors_before
        )
        active = copy.execute(
            "SELECT id, activated_from_schedule_id FROM lesson_publications "
            "WHERE group_lesson_id=13 AND kind='condition' AND state='published'"
        ).fetchone()
        assert active and active[1] is not None
        for state in ("superseded", "hidden"):
            copy.execute("SAVEPOINT lifecycle_probe")
            copy.execute(
                "UPDATE lesson_publications SET state=?, version=version+1, "
                "terminal_by_user_id=published_by_user_id, terminal_at=updated_at, "
                "hidden_at=CASE WHEN ?='hidden' THEN updated_at ELSE hidden_at END WHERE id=?",
                (state, state, active[0]),
            )
            assert copy.execute(
                "SELECT activated_from_schedule_id FROM lesson_publications WHERE id=?",
                (active[0],),
            ).fetchone() == (active[1],)
            try:
                migration["rollback"](copy)
            except RuntimeError as error:
                assert "Retain migration 0112" in str(error)
            else:
                raise AssertionError("Rollback must retain terminal history")
            copy.execute("ROLLBACK TO lifecycle_probe")
            copy.execute("RELEASE lifecycle_probe")
        assert product_snapshot(copy) == before
    output = {
        "host": "vmshbeget",
        "migration": MIGRATION_ID,
        "migration_sha256": hashlib.sha256(migration_bytes).hexdigest(),
        "migration_seconds": round(migration_seconds, 3),
        "product_tables": len(before),
        "product_rows": sum(row["count"] for row in before.values()),
        "product_rows_identical": True,
        "changed_objects": changed_objects,
        "gl13_terminal_lifecycle": "superseded/hidden PASS; lineage retained",
        "rollback_refuses_terminal_history": True,
        "integrity": "ok",
        "new_foreign_key_errors": 0,
        "existing_legacy_fk_errors": len(fk_errors_before),
        "existing_fk_errors_identical": True,
        "data_export": "Production row data stayed on server; temporary copy removed.",
    }
    print(json.dumps(output, indent=2))
finally:
    shutil.rmtree(directory)
