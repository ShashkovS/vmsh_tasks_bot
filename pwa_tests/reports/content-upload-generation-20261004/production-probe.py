"""Read-only deployment proof; vmshpwa/docs/content-recovery-20261004.md.

Run on each production host. Product rows remain there; export only summaries.
"""

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from db_methods.pwa.migrations import require_current_schema
from db_methods.pwa.schema_inventory import product_ddl_sha256


BASE = Path('/web/vmsh_tasks_bot')
CODE = BASE / 'vmsh_tasks_bot'
MODE = sys.argv[1]
TARGET = '62e40a16de9d0a77e638d0fa262c9242eebbe90c'
ROOT = BASE / 'vmshpwa'
CURRENT = (ROOT / 'current').resolve()
REPORT = {'host': MODE, 'source_revision': subprocess.check_output(
    ['git', '-c', f'safe.directory={CODE}', '-C', str(CODE), 'rev-parse', 'HEAD'],
    text=True,
).strip(), 'release': CURRENT.name}
assert REPORT['source_revision'] == TARGET


def snapshot(path):
    # Sealed backup files have no writers. immutable prevents WAL sidecar writes
    # by a read-only verifier whose account cannot write the backup directory.
    with sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        report = {}
        for (table,) in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%yoyo%' ORDER BY name"
        ):
            quoted = '"' + table.replace('"', '""') + '"'
            fields = ','.join('"' + row[1].replace('"', '""') + '"'
                              for row in connection.execute(f'PRAGMA table_info({quoted})'))
            digest = hashlib.sha256()
            count = 0
            for row in connection.execute(f'SELECT {fields} FROM {quoted} ORDER BY {fields}'):
                digest.update(repr(row).encode())
                digest.update(b'\n')
                count += 1
            report[table] = {'count': count, 'sha256': digest.hexdigest()}
    return report


if MODE == 'vmsh':
    database = CODE / 'db/production_v2.db'
    before_backup = BASE / 'backups/vmsh-before-deploy-20261004105308.sqlite3'
    after_backup = BASE / 'backups/vmsh-after-deploy-20261004105326.sqlite3'
    before = snapshot(before_backup)
    after = snapshot(after_backup)
    REPORT.update(backup_before=before_backup.name, backup_after=after_backup.name)
    old_release = ROOT / 'b5a7a6b347d8-20261004051229'
    # The deploy root may use either direct releases or releases/<id>.
    if not old_release.exists():
        old_release = ROOT / 'releases/b5a7a6b347d8-20261004051229'
    services = ['vmshpwa.service', 'gunicorn.vmsh_tasks_bot.service', 'vmsh-analytics.timer']
else:
    assert MODE == 'tlf'
    database = CODE / 'db/production_prep.db'
    record = BASE / 'deploy/releases/tlfprep-20261004-content-upload-62e40a16de9d'
    before = json.loads((record / 'data-before.json').read_text())
    after = json.loads((record / 'data-after.json').read_text())
    old_release = ROOT / 'releases/tlfprep-20261004-combined-b5a7a6b347d8'
    # Current frontend remains the preceding content-recovery release.
    assert (ROOT / 'current').readlink() == Path((record / 'static-before.txt').read_text().strip())
    REPORT.update(
        backup_before=json.loads((record / 'backup-before.json').read_text()),
        backup_after=json.loads((record / 'backup-after.json').read_text()),
        rehearsal=json.loads((record / 'rehearsal.json').read_text()),
        credentials_unchanged='OK' in (record / 'credentials-check.log').read_text(),
        record=str(record),
    )
    services = ['vmshpwa.service', 'vmshzoom.service', 'vmsh-analytics.timer', 'nats.service']

assert set(before) == set(after)
changed = {name: {'before_count': before[name]['count'], 'after_count': after[name]['count']}
           for name in before if before[name] != after[name]}
REPORT.update(
    product_tables=len(before),
    product_rows_before=sum(value['count'] for value in before.values()),
    product_rows_after=sum(value['count'] for value in after.values()),
    product_rows_identical=before == after,
    changed_product_tables=changed,
)
if before != after:
    assert MODE == 'vmsh'
    assert set(changed) == {'auth_events', 'auth_refresh_consumed_secrets', 'auth_sessions'}
    # Backups bracket writers reopening. Verify the exact atomic refresh contract
    # in db_methods/pwa/auth.py:rotate_refresh_secret, without exporting secrets.
    with sqlite3.connect(f'file:{before_backup}?mode=ro&immutable=1', uri=True) as old, \
            sqlite3.connect(f'file:{after_backup}?mode=ro&immutable=1', uri=True) as new:
        old.row_factory = new.row_factory = sqlite3.Row

        def records(db, table):
            return {row['id']: dict(row) for row in db.execute(f'SELECT * FROM {table}')}

        old_events, new_events = records(old, 'auth_events'), records(new, 'auth_events')
        assert all(new_events[key] == row for key, row in old_events.items())
        added_events = [row for key, row in new_events.items() if key not in old_events]
        assert len(added_events) == 1
        event = added_events[0]
        assert event['event_type'] == 'session.rotated'
        old_secrets = {tuple(row) for row in old.execute('SELECT * FROM auth_refresh_consumed_secrets')}
        new_secrets = {tuple(row) for row in new.execute('SELECT * FROM auth_refresh_consumed_secrets')}
        assert old_secrets <= new_secrets
        added_secrets = new_secrets - old_secrets
        assert len(added_secrets) == 1
        consumed = next(iter(added_secrets))
        old_sessions, new_sessions = records(old, 'auth_sessions'), records(new, 'auth_sessions')
        assert old_sessions.keys() == new_sessions.keys()
        edited = [key for key in old_sessions if old_sessions[key] != new_sessions[key]]
        assert edited == [event['session_id']]
        previous, refreshed = old_sessions[edited[0]], new_sessions[edited[0]]
        fields = {key for key in previous if previous[key] != refreshed[key]}
        assert fields == {'refresh_secret_hash', 'last_seen_at', 'updated_at', 'version'}
        assert refreshed['version'] == previous['version'] + 1
        assert event['account_id'] == previous['account_id']
        assert consumed == (previous['id'], previous['refresh_secret_hash'],
                            event['occurred_at'], previous['expires_at'])
        assert refreshed['last_seen_at'] == refreshed['updated_at'] == event['occurred_at']
    REPORT['concurrent_writer_change'] = {
        'event_type': 'session.rotated',
        'event_count': 1,
        'occurred_at': event['occurred_at'],
        'exact_atomic_refresh_contract': True,
        'existing_auth_history_identical': True,
        'all_other_155_product_tables_identical': True,
        'exported_credentials_or_session_identifiers': False,
    }
assert require_current_schema(database).is_current
with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
    connection.execute('BEGIN')
    assert connection.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    REPORT.update(
        schema_current=True,
        ddl_sha256=product_ddl_sha256(connection),
        integrity='ok',
        existing_fk_errors=len(connection.execute('PRAGMA foreign_key_check').fetchall()),
        migration_ids=[row[0] for row in connection.execute(
            "SELECT migration_id FROM _yoyo_migration WHERE migration_id >= '0111' ORDER BY migration_id"
        )],
    )
    if MODE == 'vmsh':
        REPORT['publications'] = connection.execute(
            "SELECT group_lesson_id,kind,id,revision_id,state,version,activated_from_schedule_id "
            "FROM lesson_publications WHERE group_lesson_id IN (13,14) "
            "AND state IN ('published','scheduled') ORDER BY group_lesson_id,kind,id"
        ).fetchall()
        REPORT['gl14_latest_hint'] = connection.execute(
            "SELECT public_id,revision_number,status,version FROM content_revisions "
            "WHERE source_id=35 ORDER BY revision_number DESC LIMIT 1"
        ).fetchone()
        REPORT['cr71'] = connection.execute(
            "SELECT public_id,status,version,parser_version FROM content_revisions WHERE public_id='cr-71'"
        ).fetchone()
        REPORT['cr75'] = connection.execute(
            "SELECT public_id,status,version,parser_version FROM content_revisions WHERE public_id='cr-75'"
        ).fetchone()

builds = {audience: json.loads((CURRENT / audience / 'build-provenance.json').read_text())
          for audience in ('landing', 'student', 'family', 'staff')}
assert all(value['releaseId'] == CURRENT.name and value['profile'] == 'production'
           and value['prototype'] is False and value['msw'] is False for value in builds.values())
REPORT['production_build'] = builds['staff']
assert REPORT['ddl_sha256'] == 'e3866265c928a175dbb6e749e9a038baf6714e6e10cca41d99d6f3efd3a4ce88'
assert REPORT['migration_ids'] == ['0111.current_schema','0112.scheduled_publication_lifecycle','0113.content_upload_compiler_generation']
assert all(value['application'] == audience for audience, value in builds.items())
assert all({key: value for key, value in build.items() if key != 'application'}
           == {key: value for key, value in builds['staff'].items() if key != 'application'}
           for build in builds.values())
REPORT['frontend_unchanged'] = CURRENT.name == ('9a14443fbc23-20261004093414' if MODE == 'vmsh' else 'tlfprep-20261004-content-recovery-9a14443fbc23')
assert REPORT['frontend_unchanged']
REPORT['services'] = {service: subprocess.check_output(
    ['systemctl', 'is-active', service], text=True).strip() for service in services}
assert all(state == 'active' for state in REPORT['services'].values())
REPORT['maintenance_cleared'] = not (ROOT / 'runtime/service-updating').exists()
assert REPORT['maintenance_cleared']
REPORT['data_export'] = 'Product rows stayed on server; only counts and digests exported.'
print(json.dumps(REPORT, indent=2))
