"""Server-only proofs for vmshpwa/docs/teacher-work.md; no personal rows exported."""
import argparse
import fcntl
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))


def facts(path):
    with sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True) as connection:
        connection.execute("BEGIN")
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        fk = sorted(connection.execute("PRAGMA foreign_key_check").fetchall(), key=repr)
        report = {}
        for (table,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE '%yoyo%' ORDER BY name"
        ).fetchall():
            quote = lambda name: '"' + name.replace('"', '""') + '"'
            fields = ','.join(quote(row[1]) for row in connection.execute(f"PRAGMA table_info({quote(table)})"))
            digest, count = hashlib.sha256(), 0
            for row in connection.execute(f"SELECT {fields} FROM {quote(table)} ORDER BY {fields}"):
                digest.update(repr(tuple(row)).encode() + b"\n")
                count += 1
            report[table] = {"count": count, "sha256": digest.hexdigest()}
        return {"tables": report, "integrity": "ok", "foreign_key_count": len(fk),
                "foreign_key_sha256": hashlib.sha256(repr(fk).encode()).hexdigest()}


def compare(before, after):
    assert before['foreign_key_count'] == after['foreign_key_count']
    assert before['foreign_key_sha256'] == after['foreign_key_sha256']
    for table, value in before['tables'].items():
        assert after['tables'][table] == value, f"Existing table changed: {table}"
    added = sorted(set(after['tables']) - set(before['tables']))
    assert len(added) == 8 and all(table.startswith('teacher_work_') for table in added)
    assert all(after['tables'][table]['count'] == 0 for table in added)
    return {"existing_tables_preserved": len(before['tables']), "added_empty_tables": added,
            "foreign_key_count_preserved": before['foreign_key_count'], "new_foreign_key_violations": 0,
            "integrity": "ok"}


def rehearsal(path):
    import yoyo
    from db_methods.pwa.migrations import apply_schema_migrations, require_current_schema
    before = facts(path)
    apply_schema_migrations(path)
    checked = compare(before, facts(path))
    migrations = yoyo.read_migrations('migrations')
    new = [item for item in migrations if item.id == '0118.teacher_work']
    with yoyo.get_backend(f"sqlite:///{Path(path).resolve()}") as backend, backend.lock():
        backend.rollback_migrations(new)
    assert facts(path) == before
    apply_schema_migrations(path)
    compare(before, facts(path))
    require_current_schema(path)
    checked['up_down_up'] = 'pass'
    return checked


def snapshots(path):
    import time
    import types
    # Load the pure accounting modules without models/__init__.py, which eagerly
    # initializes the unrelated Telegram adapter and reads its private config.
    # This maintenance process exposes no HTTP/auth surface.
    for name, folder in [('models', 'models'), ('models.pwa', 'models/pwa')]:
        package = types.ModuleType(name)
        package.__path__ = [str(Path.cwd() / folder)]
        sys.modules[name] = package
    from db_methods.pwa.migrations import require_current_schema
    from db_methods.pwa.teacher_work import latest_run, rows
    from models.pwa.teacher_work_report import build_report, export_tsv
    from models.pwa.teacher_work_runner import calculate_course_work
    require_current_schema(path)
    reports = []
    with open(str(path) + '.analytics.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with sqlite3.connect(path, timeout=10) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys=ON')
            for course in connection.execute("SELECT id,public_id FROM courses WHERE status='active' ORDER BY id").fetchall():
                start = time.monotonic()
                run_id = calculate_course_work(connection, course['id'])
                run = latest_run(connection, course['id'], completed=True)
                snapshot = json.loads(run['snapshot_json'])
                overrides = {row['cell_key']: row for row in rows(connection, 'SELECT * FROM teacher_work_overrides WHERE course_id=?', (course['id'],))}
                report = build_report(snapshot, overrides)
                tsv = export_tsv(report)
                lines = tsv.splitlines()
                widths = {len(line.split('\t')) for line in lines}
                assert len(widths) == 1 and len(lines) >= 3
                reports.append({'course_public_id': course['public_id'], 'run_id': run_id,
                    'state': run['state'], 'teachers': len(report['rows']), 'cells': len(snapshot['cells']),
                    'tsv_columns': next(iter(widths)), 'tsv_headers': 3,
                    'seconds': round(time.monotonic()-start, 3)})
    return {'snapshots': reports, 'private_rows_exported': False}


parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['facts', 'rehearse', 'compare', 'snapshots'])
parser.add_argument('paths', nargs='+')
args = parser.parse_args()
if args.mode == 'facts':
    result = facts(args.paths[0])
elif args.mode == 'rehearse':
    result = rehearsal(args.paths[0])
elif args.mode == 'compare':
    result = compare(*(json.loads(Path(path).read_text()) for path in args.paths))
else:
    result = snapshots(args.paths[0])
print(json.dumps(result, sort_keys=True))
