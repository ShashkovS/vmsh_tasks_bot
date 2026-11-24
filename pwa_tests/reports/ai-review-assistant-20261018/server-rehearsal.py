"""Fresh server-local up/down/up proof; never copies production off-host."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

source, stage, record = map(Path, sys.argv[1:])
snapshot = record / 'migration-rehearsal.sqlite3'
helper = stage / 'docs/deploy/tlf-app/rich_files_data_check.py'
rollback = stage / 'pwa_tests/reports/ai-review-assistant-20261018/rollback-combined.py'
python = sys.executable

def run(args, env=None):
    return subprocess.check_output([python, *map(str,args)], cwd=stage, env=env, text=True)

def tables():
    return json.loads(run([helper, snapshot]))

def compare(before, after):
    added = set(after) - set(before)
    assert added <= {'ai_review_tokens', 'ai_review_suggestions', 'ai_review_events'}, added
    assert all(after[name] == value for name,value in before.items())
    assert all(after[name]['count'] == 0 for name in added)
    return sorted(added)

try:
    with sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True) as src, sqlite3.connect(snapshot) as dst:
        src.backup(dst)
    with sqlite3.connect(snapshot) as c:
        migrations = [r[0] for r in c.execute('SELECT migration_id FROM _yoyo_migration ORDER BY migration_id')]
    before_path = record / 'rehearsal-migrations-before.json'
    before_path.write_text(json.dumps(migrations))
    before = tables()
    env = {**os.environ, 'PROD':'true', 'VMSH_RUNTIME_PROFILE':'pwa-production',
           'VMSH_PWA_PROTOTYPE':'false', 'VMSH_INSTANCE':'migration-rehearsal',
           'VMSH_DB_FILENAME':str(snapshot)}
    (record / 'rehearsal-up.log').write_text(run(['-m','vmshpwa.scripts.migrate_runtime'],env))
    added = compare(before,tables())
    (record / 'rehearsal-guard.json').write_text(run(['-m','vmshpwa.scripts.database_performance_guard'],env))
    (record / 'rehearsal-down.json').write_text(run([rollback,snapshot,stage/'migrations',before_path]))
    assert tables() == before
    (record / 'rehearsal-reup.log').write_text(run(['-m','vmshpwa.scripts.migrate_runtime'],env))
    assert compare(before,tables()) == added
    with sqlite3.connect(snapshot) as c:
        assert c.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    print(json.dumps({'upDownUp':'passed','businessTablesPreserved':len(before),'newEmptyTables':added,
                      'performanceGuard':'passed','integrity':'ok'}))
finally:
    for suffix in ('','-wal','-shm'):
        Path(str(snapshot)+suffix).unlink(missing_ok=True)
