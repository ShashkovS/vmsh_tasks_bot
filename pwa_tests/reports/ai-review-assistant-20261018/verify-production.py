"""Full release proof; docs/performance/scoped-reads-20261013.md."""

import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

origin, target, expected_static, database = sys.argv[1:]
import sqlite3
base = Path('/web/vmsh_tasks_bot')
code = base / 'vmsh_tasks_bot'
release = (base / 'vmshpwa/current').resolve()
release_id = release.name
if origin == 'https://vmsh.shashkovs.ru':
    services = ['vmshpwa.service', 'gunicorn.vmsh_tasks_bot.service', 'vmsh-analytics.timer']
else:
    services = ['vmshpwa.service', 'vmshzoom.service', 'vmsh-analytics.timer', 'nats.service', 'vmsh-cross-backup.timer', 'vmsh-cross-backup-sync.timer', 'vmsh-cross-backup-verify.timer']
head = subprocess.check_output(['git', '-c', f'safe.directory={code}', '-C', str(code), 'rev-parse', 'HEAD'], text=True).strip()
assert head == target, (head, target)
assert release_id == expected_static, (release_id, expected_static)
assert not (base / 'vmshpwa/runtime/service-updating').exists()
assert not list(release.rglob('*.map'))
for service in services:
    assert subprocess.check_output(['systemctl', 'is-active', service], text=True).strip() == 'active', service

def fetch(path):
    request = Request(origin + path, headers={'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'})
    with urlopen(request, timeout=30) as response:
        assert response.status == 200
        return response.read()

provenance = {}
for audience in ('landing', 'student', 'family', 'staff'):
    item = json.loads((release / audience / 'build-provenance.json').read_text())
    assert item['profile'] == 'production' and item['releaseId'] == release_id, item
    assert item['msw'] is False and item['prototype'] is False and item['sentryConfigured'] is True, item
    assert item['sentryOrigin'] == 'https://glitch.leaders.tech', item
    path = '/' if audience == 'landing' else f'/{audience}/'
    assert fetch(path) == (release / audience / 'index.html').read_bytes(), audience
    provenance[audience] = item

assets = sorted(p for p in (release / 'staff/assets').rglob('*') if p.suffix in ('.js', '.css'))
def verify_asset(path):
    local_bytes = path.read_bytes()
    relative = path.relative_to(release / 'staff').as_posix()
    served = fetch(f'/staff/{relative}?release={release_id}')
    assert hashlib.sha256(served).digest() == hashlib.sha256(local_bytes).digest(), relative
    return relative
with ThreadPoolExecutor(max_workers=6) as pool:
    matched = list(pool.map(verify_asset, assets))
try:
    fetch('/staff/api/v1/thread-entries/e-1/attachments/a-1/media')
    raise AssertionError('Anonymous media request must require authentication')
except HTTPError as error:
    assert error.code == 401, error.code
with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
    migration_ids = {row[0] for row in connection.execute('SELECT migration_id FROM _yoyo_migration')}
    assert {'0121.review_sheet_indexes', '0122.ai_review_assistant'} <= migration_ids, migration_ids
    assert connection.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'ai_review_tokens', 'ai_review_suggestions', 'ai_review_events'} <= tables
unauthorized = {}
for path, method in [('/staff/api/ai-review/v1/tools/list_courses','POST'), ('/staff/api/v1/ai-review/tokens','GET')]:
    try:
        with urlopen(Request(origin+path, data=b'{}' if method=='POST' else None, method=method, headers={'Content-Type':'application/json','Origin':origin}), timeout=30) as response:
            raise AssertionError((path, response.status))
    except HTTPError as error:
        assert error.code == 401, (path, error.code)
        unauthorized[path] = error.code
assert b'mcp-access' in fetch('/staff/mcp-access') or fetch('/staff/mcp-access') == (release/'staff/index.html').read_bytes()
assert list((release/'staff/assets').glob('mcp-access*.js'))
print(json.dumps({'ai_migration':'0122.ai_review_assistant','database_quick_check':'ok','mcp_anonymous_status':unauthorized,'backend_only': False, 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'origin': origin, 'source': head, 'static_release': release_id, 'staff_assets_sha256_matched': len(matched), 'production_provenance': provenance, 'html_sha256_matched': 4, 'media_anonymous_status': 401, 'public_sourcemaps': False, 'maintenance': False, 'services_active': services}, indent=2))
