"""Backend-only release proof; docs/performance/worker-read-cache-release.md."""

import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

origin, target, expected_static = sys.argv[1:]
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
print(json.dumps({'backend_only': True, 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'origin': origin, 'source': head, 'static_release': release_id, 'staff_assets_sha256_matched': len(matched), 'production_provenance': provenance, 'html_sha256_matched': 4, 'media_anonymous_status': 401, 'public_sourcemaps': False, 'maintenance': False, 'services_active': services}, indent=2))
