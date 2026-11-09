"""Read-only production proof; docs/performance/integrated-release-20261008.md."""

import hashlib
import ast
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from db_methods.pwa.migrations import require_current_schema


mode, target = sys.argv[1:3]
base = Path('/web/vmsh_tasks_bot')
code = base / 'vmsh_tasks_bot'


def command(*arguments):
    return subprocess.check_output(arguments, text=True).strip()


revision = command('git', '-c', f'safe.directory={code}', '-C', str(code), 'rev-parse', 'HEAD')
assert revision == target
current = (base / 'vmshpwa/current').resolve(strict=True)
assert target[:12] in current.name
builds = {audience: json.loads((current / audience / 'build-provenance.json').read_text())
          for audience in ('landing', 'student', 'family', 'staff')}
origin = ('https://vmshstor.shashkovs.ru' if mode == 'vmsh'
          else 'https://tlfprepimages.nbg1.your-objectstorage.com')
assert all(build['releaseId'] == current.name and build['profile'] == 'production'
           and build['publicMediaOrigin'] == origin
           and not build['prototype'] and not build['msw']
           for build in builds.values())
assets = []
for audience in builds:
    html = (current / audience / 'index.html').read_text()
    entrypoints = re.findall(r'(?:src|href)="(/[^" ]+/assets/[^" ]+\.(?:js|css)(?:\?[^" ]+)?)"', html)
    assert entrypoints
    for url in entrypoints:
        file = current / audience / 'assets' / url.split('/assets/', 1)[1].split('?', 1)[0]
        assets.append({'path': url, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    for file in (current / audience / 'assets').glob('*image-compression*'):
        if file.is_file():
            assets.append({'path': f'/{audience}/assets/{file.name}?release={current.name}',
                           'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})

database = code / 'db' / ('production_v2.db' if mode == 'vmsh' else 'production_prep.db')
state = require_current_schema(database)
assert state.is_current and len(state.expected) == 6
# Read constants and the pure rewrite function without initializing yoyo steps.
tree = ast.parse((code / 'migrations/0115.vmsh_public_media_domain.py').read_text())
names = {'NEW_ORIGIN', 'OLD_ORIGINS', 'TEXT_COLUMNS', 'HASH_COLUMNS', 'IMMUTABILITY_TRIGGERS'}
nodes = [node for node in tree.body
         if (isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id in names
                                                for item in node.targets))
         or (isinstance(node, ast.FunctionDef) and node.name == '_rewrite')]
namespace = {}
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<migration read-only constants>', 'exec'), namespace)
domain = SimpleNamespace(**namespace)
with sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True) as connection:
    connection.execute('BEGIN')
    assert connection.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    remaining = {}
    for table, columns in domain.TEXT_COLUMNS.items():
        for column in columns:
            values = [item[0] for item in connection.execute(f'SELECT "{column}" FROM "{table}"')
                      if item[0] is not None]
            remaining[f'{table}.{column}'] = sum(domain._rewrite(value) != value for value in values)
    assert not any(remaining.values())
    hash_checks = {}
    for (table, column), hash_column in domain.HASH_COLUMNS.items():
        rows = connection.execute(f'SELECT "{column}", "{hash_column}" FROM "{table}"')
        checked = 0
        for text, digest in rows:
            if text and domain.NEW_ORIGIN in text:
                assert hashlib.sha256(text.encode()).hexdigest() == digest
                checked += 1
        hash_checks[f'{table}.{column}'] = checked
    triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='trigger'")}
    assert set(domain.IMMUTABILITY_TRIGGERS) <= triggers
    indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='index'")}
    assert {'pwa_image_uploads_cleanup', 'notification_events_push_due_idx'} <= indexes
    uploads = dict(connection.execute('SELECT state, count(*) FROM pwa_image_uploads GROUP BY state'))
services = ['vmshpwa.service', 'vmsh-analytics.timer']
services += (['gunicorn.vmsh_tasks_bot.service', 'nats-server.service'] if mode == 'vmsh'
             else ['vmshzoom.service', 'nats.service'])
states = {service: {'state': command('systemctl', 'is-active', service),
                    'pid': command('systemctl', 'show', '-p', 'MainPID', '--value', service),
                    'restarts': command('systemctl', 'show', '-p', 'NRestarts', '--value', service)}
          for service in services}
assert all(item['state'] == 'active' for item in states.values())
assert not (base / 'vmshpwa/runtime/service-updating').exists()
report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'host': mode,
          'source_revision': revision, 'frontend_release': current.name,
          'builds': builds, 'public_assets': assets, 'services': states,
          'maintenance_cleared': True, 'schema_current': True,
          'expected_migrations': [item[0] for item in state.expected],
          'remaining_old_presentation_urls': remaining, 'rewritten_hash_checks': hash_checks,
          'immutability_triggers_restored': True, 'upload_and_push_indexes_present': True,
          'image_upload_states': uploads}
if mode == 'tlf':
    record = base / 'deploy/releases' / current.name
    assert 'OK' in (record / 'credentials-check.log').read_text()
    assert 'Every existing product table preserved' in (record / 'live-data-check.log').read_text()
    assert 'Three migrations up/down/up PASS' in (record / 'rehearsal.log').read_text()
    config = json.loads((code / 'creds_prod/vmsh_bot_config_prod.json').read_text())
    assert config.get('s3_direct_image_uploads_verified', False) is False
    report.update(credentials_unchanged=True, existing_product_rows_preserved=True,
                  rehearsal_up_down_up=True, direct_s3_verified=False,
                  backup_before=json.loads((record / 'backup-before.json').read_text()),
                  backup_after=json.loads((record / 'backup-after.json').read_text()))
else:
    assert (base / 'deploy/runtime/deploy/vmsh-tasks-bot.revision').read_text().strip() == target
    report['backups'] = []
    for label in ('before', 'after'):
        path = sorted((base / 'backups').glob(f'vmsh-{label}-deploy-20261008*.sqlite3'))[-1]
        # These completed backup snapshots have no writers or journal sidecars.
        with sqlite3.connect(f'{path.as_uri()}?mode=ro&immutable=1', uri=True) as backup:
            assert backup.execute('PRAGMA quick_check').fetchall() == [('ok',)]
        report['backups'].append({'path': str(path), 'quick_check': 'ok'})
print(json.dumps(report, indent=2))
