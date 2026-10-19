"""Read-only release proof; docs/hint-preview-empty-materials-20261004.md."""

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from db_methods.pwa.migrations import require_current_schema
from db_methods.pwa.schema_inventory import product_ddl_sha256

BASE = Path('/web/vmsh_tasks_bot')
CODE = BASE / 'vmsh_tasks_bot'
MODE, TARGET = sys.argv[1:3]
ROOT = BASE / 'vmshpwa'
CURRENT = (ROOT / 'current').resolve()
revision = subprocess.check_output(
    ['git', '-c', f'safe.directory={CODE}', '-C', str(CODE), 'rev-parse', 'HEAD'], text=True,
).strip()
assert revision == TARGET
builds = {audience: json.loads((CURRENT / audience / 'build-provenance.json').read_text())
          for audience in ('landing', 'student', 'family', 'staff')}
assert all(build['releaseId'] == CURRENT.name and build['application'] == audience
           and build['profile'] == 'production' and not build['prototype'] and not build['msw']
           for audience, build in builds.items())
compiler = re.search(r'COMPILER_VERSION = "([^"]+)"',
                     (CODE / 'helpers/pwa/content/compiler.py').read_text()).group(1)
assert compiler == 'vmsh-latex-compiler/10'
database = CODE / ('db/production_v2.db' if MODE == 'vmsh' else 'db/production_prep.db')
assert require_current_schema(database).is_current
with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
    db.execute('BEGIN')
    assert db.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    ddl = product_ddl_sha256(db)
    assert ddl == 'e3866265c928a175dbb6e749e9a038baf6714e6e10cca41d99d6f3efd3a4ce88'
    migrations = [row[0] for row in db.execute(
        "SELECT migration_id FROM _yoyo_migration WHERE migration_id >= '0111' ORDER BY migration_id")]
    assert migrations == ['0111.current_schema', '0112.scheduled_publication_lifecycle', '0113.content_upload_compiler_generation']
    fk = len(db.execute('PRAGMA foreign_key_check').fetchall())
services = ['vmshpwa.service', 'vmsh-analytics.timer']
services += ['gunicorn.vmsh_tasks_bot.service'] if MODE == 'vmsh' else ['vmshzoom.service', 'nats.service']
states = {service: subprocess.check_output(['systemctl', 'is-active', service], text=True).strip() for service in services}
assert all(state == 'active' for state in states.values())
assert not (ROOT / 'runtime/service-updating').exists()
report = dict(host=MODE, source_revision=revision, compiler=compiler, release=CURRENT.name,
              production_build=builds['staff'], schema_current=True, ddl_sha256=ddl,
              migration_ids=migrations, integrity='ok', existing_fk_errors=fk,
              services=states, maintenance_cleared=True)
if MODE == 'tlf':
    record = BASE / 'deploy/releases' / CURRENT.name
    before = json.loads((record / 'data-before.json').read_text())
    after = json.loads((record / 'data-after.json').read_text())
    assert before == after
    assert 'OK' in (record / 'credentials-check.log').read_text()
    report.update(product_tables=len(before), product_rows_identical=True,
                  product_rows=sum(row['count'] for row in before.values()),
                  backup_before=json.loads((record / 'backup-before.json').read_text()),
                  backup_after=json.loads((record / 'backup-after.json').read_text()), credentials_unchanged=True)
print(json.dumps(report, indent=2))
